"""Parse each state's and territory's official keeping lists into data/lists/states/<STATE>.json.

Run from anywhere:  python tools/state_lists.py

Reads the saved source files in data/sources/states (downloaded once; see
docs/STATES.md for where each came from). These lists change rarely, so they
are not re-downloaded weekly like WA's. Tasmania's tables were extracted with
Xpdf's `pdftotext -table`, which Poppler (on GitHub's runners) doesn't have,
so the extracted text is what's saved.

Each output entry: {"sci", "common", "group", "level", "label", "detail"}.
group is one of birds, reptiles, frogs, mammals, inverts, fish.
"""
import collections, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "sources", "states")
OUT = os.path.join(ROOT, "data", "lists", "states")

# Where each state's lists came from, shown on the site with every status.
SOURCES = {
    "NSW": [("NSW Native Animal Keeper Species List (2016, reprinted 2019)",
             "https://www.environment.nsw.gov.au/publications/nsw-native-animal-keepers-species-list")],
    "VIC": [("Wildlife Regulations 2024, Schedules 2, 3, 4 and 7",
             "https://wildlife.vic.gov.au/wildlife-regulations-2024")],
    "QLD": [("Nature Conservation (Animals) Regulation 2020, Schedule 3",
             "https://www.legislation.qld.gov.au/view/whole/html/inforce/current/sl-2020-0136"),
            ("Biosecurity Queensland: illegal pets fact sheet",
             "https://www.publications.qld.gov.au/dataset/e1aa5912-b5c2-4faa-a583-3c04cdba950d/resource/3df2d637-688d-4a67-9e72-d6cd949cb693/download/prohibited-pets.pdf")],
    "SA": [("SA native animal keeping categories species list",
            "https://www.environment.sa.gov.au/licences-and-permits/wildlife-permits/native-animal-categories/species-list")],
    "TAS": [("Requirements for importing and keeping wildlife in Tasmania (2017)",
             "https://nre.tas.gov.au/Documents/Requirements%20for%20importing%20and%20keeping%20wildlife%20in%20Tasmania.pdf")],
    "NT": [("NT animals that do not need a permit",
            "https://nt.gov.au/environment/animals/wildlife-permits/animals-that-do-not-need-a-permit"),
           ("NT native animals that need a permit (exempt list)",
            "https://nt.gov.au/environment/animals/wildlife-permits/native-animals-that-need-a-permit")],
    "ACT": [("Nature Conservation (Exempt Animals) Declaration 2026 (DI2026-61)",
             "https://www.legislation.act.gov.au/di/2026-61")],
}

# The rule for anything NOT on a state's lists, shown instead of a status.
DEFAULTS = {
    "NSW": "Most native animals need a licence in NSW; only the listed birds are exempt. Exotic animals fall under the Biosecurity Act, which isn't loaded yet.",
    "VIC": "All Victorian wildlife is protected; species not in the loaded schedules generally can't be kept privately. Exotic pests aren't loaded yet.",
    "QLD": "Native animals not listed as exempt, Class 1 or Class 2 are prohibited by default. Introduced mammals can't be kept unless listed as exceptions.",
    "SA": "Any protected native animal (mammal, bird, reptile) not on SA's list is Specialist category. Exotic pests aren't loaded yet.",
    "TAS": "Mammals, birds, reptiles and amphibians not on Tasmania's import list are prohibited. Tasmania doesn't allow reptiles to be imported as pets.",
    "NT": "Most native animals need a permit in the NT, and all wildlife not native to the NT is prohibited without a permit.",
    "ACT": "Any animal not on the ACT exempt list needs a nature conservation licence to import, keep or sell.",
}

BINOMIAL = re.compile(r"\b([A-Z][a-z]+) (spp\.|[a-z]{3,})(?: ([a-z]{3,}))?(?!\w)")
NOT_GENUS = {"Australian", "Common", "Eastern", "Western", "Northern", "Southern", "Little", "Great", "Red", "Black",
             "White", "Brown", "Green", "Blue", "Yellow", "Grey", "Spotted", "Striped", "Lesser", "Greater", "Golden",
             "Scientific", "Common", "Column", "Item", "Schedule", "Part", "Page", "Current", "Authorised", "Nature",
             "Regulation", "Wildlife", "Species", "Mice", "Rats", "Stock", "Native", "Exotic", "Mammals", "Birds",
             "Reptiles", "Amphibians", "Frogs", "Fish", "Invertebrates", "Division", "Cat", "Dog", "Fancy", "Llama",
             "Rabbit", "Guinea", "Licence", "Basic", "Advanced", "Exempt", "Category", "Not", "Any", "The", "This", "All"}


def read(name):
    return open(os.path.join(SRC, name), encoding="utf-8").read()


def column_names(lines):
    """Binomials that sit in the page's scientific-name column (found by where
    most binomials start), so capitalised common names like 'Australian
    ringneck' in another column are ignored."""
    hits = []
    for i, l in enumerate(lines):
        for m in BINOMIAL.finditer(l):
            if m.group(1) not in NOT_GENUS:
                hits.append((i, m.start(), m))
    if not hits:
        return []
    col = collections.Counter(c // 3 for _, c, _ in hits).most_common(1)[0][0] * 3
    out = []
    for i, c, m in hits:
        if abs(c - col) <= 4:
            if m.group(2) == "spp.":
                out.append((i, m.group(1) + " spp."))
                continue
            name = m.group(1) + " " + m.group(2) + (" " + m.group(3) if m.group(3) else "")
            out.append((i, name))
    return out


def group_of(text):
    t = text.lower()
    for k, g in (("amphibian", "frogs"), ("frog", "frogs"), ("reptile", "reptiles"), ("bird", "birds"),
                 ("mammal", "mammals"), ("invertebrate", "inverts"), ("fish", "fish")):
        if k in t:
            return g
    return None


# ---------- each state ----------

def sa():
    s = read("sa_species.html")
    out, group = [], None
    for chunk in re.split(r"(<h[23][^>]*>.*?</h[23]>)", s, flags=re.S):
        if chunk.startswith("<h"):
            group = group_of(re.sub("<[^>]+>", "", chunk)) or group
            continue
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
            c = [html.unescape(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
            if len(c) < 4 or not BINOMIAL.match(c[1] or ""):
                continue
            cat = c[3].strip().rstrip(".")
            cat = "Exempt" if cat.startswith("Exemp") else cat
            st = {"Exempt": ("ok", "No permit needed (Exempt)"), "Unprotected": ("ok", "Unprotected: no permit needed"),
                  "Basic": ("permit", "Basic permit needed"), "Specialist": ("permit", "Specialist permit needed")}.get(cat)
            if st:
                out.append({"sci": " ".join(c[1].split()), "common": " ".join(c[0].split()), "group": group or "",
                            "level": st[0], "label": st[1], "detail": f"SA keeping category: {cat}"})
    return out


def nsw():
    t = read("nsw_species.txt")
    lines = t.splitlines()
    out = []
    ex = next(i for i, l in reversed(list(enumerate(lines))) if l.strip() == "Exempt species")
    group = None
    cls = r"(?:A1|A2|B1|B2|B3|M1|R1|R2|R3|R4|R5|Companion)"
    for i, l in enumerate(lines[:ex]):
        g = re.match(r"\s*Scientific name\b.*?\b(Amphibians|Birds|Reptiles|Mammals)\b", l)
        if g:
            group = group_of(g.group(1))
        m = re.match(r"\s*([A-Z][a-z]+ [a-z]+(?: [a-z]+)?)\s+.*?\b\d{4}[A-Z]?\s+(" + cls + r"(?:,\s*" + cls + r")*)", l)
        if not m:
            continue
        classes = [c.strip() for c in m.group(2).split(",")]
        # the list gives every class that covers a species; the lowest one is what you need
        lowest = min((c for c in classes if c != "Companion"), key=lambda c: (c[0], int(c[1:])), default="")
        if "Companion" in classes:
            label = "Licence needed (companion animal keeper)"
        elif lowest[1:] == "1":
            label = f"Licence needed (basic class {lowest})"
        else:
            label = f"Licence needed (advanced class {lowest})"
        venom = lowest in ("R3", "R4", "R5")
        out.append({"sci": m.group(1), "common": "", "group": group or "", "level": "permit",
                    "label": label + (", venomous" if venom else ""), "detail": "NSW licence classes: " + ", ".join(classes)})
    for l in lines[ex:]:
        cells = [c for c in re.split(r"\s{2,}", l.strip()) if c]
        if cells and all(re.fullmatch(r"[A-Z][a-z]+ [a-z]+(?: [a-z]+)?", c) for c in cells):
            for name in cells:
                out.append({"sci": name, "common": "", "group": "birds", "level": "ok", "label": "No licence needed (exempt)",
                            "detail": "On NSW's list of 41 exempt native birds"})
    return out


def qld():
    t = read("qld_reg.txt")
    a = t.index("Schedule 3 Categories of animals")
    b = t.index("Schedule 4", a + 100)
    sec = t[a:b]
    parts = re.split(r"\n\s*Part (\d)\s+(Exempt animals|Class 1 animals|Class 2 animals)", sec)
    out = []
    for k in range(1, len(parts), 3):
        kind, body = parts[k + 1], parts[k + 2]
        group = None
        for chunk in re.split(r"\n\s*\d+\s+(Birds|Mammals|Reptiles|Amphibians|Invertebrates|Fish|Insects|Arachnids|Crustaceans)\s*\n", body):
            if chunk in ("Birds", "Mammals", "Reptiles", "Amphibians", "Invertebrates", "Fish", "Insects", "Arachnids", "Crustaceans"):
                group = group_of(chunk) or ("inverts" if chunk in ("Insects", "Arachnids", "Crustaceans") else None)
                continue
            lines = chunk.splitlines()
            for i, name in column_names(lines):
                dangerous = kind == "Class 2 animals" and re.search(r"\byes\b", lines[i])
                level, label = {"Exempt animals": ("ok", "No licence needed (exempt)"),
                                "Class 1 animals": ("permit", "Licence needed (Class 1)"),
                                "Class 2 animals": ("permit", "Licence needed (Class 2)")}[kind]
                out.append({"sci": name, "common": "", "group": group or "", "level": level,
                            "label": label + (", dangerous animal" if dangerous else ""), "detail": "QLD Animals Regulation: " + kind})
    # Biosecurity Queensland fact sheet: species it names as illegal pets
    named = [("Boa constrictor", "reptiles"), ("Trachemys scripta", "reptiles"), ("Chamaeleonidae", "reptiles"),
             ("Mustela furo", "mammals"), ("Mustela putorius", "mammals"), ("Iguana iguana", "reptiles"),
             ("Oryctolagus cuniculus", "mammals"), ("Pantherophis guttatus", "reptiles"), ("Cyprinus carpio", "fish"),
             ("Misgurnus anguillicaudatus", "fish"), ("Anabas testudineus", "fish"), ("Corbicula fluminea", "fish"),
             ("Gambusia holbrooki", "fish"), ("Oreochromis mossambicus", "fish"), ("Mesocricetus auratus", "mammals")]
    for sci, g in named:
        out.append({"sci": sci, "common": "", "group": g, "level": "no", "label": "Illegal pet in Queensland",
                    "detail": "Named as illegal to keep in Biosecurity Queensland's illegal pets fact sheet (Biosecurity Act 2014)"})
    return out


def vic():
    t = read("vic_regs.txt")
    body_start = t.index("Schedule 2—Taxa of wildlife that may be the subject of wildlife basic", 1000)
    t = t[body_start:]
    heads = list(re.finditer(r"\n\s*Schedule (\d)—Taxa of wildlife", t))
    heads = [h for h in heads if not t[h.start():h.start() + 400].count("....")]
    out, seen = [], set()
    for n, h in enumerate(heads):
        num = h.group(1)
        if num not in ("2", "3", "4", "7"):
            continue
        end = heads[n + 1].start() if n + 1 < len(heads) else len(t)
        lines = t[h.start():end].splitlines()
        level, label = {"2": ("permit", "Licence needed (wildlife basic licence)"),
                        "3": ("permit", "Licence needed (wildlife advanced licence)"),
                        "4": ("ok", "No licence needed (Schedule 4)"),
                        "7": ("permit", "Licence needed (wildlife basic licence)")}[num]
        group, groups_at = None, {}
        for k, l in enumerate(lines):
            for c in re.split(r"\s{2,}", l.strip()):
                if c in ("Birds", "Mammals", "Reptiles", "Amphibians", "Frogs", "Invertebrates", "Fish"):
                    group = group_of(c)
            groups_at[k] = group
        for i, name in column_names(lines):
            g = groups_at.get(i)
            if (num, name) in seen:
                continue
            seen.add((num, name))
            out.append({"sci": name, "common": "", "group": g or "", "level": level, "label": label,
                        "detail": f"VIC Wildlife Regulations 2024, Schedule {num}"})
    return out


def act():
    t = read("act_exempt2026.txt")
    t = t[t.index("Schedule 1"):]
    out, group = [], None
    for l in t.splitlines():
        g = re.match(r"\s*(Mammals|Native Birds|Exotic Birds|Birds|Reptiles|Amphibians|Frogs|Invertebrates|Fish)\s*$", l)
        if g:
            group = group_of(g.group(1))
            continue
        m = re.search(r"\s{2,}([A-Z][a-z]+ [a-z]+(?: [a-z]+)?)\s*$", l)
        if m and m.group(1).split()[0] not in NOT_GENUS:
            common = l[:m.start()].strip()
            out.append({"sci": m.group(1), "common": common, "group": group or "", "level": "ok",
                        "label": "No licence needed (exempt)", "detail": "On the ACT exempt animals list"})
    return out


def nt():
    out = []
    for f, note in (("nt_permit.html", "NT exempt native animal"), ("nt_nopermit.html", "Non-native animal that needs no NT permit")):
        s = read(f)
        group = None
        for chunk in re.split(r"(<h[234][^>]*>.*?</h[234]>)", s, flags=re.S):
            if chunk.startswith("<h"):
                group = group_of(re.sub("<[^>]+>", "", chunk)) or group
                continue
            for r in re.findall(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
                c = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", x)).split()) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
                if len(c) >= 2 and BINOMIAL.match(c[1]):
                    out.append({"sci": BINOMIAL.match(c[1]).group(0), "common": c[0], "group": group or "", "level": "ok",
                                "label": "No permit needed", "detail": note})
    return out


def tas():
    """Tasmania's tables (from Xpdf -table): common name, species, import
    requirements, keeping requirements. Column positions are worked out per
    page from the species rows; text cells continue onto following lines."""
    out = []
    group = None
    for page in read("tas_wildlife.txt").split("\f"):
        lines = page.splitlines()
        for l in lines:
            h = re.match(r"\s*3\.\d\.\s+(Invertebrates|Amphibians|Reptiles|Birds|Mammals)\s*$", l)
            if h:
                group = group_of(h.group(1)) or "inverts"
        if not any("Import Requirements" in l for l in lines) or group is None:
            continue
        anchors = []
        for i, l in enumerate(lines):
            cells = [(m.start(), m.group(0)) for m in re.finditer(r"\S+(?: \S+)*", l)]
            for k, (pos, txt) in enumerate(cells):
                m = re.fullmatch(r"([A-Z][a-z]+ [a-z]+(?: [a-z]+)?)", txt)
                if m and m.group(1).split()[0] not in NOT_GENUS and k >= 1:
                    anchors.append((i, m.group(1), pos, [c[0] for c in cells[k + 1:]]))
                    break
        if not anchors:
            continue
        sci_col = collections.Counter(a[2] for a in anchors).most_common(1)[0][0]
        anchors = [a for a in anchors if abs(a[2] - sci_col) <= 3]
        starts = [a[3][0] for a in anchors if a[3]]
        imp_col = collections.Counter(starts).most_common(1)[0][0] if starts else sci_col + 26
        keeps = [a[3][1] for a in anchors if len(a[3]) > 1]
        keep_col = collections.Counter(keeps).most_common(1)[0][0] if keeps else imp_col + 31

        def part(l, c0, c1):
            return l[c0:c1].strip() if len(l) > c0 else ""

        def cell(i, prv, nxt, c0, c1):
            # cells are vertically centred on the species name, so take the
            # lines halfway to the previous and next species
            lo = (prv + i) // 2 + 1 if prv >= 0 else max(0, i - 3)
            hi = (i + nxt + 1) // 2 if nxt < len(lines) else min(len(lines), i + 4)
            return " ".join(x for x in (part(lines[k], c0, c1) for k in range(lo, hi)) if x)
        for n, (i, sci, _, _) in enumerate(anchors):
            prv = anchors[n - 1][0] if n else -1
            nxt = anchors[n + 1][0] if n + 1 < len(anchors) else len(lines)
            imp = cell(i, prv, nxt, imp_col - 1, keep_col - 1)
            keep = cell(i, prv, nxt, keep_col - 1, keep_col + 60)
            both = (imp + " " + keep).lower()
            if "import prohibited" in both:
                level, label = "no", "Can't be brought into Tasmania"
            elif re.search(r"without a permit|(may|can) be bought", keep.lower()) and "permit to possess" not in keep.lower():
                level, label = "ok", "No permit needed to keep" + (" (import permit needed)" if "import permit" in imp.lower() else "")
            elif "permit to possess" in both or "permit required to possess" in both or "licence required" in both:
                level, label = "permit", "Permit needed to keep"
            elif "import permit required" in both or ("import permitted" in both and "exhibition" not in both and "travelling" not in both):
                level, label = "permit", "Import permit needed"
            elif "domestic stock" in both or "without a permit" in both or both.replace("-", "").strip() == "":
                level, label = "ok", "No permit needed"
            else:
                level, label = "check", "Check with NRE Tasmania"
            out.append({"sci": sci, "common": "", "group": group, "level": level, "label": label,
                        "detail": f"Import: {imp or '-'}. Keeping: {keep or '-'}"[:240]})
    return out


PARSERS = {"NSW": nsw, "VIC": vic, "QLD": qld, "SA": sa, "TAS": tas, "NT": nt, "ACT": act}
CANARIES = {"NSW": ["Melopsittacus undulatus", "Morelia spilota"], "VIC": ["Pogona vitticeps"],
            "QLD": ["Melopsittacus undulatus", "Morelia spilota"], "SA": ["Pogona vitticeps"],
            "TAS": ["Melopsittacus undulatus"], "NT": ["Pogona vitticeps"], "ACT": ["Melopsittacus undulatus"]}


def main():
    os.makedirs(OUT, exist_ok=True)
    problems = []
    results = {}
    for st, fn in PARSERS.items():
        rows = fn()
        # Zoo species (cheetahs, camels...) are "permit" on paper, but only
        # for exhibition licence holders, so say that rather than "Permit".
        for r in rows:
            if r["level"] == "permit" and re.search(r"exhibition licen[cs]e (holders only|required)|exhibition only", r["detail"], re.I):
                r["label"] = "Zoos and exhibitors only"
        # one entry per species: the strictest if a list names it twice
        sev = {"ok": 0, "check": 1, "permit": 2, "no": 3}
        best = {}
        for r in rows:
            k = r["sci"].lower()
            if k not in best or sev[r["level"]] > sev[best[k]["level"]]:
                best[k] = r
        rows = sorted(best.values(), key=lambda r: r["sci"])
        names = {r["sci"] for r in rows}
        for c in CANARIES.get(st, []):
            if not any(n.startswith(c) for n in names):
                problems.append(f"{st}: expected {c}")
        results[st] = rows
        print(f"{st:4} {len(rows):5} species  " + ", ".join(f"{k} {v}" for k, v in collections.Counter(r['level'] for r in rows).most_common()))
    if problems:
        raise SystemExit("Not writing state lists:\n  " + "\n  ".join(problems))
    for st, rows in results.items():
        json.dump({"state": st, "sources": SOURCES[st], "default": DEFAULTS[st], "species": rows},
                  open(os.path.join(OUT, st + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()

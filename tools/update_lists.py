"""Download the official WA lists and turn them into JSON the site can use.

Run from anywhere:  python tools/update_lists.py [--offline]

Sources (all official, all public downloads):
  - WA Organism List (DPIRD): full CSV export, the same file the site's
    Download button gives. Legal status for ~56,000 organisms.
  - Noxious fish list (Fish Resources Management Regulations 1995, Sch 5)
  - High-risk non-endemic fish list (DPIRD)
  - Live Import List Part 1 (EPBC Act): species allowed into Australia
    without an import permit

Writes data/sources/* (raw downloads as text) and data/lists/*.json.
Needs `pdftotext` (poppler) for the three PDFs. --offline re-parses the
files already in data/sources without downloading.
"""
import base64, collections, csv, io, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from http.cookiejar import CookieJar

UA = "wa-pets-list-updater/1.0 (https://github.com/theFlay/wa-pets)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "sources")
OUT = os.path.join(ROOT, "data", "lists")
DPIRD = "https://www.dpird.wa.gov.au"
PDFS = {
    "wa_noxious_fish": DPIRD + "/siteassets/documents/biosecurity/animal/noxious_fish_list.pdf",
    "wa_high_risk_fish": DPIRD + "/siteassets/documents/biosecurity/aquatic/high_risk_non_endemic_fish_list.pdf",
    # Compilation No. 104 (28 Jan 2026). legislation.gov.au's "latest" page is
    # JavaScript-only, so bump this URL when a newer compilation is registered.
    "live_import_list_part1": "https://www.legislation.gov.au/F2006B01053/2026-01-28/2026-01-28/text/original/pdf",
}
PAGES = {
    "waol": DPIRD + "/online-tools/western-australian-organism-list/",
    "wa_noxious_fish": "https://www.dpird.wa.gov.au/businesses/biosecurity/aquatic-biosecurity/importing-and-keeping-live-fish-translocation/",
    "wa_high_risk_fish": "https://www.dpird.wa.gov.au/businesses/biosecurity/aquatic-biosecurity/importing-and-keeping-live-fish-translocation/",
    "live_import_list_part1": "https://www.legislation.gov.au/F2006B01053/latest/text",
}

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def get(url, params=None, timeout=120):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"})
    with opener.open(req, timeout=timeout) as r:
        return r.read()


def download_waol():
    """Use the WAOL site's own export: ask for a token, then poll for the file."""
    get(PAGES["waol"])  # session cookie
    tok = get(DPIRD + "/Organism/GetExportDataToken",
              {"searchParam": "", "exportFormat": "csv", "resultCount": "60000"}).decode().strip().strip('"')
    for _ in range(30):
        time.sleep(10)
        body = get(DPIRD + "/Organism/GetExportDataFile", {"exportToken": tok, "exportFormat": "csv"}, 300)
        if len(body) > 10:
            return base64.b64decode(body.strip().strip(b'"')).decode("utf-8-sig")
    raise RuntimeError("WAOL export never became ready")


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", path, "-"], capture_output=True, check=True).stdout.decode("utf-8", "replace")


# ---------- parsing ----------

NAME = re.compile(r"\b([A-Z][a-z]+)(?:\s+\(([A-Z][a-z]+)\))?\s+(spp\.?(?![a-z])|sp\.|[a-z]{3,}(?:\s+[a-z]{3,})?)")
FAMILY = re.compile(r"\b([A-Z][a-z]+(?:idae|inae))\b")
SKIP_WORDS = {"Any", "Examples", "Scientific", "Including", "Port", "Montebello", "Published", "Fish", "Schedule",
              "Heading", "Class", "Marine", "Taxon", "Only", "Note", "General", "All", "Part", "Compilation", "Page"}


def page_lines(text):
    """Every line with the first-column indent of its page.

    pdftotext versions place tables differently (column 0, 1, or centred, and
    it can change from page to page), so find where scientific names line up."""
    tagged = []
    for page in text.split("\f"):
        lines = page.splitlines()
        starts = [len(l) - len(l.lstrip()) for l in lines
                  if re.match(r"\s*[A-Z][a-z]+(\s+(spp\.?|[a-z]{3,})|\s*$)", l)
                  and not re.match(r"\s*(Any|Examples|Scientific|Including|Translocation|Published|Fish|Page)\b", l)]
        base = collections.Counter(starts).most_common(1)[0][0] if starts else 0
        tagged += [(l, base) for l in lines]
    return tagged


def col1_blocks(text):
    """Yield the first-column fragments of each blank-line-separated table row.

    Header rows and prose lines (long sentences) are dropped line by line, so
    a header sharing a block with real entries doesn't hide them."""
    block = []
    for line, base in page_lines(text) + [("", 0)]:
        if not line.strip():
            if block:
                yield block
            block = []
            continue
        if abs(len(line) - len(line.lstrip()) - base) <= 2:  # line starts in the first column
            frag = re.split(r"\s{2,}", line.strip())[0]
            prose = re.search(r"\b(the|will|is|are|this|for|be)\b", frag.replace("Any area of the State", ""))
            if frag.startswith(("Scientific name", "names used")) or (len(frag.split()) > 7 and prose and not frag.startswith("(")):
                continue
            block.append(frag)
        elif block and re.match(r"\s{0,3}\(", line):
            block.append(line.strip())


def strict_taxa(frag, nxt):
    """Taxa that START a first-column fragment (optionally wrapped onto the next one)."""
    text = frag + (" " + nxt if nxt and (nxt[:1].islower() or nxt.startswith("(")) else "")
    m = re.match(r"([A-Z][a-z]+(?:idae|inae))\b", text)
    if m and re.search(r"\((entire family|subfamily)", text):
        return [{"rank": "family", "name": m.group(1)}]
    m = re.match(r"([A-Z][a-z]+)(?:\s+\([A-Z][a-z]+\))?\s*(?:\(entire genus\)|\(entire\s+genus|spp\.?(?![a-z])|sp\.)", text)
    if m and m.group(1) not in SKIP_WORDS:
        return [{"rank": "genus", "name": m.group(1)}]
    m = re.match(r"([A-Z][a-z]+)\s+([a-z]{3,})", text)
    if m and m.group(1) not in SKIP_WORDS:
        return [{"rank": "species", "name": f"{m.group(1)} {m.group(2)}"}]
    return []


def taxa_in(text):
    out = []
    for m in FAMILY.finditer(text):
        if re.search(re.escape(m.group(1)) + r"\s*\((entire family|subfamily)", text) or "All species of the family" in text:
            out.append({"rank": "family", "name": m.group(1)})
    for m in NAME.finditer(text):
        g, ep = m.group(1), m.group(3)
        if g in SKIP_WORDS or g.endswith(("idae", "inae")):
            continue
        if ep.rstrip(".") in ("spp", "sp"):
            out.append({"rank": "genus", "name": g})
        else:
            out.append({"rank": "species", "name": f"{g} {ep.split()[0]}"})
    for m in re.finditer(r"\b([A-Z][a-z]+)\s*\(entire genus\)", text):
        out.append({"rank": "genus", "name": m.group(1)})
    return out


def parse_fish_list(text, with_area):
    entries = []
    last = None  # most recent entry; an "(except ...)" clause can sit in the next block
    for frags in col1_blocks(text):
        if any(w in " ".join(frags) for w in ("In this Schedule", "means the area", "means all waters")):
            continue
        exc = None  # collects an "except ... )" clause across fragments
        for i, f in enumerate(frags):
            nxt = frags[i + 1] if i + 1 < len(frags) else ""
            head = f
            if exc is None and "except" in f:
                head, _, tail = f.partition("except")
                exc = tail
            elif exc is not None:
                head, exc = "", exc + " " + f
            head = head.strip()
            if head and not head[:1].islower() and not head.startswith("("):
                for t in strict_taxa(head, "" if "except" in f else nxt):
                    last = {"taxa": [t], "raw": (head + (" " + nxt if nxt[:1].islower() or nxt.startswith("(entire") else "")).strip()[:120]}
                    entries.append(last)
            if exc is not None and (")" in exc or not nxt):
                if last is not None:
                    clause = exc.split(")")[0]
                    # "T. buttikoferi" style abbreviations: expand with the listed genus
                    g = last["taxa"][0]["name"].split()[0]
                    clause = re.sub(r"\b" + g[0] + r"\.\s+([a-z]{3,})", g + r" \1", clause)
                    last["except"] = taxa_in(clause) or [{"rank": "note", "name": clause.strip(" (,")[:120]}]
                exc = None
    if with_area:  # noxious list: note species that are only noxious in some areas
        whole, partial, current = set(), set(), None
        for line, base in page_lines(text):
            if abs(len(line) - len(line.lstrip()) - base) <= 2 and line.strip():
                found = strict_taxa(re.split(r"\s{2,}", line.strip())[0], "")
                if found:
                    current = found[0]["name"]
            if current and "Any area of the State" in line:
                whole.add(current)
            elif current and re.search(r"Port of|Marine Park|Islands|waters", line):
                partial.add(current)
        for e in entries:
            if any(t["name"] in partial - whole for t in e["taxa"]):
                e["area"] = "Some areas only"
    return entries


def parse_lil(text):
    """Live Import List Part 1: keep the taxon lines with their section."""
    start = text.find("Bony fishes")
    m = re.compile(r"Part 2\s*\W\s*Live specimens requiring an import permit").search(text, max(start, 0))
    part1 = text[:m.start()] if m else text
    taxon_start = re.compile(r"([A-Z][a-z]+\s+(spp\.?|sp\.|[a-z]{3,})|All species of the family|Only )")
    section, out = "", []
    for page in part1.split("\f"):
        lines = page.splitlines()
        # taxa sit in one column per page; its indent varies between pdftotext builds
        starts = [len(l) - len(l.lstrip()) for l in lines if len(l) > len(l.lstrip()) and taxon_start.match(l.strip())]
        base = collections.Counter(starts).most_common(1)[0][0] if starts else 2
        for line in lines:
            s = line.strip()
            cell = re.split(r"\s{2,}", s)[0]
            is_taxon_line = abs(len(line) - len(line.lstrip()) - base) <= 1 and bool(taxon_start.match(cell))
            if not is_taxon_line:
                for key, name in (("Freshwater Fish", "freshwater_fish"), ("Marine Fish", "marine_fish"),
                                  ("Birds (Aves)", "birds"), ("Mammals (Mammalia)", "mammals"),
                                  ("Invertebrate", "invertebrates"), ("Cartilaginous fishes", "sharks_rays"),
                                  ("Reptil", "reptiles"), ("Amphibia", "amphibians")):
                    if re.search(r"(^|\s{2,})" + re.escape(key), line):
                        section = name
                continue
            if not section:
                continue
            out += lil_taxa(cell, section)
    return out


def lil_taxa(cell, section):
    """Taxa in one Live Import List taxon cell, with any import condition."""
    cond = None
    m = re.search(r"(of minimum length.*|of maximum length.*|excluding.*)$", cell)
    if m:
        cond = m.group(1)
    if cell.startswith("Only "):
        cond = cell
    out = []
    for t in taxa_in(cell):
        if t["rank"] == "species" and t["name"].split()[1] in ("of", "excluding"):
            continue
        out.append({**t, "section": section, **({"condition": cond} if cond else {})})
    return out


def parse_waol(csvtext):
    lines = csvtext.splitlines()
    exported = lines[0].strip().lstrip("﻿").strip('"')
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[1:]))))
    keep = []
    for r in rows:
        r = {k: (v or "").strip() for k, v in r.items() if k}
        sci = re.sub(r"\s+", " ", r.get("Scientific name", ""))
        keep.append([sci] + [r.get(c, "") for c in ("Legal status", "Keeping category", "Control category", "Declared areas",
                                                     "Phylum", "Class", "Order", "Family", "Common name(s)")])
    return {"exported": exported, "columns": ["scientific", "legal", "keeping", "control", "areas", "phylum",
                                              "class", "order", "family", "common"], "rows": keep}


# Entries that must always be found. If the parser misses any, the source
# layout has probably changed: stop rather than publish a broken list.
CANARIES = {
    "wa_noxious_fish": ["Gambusia", "Procambarus clarkii", "Oreochromis", "Misgurnus anguillicaudatus", "Pygocentrus"],
    "wa_high_risk_fish": ["Osteoglossum bicirrhosum", "Clariidae", "Barbonymus schwanenfeldii", "Serrasalminae"],
    "live_import_list_part1": ["Danio rerio", "Poecilia reticulata", "Betta", "Pomacentridae"],
}


def sanity_check(new):
    """Refuse to overwrite the lists if anything looks broken."""
    problems = []
    for key, data in new.items():
        if key == "waol":
            n = len(data)
            old_path = os.path.join(OUT, "waol.json")
            old = len(json.load(open(old_path, encoding="utf-8"))["rows"]) if os.path.exists(old_path) else 0
        else:
            names = {t["name"] for e in data for t in (e["taxa"] if "taxa" in e else [e])}
            n = len(names)
            for c in CANARIES.get(key, []):
                if c not in names:
                    problems.append(f"{key}: expected entry '{c}' not found")
            old_path = os.path.join(OUT, key + ".json")
            old = 0
            if os.path.exists(old_path):
                od = json.load(open(old_path, encoding="utf-8"))
                old = len({t["name"] for e in od for t in (e["taxa"] if "taxa" in e else [e])})
        if old and n < old * 0.9:
            problems.append(f"{key}: {n} entries, down from {old} (more than 10% fewer)")
    if problems:
        raise SystemExit("Not updating the lists:\n  " + "\n  ".join(problems))


def main():
    offline = "--offline" in sys.argv
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    meta_path = os.path.join(OUT, "meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}

    waol_csv = os.path.join(SRC, "waol.csv")
    if not offline:
        print("WAOL: requesting full CSV export...", flush=True)
        open(waol_csv, "w", encoding="utf-8", newline="\n").write(download_waol())
        meta["waol"] = {"checked": today, "page": PAGES["waol"]}
    for key, url in PDFS.items():
        txt = os.path.join(SRC, key + ".txt")
        if not offline:
            print(f"{key}: downloading", flush=True)
            pdf = os.path.join(SRC, key + ".pdf")
            open(pdf, "wb").write(get(url))
            open(txt, "w", encoding="utf-8", newline="\n").write(pdf_text(pdf))
            os.remove(pdf)
            meta[key] = {"checked": today, "page": PAGES[key], "file": url}
            time.sleep(2)

    waol = parse_waol(open(waol_csv, encoding="utf-8").read())
    nox = parse_fish_list(open(os.path.join(SRC, "wa_noxious_fish.txt"), encoding="utf-8").read(), True)
    hr = parse_fish_list(open(os.path.join(SRC, "wa_high_risk_fish.txt"), encoding="utf-8").read(), False)
    lil = parse_lil(open(os.path.join(SRC, "live_import_list_part1.txt"), encoding="utf-8").read())
    sanity_check({"waol": waol["rows"], "wa_noxious_fish": nox, "wa_high_risk_fish": hr, "live_import_list_part1": lil})
    json.dump(waol, open(os.path.join(OUT, "waol.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for name, data in (("wa_noxious_fish", nox), ("wa_high_risk_fish", hr), ("live_import_list_part1", lil)):
        json.dump(data, open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    # record each document's own version so the site can show how current it is
    nox_txt = open(os.path.join(SRC, "wa_noxious_fish.txt"), encoding="utf-8").read()
    m = re.search(r"As at (\d{1,2} \w{3,9} \d{4})", nox_txt)
    if m:
        meta.setdefault("wa_noxious_fish", {})["version"] = "As at " + m.group(1)
    lil_txt = open(os.path.join(SRC, "live_import_list_part1.txt"), encoding="utf-8").read()
    m = re.search(r"Compilation No\.\s*(\d+).*?Compilation date:\s*(\d{2})/(\d{2})/(\d{4})", lil_txt, re.S)
    if m:
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        meta.setdefault("live_import_list_part1", {})["version"] =             f"Compilation No. {m.group(1)}, {int(m.group(2))} {months[int(m.group(3)) - 1]} {m.group(4)}"
    meta.setdefault("waol", {})["version"] = waol["exported"].replace("WAOL data exported on ", "Exported ")
    for k, url in PAGES.items():
        meta.setdefault(k, {}).setdefault("page", url)
    json.dump(meta, open(meta_path, "w"), indent=1)
    print(f"WAOL {len(waol['rows'])} rows ({waol['exported']}); noxious {len(nox)} entries; "
          f"high-risk {len(hr)}; live import list part 1 {len(lil)} taxa")


if __name__ == "__main__":
    main()

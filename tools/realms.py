"""Build data/site/<realm>.json for every main tab.

Each file has:
  guide   - hobby species (data/hobby/<realm>.json) with photo and WA status
  list    - every official entry for the tab, as compact rows
  statuses- the distinct status objects rows point at (keeps files small)
  subs    - subcategory ids -> labels, in display order
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOBBY = os.path.join(ROOT, "data", "hobby")
OUT = os.path.join(ROOT, "data", "site")

SUBS = {
    "fauna": [("frogs", "Frogs"), ("reptiles", "Reptiles"), ("birds", "Birds")],
    "mammals": [("pets", "Pets, livestock & carnivores"), ("rodents", "Rodents"), ("rabbits", "Rabbits & hares"),
                ("marsupials", "Marsupials"), ("others", "Other mammals")],
    "aquatic": [("fresh", "Freshwater fish"), ("native", "Australian native fish"), ("marine", "Marine fish"),
                ("crust", "Crayfish & shrimp"), ("other", "Snails & others"),
                ("banned", "WA noxious & high-risk lists")],
    "bugs": [("ants", "Ants"), ("bees", "Bees & wasps"), ("beetles", "Beetles"), ("butterflies", "Butterflies & moths"),
             ("phasmids", "Stick insects & mantids"), ("roaches", "Roaches, crickets & feeders"),
             ("truebugs", "True bugs, aphids & scale"), ("flies", "Flies"), ("insects", "Other insects"),
             ("spiders", "Spiders"), ("scorpions", "Scorpions"), ("mites", "Mites & ticks"),
             ("others", "Centipedes, slaters, snails & worms")],
    "plants": [("cacti", "Cacti & succulents"), ("orchids", "Orchids"), ("carnivorous", "Carnivorous plants"),
               ("aquatic", "Aquarium & pond plants"), ("palms", "Palms"), ("bromeliads", "Bromeliads"),
               ("grasses", "Grasses & sedges"), ("ferns", "Ferns & allies"), ("conifers", "Conifers & cycads"),
               ("mosses", "Mosses"), ("flowering", "Other flowering plants")],
    "fungi": [("fungi", "Fungi & moulds"), ("watermoulds", "Water moulds"), ("bacteria", "Bacteria"),
              ("viruses", "Viruses"), ("protists", "Protists & others")],
}

PLANT_FAM = {
    "cacti": {"Cactaceae", "Aizoaceae", "Crassulaceae"},
    "orchids": {"Orchidaceae"},
    "carnivorous": {"Droseraceae", "Nepenthaceae", "Sarraceniaceae", "Lentibulariaceae", "Cephalotaceae",
                    "Byblidaceae", "Drosophyllaceae", "Roridulaceae"},
    "aquatic": {"Hydrocharitaceae", "Nymphaeaceae", "Aponogetonaceae", "Cabombaceae", "Pontederiaceae",
                "Alismataceae", "Nelumbonaceae", "Limnocharitaceae", "Potamogetonaceae", "Ceratophyllaceae",
                "Menyanthaceae", "Lemnaceae", "Haloragaceae"},
    "palms": {"Arecaceae"},
    "bromeliads": {"Bromeliaceae"},
    "grasses": {"Poaceae", "Cyperaceae", "Juncaceae", "Restionaceae"},
}
PLANT_PHYLA = {"MAGNOLIOPHYTA", "PTERIDOPHYTA", "CONIFEROPHYTA", "CYCADOPHYTA", "BRYOPHYTA", "LYCOPODIOPHYTA",
               "EQUISETOPHYTA", "GNETOPHYTA", "PSILOPHYTA", "ANTHOCEROTOPHYTA", "MARCHANTIOPHYTA", "CHAROPHYTA",
               "CHLOROPHYTA", "RHODOPHYTA"}
BACTERIA = {"PROTEOBACTERIA", "FIRMICUTES", "ACTINOBACTERIA", "TENERICUTES", "SPIROCHAETES", "BACTEROIDETES",
            "CHLAMYDIAE", "CYANOBACTERIA"}
MITES = {"TROMBIDIFORMES", "MESOSTIMATA", "MESOSTIGMATA", "SARCOPTIFORMES", "IXODIDA", "ASTIGMATA"}


def classify(row):
    """WAOL row -> (realm, sub) or None if it belongs to no tab."""
    sci, phylum, cls, order, fam = row[0], row[5], row[6], row[7], row[8]
    if cls == "AMPHIBIA":
        return "fauna", "frogs"
    if cls == "REPTILIA":
        return "fauna", "reptiles"
    if cls == "AVES":
        return "fauna", "birds"
    if cls == "MAMMALIA":
        if order == "RODENTIA":
            return "mammals", "rodents"
        if order == "LAGOMORPHA":
            return "mammals", "rabbits"
        if order in ("DIPROTODONTIA", "DASYUROMORPHIA", "PERAMELEMORPHIA", "DIDELPHIMORPHIA", "NOTORYCTEMORPHIA",
                     "MICROBIOTHERIA", "PAUCITUBERCULATA") or "MARSUPIAL" in order:
            return "mammals", "marsupials"
        if order in ("CARNIVORA", "ARTIODACTYLA", "PERISSODACTYLA"):
            return "mammals", "pets"
        return "mammals", "others"
    if cls in ("ACTINOPTERYGII", "OSTEICHTHYES", "CHONDRICHTHYES") or (phylum == "CHORDATA" and cls == "ASCIDIACEA"):
        return "aquatic", "other"
    if cls == "INSECTA":
        if fam == "Formicidae":
            return "bugs", "ants"
        o = order.split(":")[0].strip()
        return "bugs", {"HYMENOPTERA": "bees", "COLEOPTERA": "beetles", "LEPIDOPTERA": "butterflies",
                        "PHASMIDA": "phasmids", "MANTODEA": "phasmids", "BLATTODEA": "roaches",
                        "ORTHOPTERA": "roaches", "HEMIPTERA": "truebugs", "DIPTERA": "flies"}.get(o, "insects")
    if cls == "ARACHNIDA":
        if order in ("ARANEAE", "ARANEIDA"):
            return "bugs", "spiders"
        if order == "SCORPIONES":
            return "bugs", "scorpions"
        if order in MITES:
            return "bugs", "mites"
        return "bugs", "others"
    if phylum in ("ARTHROPODA", "MOLLUSCA", "ANNELIDA", "NEMATODA", "PLATYHELMINTHES", "ECHINODERMATA", "CNIDARIA"):
        return "bugs", "others"
    if phylum in PLANT_PHYLA:
        if phylum in ("PTERIDOPHYTA", "LYCOPODIOPHYTA", "EQUISETOPHYTA", "PSILOPHYTA"):
            return "plants", "ferns"
        if phylum in ("CONIFEROPHYTA", "CYCADOPHYTA", "GNETOPHYTA"):
            return "plants", "conifers"
        if phylum in ("BRYOPHYTA", "ANTHOCEROTOPHYTA", "MARCHANTIOPHYTA"):
            return "plants", "mosses"
        f = fam.split(" - ")[0].strip()
        for sub, fams in PLANT_FAM.items():
            if f in fams:
                return "plants", sub
        return "plants", "flowering"
    if phylum in ("ASCOMYCOTA", "BASIDIOMYCOTA", "ZYGOMYCOTA", "CHYTRIDIOMYCOTA", "GLOMEROMYCOTA", "MUCOROMYCOTA"):
        return "fungi", "fungi"
    if phylum == "OOMYCOTA":
        return "fungi", "watermoulds"
    if phylum in BACTERIA or "BACTERI" in phylum:
        return "fungi", "bacteria"
    if not phylum and re.search(r"vir(us|oid|idae)|phytoplasma|prion", sci + " " + row[9], re.I):
        return "fungi", "viruses"
    return "fungi", "protists"


class Statuses:
    """Interns status dicts so list rows can store a small index."""

    def __init__(self):
        self.items, self.index = [], {}

    def add(self, st):
        key = json.dumps(st, sort_keys=True)
        if key not in self.index:
            self.index[key] = len(self.items)
            self.items.append(st)
        return self.index[key]


def common_name(s):
    return s.split(",")[0].strip()[:60]


# States and territories, in the order the picker shows them. A state only
# gets statuses once a source for it is added below; until then the site says
# "not added yet" for it rather than guessing.
STATES = [("WA", "Western Australia"), ("NSW", "New South Wales"), ("VIC", "Victoria"), ("QLD", "Queensland"),
          ("SA", "South Australia"), ("TAS", "Tasmania"), ("NT", "Northern Territory"),
          ("ACT", "Australian Capital Territory")]
SEVERITY = {"ok": 0, "check": 1, "permit": 2, "no": 3}


def taxon_key(name):
    """Match key for a name: genus, species and any lowercase qualifiers, without
    the author. 'Dionaea muscipula J.Ellis' and 'Dionaea muscipula' match;
    'Oryctolagus cuniculus (domestic)' and '(feral)' stay separate."""
    words, out = name.replace("×", "x").split(), []
    for i, w in enumerate(words):
        if i == 0:
            out.append(w)
        elif i == 1 and re.fullmatch(r"\([A-Z][a-z]+\)", w):
            continue  # subgenus
        elif w[:1].islower() or re.fullmatch(r"\([a-z][^)]*\)?", w) or (out and out[-1].startswith("(") and not out[-1].endswith(")")):
            out.append(w)
        else:
            break
    return " ".join(out).lower()


class Catalogue:
    """One entry per taxon per tab, whatever list it came from.

    Sources call add() with the state they cover. A taxon that's already there
    just gains that state's status (or a stricter one if two lists for the same
    state disagree), so adding a new state's lists never duplicates species."""

    def __init__(self):
        self.rows = {r: {} for r in SUBS}

    def add(self, realm, name, common, sub, state, st):
        key = taxon_key(name)
        row = self.rows[realm].get(key)
        if row is None:
            row = self.rows[realm][key] = {"n": name, "c": common, "sub": sub, "st": {}}
        elif common and not row["c"]:
            row["c"] = common
        old = row["st"].get(state)
        if old is None or SEVERITY[st["level"]] > SEVERITY[old["level"]]:
            row["st"][state] = st


def add_wa(cat):
    """Western Australia: WA Organism List, WA noxious and high-risk fish lists,
    and (for import notes) the national Live Import List."""
    for row in S.WAOL["rows"]:
        c = classify(row)
        if not c:
            continue
        lvl, label, detail = S.waol_status(row)
        cat.add(c[0], re.sub(r"\s+", " ", row[0]), common_name(row[9]), c[1], "WA",
                {"level": lvl, "label": label, "detail": detail, **S.src("waol")})
    rank_suffix = {"genus": " (whole genus)", "family": " (whole family)"}
    for key, entries, lvl, label in (("wa_noxious_fish", S.NOX, "no", "Noxious: banned in WA"),
                                     ("wa_high_risk_fish", S.HR, "no", "High risk: can't be brought into WA")):
        for e in entries:
            t = e["taxa"][0]
            extra = " in some areas" if e.get("area") else ""
            exc = ", except " + ", ".join(x["name"] for x in e["except"]) if e.get("except") else ""
            cat.add("aquatic", t["name"] + rank_suffix.get(t["rank"], ""), "", "banned", "WA",
                    {"level": lvl, "label": label + extra, "detail": "Listed" + exc, **S.src(key)})
    for x in S.LIL:
        if x["section"] not in ("freshwater_fish", "marine_fish", "sharks_rays"):
            continue
        rec = {"sci": x["name"], "sub": "fresh" if x["section"] == "freshwater_fish" else "marine",
               "fam": x["name"] if x["rank"] == "family" else ""}
        st = S.aquatic(rec)
        if x.get("condition"):
            st = {**st, "detail": st["detail"] + " Import condition: " + x["condition"] + "."}
        cat.add("aquatic", x["name"] + rank_suffix.get(x["rank"], ""), "", rec["sub"], "WA", st)


STATE_DIR = os.path.join(ROOT, "data", "lists", "states")
GROUP_TO = {"birds": ("fauna", "birds"), "reptiles": ("fauna", "reptiles"), "frogs": ("fauna", "frogs"),
            "mammals": ("mammals", "others"), "inverts": ("bugs", "others"), "fish": ("aquatic", "fresh")}


def load_states():
    """data/lists/states/<STATE>.json, written by tools/state_lists.py."""
    out = {}
    if os.path.isdir(STATE_DIR):
        for f in sorted(os.listdir(STATE_DIR)):
            if f.endswith(".json"):
                d = json.load(open(os.path.join(STATE_DIR, f), encoding="utf-8"))
                out[d["state"]] = d
    return out


STATE_DATA = load_states()
CHECKED = json.load(open(os.path.join(ROOT, "data", "lists", "meta.json"))).get("states", {}).get("checked", "")


def state_status(st, e):
    srcs = STATE_DATA[st]["sources"]
    name, url = srcs[1] if len(srcs) > 1 and "fact sheet" in e["detail"] else srcs[0]
    return {"level": e["level"], "label": e["label"], "detail": e["detail"], "src": name, "url": url, "checked": CHECKED}


def add_states(cat):
    """Every other state: a species already in the catalogue just gains the
    state's status; genus-wide entries ('Acanthophis spp.') apply to every
    species of that genus that has no more specific entry; anything new gets
    its own row, placed by the WA Organism List's classification of its genus
    when possible."""
    where = {}  # taxon key -> realm
    for realm, rows in cat.rows.items():
        for k in rows:
            where.setdefault(k, realm)
    genus_home = {}
    for row in S.WAOL["rows"]:
        c = classify(row)
        if c and c[0] in ("fauna", "mammals", "bugs", "aquatic"):
            genus_home.setdefault(row[0].split()[0], c)
    for st, d in STATE_DATA.items():
        genus_entries = []
        for e in d["species"]:
            if e["sci"].endswith(" spp."):
                genus_entries.append(e)
                continue
            k = taxon_key(e["sci"])
            if k in where:
                realm = where[k]
                sub = cat.rows[realm][k]["sub"]
            else:
                realm, sub = genus_home.get(e["sci"].split()[0]) or GROUP_TO.get(e["group"], ("fauna", "reptiles"))
                where[k] = realm
            cat.add(realm, e["sci"], e.get("common", ""), sub, st, state_status(st, e))
        # a state that lists only subspecies: the species row shows the strictest of them
        subsp = {}
        for e in d["species"]:
            w = e["sci"].split()
            if len(w) == 3 and not e["sci"].endswith(" spp."):
                subsp.setdefault((w[0] + " " + w[1]).lower(), []).append(e)
        for k, es in subsp.items():
            realm = where.get(k)
            if not realm or st in cat.rows[realm][k]["st"]:
                continue
            worst = max(es, key=lambda e: SEVERITY[e["level"]])
            parts = "; ".join(f"{e['sci'].split()[2]}: {e['label']}" for e in es)[:200]
            cat.rows[realm][k]["st"][st] = state_status(st, {**worst, "label": "Varies by subspecies",
                                                             "detail": "Listed by subspecies. " + parts})
        for e in genus_entries:
            g = e["sci"].split()[0]
            realm, sub = genus_home.get(g) or GROUP_TO.get(e["group"], ("fauna", "reptiles"))
            st_obj = state_status(st, {**e, "detail": e["detail"] + f" (listed as {g} spp.)"})
            for k, row in cat.rows[realm].items():
                if k.split()[0] == g.lower() and st not in row["st"]:
                    row["st"][st] = st_obj
            cat.add(realm, g + " (whole genus)", "", sub, st, st_obj)


def state_lookup(st, names):
    """A hobby guide species' entry in a state's list: exact name, else its genus."""
    d = STATE_DATA.get(st)
    if not d:
        return None
    keys = {taxon_key(n) for n in names}
    for e in d["species"]:
        if taxon_key(e["sci"]) in keys:
            return e
    genera = {n.split()[0] for n in names}
    for e in d["species"]:
        if e["sci"].endswith(" spp.") and e["sci"].split()[0] in genera:
            return {**e, "detail": e["detail"] + f" (listed as {e['sci']})"}
    return None


def guide_statuses(realm, rec):
    """Status per state for a hobby guide species."""
    sts = {"WA": S.aquatic(rec) if realm == "aquatic" else S.organism(rec)}
    names = [rec["sci"]] + rec.get("also", [])
    for st in STATE_DATA:
        e = state_lookup(st, names)
        if e:
            sts[st] = state_status(st, e)
    return sts


def build(photo_for):
    os.makedirs(OUT, exist_ok=True)
    cat = Catalogue()
    add_wa(cat)
    add_states(cat)

    counts, covered = {}, set()
    for realm in SUBS:
        store = Statuses()
        guide = []
        path = os.path.join(HOBBY, realm + ".json")
        if os.path.exists(path):
            for rec in json.load(open(path, encoding="utf-8")):
                sts = guide_statuses(realm, rec)
                covered |= set(sts)
                guide.append({**{k: rec[k] for k in ("n", "sci", "sub", "fam", "size", "care", "temp", "setup", "note", "flags") if k in rec},
                              "st": sts, "photo": photo_for(rec.get("photo") or rec["sci"]),
                              "verified": bool(rec.get("verified"))})
        rows = []
        for r in sorted(cat.rows[realm].values(), key=lambda r: r["n"].lower()):
            covered |= set(r["st"])
            rows.append([r["n"], r["c"], r["sub"], {s: store.add(st) for s, st in r["st"].items()}])
        data = {"realm": realm, "subs": SUBS[realm], "guide": guide, "statuses": store.items, "list": rows}
        with open(os.path.join(OUT, realm + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        counts[realm] = {"guide": len(guide), "list": len(rows)}
    states = [{"id": s, "name": n, "ready": s in covered,
               "default": STATE_DATA[s]["default"] if s in STATE_DATA else "",
               "sources": STATE_DATA[s]["sources"] if s in STATE_DATA else []} for s, n in STATES]
    return counts, states


def hobby_photo_keys():
    keys = []
    for realm in SUBS:
        path = os.path.join(HOBBY, realm + ".json")
        if os.path.exists(path):
            keys += [r.get("photo") or r["sci"] for r in json.load(open(path, encoding="utf-8"))]
    return keys

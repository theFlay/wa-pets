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


def build(photo_for):
    os.makedirs(OUT, exist_ok=True)
    lists = {r: [] for r in SUBS}
    stores = {r: Statuses() for r in SUBS}
    for row in S.WAOL["rows"]:
        c = classify(row)
        if not c:
            continue
        realm, sub = c
        lvl, label, detail = S.waol_status(row)
        st = {"level": lvl, "label": label, "detail": detail, **S.src("waol")}
        lists[realm].append([re.sub(r"\s+", " ", row[0]), common_name(row[9]), sub, stores[realm].add(st)])

    # aquatic: the WA fish lists and the national import list
    aq = stores["aquatic"]
    seen = set()
    for key, entries, lvl, label in (("wa_noxious_fish", S.NOX, "no", "Noxious: banned in WA"),
                                     ("wa_high_risk_fish", S.HR, "no", "High risk: can't be brought into WA")):
        for e in entries:
            t = e["taxa"][0]
            nm = t["name"] + (" (whole genus)" if t["rank"] == "genus" else " (whole family)" if t["rank"] == "family" else "")
            if nm in seen:
                continue
            seen.add(nm)
            extra = " in some areas" if e.get("area") else ""
            exc = ", except " + ", ".join(x["name"] for x in e["except"]) if e.get("except") else ""
            st = {"level": lvl, "label": label + extra, "detail": "Listed" + exc, **S.src(key)}
            lists["aquatic"].append([nm, "", "banned", aq.add(st)])
    for x in S.LIL:
        if x["section"] not in ("freshwater_fish", "marine_fish", "sharks_rays"):
            continue
        nm = x["name"] + (" (whole genus)" if x["rank"] == "genus" else " (whole family)" if x["rank"] == "family" else "")
        if nm in seen:
            continue
        seen.add(nm)
        rec = {"sci": x["name"], "sub": "fresh" if x["section"] == "freshwater_fish" else "marine",
               "fam": x["name"] if x["rank"] == "family" else ""}
        st = S.aquatic(rec)
        if x.get("condition"):
            st = {**st, "detail": st["detail"] + " Import condition: " + x["condition"] + "."}
        lists["aquatic"].append([nm, "", rec["sub"], aq.add(st)])

    counts = {}
    for realm in SUBS:
        guide = []
        path = os.path.join(HOBBY, realm + ".json")
        if os.path.exists(path):
            for rec in json.load(open(path, encoding="utf-8")):
                st = S.aquatic(rec) if realm == "aquatic" else S.organism(rec)
                guide.append({**{k: rec[k] for k in ("n", "sci", "sub", "fam", "size", "care", "temp", "setup", "note", "flags") if k in rec},
                              "st": st, "photo": photo_for(rec.get("photo") or rec["sci"]),
                              "verified": bool(rec.get("verified"))})
        rows = sorted(lists[realm], key=lambda r: r[0].lower())
        data = {"realm": realm, "subs": SUBS[realm], "guide": guide, "statuses": stores[realm].items, "list": rows}
        with open(os.path.join(OUT, realm + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        counts[realm] = {"guide": len(guide), "list": len(rows)}
    return counts


def hobby_photo_keys():
    keys = []
    for realm in SUBS:
        path = os.path.join(HOBBY, realm + ".json")
        if os.path.exists(path):
            keys += [r.get("photo") or r["sci"] for r in json.load(open(path, encoding="utf-8"))]
    return keys

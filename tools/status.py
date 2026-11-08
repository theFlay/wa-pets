"""Work out a species' WA legal status from the official lists in data/lists.

Every answer carries the list it came from and the date that list was last
downloaded, so the site can show "Source: ... (checked YYYY-MM-DD)".

Levels: "ok" (allowed), "permit" (allowed with conditions or a permit),
"check" (unclear: ask the department), "no" (prohibited or noxious).
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTS = os.path.join(ROOT, "data", "lists")

SOURCES = {
    "waol": ("WA Organism List (DPIRD)", "https://www.dpird.wa.gov.au/online-tools/western-australian-organism-list/"),
    "wa_noxious_fish": ("WA noxious fish list (FRMR 1995, Sch 5)",
                        "https://www.dpird.wa.gov.au/siteassets/documents/biosecurity/animal/noxious_fish_list.pdf"),
    "wa_high_risk_fish": ("WA high-risk non-endemic fish list (DPIRD)",
                          "https://www.dpird.wa.gov.au/siteassets/documents/biosecurity/aquatic/high_risk_non_endemic_fish_list.pdf"),
    "live_import_list_part1": ("Live Import List, Part 1 (EPBC Act)",
                               "https://www.legislation.gov.au/F2006B01053/latest/text"),
    "translocation": ("Importing and keeping live fish (DPIRD)",
                      "https://www.dpird.wa.gov.au/businesses/biosecurity/aquatic-biosecurity/importing-and-keeping-live-fish-translocation/"),
}


def _load(name):
    return json.load(open(os.path.join(LISTS, name + ".json"), encoding="utf-8"))


META = _load("meta")
WAOL = _load("waol")
NOX = _load("wa_noxious_fish")
HR = _load("wa_high_risk_fish")
LIL = _load("live_import_list_part1")


def binomial(name):
    w = re.sub(r"\(.*?\)", " ", name).split()
    return " ".join(w[:2]) if len(w) >= 2 and w[1].islower() else (w[0] if w else "")


WAOL_BY = {}
for row in WAOL["rows"]:
    WAOL_BY.setdefault(binomial(row[0]), []).append(row)


def src(key, extra=None):
    label, url = SOURCES[key]
    s = {"src": label, "url": url, "checked": META.get(key, META.get("waol", {})).get("checked", "")}
    if META.get(key, {}).get("version"):
        s["version"] = META[key]["version"]
    if extra:
        s.update(extra)
    return s


def taxon_hit(entries, names, genus, families):
    for e in entries:
        hit = any((t["rank"] == "species" and t["name"] in names) or (t["rank"] == "genus" and t["name"] == genus)
                  or (t["rank"] == "family" and t["name"] in families) for t in e["taxa"])
        if not hit:
            continue
        exc = e.get("except", [])
        if any((t["rank"] == "species" and t["name"] in names) or (t["rank"] == "genus" and t["name"] == genus)
               for t in exc):
            continue
        return e
    return None


def taxon_label(e):
    t = e["taxa"][0]
    return t["name"] + {"genus": " (whole genus)", "family": " (whole family)"}.get(t["rank"], "")


def waol_status(row):
    """The keeping category, when given, is the rule for keeping, so it decides.
    Otherwise the legal status (entry into WA) does."""
    legal, keeping = row[1], row[2]
    detail = legal + (f"; keeping: {keeping}" if keeping else "")
    if keeping == "Prohibited":
        return "no", "Prohibited in WA", detail
    if keeping == "Restricted":
        return "permit", "Permit needed to keep", detail
    if keeping == "Exempt":
        if legal.startswith("Permitted"):
            return "ok", "Permitted in WA", detail
        return "ok", "Declared pest: keeping exempt", detail
    if legal.startswith("Permitted, Requires Permit"):
        return "permit", "Permit needed", detail
    if legal.startswith("Permitted"):
        return "ok", "Permitted in WA", detail
    if "Prohibited - s12" in legal:
        return "no", "Prohibited in WA", detail
    return "check", "Declared pest", detail


def waol_lookup(names):
    for n in names:
        rows = WAOL_BY.get(binomial(n))
        if rows:
            # prefer the row for the plain species over subspecies rows
            rows = sorted(rows, key=lambda r: len(r[0].split()))
            return rows[0]
    return None


def aquatic(rec):
    """Fish and other aquatic animals: WA fish lists first, then the WAOL."""
    names = {binomial(rec["sci"])} | {binomial(a) for a in rec.get("also", [])}
    genus = binomial(rec["sci"]).split()[0]
    fams = {rec.get("fam", ""), rec.get("subfam", "")} - {""}
    notes = []
    lil = taxon_hit([{"taxa": [x]} for x in LIL], names, genus, fams)
    lil_txt = ("On the national Live Import List" + (f" ({lil['taxa'][0].get('condition')})" if lil and lil["taxa"][0].get("condition") else "")
               if lil else "Not on the national Live Import List, so only Australian-bred stock")
    e = taxon_hit(NOX, names, genus, fams)
    if e:
        area = " in some areas" if e.get("area") else ""
        return {"level": "no", "label": "Noxious: banned in WA" + area, "detail": "Listed: " + taxon_label(e), **src("wa_noxious_fish")}
    e = taxon_hit(HR, names, genus, fams)
    if e:
        return {"level": "no", "label": "High risk: can't be brought into WA",
                "detail": "Listed: " + taxon_label(e), **src("wa_high_risk_fish")}
    row = waol_lookup(names)
    if row:
        lvl, label, detail = waol_status(row)
        return {"level": lvl, "label": label, "detail": detail, **src("waol")}
    if rec.get("native"):
        return {"level": "ok", "label": "WA native",
                "detail": "Not on WA's noxious or high-risk lists. Buy captive-bred; collecting from the wild follows fishing rules.",
                **src("translocation")}
    if rec.get("sub") in ("crust", "other"):
        return {"level": "check", "label": "Check with DPIRD",
                "detail": "Not on WA's noxious or high-risk lists, but non-native crustaceans and snails usually need approval. "
                          + lil_txt + ".", **src("translocation")}
    return {"level": "ok", "label": "Not banned in WA",
            "detail": "Not on WA's noxious or high-risk lists. Bringing it in from interstate needs DPIRD translocation approval. "
                      + lil_txt + ".", **src("translocation")}


def organism(rec):
    """Everything else: the WA Organism List."""
    names = [rec["sci"]] + rec.get("also", [])
    row = waol_lookup(names)
    if row:
        lvl, label, detail = waol_status(row)
        return {"level": lvl, "label": label, "detail": detail, **src("waol")}
    return {"level": "check", "label": "Unlisted in WA",
            "detail": "Not on the WA Organism List. Unlisted organisms can't be brought into WA until assessed. "
                      "If it already lives wild in WA, ask DPIRD.", **src("waol")}

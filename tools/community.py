"""Apply an approved community suggestion (a GitHub issue from the
"Suggest an edit" form) to the site data.

Run by .github/workflows/community.yml when the maintainer adds the
"approved" label:  python tools/community.py <path to the GitHub event JSON>

The issue text is untrusted: it's only ever parsed as data and stored as
plain text (the page escapes it when showing it). Writes:
  - data/community/notes.json: every approved note, shown beside its species
  - data/hobby/<tab>.json: new species ("Add a species") and the verified
    flag ("This card is correct")
Prints a one-line summary for the issue comment.
"""
import json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES = os.path.join(ROOT, "data", "community", "notes.json")
HOBBY = os.path.join(ROOT, "data", "hobby")
GROWN = os.path.join(ROOT, "data", "grown")
TABS = {"fauna", "mammals", "aquatic", "bugs", "plants", "fungi"}
STATES = {"WA", "NSW", "VIC", "QLD", "SA", "TAS", "NT", "ACT", "ALL"}
KINDS = {
    "Correction to the care info or description": "correction",
    "The legal status looks wrong": "status",
    "Add a species to a hobby guide": "add",
    "Better photo": "photo",
    "I keep this species (experience report)": "experience",
    "This card is correct (please verify it)": "verify",
}
SCI = re.compile(r"[A-Z][a-z]+(?: [a-z]+(?:-[a-z]+)?){1,2}")


def fields(body):
    """Issue form bodies are '### Label' followed by the answer."""
    out = {}
    for m in re.finditer(r"^### (.+?)\n+(.*?)(?=\n### |\Z)", body or "", re.S | re.M):
        v = m.group(2).strip()
        out[m.group(1).strip()] = "" if v == "_No response_" else v
    return out


def clean(s, n):
    s = re.sub(r"<[^>]*>", "", s or "")             # no HTML
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", s)  # no control characters
    return s.strip()[:n]


def fail(msg):
    print("Not applied: " + msg)
    sys.exit(1)


def main():
    ev = json.load(open(sys.argv[1], encoding="utf-8"))
    issue = ev["issue"]
    f = fields(issue.get("body", ""))
    kind = KINDS.get(f.get("What kind of suggestion?", ""))
    sci = " ".join(clean(f.get("Scientific name", ""), 80).split())
    tab = clean(f.get("Tab", ""), 20).lower()
    state = clean(f.get("State or territory it applies to", ""), 10).upper()
    text = clean(f.get("Your suggestion", ""), 2000)
    common = clean(f.get("Common name", ""), 80)
    source = clean(f.get("Evidence or source (link)", ""), 300)
    if not kind:
        fail("unknown suggestion type")
    if not SCI.fullmatch(sci):
        fail(f"'{sci}' doesn't look like a scientific name")
    if tab not in TABS:
        fail(f"tab should be one of {', '.join(sorted(TABS))}")
    if state not in STATES:
        fail("state should be WA, NSW, VIC, QLD, SA, TAS, NT, ACT or all")
    if source and not re.match(r"https?://[^\s<>\"]+$", source):
        source = ""
    if not text:
        fail("the suggestion is empty")

    notes = json.load(open(NOTES, encoding="utf-8")) if os.path.exists(NOTES) else []
    notes = [n for n in notes if n["issue"] != issue["number"]]  # re-approving replaces
    note = {"issue": issue["number"], "url": issue["html_url"], "kind": kind, "sci": sci, "tab": tab,
            "state": state, "text": text, "source": source, "date": time.strftime("%Y-%m-%d")}
    notes.append(note)
    summary = f"Added a community note for {sci}."

    # Hand-written cards first, then ones grown automatically from Wikipedia.
    path = rec = None
    for folder in (HOBBY, GROWN):
        p = os.path.join(folder, tab + ".json")
        g = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
        rec = next((r for r in g if r["sci"].lower() == sci.lower()), None)
        if rec or folder == HOBBY:
            path, guide = p, g
        if rec:
            break
    if kind == "verify":
        if not rec:
            fail(f"{sci} isn't in the {tab} hobby guide, so there's no card to verify")
        rec["verified"] = True
        summary = f"Marked the {sci} card as verified."
    elif kind == "add" and not rec:
        guide.append({"n": common or sci, "sci": sci, "sub": "", "note": text[:300], "flags": "",
                      "community": issue["number"]})
        summary = f"Added {sci} to the {tab} hobby guide. Its status and photo fill in automatically."
    if kind in ("verify", "add"):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in guide) + "\n]\n")

    os.makedirs(os.path.dirname(NOTES), exist_ok=True)
    with open(NOTES, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(sorted(notes, key=lambda n: n["issue"]), fh, ensure_ascii=False, indent=1)
    print(summary)


if __name__ == "__main__":
    main()

"""Grow the hobby guides automatically, a few species per run.

Run from the repo root:  python tools/grow_guide.py [--max N] [--delay SECONDS]

Candidates are species (not genera) that some state's official list allows
you to keep, or that the WA Organism List permits. Ones allowed without a
permit come first, then ones on a state keeping list, then ones with a common
name, then the hobby-heavy subcategories. For each
one it reads the English Wikipedia summary and, if the article really is about
that species, adds an "Unchecked" card to data/grown/<tab>.json with:
  - the first sentences of the summary (CC BY-SA, credited on the card)
  - the article's lead photo, only if it's on Wikimedia Commons (free licence);
    the ~320 px thumbnail URL goes into src/img_urls.json for fetch_photos.py
Species without a usable article are remembered in data/grown/tried.json and
retried after RETRY_DAYS, so each run only spends requests on new ones.

The frogs, reptiles and birds tab has its own WA licence guide, and fungi are
mostly diseases, so those two aren't grown. Standard library only.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realms  # noqa: E402

UA = "wa-pets-guide-grower/1.0 (https://github.com/theFlay/wa-pets; static species guide)"
ROOT = realms.ROOT
GROWN = os.path.join(ROOT, "data", "grown")
TRIED = os.path.join(GROWN, "tried.json")
URLS = os.path.join(ROOT, "src", "img_urls.json")
RETRY_DAYS = 180

# Most cards each tab may grow to. Keeps the site (and img/) well inside
# GitHub Pages' 1 GB: about 11,000 photos at ~25 KB each.
CAPS = {"mammals": 400, "aquatic": 800, "bugs": 2000, "plants": 8000}
SKIP_SUBS = {"bugs": {"mites", "flies", "truebugs"}}  # mostly pests, not kept
HOBBY_SUBS = {"bugs": {"ants", "beetles", "phasmids", "roaches", "spiders", "scorpions", "butterflies"},
              "plants": {"cacti", "orchids", "carnivorous", "aquatic", "bromeliads", "palms", "ferns"},
              "mammals": {"pets", "rodents", "rabbits"}, "aquatic": {"fresh", "marine", "crust"}}
KEEP = {"ok", "permit"}
NOT_EPITHETS = {"form", "forms", "variety", "varieties", "hybrid", "hybrids", "strain", "strains", "species", "group"}
DANGER = re.compile(r"(?<!non-)(?<!not )\b(venomous|poisonous|highly toxic|toxic to (?:humans|people|pets|dogs|cats))\b", re.I)


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def save_cards(path, cards):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n" + ",\n".join(json.dumps(c, ensure_ascii=False) for c in cards) + "\n]\n")


def candidates(have, tried, today):
    """Per tab, keepable species not already carded, best first."""
    cat = realms.Catalogue()
    realms.add_wa(cat)
    realms.add_states(cat)
    out = {}
    for realm in CAPS:
        q = []
        for k, r in cat.rows[realm].items():
            if not re.fullmatch(r"[a-z]+ [a-z][a-z-]+", k) or k in have or k.split()[1] in NOT_EPITHETS:
                continue
            if r["sub"] in SKIP_SUBS.get(realm, ()) or not any(s["level"] in KEEP for s in r["st"].values()):
                continue
            t = tried.get(k)
            if t and (today - time.mktime(time.strptime(t, "%Y-%m-%d"))) < RETRY_DAYS * 86400:
                continue
            lv = {s["level"] for s in r["st"].values()}
            score = (3 if "ok" in lv else 0) + (2 if any(s != "WA" for s in r["st"]) else 0) \
                + (2 if r["c"] else 0) + (1 if r["sub"] in HOBBY_SUBS.get(realm, ()) else 0)
            q.append((-score, k, r))
        q.sort(key=lambda x: (x[0], x[1]))
        out[realm] = [x[2] for x in q]
    return out


class RateLimited(Exception):
    pass


def summary(sci):
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(sci.replace(" ", "_")) + "?redirect=true"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited()
        if e.code == 404:
            return None
        raise


def first_sentences(text, limit=320):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "..."


def card_for(row, d):
    """A card from a Wikipedia summary, or None if the article isn't about this species."""
    sci = " ".join(row["n"].split()[:2])
    if not d or d.get("type") != "standard":
        return None, "no article"
    title, extract = d.get("title", ""), d.get("extract", "")
    # We asked for the species name, so a redirect (Acinonyx jubatus -> Cheetah)
    # is fine, unless it lands on a genus or family page.
    first = re.split(r"(?<=[.!?]) ", extract, maxsplit=1)[0]
    if re.match(r"(genus|family|subfamily|order|tribe|list) ", d.get("description", ""), re.I) \
            or re.search(r"\b(is|are|was) an? (?:\w+ ){0,3}(genus|family|subfamily|tribe|order|group)\b", first):
        return None, "genus or group article"
    note = first_sentences(extract)
    if len(note) < 40:
        return None, "summary too short"
    name = re.sub(r"\s*\([^)]*\)$", "", title)
    if name.lower() == sci.lower():
        m = re.search(r"\bknown as (?:the |a |an )?([A-Za-z\u00c0-\u017f' -]{3,40}?)(?:,| or | and |\.| \u2013| -| is| \()", extract)
        c = m.group(1) if m else re.sub(r"^(.+?) \((.+)\)$", lambda x: x.group(2) + " " + x.group(1).lower(), row["c"])
        name = (c[:1].upper() + c[1:]) if c and not re.search(r"\d", c) else sci
    card = {"n": name, "sci": sci, "sub": row["sub"], "note": note, "w": title,
            "flags": "d" if DANGER.search(extract) else "", "auto": time.strftime("%Y-%m-%d")}
    th = (d.get("thumbnail") or {}).get("source", "")
    if "/wikipedia/commons/" not in th:
        card["photo"] = "none"  # no photo, or a non-free local one we shouldn't copy
    return card, th if card.get("photo") != "none" else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20, help="species to look up this run")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    a = ap.parse_args()
    os.makedirs(GROWN, exist_ok=True)
    tried = load(TRIED, {})
    store = load(URLS, {"urls": {}})
    cards, have = {}, set()
    for realm in CAPS:
        cards[realm] = load(os.path.join(GROWN, realm + ".json"), [])
        hobby = load(os.path.join(realms.HOBBY, realm + ".json"), [])
        have |= {realms.taxon_key(r["sci"]) for r in cards[realm] + hobby}
        have |= {realms.taxon_key(x) for r in hobby for x in r.get("also", [])}
    queues = candidates(have, tried, time.time())
    for realm in CAPS:
        queues[realm] = queues[realm][:max(0, CAPS[realm] - len(cards[realm]))]
    print("candidates left: " + ", ".join(f"{r} {len(q)}" for r, q in queues.items()), flush=True)

    added, looked, i = 0, 0, 0
    order = [r for r in CAPS if queues[r]]
    while looked < a.max and order:
        realm = order[i % len(order)]
        row = queues[realm].pop(0)
        if not queues[realm]:
            order.remove(realm)
        else:
            i += 1
        sci = " ".join(row["n"].split()[:2])
        try:
            d = summary(sci)
        except RateLimited:
            print("  rate limited by Wikipedia, stopping", flush=True)
            break
        except Exception as e:
            print(f"  failed {sci}: {e}", flush=True)
            looked += 1
            time.sleep(a.delay)
            continue
        looked += 1
        card, extra = card_for(row, d)
        if card:
            cards[realm].append(card)
            if extra:
                store["urls"][sci] = extra
            tried.pop(realms.taxon_key(sci), None)
            added += 1
            print(f"  + {realm}: {card['n']} ({sci}){'' if extra else ', no free photo'}", flush=True)
        else:
            tried[realms.taxon_key(sci)] = time.strftime("%Y-%m-%d")
            print(f"  - {sci}: {extra}", flush=True)
        time.sleep(a.delay)

    for realm in CAPS:
        if cards[realm]:
            save_cards(os.path.join(GROWN, realm + ".json"), sorted(cards[realm], key=lambda c: c["sci"]))
    with open(TRIED, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(tried.items())), f, indent=0, ensure_ascii=False)
        f.write("\n")
    with open(URLS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(store, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"looked up {looked}, added {added}; grown cards: " + ", ".join(f"{r} {len(c)}" for r, c in cards.items()))


if __name__ == "__main__":
    sys.exit(main())

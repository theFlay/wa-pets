"""Build the site. Run from anywhere:  python src/build.py

- index.html: the page, with the fauna guide (src/data.js) built in
- data/site/<tab>.json: hobby guide and full official list for every main tab
  (loaded by the page when that tab is opened)

Photos in img/ (named by tools/fetch_photos.py) are served from the site.
Anything without a cached photo yet falls back to its Wikimedia URL.
"""
import json, os, re, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
EXTS = (".jpg", ".png", ".webp", ".gif")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import realms  # noqa: E402


def read(name):
    return open(os.path.join(SRC, name), encoding="utf-8").read()


def slug(key):
    k = re.sub(r"^File:", "", key)
    k = re.sub(r"\.(jpe?g|png|gif|webp|tiff?)$", "", k, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", k.lower()).strip("-")


def credit_page(url, key):
    m = re.search(r"/wikipedia/(commons|en)/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?]+)", url or "")
    if m:
        host = "commons.wikimedia.org" if m.group(1) == "commons" else "en.wikipedia.org"
        return f"https://{host}/wiki/File:{m.group(2)}"
    return "https://en.wikipedia.org/w/index.php?search=" + urllib.parse.quote(key)


URLS = json.loads(read("img_urls.json"))["urls"]


def photo_for(k):
    if not k or k == "none":
        return None
    u = URLS.get(k, "")
    f = next((f"img/{slug(k)}{e}" for e in EXTS if os.path.exists(os.path.join(ROOT, "img", slug(k) + e))), None)
    if f:
        return {"f": f, "c": credit_page(u, k)}
    if u:
        return {"f": re.sub(r"^https://thumb\.wikimedia\.org/", "https://upload.wikimedia.org/", u).split("?")[0],
                "c": credit_page(u, k)}
    return None


data = read("data.js")
keys = [json.loads(l.strip().rstrip(","))[-1] for l in data.splitlines() if l.strip().startswith('["')]
photos = [photo_for(k) for k in keys]
counts, states, fauna_notes = realms.build(photo_for)
meta = json.load(open(os.path.join(ROOT, "data", "lists", "meta.json")))
info = {"counts": counts, "sources": meta, "states": states, "faunaNotes": fauna_notes}

html = (read("template.html").replace("__DATA__", data).replace("__PHOTOS__", json.dumps(photos))
        .replace("__TOTAL__", str(len(keys))).replace("__INFO__", json.dumps(info)))
with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write(html)
local = sum(1 for p in photos if p and p["f"].startswith("img/"))
print(f"index.html: {len(keys)} fauna guide species, {local} photos from img/")
for r, c in counts.items():
    print(f"  {r:8} guide {c['guide']:3}  official list {c['list']:6}")

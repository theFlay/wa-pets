"""Build index.html from src/. Run from anywhere:  python src/build.py

Photos in img/ (named by tools/fetch_photos.py) are served from the site.
Any species without a cached photo yet falls back to its Wikimedia URL.
"""
import json, os, re, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
EXTS = (".jpg", ".png", ".webp", ".gif")


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


data = read("data.js")
keys = [json.loads(l.strip().rstrip(","))[-1] for l in data.splitlines() if l.strip().startswith('["')]
urls = json.loads(read("img_urls.json"))["urls"]
photos, local = [], 0
for k in keys:
    u = urls.get(k, "")
    f = next((f"img/{slug(k)}{e}" for e in EXTS if os.path.exists(os.path.join(ROOT, "img", slug(k) + e))), None)
    if k == "none":
        photos.append(None)
    elif f:
        local += 1
        photos.append({"f": f, "c": credit_page(u, k)})
    elif u:
        photos.append({"f": re.sub(r"^https://thumb\.wikimedia\.org/", "https://upload.wikimedia.org/", u).split("?")[0],
                       "c": credit_page(u, k)})
    else:
        photos.append(None)

html = (read("template.html").replace("__DATA__", data).replace("__PHOTOS__", json.dumps(photos))
        .replace("__TOTAL__", str(len(keys))))
with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write(html)
print(f"index.html: {len(keys)} species, {sum(1 for p in photos if p)} with photos, {local} served from img/")

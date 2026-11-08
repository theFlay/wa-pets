"""Download missing species photos into img/ so the site does not hotlink.

Run from the repo root:  python tools/fetch_photos.py [--max N] [--delay SECONDS]

For every species in src/data.js whose photo key is not "none" and has no
file in img/, it finds a photo URL (src/img_urls.json first, otherwise the
Wikipedia / Commons API), downloads a ~500 px thumbnail and records the
source URL in src/img_urls.json so build.py can link the photo credit.

It is polite to Wikimedia on purpose: one request at a time, a pause between
downloads, an honest User-Agent, and it stops early if it gets rate limited.
Standard library only, so it also runs in GitHub Actions without installs.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

UA = "wa-pets-photo-cache/1.0 (https://github.com/theFlay/wa-pets; static species guide)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "img")
DATA = os.path.join(ROOT, "src", "data.js")
URLS = os.path.join(ROOT, "src", "img_urls.json")
EXTS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


HOBBY = os.path.join(ROOT, "data", "hobby")
GROWN = os.path.join(ROOT, "data", "grown")
# GitHub Pages sites must stay under 1 GB; stop caching well before that.
MAX_IMG_MB = 700


def species_keys():
    """Photo keys for the fauna guide (src/data.js), every hand-written hobby
    guide (data/hobby/*.json), then the grown guides (data/grown/*.json)."""
    rows = [json.loads(l.strip().rstrip(",")) for l in open(DATA, encoding="utf-8") if l.strip().startswith('["')]
    keys = [r[-1] for r in rows]
    for folder in (HOBBY, GROWN):
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".json") and name != "tried.json":
                    keys += [r.get("photo") or r["sci"] for r in json.load(open(os.path.join(folder, name), encoding="utf-8"))]
    return keys


def img_mb():
    return sum(os.path.getsize(os.path.join(IMG, f)) for f in os.listdir(IMG)) / 1e6


def slug(key):
    k = re.sub(r"^File:", "", key)
    k = re.sub(r"\.(jpe?g|png|gif|webp|tiff?)$", "", k, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", k.lower()).strip("-")


def local_file(key):
    for ext in EXTS.values():
        p = os.path.join(IMG, slug(key) + ext)
        if os.path.exists(p):
            return p
    return None


class RateLimited(Exception):
    def __init__(self, wait):
        self.wait = wait


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.headers.get("Content-Type", "").split(";")[0], r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(int(e.headers.get("Retry-After") or 60))
        raise


def api_lookup(key):
    """Find a ~500 px thumbnail URL for a page title or a File: name."""
    if key.startswith("File:"):
        q = {"action": "query", "titles": key, "prop": "imageinfo", "iiprop": "url",
             "iiurlwidth": "500", "format": "json", "formatversion": "2"}
        _, body = get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q))
        pages = json.loads(body)["query"]["pages"]
        info = pages[0].get("imageinfo") if pages else None
        return info[0].get("thumburl") if info else None
    q = {"action": "query", "titles": key, "prop": "pageimages", "piprop": "thumbnail",
         "pithumbsize": "500", "redirects": "1", "format": "json", "formatversion": "2"}
    _, body = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q))
    pages = json.loads(body)["query"]["pages"]
    th = pages[0].get("thumbnail") if pages else None
    return th["source"] if th else None


def clean(u):
    return re.sub(r"^https://thumb\.wikimedia\.org/", "https://upload.wikimedia.org/", u).split("?")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0, help="stop after this many downloads (0 = no limit)")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests")
    a = ap.parse_args()
    os.makedirs(IMG, exist_ok=True)
    store = json.load(open(URLS, encoding="utf-8")) if os.path.exists(URLS) else {"urls": {}}
    urls = store["urls"]
    # Species with no photo on Wikipedia are only looked up again after 30 days.
    nofind = store.setdefault("not_found", {})
    soon = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 30 * 86400))
    todo, seen = [], set()
    for k in species_keys():
        if k != "none" and k not in seen and not local_file(k) and nofind.get(k, "") < soon:
            seen.add(k)
            todo.append(k)
    print(f"{len(todo)} species photos to fetch", flush=True)
    done = failed = 0
    used = img_mb()
    for k in todo:
        if a.max and done >= a.max:
            break
        if used > MAX_IMG_MB:
            print(f"  img/ is {used:.0f} MB, over the {MAX_IMG_MB} MB budget: stopping", flush=True)
            break
        try:
            u = urls.get(k)
            if not u:
                u = api_lookup(k)
                time.sleep(a.delay)
                if not u:
                    print(f"  no photo found: {k}", flush=True)
                    nofind[k] = time.strftime("%Y-%m-%d")
                    failed += 1
                    continue
                urls[k] = u
                nofind.pop(k, None)
            ctype, body = get(clean(u))
            ext = EXTS.get(ctype)
            if not ext or len(body) < 1000:
                print(f"  not an image ({ctype}, {len(body)} B): {k}", flush=True)
                failed += 1
            else:
                with open(os.path.join(IMG, slug(k) + ext), "wb") as f:
                    f.write(body)
                done += 1
                used += len(body) / 1e6
                print(f"  [{done}] {slug(k)}{ext} {len(body)//1024} KB", flush=True)
        except RateLimited as e:
            print(f"  rate limited by Wikimedia, stopping (retry after {e.wait}s)", flush=True)
            break
        except Exception as e:
            print(f"  failed {k}: {e}", flush=True)
            failed += 1
        time.sleep(a.delay)
    with open(URLS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(store, f, indent=1, ensure_ascii=False)
        f.write("\n")
    left = sum(1 for k in set(species_keys()) if k != "none" and not local_file(k))
    print(f"downloaded {done}, failed {failed}, still missing {left}")


if __name__ == "__main__":
    sys.exit(main())

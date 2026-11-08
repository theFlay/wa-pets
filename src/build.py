import json, os, re, urllib.parse, sys
os.chdir(sys.argv[1])
HOTLINK = len(sys.argv) > 2 and sys.argv[2] == 'gh'
OUT = 'gh' if HOTLINK else 'site'
data = open('data.js').read()
keys = json.load(open('keys.json'))
urls = json.load(open('img_urls.json'))['urls'] if os.path.exists('img_urls.json') else {}
photos = []
for i, k in enumerate(keys):
    fn = f'img/{i:03d}.jpg'
    if os.path.exists(fn):
        u = urls.get(k, '')
        m = re.search(r'/commons/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/', u) or re.search(r'/commons/[0-9a-f]/[0-9a-f]{2}/([^/?]+)', u)
        credit = 'https://commons.wikimedia.org/wiki/File:' + m.group(1) if m else 'https://en.wikipedia.org/w/index.php?search=' + urllib.parse.quote(k)
        photos.append({'f': fn, 'c': credit})
    elif HOTLINK and urls.get(k):
        u = re.sub(r'^https://thumb\.wikimedia\.org/', 'https://upload.wikimedia.org/', urls[k]).split('?')[0]
        m = re.search(r'/commons/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/', u)
        photos.append({'f': u, 'c': 'https://commons.wikimedia.org/wiki/File:' + m.group(1) if m else u})
    else:
        photos.append(None)
html = open('template.html').read().replace('__DATA__', data).replace('__PHOTOS__', json.dumps(photos)).replace('__TOTAL__', str(len(keys)))
os.makedirs(OUT, exist_ok=True)
open(OUT + '/index.html', 'w').write(html)
print('photos:', sum(1 for p in photos if p), 'of', len(photos))

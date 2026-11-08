# Source for the guide

- `data.js` - every species: [common, scientific, category, group, size, care 1-3, temperament, setup, note, flags, photo key]
- `template.html` - page layout, styles and script
- `img_urls.json` - Wikimedia photo URL for each photo key
- `build.py` - merges these into the root index.html

Rebuild (run from the repo root, needs Python 3):
1. Copy `src/data.js`, `src/template.html`, `src/keys.json`, `src/img_urls.json` and the root `img/` folder into one working folder
2. `python3 src/build.py <that folder> gh`
3. Copy `<that folder>/gh/index.html` to the repo root

Photos in `img/` are served locally; any species without a local photo loads it straight from upload.wikimedia.org.

# Source for the guide

- `data.js` - every species: [common, scientific, category, group, size, care 1-3, temperament, setup, note, flags, photo key]
- `template.html` - page layout, styles and script
- `img_urls.json` - Wikimedia photo URL for each photo key
- `build.py` - merges these into the root index.html

Rebuild from the repo root (needs Python 3, nothing to install):

    python src/build.py

## Photos

Photos are cached in the root `img/` folder, named after their photo key (for example `img/litoria-splendida.jpg`). Any species without a cached photo yet falls back to loading it from upload.wikimedia.org.

`tools/fetch_photos.py` downloads missing photos one at a time with a pause between each. If a photo key has no entry in `img_urls.json`, it looks one up through the Wikipedia or Commons API. Set the photo key to `none` for species with no free photo.

The `Cache photos` GitHub Action runs it every 30 minutes, fetching up to 5 photos per run, then rebuilds and commits. To add a species, add a line to `data.js` and push: the Action finds its photo.

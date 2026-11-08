# How the site is built

Everything is plain Python 3 (standard library only) and a static page, so it runs on GitHub Pages.

Rebuild from anywhere:

    python src/build.py

## Files

- `src/template.html` - page layout, styles and script
- `src/data.js` - the pet keeper's licence guide: [common, scientific, category, group, size, care 1-3, temperament, setup, note, flags, photo key]
- `src/img_urls.json` - Wikimedia photo URL for each photo key
- `data/hobby/<tab>.json` - hobby guide species for a tab (`aquatic`, `bugs`, ...). Fields: `n` common name, `sci`, `sub` subcategory id, `fam` family, `size`, `care` 1-3, `temp`, `setup`, `note`, `flags`, optional `native` (WA native), `also` (other scientific names to match), `photo` (photo key if not the scientific name), `verified`
- `data/lists/` - the official lists, parsed (`waol.json`, `wa_noxious_fish.json`, `wa_high_risk_fish.json`, `live_import_list_part1.json`) and `meta.json` with download dates and versions
- `data/sources/` - the official PDFs as text, for checking the parser
- `data/grown/<tab>.json` - cards added automatically by `tools/grow_guide.py`: `n`, `sci`, `sub`, `note` (Wikipedia summary), `w` (Wikipedia article title), `flags`, `auto` (date added), optional `photo` (`none` if there's no free photo). `data/grown/tried.json` lists species without a usable article, retried after 180 days
- `data/site/<tab>.json` - generated: each tab's full official list, loaded by the page when the tab opens
- `data/site/<tab>-guide.json` - generated: each tab's hobby guide (hand-written cards, then grown ones), loaded when the guide is opened
- `tools/update_lists.py` - downloads and parses the official lists (needs `pdftotext`; `--offline` re-parses what's in data/sources)
- `tools/status.py` - works out a species' WA status from the lists
- `tools/realms.py` - sorts every official entry into a tab and subcategory, and writes data/site
- `tools/fetch_photos.py` - downloads missing photos one at a time, politely. Stops once `img/` reaches 700 MB (GitHub Pages allows 1 GB), and only retries species with no photo after 30 days
- `tools/grow_guide.py` - grows the hobby guides: picks keepable species (allowed without a permit first, then ones on a state keeping list, then ones with a common name), reads the Wikipedia summary, and adds a card if the article is really about that species. Caps per tab are in `CAPS`

Flags: `d` dangerous, `r` colour morphs or forms, `x` males and females look different, `l` lives around Perth/Peel, `m` suits a mixed finch/quail aviary, `t` threatened or hard to source.

## Statuses

Every status carries its source and the date that list was downloaded. Levels:

- `ok` allowed: permitted on the WA Organism List, or a fish that isn't on WA's noxious or high-risk lists
- `permit` allowed with a permit or conditions
- `check` unclear: unlisted in WA, or (for crustaceans and snails) not on the fish lists but likely needs DPIRD approval
- `no` prohibited, noxious or high risk

## States

Statuses are stored per state. `tools/realms.py` builds one catalogue per tab where each taxon (matched on scientific name, ignoring the author) holds a status for every state that has one. Other states come from `tools/state_lists.py` (parses saved sources into `data/lists/states/`); see [docs/STATES.md](../docs/STATES.md).

## Community

- `.github/ISSUE_TEMPLATE/community.yml` - the "Suggest an edit" form (the page pre-fills species, tab and state)
- `tools/community.py` - applies an approved suggestion: writes `data/community/notes.json`, adds new species to `data/hobby/<tab>.json`, or marks a card verified. Issue text is treated as untrusted data (HTML stripped, links must be http(s), names validated)
- `Apply community suggestion` workflow: runs when the `approved` label is added to an issue labelled `community`

## Automation

- `Grow guides and cache photos` (every 30 minutes): looks up 20 new species for the hobby guides, fetches up to 25 missing photos, rebuilds and commits
- `Update official lists` (weekly): re-downloads every official list, rebuilds and commits if anything changed

To add a species, add it to `src/data.js` or a `data/hobby/*.json` file and push. Its status and photo fill in automatically. The Live Import List URL in `tools/update_lists.py` is pinned to a compilation; bump it when a new one is registered.

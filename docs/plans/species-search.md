# Plan: "Search further" and live species requests for wa-pets

Repo: theFlay/wa-pets (static site on GitHub Pages, Python 3 stdlib tools, GitHub Actions for data).
Read `README.md`, `src/README.md`, `tools/grow_guide.py`, `tools/realms.py`, `tools/push.sh` and the workflows in `.github/workflows/` before starting. Follow the repo's existing style: stdlib-only Python, plain JS in `src/template.html`, comments that explain why, files committed one entry per line.

## What we're building

1. A visitor searches a tab (e.g. "bobtail") and nothing shows.
2. A **Search further** button searches every official list across all tabs, then the Atlas of Living Australia (ALA) name service, which knows Australian common names (ALA maps "bobtail" to *Tiliqua rugosa*; the WA Organism List has that species but no common name for it).
3. The visitor picks one result. The browser builds the card **instantly** for them (status from our lists, summary and photo from Wikipedia).
4. One click on **Add to the guide for everyone** sends only the scientific name to a Cloudflare Worker. The Worker queues it and triggers a GitHub Action. The Action re-validates the name, does the same grab as the scheduled job but for that one species, commits, and redeploys. It's live for everyone in a few minutes. No GitHub account needed.
5. Separately, the scheduled 30-minute grab stops discarding species that have no usable Wikipedia article. It adds a **bare card** instead and fills it in later.

## Decisions already made (don't revisit)

- Relay: **Cloudflare Worker** (owner wants the least to maintain). Not his VPS, not GitHub issues.
- Search order: **official lists first, then ALA**.
- **Any species can be requested**, including prohibited and unlisted ones. The card shows its real status (Prohibited / Unlisted, etc).
- **No usable Wikipedia article means a bare card**, not a skip. This applies to requests AND the scheduled grab. Bare cards get filled in later when an article turns up.
- The scheduled grab must add **exactly its target number of new cards** per run when candidates exist (a failed lookup is replaced by the next candidate), and runs **50 every 10 minutes** with an authenticated Wikimedia token.
- The owner doesn't need to understand or hand-write this code. Optimise for correctness and low maintenance.

## Architecture

```
Browser (GitHub Pages)
  |- local search: built cross-tab name index (data/site)
  |- ALA name search (direct if CORS allows, else via Worker /search)
  |- Wikipedia REST summary (direct, CORS ok) -> instant card
  '- POST /request {sci, turnstileToken} -> Worker

Cloudflare Worker (worker/ in this repo)
  |- verifies Turnstile, rate limits, validates name shape
  |- stores the request in D1 (queue table)
  '- POST GitHub /repos/theFlay/wa-pets/dispatches (event_type: species-request)

GitHub Action (requests.yml, also drained by photos.yml)
  |- GET Worker /pending (shared secret) -> list of queued names
  |- tools/add_species.py: validate via ALA + lists, grab, write data/grown
  |- fetch photos for those, build, tools/push.sh, POST Worker /done
  '- calls pages.yml to deploy
```

### Why a queue instead of putting the name in the dispatch payload

GitHub `concurrency` groups keep only **one pending run**. A newer queued run cancels the older pending one. If three people request species within a minute, payload-only runs would silently drop names. With a queue, every run **drains everything pending**, so a cancelled run loses nothing. The scheduled 30-minute run also drains the queue as a safety net, so even a failed dispatch is picked up within 30 minutes.

Use **D1** for the queue, not KV. KV reads and lists are eventually consistent (up to ~60 s across locations), and the Action reads from a different location than the visitor wrote from. D1 has a single primary, so it doesn't have that problem. Verify current D1 free-tier limits in Cloudflare docs; the expected volume is tiny.

## Phase 1: bare cards in the scheduled grab (ship this first, it's independent)

In `tools/grow_guide.py`:

- When `card_for` fails ("no article", "genus or group article", "summary too short"), still add a card: `{"n", "sci", "sub", "note": "", "flags": "", "auto": date, "bare": 1, "chk": date}`.
  - Name: the official list's common name if it passes the same English check `card_for` already uses, else the scientific name.
  - If the article was a genus/group page, still don't use its text, but its Commons thumbnail can't be trusted either (it's of a different species), so set `"photo": "none"`. Leave the photo empty for "no article" so `fetch_photos.py` behaves as it does today for photo-less species. Check how `fetch_photos.py` treats missing URLs and match it.
- Add a **refill pass** to each run: re-check a few bare cards (e.g. up to 5 per run) whose `chk` is older than 30 days. If Wikipedia now gives a usable card, replace the bare card in place (keep `auto`, drop `bare`/`chk`). Otherwise just update `chk`. Count these lookups against the same `--max` budget and politeness delay.
- **Migrate `data/grown/tried.json`**: on first run, turn its entries into bare cards. Only do this for species that would still be candidates; `candidates()` already knows what's keepable and which tab and sub each one is in. Then delete `tried.json` and remove the `RETRY_DAYS` logic. Keep the migration code out of the hot path, or as a one-off `--migrate-tried` flag run once in this PR.
- **Caps**: bare cards count toward `CAPS`. Note in a comment that plants will grow lots of bare cards (obscure plants rarely have articles).
- **Template**: render cards with an empty `note` cleanly (no empty paragraph). Show a small "Few details yet" style tag, and sort bare cards after full ones and after `pest` ones within each subcategory.
- **`--max` means cards added, not lookups.** Today `--max 20` is 20 lookups, so failures mean fewer than 20 new cards. Change the loop to keep pulling the next candidate until `--max` NEW cards (full or bare) have been added. Lookups that don't produce a card (network error, timeout, a candidate turning out to be already carded) are replaced by the next candidate. Stop early only when: the candidate queues are empty (caps reached), Wikipedia rate-limits us (429), or a safety budget of total lookups is spent (e.g. `3 x --max`, so a Wikipedia outage can't loop for the whole run). Print why it stopped. Refill lookups for bare cards come out of a **separate** small budget (`--refill N`, default 5) so they never eat into the new-card target.
- Update the module docstring, `src/README.md` (`data/grown` fields, `tried.json` gone) and the README's "grow by themselves" paragraph.

## Phase 1b: faster schedule (50 every 10 minutes) with a Wikimedia token

Owner wants **50 new cards every 10 minutes** instead of 20 every 30.

**Why a token is needed.** In 2026 Wikimedia started enforcing API rate limits. Anonymous requests get a low limit (documented as 500/hour per IP on the old gateway, "hundreds per hour" on the new one), and GitHub-hosted runners share IPs with other users. 50 lookups + up to 50 photos + refills every 10 minutes is roughly 600+ requests/hour, so anonymous would hit 429s. Authenticated requests get "several thousand per hour". Rate limits are counted per user/token, so one token covers all workflows.

Changes:
- `photos.yml`: cron `*/10 * * * *` (pick an offset like `3-59/10 * * * *` to avoid the top-of-hour rush), `grow_guide.py --max 50`, `fetch_photos.py --max 50`. Set `timeout-minutes` so a run reliably finishes inside 10 minutes (measure a real run; expect ~3-5 min at 1.5 s delay). Keep `concurrency: site-data` so runs never overlap.
- New repo secret `WIKIMEDIA_TOKEN`, passed to the scripts via `env:`. One shared helper (e.g. in `realms.py` or a small `tools/wiki.py`) used by `grow_guide.py`, `fetch_photos.py` and `add_species.py` that:
  - sends `Authorization: Bearer <token>` when the env var is set, and works anonymously (as today) when it isn't, so local runs still work;
  - keeps cookies across requests in a run (`http.cookiejar`). Wikimedia's docs say owner-only token clients must return cookies or they can still get strict limits;
  - keeps the descriptive `User-Agent` already in `grow_guide.py`;
  - on 429, honours `Retry-After` once if it's short (under ~60 s), otherwise stops the run cleanly and saves progress. Don't hammer.
- Verify the current rules on mediawiki.org ("Wikimedia APIs/Rate limits", "OAuth/Owner-only consumers") before finalising. These limits were new in 2026 and Wikimedia says they may change. Also check whether `upload.wikimedia.org` photo downloads count toward the limit or have their own policy.
- **Caps get hit fast at this rate.** There are ~490 grown cards now and the caps total 13,000. At 50 per 10 minutes (~7,200/day) the guides fill to their caps in about 2 days, mostly plants. After that, runs only do refills and photos. That's fine, but log "all tabs at cap" clearly, and make the run skip Wikipedia lookups entirely when there's nothing to do. Owner may raise caps later; keep them in `CAPS`. `fetch_photos.py` already stops at 700 MB of photos, which is ~28,000 at ~25 KB, so the photo limit isn't the bottleneck.
- Deploys every 10 minutes are fine: GitHub Pages' 10-builds-per-hour soft limit doesn't apply to custom Actions workflow deploys, which this repo uses. Actions minutes on public repos are free.

## Phase 2: single-species add (Python + Action)

New `tools/add_species.py` (reuse `grow_guide.py` functions; refactor them into importable helpers if needed, don't copy-paste):

- Input: list of scientific names (from the Worker queue, or CLI args for testing: `python tools/add_species.py --names "Tiliqua rugosa"`).
- For each name:
  1. **Validate the shape** with the same regex style as `tools/community.py` (`SCI`), max length, no HTML. Never put the name into a shell command.
  2. **Already carded anywhere?** Use the same `have` set logic as `grow_guide.main()`: grown, hobby, `also`, and `src/data.js`. If yes, mark the request done with result "already in the guide".
  3. **Find the tab and sub**: if the name is in the official-lists catalogue (`realms.Catalogue` + `add_wa` + `add_states`), use that row. If not, ask ALA for its classification, build a WAOL-shaped pseudo-row (uppercase phylum, class, order; family) and reuse `realms.classify()`. ALA's plant phyla don't match WAOL's (ALA often gives Charophyta/Streptophyta/Equisetopsida), so add a fallback: kingdom Plantae means plants, then let family-based plant subs work as usual. If ALA doesn't recognise the name at species or subspecies rank, **reject** it (this is what stops junk getting in).
  4. **Fungi tab** has no guide today (grow_guide doesn't grow it). If it's cheap to support a fungi guide in `realms.py`/`build.py`/the template, do it for requested species only. Otherwise reject with "The Fungi tab doesn't have a guide yet". Say which you chose in the PR.
  5. **Grab**: Wikipedia summary via the existing `summary()`/`card_for()`. Usable means a normal card; not usable means a bare card (Phase 1 shape). Add `"req": date` so requested cards are distinguishable. **Requests ignore `CAPS`** and the "keepable" filter.
  6. Unlisted species get no status row today. Make sure `guide_statuses` / the page show them as **Unlisted / check** rather than blank or crashing.
- Write results to `data/grown/<tab>.json` and `src/img_urls.json` exactly as `grow_guide.py` does (sorted, one per line).
- Print a machine-readable summary (JSON lines: name, result, tab) for the workflow to send back to the Worker.

New workflow `.github/workflows/requests.yml`:

- `on: repository_dispatch: types: [species-request]` plus `workflow_dispatch` (for manual testing with a `names` input).
- `concurrency: group: site-data, cancel-in-progress: false`. That's the same group as `photos.yml`, so they never push the same files at once. A cancelled pending run is harmless because of the drain design.
- Steps: checkout, `curl` the Worker's `/pending` with `secrets.WORKER_SECRET` (secrets go via `env:`, never inline in `run:`), run `add_species.py`, `fetch_photos.py` limited to the new species (add a `--only` option if needed), `src/build.py`, `git add` the data paths, `sh tools/push.sh "Add requested species"`, then POST results to `/done`. Only ack names that were actually pushed. If push fails, don't ack, so they retry next run.
- `deploy` job calling `pages.yml` like the other workflows.
- Add the same drain steps to `photos.yml` (before the grow step), guarded so a Worker outage never fails the scheduled grab.
- The payload from `repository_dispatch` isn't trusted and isn't needed: the workflow reads names only from the Worker queue.

## Phase 3: Cloudflare Worker (`worker/` folder in this repo)

- `wrangler.jsonc` (or `.toml`), `src/index.js`, `schema.sql`, and a `worker/README.md` with deploy steps. Plain JS, no framework needed.
- Bindings and secrets: D1 database `DB`; secrets `GITHUB_TOKEN`, `TURNSTILE_SECRET`, `WORKER_SECRET`; var `ALLOWED_ORIGIN = https://theflay.github.io`.
- D1 tables:
  - `requests(sci TEXT PRIMARY KEY, first_at, last_at, count, status, result)`: `status` is `pending` or `done`. A duplicate request just bumps `count` and doesn't re-dispatch if it's already pending.
  - `hits(ip_hash, at)` for rate limiting. Hash with a secret salt and delete rows older than a day, so it never stores raw IPs.
- Endpoints:
  - `POST /request {sci, token}`: CORS limited to `ALLOWED_ORIGIN`. Verify Turnstile server-side and validate the name shape. Rate limit **10 per IP per hour** and a **global 200 per day** (both via D1; the built-in Workers rate-limit binding only supports 10 s or 60 s periods, so it can't do per-hour). Insert or bump in the queue, then POST `https://api.github.com/repos/theFlay/wa-pets/dispatches` with `{"event_type":"species-request"}`. Debounce: skip the dispatch if one was sent in the last ~20 s, since the next run drains everything anyway. Respond `{queued: true}` or a clear error.
  - `GET /pending` (header `Authorization: Bearer WORKER_SECRET`): names with status pending.
  - `POST /done` (same auth): `[{sci, result}]` and mark them done.
  - `GET /status?sci=`: public, so the page can show "added" / "rejected: reason".
  - `GET /search?q=`: only if ALA turns out to lack CORS for browser calls (check this first). If needed, proxy to ALA autocomplete with a short cache and the same per-IP limit.
- Turnstile: the page loads the widget only when the visitor opens the add dialog, not on page load.
- Keep it small and commented. No other services.

## Phase 4: front end (`src/template.html`, `src/build.py`)

- **Cross-tab name index**: the official lists are big (`plants.json` is ~2.9 MB, ~600 KB gzipped), so don't load every tab to search. Have `build.py` / `realms.py` write a compact `data/site/names.json`: scientific name, common names, tab, sub, and per-state status refs (or enough to show the status pill), plus guide membership. Include `src/data.js` species and hobby/grown cards, so a common name that's only on a card (e.g. "Bobtail (shingleback)") is found. Measure the gzipped size. Load it **only when Search further is clicked**, and shard it if it's big enough to feel slow on mobile.
- **Search further button**: appears in the empty state of both the guide view and the list view, and also as a small link under results ("Not what you're after? Search further").
- **Results**: two sections, "On the official lists" (local index) then "From Atlas of Living Australia". ALA autocomplete endpoint (verified working): `https://api.ala.org.au/species/search/auto?q=bobtail&idxType=TAXON&limit=10`, which returns `autoCompleteList[]` with `name`, `commonName`, `commonNameMatches`, `rankString`, `guid`. Show only rank species/subspecies. Show the **matched** common name (from `commonNameMatches`, strip the `<b>` tags safely) as well as `commonName`, because ALA's preferred name can be unexpected (bobtail's is "Garrbaali"). De-duplicate ALA results already shown in the first section. Each result shows the status pill for the selected state (or "Unlisted"). Debounce input, and handle ALA being down gracefully.
- **Picking a result**: if it's already a card, jump to it. Otherwise build an **instant card** client-side, matching the existing card markup: status from the index; summary and Commons-only thumbnail from `https://en.wikipedia.org/api/rest_v1/page/summary/<name>?redirect=true`, applying the same "is this really the species" checks as `card_for` (port the logic, keep it in one clearly named JS function with a comment pointing at the Python). Mark it "Preview, only you can see this".
- **Add to the guide for everyone** button on the preview: Turnstile, then POST `/request`. Show "Queued, it'll be on the site in a few minutes". Remember pending requests in `localStorage` (wrapped in try/catch) and poll `/status` gently (e.g. every 30 s, stop after ~15 min). When done, show a link to the real card (it appears after the next deploy and page reload).
- Escape everything from ALA and Wikipedia with the existing `esc()`. Never use `innerHTML` with unescaped external text.
- The Worker URL goes in one constant at the top of the script.

## Phase 5: docs

- README: describe Search further and requests in a short paragraph. Update the "grow by themselves" paragraph for bare cards.
- `src/README.md`: new files (`tools/add_species.py`, `data/site/names.json`, `worker/`), new card fields (`bare`, `chk`, `req`), new workflow, `tried.json` removed.
- `worker/README.md`: the owner's manual steps below, written as a checklist.

## Owner's manual steps (agent can't do these; put them in worker/README.md)

1. Cloudflare account (free) and install Wrangler. Create the D1 database and apply `schema.sql`.
2. Turnstile: add a site for `theflay.github.io`, put the **site key** in the template constant and the **secret** as a Worker secret.
3. GitHub fine-grained personal access token: only the `theFlay/wa-pets` repo, permission **Contents: Read and write** (that's what `/dispatches` needs). Set the longest expiry allowed and note the date. Store it as the Worker secret `GITHUB_TOKEN`.
4. Make a random `WORKER_SECRET`. Store it both as a Worker secret and as the GitHub Actions repo secret `WORKER_SECRET`. Store the Worker URL as the Actions variable `WORKER_URL`.
5. Wikimedia token: log in to Wikimedia (any Wikipedia account), go to `Special:OAuthConsumerRegistration/propose/oauth2` on meta.wikimedia.org, register an **OAuth 2.0** consumer, tick **"This consumer is for use only by [you]"** (owner-only, no review needed), and grant read-only basic rights. Copy the access token and store it as the GitHub Actions secret `WIKIMEDIA_TOKEN`. The agent should check that these steps still match Wikimedia's docs and correct them in the README.
6. `wrangler deploy`, then paste the Worker URL into the template constant if it differs from the placeholder.

Give each command its own code block in the README.

## Testing and acceptance

- Phase 1: run `python3 tools/grow_guide.py --max 20 --delay 1.5` locally. Species without articles appear as bare cards; `tried.json` is migrated and gone; the site builds; bare cards render cleanly and sort last.
- `--max 20` with a forced failure (e.g. temporarily make every 3rd lookup raise): still adds exactly 20 cards, and the log says how many lookups it took. With all queues empty it exits quickly with "all tabs at cap".
- With `WIKIMEDIA_TOKEN` set, requests carry the bearer header and cookies are returned; without it, scripts still run anonymously.
- After switching to `*/10`, check 3 consecutive real runs each finish well inside 10 minutes and each add 50 cards.
- `python3 tools/add_species.py --names "Tiliqua gigas"`: card added on the fauna tab with WA status Prohibited.
- `--names "Tiliqua rugosa"`: "already in the guide" (it's in `src/data.js`).
- An unlisted real species ALA knows: added with status Unlisted.
- A made-up name like "Fakeus notrealus": rejected, nothing written.
- A name with HTML or shell characters: rejected by shape validation in both the Worker and Python.
- Search "bobtail" on the fauna tab with Search further: the local index finds the licence-guide bobtail. Searching a common name that's only known to ALA shows ALA results with status pills.
- Worker: 11th request from one IP inside an hour gets 429; duplicate pending request doesn't double-dispatch; `/pending` and `/done` reject without the secret; CORS refuses other origins.
- Fire 3 requests within a few seconds: all 3 species land, even if GitHub cancels pending runs.
- Kill the Worker (or wrong URL): the scheduled `photos.yml` still succeeds.
- Mobile layout of the results and preview card looks right.

## Things to verify early (don't assume)

- Whether ALA's API sends CORS headers for browser requests. This decides if the Worker needs `/search`.
- ALA's endpoint for a species' classification (kingdom, phylum, class, order, family) by name or `guid`, and its exact JSON fields.
- Current Wrangler config shape and D1 free-tier limits.
- That `repository_dispatch` only triggers workflows on the default branch (it does today; confirm and develop accordingly).

## Suggested PR split

1. Bare cards, tried.json migration, "--max means added", Wikimedia token helper, 10-minute schedule (Phases 1 and 1b). Switch the cron only after the token secret exists.
2. `add_species.py` + `requests.yml` + Worker + docs (Phases 2, 3, 5), testable via `workflow_dispatch` before the UI exists.
3. Front end (Phase 4).

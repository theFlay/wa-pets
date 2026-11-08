# State and territory sources

Each state usually has three separate kinds of rules, often run by different departments:

1. **Native animal keeping**: which native animals need a licence and which are exempt (environment department)
2. **Pests and biosecurity**: prohibited or restricted animals and plants, including exotics (agriculture department)
3. **Fish and aquatic animals**: noxious or prohibited aquatic species (fisheries)

## What's loaded

| State | Native keeping | Pests and biosecurity | Fish |
|---|---|---|---|
| WA | DBCA pet keeper's licence (fauna guide) | WA Organism List (full, weekly) | Noxious and high-risk lists (weekly) |
| NSW | Native Animal Keeper Species List 2016 (505 species) | not yet | not yet |
| VIC | Wildlife Regulations 2024, Schedules 2, 3, 4, 7 (315) | not yet | not yet |
| QLD | Animals Regulation 2020, Schedule 3 (608, incl. genus entries) | illegal pets fact sheet (examples only) | fact sheet examples only |
| SA | Keeping categories species list (360) | not yet | not yet |
| TAS | Requirements for importing and keeping wildlife (2017, 309) | covered by the same document for vertebrates | not yet |
| NT | Exempt native and non-native no-permit lists (70) | not yet | not yet |
| ACT | Exempt Animals Declaration 2026 (81) | not yet | not yet |

Anything not on a state's loaded lists shows "Not on <state>'s lists" with that state's rule for unlisted animals (for example, "Most native animals need a licence in NSW"), never a guessed status.

## How it works

- Source files are saved in `data/sources/states/` (text extracted once; Queensland and Victoria trimmed to the relevant schedules).
- `python tools/state_lists.py` parses them into `data/lists/states/<STATE>.json`. It refuses to write if a known species (budgie, carpet python, bearded dragon) goes missing.
- `tools/realms.py` merges every state into the same catalogue by scientific name: a species already there gains the state's status; a genus-wide entry ("*Acanthophis* spp.") applies to every species of that genus without a more specific entry; a state that lists only subspecies gives the species row the strictest of them, labelled "Varies by subspecies".
- These lists change rarely, so they aren't re-downloaded weekly like WA's. Re-download and re-run when a state publishes a new version.
- Tasmania's tables were extracted with Xpdf's `pdftotext -table` (Poppler, on GitHub's runners, doesn't have it), which is why the extracted text is what's saved.

## Known limits

- **NSW**: the species list is from 2016 (reprinted 2019). NSW has reviewed native animal keeping since, so some classes may have changed.
- **Tasmania**: the requirements document is from 2017, under the older 2010 regulations. 26 entries show "Check" where the table text couldn't be read cleanly (mostly travelling exhibition animals).
- **Queensland**: the Biosecurity Act's full prohibited and restricted lists aren't loaded, only the species the illegal pets fact sheet names (rabbits, ferrets, corn snakes, boas, red-eared sliders, hamsters, carp, gambusia...).
- **Victoria**: the 2025 reforms (for example, no more pet crocodiles) aren't in the 2024 schedules yet.
- **All states except WA**: exotic pest lists, plants and fish are still to find.

## Sources

- NSW: [Native Animal Keeper Species List](https://www.environment.nsw.gov.au/publications/nsw-native-animal-keepers-species-list)
- VIC: [Wildlife Regulations 2024](https://wildlife.vic.gov.au/wildlife-regulations-2024) ([authorised PDF](https://content.legislation.vic.gov.au/sites/default/files/2024-06/24-45sra001-authorised.pdf))
- QLD: [Nature Conservation (Animals) Regulation 2020](https://www.legislation.qld.gov.au/view/whole/html/inforce/current/sl-2020-0136); [illegal pets fact sheet](https://www.publications.qld.gov.au/dataset/e1aa5912-b5c2-4faa-a583-3c04cdba950d/resource/3df2d637-688d-4a67-9e72-d6cd949cb693/download/prohibited-pets.pdf)
- SA: [native animal keeping categories species list](https://www.environment.sa.gov.au/licences-and-permits/wildlife-permits/native-animal-categories/species-list)
- TAS: [Requirements for importing and keeping wildlife in Tasmania](https://nre.tas.gov.au/Documents/Requirements%20for%20importing%20and%20keeping%20wildlife%20in%20Tasmania.pdf)
- NT: [animals that do not need a permit](https://nt.gov.au/environment/animals/wildlife-permits/animals-that-do-not-need-a-permit), [native animals that need a permit](https://nt.gov.au/environment/animals/wildlife-permits/native-animals-that-need-a-permit), [prohibited wildlife](https://nt.gov.au/environment/animals/wildlife-permits/prohibited-wildlife)
- ACT: [Nature Conservation (Exempt Animals) Declaration 2026](https://www.legislation.act.gov.au/di/2026-61)
- National: Live Import List (EPBC Act), already loaded

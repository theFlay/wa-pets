# State and territory sources

Only Western Australia's lists are loaded so far. This file records where each other state's official lists are, so they can be added one at a time. Nothing here has been downloaded or parsed yet.

Each state usually has three separate kinds of rules, often run by different departments:

1. **Native animal keeping**: which native animals need a licence and which are exempt (environment department)
2. **Pests and biosecurity**: prohibited or restricted animals and plants, including exotics (agriculture or primary industries department)
3. **Fish and aquatic animals**: noxious or prohibited aquatic species (fisheries)

How adding a state works: write an `add_<state>(cat)` function in `tools/realms.py` that reads the state's lists and calls `cat.add(..., "<STATE>", status)`. Species already in the catalogue (matched on scientific name) just gain that state's status, so nothing is duplicated. Extend `guide_statuses()` the same way for the hobby guides. The state picker switches from "(coming)" to live by itself once a state has any statuses.

## Western Australia (loaded)

- Pests and imports: DPIRD [WA Organism List](https://www.dpird.wa.gov.au/online-tools/western-australian-organism-list/), full CSV export
- Fish: DPIRD noxious fish list and high-risk non-endemic fish list
- Native animal keeping: DBCA pet keeper's licence guidelines, Appendix 1 (the fauna guide)

## New South Wales

- Native animal keeping: [NSW native animal keepers species list](https://www.environment.nsw.gov.au/publications/nsw-native-animal-keepers-species-list) ([PDF](https://www.environment.nsw.gov.au/sites/default/files/nsw-native-animal-keepers-species-list.pdf)). Most native animals need a biodiversity conservation licence; about 41 captive-bred native birds are exempt (Biodiversity Conservation Regulation 2017). The species list is dated 2016, so check it is still current.
- Pests (Biosecurity Act 2015 prohibited matter) and noxious fish: not found yet. Start at NSW DPI.

## Victoria

- Native animal keeping: [Wildlife Regulations 2024](https://wildlife.vic.gov.au/wildlife-regulations-2024). Schedule 4 Parts A and B are exempt (no licence); Schedules 2 and 7 need a basic licence, Schedule 3 an advanced licence. See the [private wildlife licence guide](https://www.vic.gov.au/sites/default/files/2025-08/Private-wildlife-licence-guide-250829-.pdf). Reforms announced October 2025 (for example, no more pet crocodiles) may change the schedules.
- Pests (Agriculture Victoria prohibited, controlled and restricted pest animals) and noxious aquatic species: not found yet.

## Queensland

- Native animal keeping: Nature Conservation (Animals) Regulation 2020 ([current text](https://www.legislation.qld.gov.au/view/whole/pdf/inforce/current/sl-2020-0136)) and the [exempt, prohibited and species class listings](https://www.qld.gov.au/environment/plants-animals/wildlife-permits/permit-types/wildlife-licence/keeping-native-animals/what-animals-can-i-keep/animals-that-dont-need-a-licence). Species are Exempt, Class 1 or Class 2; anything not listed is prohibited by default. Most invertebrates are exempt except protected crayfish, *Urodacus* scorpions and tarantulas (Theraphosidae). No reptiles or amphibians are exempt.
- Pests: Biosecurity Queensland [prohibited pets](https://www.publications.qld.gov.au/dataset/e1aa5912-b5c2-4faa-a583-3c04cdba950d/resource/3df2d637-688d-4a67-9e72-d6cd949cb693/download/prohibited-pets.pdf) (PDF). Full prohibited and restricted matter lists and noxious fish: not found yet.

## South Australia

- Native animal keeping: [keeping categories](https://www.environment.sa.gov.au/licences-and-permits/wildlife-permits/keep-sell/keeping-categories) and the [species list](https://www.environment.sa.gov.au/licences-and-permits/wildlife-permits/native-animal-categories/species-list) ([PDF](https://cdn.environment.sa.gov.au/environment/docs/Keeping-categories-species-list.pdf)): Basic, Specialist, Exempt and Unprotected. The list has scientific names and codes, which makes it a good first state to add. Legal basis: [National Parks and Wildlife (Wildlife) Regulations 2019](https://www.legislation.sa.gov.au/__legislation/lz/c/r/national%20parks%20and%20wildlife%20(wildlife)%20regulations%202019/current/2019.36.auth.pdf).
- Pests and fish: not found yet. Start at PIRSA.

## Tasmania

- Not found yet. Start at the Department of Natural Resources and Environment Tasmania (NRE Tas) for wildlife permits and Biosecurity Tasmania for import and pest rules.

## Northern Territory

- Native animal keeping: [animals that do not need a permit](https://nt.gov.au/environment/animals/wildlife-permits/animals-that-do-not-need-a-permit), [native animals that need a permit](https://nt.gov.au/environment/animals/wildlife-permits/native-animals-that-need-a-permit), and [protected and prohibited wildlife](https://nt.gov.au/environment/animals/wildlife-permits/keeping-protected-prohibited-wildlife). Australian natives that don't occur naturally in the NT are prohibited.
- Pests and fish: not found yet.

## Australian Capital Territory

- Native animal keeping: [keeping or selling animals in the ACT](https://www.act.gov.au/environment/animals-and-plants/licensing-of-plants-and-animals/keeping-or-selling-animals-in-the-act). A short, mostly bird exempt list; everything else needs a nature conservation licence.
- Pests and fish: not found yet.

## National

- Live Import List (EPBC Act): what can be imported into Australia at all. Already loaded.

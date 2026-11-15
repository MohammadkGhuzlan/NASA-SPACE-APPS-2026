# Phase 3: agricultural knowledge and crop-rotation engine

## Delivered

Phase 3 now has a working, source-linked agricultural planning foundation in the
existing Field Shift application. The map, farm profiles, Phase 2 NASA services,
manual rotation drafts and database are preserved. Reports use the existing
recommendation-results table and save an immutable input/evidence snapshot.

The public Reference library contains 13 species: wheat, barley, grain maize,
common bean, pea, potato, sorghum, chickpea, lentil, oat, sunflower, soybean and
rice. Each crop lists its scientific name, botanical family, broad and optimal
ECOCROP temperature/pH ranges, annual rainfall reference, cycle range, EcoPort
record number and source links. FAO crop-water ranges are included only for the
six species covered by the referenced FAO crop-water table.

The data subset was read from the OpenCLIM EcoCrop database pinned at commit
`ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4`. Its source-file SHA-256 is
`4187e8846336e185c4583165211c5981855e95adfbefd897bd2bd481de48d106`. It is
attributed to FAO ECOCROP; the matching CGIAR Climate Action Data Hub export is
licensed CC BY 4.0 and that license is identified in the app. The Hub's notes
explain that ECOCROP values are expert estimates
with uneven provenance; missing and anomalous values exist in the larger
database. This implementation uses a small selected subset, not all 2,568
species, and does not claim the facts are field measurements.

## Farmer inputs and report behavior

The report form accepts a chronological previous-crop list, the current/planned
rotation, exclusions, a planning priority, a hypothetical planting date, an
optional farmer estimate of total crop-available seasonal water, and operational
limitations. The farm profile contributes its selected coordinates, current crop,
goal, irrigation category, source-tagged pH, soil description, water constraints
and saved farmer drafts.

Each report compares:

1. The farmer-reported rotation and supplied history.
2. Alternative A, generated from the curated crops and priority rules unless a
   saved farmer draft occupies that slot.
3. Alternative B, likewise generated or populated by the saved farmer draft.

The rotation rules preserve unknown farmer-entered crops, warn about adjacent
repeats of the same species or botanical family, and link diversity/legume
considerations to FAO or USDA NRCS references. Alternative ordering avoids
available temperature/pH conflict flags where possible, avoids adjacent family
repetition, and uses the stated priority transparently. The water-conservation
priority orders only crops with a comparable FAO crop-water range; an entered
seasonal water amount only screens species with that comparable range. If that
leaves too few supported crops, alternatives are withheld rather than inventing
requirements.

Priority rules are not suitability scores:

- **Conserve water:** order comparable FAO crop-water ranges from lower to higher.
- **Support soil health:** prefer legume inclusion and family diversity as
  reference-based design considerations; no soil-health outcome is quantified.
- **Reduce rotation risk:** prefer family diversity and no same-family adjacency;
  this is not a pest/disease model.
- **Productivity:** record the priority, but do not optimize without verified
  yield or market evidence.

## How location and soil evidence are used

NASA POWER daily observations remain tied to the exact farm coordinates and
2019–2025 reference period. If a farmer supplies a hypothetical sowing date, the
engine presents complete-month historical context across the months touched by
the maximum ECOCROP cycle. It compares monthly means of daily minimum and maximum
air temperature with ECOCROP broad thresholds and reports possible mismatches for
human review. This is deliberately not a daily exceedance count, crop-stage
simulation, planting-window detector, forecast or suitability prediction.

NASA rainfall and modeled `GWETTOP`/`GWETROOT` appear as provenance/context only.
They are not treated as effective rainfall, irrigation supply, farm soil moisture
or SMAP data. ECOCROP's annual precipitation estimates are not directly compared
with NASA rainfall because their crop-cycle interpretation depends on method.

Soil pH screening prefers the existing latest matching 0–5 cm farmer-entered
measurement; if none exists, it can use the farmer profile's self-reported pH.
Both remain unverified inputs. A SoilGrids proxy is explicitly marked and never
filters a crop. A pH-range conflict is a review flag, not a rejection, and
topsoil may not represent the crop root zone. Soil texture, salinity, drainage,
root depth and other farm soil constraints are not comprehensively screened.

The report distinguishes source facts, NASA historical estimates, farmer inputs,
proxy values, saved farmer drafts, and missing evidence. It explains risk and
benefit findings, includes source links and preserves a versioned report snapshot.
No prediction confidence, yield, savings or unsupported agronomic measurement is
produced; `modelStatus` remains `not_trained`.

## References checked on 2026-11-15

- [FAO ECOCROP via GAEZ](https://gaez.fao.org/pages/ecocrop): database scope and
  environmental descriptor definitions.
- [CGIAR Climate Action Data Hub ECOCROP catalog](https://cgiar-climate-data-hub.github.io/catalog/ecocrop/):
  data export, processing, attribution, license and quality limitations.
- [Pinned OpenCLIM EcoCrop database](https://github.com/OpenCLIM/ecocrop/blob/ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4/EcoCrop_DB.csv):
  source records used for the selected crop subset.
- [FAO Crop Water Needs, Chapter 3](https://www.fao.org/4/s2022e/s2022e07.htm):
  generic crop-cycle and total crop-water ranges where available.
- [USDA NRCS Conservation Crop Rotation, Practice Code 328](https://www.nrcs.usda.gov/publications/nhcp-notice-179/328-cps-conservation-crop-rotation-2026.pdf):
  U.S. national planning criteria; local/state Field Office Technical Guide
  requirements still apply.
- [USDA NRCS Cover Crop, Practice Code 340](https://www.nrcs.usda.gov/resources/guides-and-instructions/cover-crop-ac-340-conservation-practice-standard):
  conservation purposes and need for local/state practice criteria.
- [FAO Conservation Agriculture](https://www.fao.org/conservation-agriculture/en)
  and [species diversification](https://www.fao.org/conservation-agriculture/in-practice/species-diversification/en/):
  general conservation and diversity principles.
- [NASA POWER](https://power.larc.nasa.gov/): existing exact-coordinate historical
  climate and modeled wetness source.

## Still needed before Phase 3 can be called locally validated

- Region- and cultivar-specific planting/harvest windows and local extension
  validation for Irbid, Al Ain, Colusa and Stuttgart.
- Wider authoritative crop coverage and review of each species' ECOCROP record
  against locally relevant sources.
- Root-zone soil evidence and explicit salinity, texture, drainage and depth checks.
- Irrigation delivery/capacity and a crop-stage water-balance method. The current
  farmer-entered total water estimate is not an irrigation schedule.
- Structured pest, disease, cultivar, market, equipment and labor constraints;
  free text remains for human review.
- Independent agronomist review of the rules and generated scenarios.

## Phase 4 boundary

Phase 4 remains unimplemented. It still needs a reproducible supervised model
trained against verified FAO GAEZ crop-suitability labels, documented crop/feature
mapping, reproducible preprocessing and splits, independent validation, and
calibrated evidence/coverage limits. Farmer reports, profile inputs, NASA
observations and proxy soil values must not be converted into suitability labels.
No Phase 4 model is trained or claimed operational here.

Earlier Phase 2 dashboard and source-coverage gaps remain outside this work.

## Verification

`PYTHONPATH=artifacts/api-server uv run --no-sync python -B -m unittest discover
-s artifacts/api-server/tests -v` passed all 80 tests, including source facts,
priority validation, reference conflict flags, proxy-versus-farmer soil handling,
zero-water behavior, alternatives, saved-report ownership, idempotent data seeding
and farmer-draft preservation.

`pnpm run typecheck` passed. After restarting both app workflows, the public
Reference library rendered in a full-page desktop capture and at a mobile viewport.
API tests exercised report generation, saving, re-opening, ownership checks and
preservation of manual drafts.

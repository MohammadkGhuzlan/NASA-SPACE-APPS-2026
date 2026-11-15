# Field Shift — FAO GAEZ evidence engine review

**Date:** 2026-11-15  
**Feature branch:** `gaez-evidence-engine`  
**Base:** reviewed main, including the completed Phase 5 Stage A integration.

## 1. Implementation status

- **Stage A — source verification:** complete. Authentic official data acquired
  before building the agricultural interface. See [DATA_ACCESS.md](DATA_ACCESS.md).
- **Stage B — evidence engine:** complete for the explicitly verified subset:
  seven crop types × four management scenarios, one historical period.
- **Stage C — agricultural integration:** implemented as additional published
  evidence; the original Phase 3 engine and option ordering are preserved.
- **Stage D — UI and verification:** implemented; automated and real-data
  verification passed. Browser findings and correction are recorded below.

This is the **GAEZ** workstream's Stage B, not activation of Phase 5 ML Stage B.
Rejected ML candidates remain disabled.

## 2. Source acquisition

Twenty-eight genuine **RES05-SIX** GeoTIFFs were acquired from the public FAO
Google Cloud Storage bucket using exact official catalog rows. Total raster
bytes: **15,668,630**. The selected global coarse-grid layers—not the full
GAEZ collection—are cached locally with SHA-256, ETag, source URL and time.

The official workbook, CKAN dataset metadata, dimensions and categorical SLD
were acquired/checked. Public GET and HTTP byte-range access worked. No API key
or service account was required. No unverified numerical FAO point API is used.

Metadata: GAEZ v5, HP0120, 2001–2020, AgERA5, HIST, EPSG:4326,
4320×2160, 5 arc minutes, UInt8, NoData 0, CC BY 4.0. Metadata version
numbers are not relabeled as the GAEZ framework version.

Exact object identifiers, class definitions, attribution and reproduction
commands are in [DATA_ACCESS.md](DATA_ACCESS.md). Per-asset source sidecars and
the machine-readable manifest remain with the ignored source cache.

## 3. Verified crops and management

| Crop | Official code |
|---|---|
| Wheat | WHE |
| Barley | BRL |
| Maize | MZE |
| Soybean | SOY |
| Chickpea | CHK |
| Dryland rice | RCD |
| Wetland rice | RCW |

All four scenarios were acquired and successfully sampled:
LRLM (rain-fed/low input), HRLM (rain-fed/high input),
LILM (irrigation/low input), HILM (irrigation/high input).

Generic Rice does not silently become wetland rice. The UI requires explicit
selection; reports retain both interpretations and flag ambiguity. An
irrigated/high-input class is not automatically preferred. The live result
also warns when the farmer's irrigation is limited or unquantified.

## 4. Geographic verification

**140 actual extractions:** 5 locations × 7 crop types × 4 scenarios.
All returned genuine class values at these test coordinates; none of these
140 results was NoData or unavailable. Every value was checked against a
separate `rasterio.sample` extraction, rather than against expected-looking
handwritten values.

Wheat examples below are **class codes**, not percentages:

| Location | Latitude, longitude | LRLM | HRLM | LILM | HILM |
|---|---|---:|---:|---:|---:|
| Irbid | 32.55696, 35.84790 | 6 | 6 | 6 | 6 |
| Al Ain | 24.2249, 55.7452 | 8 | 8 | 5 | 6 |
| Colusa | 39.2146, −122.0094 | 6 | 1 | 6 | 1 |
| Stuttgart | 34.5004, −91.5526 | 4 | 2 | 4 | 2 |
| Córdoba | 37.8882, −4.7794 | 6 | 5 | 6 | 5 |

Legend: 1 Very high, 2 High, 3 Good, 4 Medium, 5 Moderate,
6 Marginal, 7 Very marginal, 8 Not suitable.

For Stuttgart: wetland rice RCW returned LRLM 2, HRLM 3, LILM 2,
HILM 1. Dryland rice RCD returned 8 in all four scenarios.
This difference is why a generic Rice label must not be silently mapped.
Scenario differences do not establish irrigation feasibility or causal benefits.

The complete values, hashes, coordinates and pixel geometry are in the
generated `real-lookups.json` evidence file. Another test located a genuine
NoData pixel in an authentic raster and confirmed it was not reported as a
successful lookup.

## 5. Backend and data flows

New package: `artifacts/api-server/backend/gaez/`.

| Module | Responsibility |
|---|---|
| `catalog.py` | Closed verified subset, crop/scenario/class mappings and source-contract validation |
| `ingest.py` | Explicit operator acquisition, official workbook selection, budget/locks, header/class validation and atomic manifest publication |
| `sampling.py` | Coordinate validation, CRS transformation, containing-cell extraction, masks, checksum verification and unavailable states |
| `service.py` | Farmer-aware evidence adapter, source-linked review findings and immutable report evidence |
| `routes.py` | Owner-scoped farm assessment and public source catalog |

Endpoints:

- `GET /api/gaez/catalog` — verified catalog, class definitions and cache status.
- `POST /api/farms/{id}/gaez` — crop/scenario/version/period input; coordinates
  come from the owned farm, not an arbitrary caller override.
- Existing `POST /api/farms/{id}/plans` — retains the Phase 3/5 pipeline and
  adds `gaezEvidence` to newly saved report JSON.

The OpenAPI specification, React Query hooks and Zod types were regenerated.
There are **no schema migrations** or new database tables. Raster binaries
are not stored in PostgreSQL. Existing reports are not recomputed or backfilled.

Public lookups never trigger large downloads. Cache integrity is checked against
acquisition hashes; repeated lookups use local files. Acquisition is serialized,
bounded and resumable. Query metadata and hash caches are bounded.

## 6. Scientific interpretation

RES05-SIX contains categorical published **modeled assessments**, not observations
of current farm performance. Its codes are not SXX's 0–10,000 numerical index.
No class is converted into probability, yield, profit, water savings or an
invented continuous score.

The point samples one original coarse cell, without interpolation. It does not
assess every hectare inside a farm boundary.

GAEZ's 2001–2020 AgERA5 context remains distinct from NASA POWER's 2019–2025
history. No weather-based numerical correction to GAEZ is invented.

Soil inputs retain their source/depth/unit and available measurement dates,
proxy offsets and provenance. Individual laboratory sample coordinates are
not recorded by the existing app; the farmer's location is not falsely
substituted for verified sample coordinates. Laboratory-confirmed is still a
farmer claim, not independent verification. FAO's embedded soil assumptions
are not treated as another independent soil test.

ECOCROP is identified as historical/discontinued around 2015, with the official
FAO status reference. No current local-trial coverage is claimed.

## 7. Agricultural planning and UI

The adapter retains the current rotation plus two Phase 3 alternatives. It adds
published class explanations to supported candidates and review flags to
scenarios with marginal/not-suitable rain-fed comparator classes. It does not
replace option ordering, create a numeric crop rank or instruct a farmer to
abandon rice.

Existing priorities, oldest-first structured crop history, reference requirements,
water budgets, crop families and soil screening still drive Phase 3. Generic
profile history is not silently parsed. GAEZ classes alone never establish
soil-health improvement, pest control or rotation water savings.

The new `gaez-evidence.tsx` provides:

- Live explicit crop/scenario selection and exact source lookup.
- Loading/error/unsupported/NoData handling, without demo-value fallbacks.
- Categorical results, class definitions and reproducible per-result provenance.
- An immutable seven-crop/four-scenario saved-report comparison.
- Separate FAO/NASA/soil/farmer/guidance labels and limitations.
- Responsive stacked comparisons on mobile.

Phase 5 readiness/refusal diagnostics remain separate and disabled. The legacy
planner sentence incorrectly saying no model had ever been trained was corrected:
research candidates failed validation, and no accepted model is running.

## 8. Executed tests and browser evidence

| Check | Actual result |
|---|---|
| Full Python discovery suite | **179 passed, zero failures/errors** |
| GAEZ tests within that suite | **26** |
| Real location/crop/scenario extractions | **140 matched repeat extraction** |
| Authentic source mask | Actual NoData pixel correctly refused |
| Workspace TypeScript checks | Passed |
| Final Field Shift TypeScript check | Passed |
| Existing frontend retry tests | **3 passed** |
| OpenAPI code generation and library types | Passed |
| Original Phase 3 engine, Phase 4 code, dependency/deployment diff | Unchanged |

Tests cover catalog/crop/scenario semantics, masks, invalid coordinates,
cross-CRS extraction, bounds, unknown classes, unsupported periods/crops,
missing/corrupt cache, local cache reuse, owner isolation, source-period
separation, soil provenance, irrigation cautions and preservation of rules.

The initial regression pass caught an adapter assumption about the existing
alias function's return type, which was corrected. Test-only fixtures were also
aligned with the existing planner signature and irrigation representation.
The final full suite above includes those corrections.

### Browser journey

The real browser created synthetic farm **138**, `GAEZ Arkansas Test VXGLJ`,
at Stuttgart: 15 ha, Rice, limited irrigation, conserve-water priority, previous
crops entered as Soybean then Rice. Soil and seasonal water quantities remained
unknown.

Verified: rice not preselected ambiguously; RCW/LRLM and RCW/LILM each returned
actual class 2; source asset IDs and official links; saved report **58** with
28 genuine class results; three rotation scenarios; separate FAO/NASA periods;
reload persistence; unsupported crop returning null; and a clean second
workspace denied access with 404. The server log independently recorded 201
for the original report creation. No page JavaScript errors or console
warnings/errors occurred in the initial journey.

The first browser pass found that the live LILM result lacked a farmer-specific
limited-water caution, despite the saved report containing it. This was fixed
for **both** irrigated scenarios and regression-tested. The focused follow-up
result is recorded in the completion note below.

There is no account-login flow in this app. Testing used the existing signed
anonymous browser workspace, not invented login credentials. Farm/report 138/58
belong to that testing workspace and are not public links.

## 9. Data preservation

Hash comparison found **zero original rows changed or missing**:

| Table | Original records preserved |
|---|---:|
| Farms | 5 |
| Environmental values | 107,394 |
| Environmental locations | 6 |
| Soil-property estimates | 4 |
| Saved reports | 3 |

The synthetic browser farm/report were added. Environmental cache records also
grew during concurrent development-preview use; those additions are not claimed
as FAO data or attributed to the browser test. Its Stuttgart NASA data were
already cached. No original records were removed or overwritten.

## 10. Remaining limitations and safe integration

- Seven verified crop types, four scenarios and 2001–2020 only; not universal
  validated crop/farm coverage. Other crops remain unsupported here.
- Coarse source cells; no farm-boundary aggregation, local calibration,
  current laboratory verification or next-season forecasting.
- Reference-based rotation advice still has limitations, including incomplete
  local planting calendars and crop-season water-balance information.
- No yield, profit, causal rotation benefit or ML confidence forecasts.
- No load/saturation benchmark or production-environment acceptance was run.
- Raster cache is currently operator-provisioned, regenerable development data
  under `generated-artifacts/gaez-evidence/`, excluded from Git and deployment.
  A reviewed production asset-provisioning/persistent-storage plan is required;
  a clean environment without the cache honestly returns unavailable.
- Validating a future ML model against the FAO data it learned from is not
  independent validation. Both lanes must remain distinguishable.

Integration plan: review this branch against its main base; inspect source
definitions and sampled evidence; reproduce acquisition/tests; retain the
existing database and apply no destructive migration; then perform an
explicitly approved normal merge. Do not reset main or deploy automatically.

| Readiness question | Answer |
|---|---|
| Implemented | Yes, for the verified subset |
| Tested with genuine FAO rasters | Yes |
| Integrated with current app architecture | Yes, on the isolated feature branch |
| Merged into main | **No — awaiting review** |
| Verified in browser | Yes — original journey and focused irrigation-warning/mobile correction verification |
| Approved for deployment | **No** |

### Completion note

The focused browser follow-up **passed** on the existing synthetic farm, without
new records or source mocking. RCW/LILM retained genuine class 2 and visibly
showed the farmer-specific limited-water warning. The obsolete claim that no
model had ever been trained was absent. At 402×874, the saved crop/scenario
cards were visually inspected and readable, with no horizontal page overflow.
Class-pill wrapping remains a minor cosmetic limitation.

No page JavaScript exceptions occurred. A brief Vite reconnection coincided
with the managed development-server restart, not a failing application request.
No deployment approval is implied by passing compilation, tests or this
development-browser check.

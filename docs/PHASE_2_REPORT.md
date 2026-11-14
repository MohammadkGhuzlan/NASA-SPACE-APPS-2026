# Field Shift — Phase 2 implementation report

## Data imported

The application was extended in place: React/TypeScript/Tailwind, FastAPI, PostgreSQL, Leaflet/OpenStreetMap and Recharts remain. Existing farms, geometry, drafts, session ownership, navigation and branding were retained.

| Original file, preserved in `data/imports/` | Source rows processed | Stored source rows | Stored parameter values | Validation |
|---|---:|---:|---:|---|
| `nasa_daily.csv` | 10,228 | 10,228 | 51,140 | Five parameters; no invalid or missing cells found |
| `nasa_monthly.csv` | 336 | 0 | 0 | All 336 checked against daily calculations; deliberately not stored as competing observations |
| `nasa_soil_moisture_daily.csv` | 10,228 | 10,228 | 20,456 | GWETTOP/GWETROOT only; empty SFMC/RZMC not interpreted as data |
| `soilgrids_0_5cm_aligned.csv` | 4 | 4 | 20 property values within four proxy records | Texture sums and ranges pass; Al Ain distance flagged |

**Uploaded NASA total: 71,596 daily parameter observations.** Each study point has 2,557 days from **2019-01-01 through 2025-12-31**, including leap days. Monthly summaries cover January 2019–December 2025. Soil proxies have no observation date in the input; they retain ingestion date, not an invented sampling date.

| Regional reference (not a validated farm center) | Latitude | Longitude | Soil proxy source offset |
|---|---:|---:|---:|
| Irbid, Jordan | 32.55696 | 35.84790 | 1.741 km |
| Al Ain, Abu Dhabi, UAE | 24.22490 | 55.74520 | 7.073 km |
| Colusa, California, USA | 39.21460 | -122.00940 | 0.395 km |
| Stuttgart, Arkansas, USA | 34.50040 | -91.55260 | 0.729 km |

The existing case-study selector was corrected to these exact uploaded reference coordinates.

## Validation and provenance

- Fixed-file, size-limited ZIP extraction; originals remain byte-for-byte unchanged. SHA-256 hashes and actual headers are retained in import reports.
- Checks cover expected files/columns, malformed rows, dates, coordinates, duplicate location-days, finite numeric values, missing/fill markers, ranges, classifications, units and immutable stored conflicts.
- Monthly means, precipitation totals, valid-day counts, month lengths and strictly `>35°C` hot-day counts are independently recomputed from daily observations. All 336 supplied rows agree within 0.0011 for means and 0.011 mm for rainfall.
- Repeated imports skip identical stored observations. Conflicting values are flagged, not overwritten. Monthly source rows are counted as validation-only skipped rows.
- Soil texture components total approximately 100%, pH and carbon pass physical screening, and original/sample positions and 0–5 cm depth are preserved.
- **Al Ain input inconsistency:** source offset 7.073 km versus coordinate-derived haversine distance approximately 6.451 km. Both retained, with a visible `distance_discrepancy` warning. An early import rejected that row; a subsequent audited run accepted it only as a flagged proxy. The earlier failed audit remains visible by design.
- **Climate metadata limitation:** daily climate CSV has no units/coordinates/retrieval date/time standard/source URL embedded. Coordinates come from the brief; units were checked against NASA's official AG parameter definitions on 2026-11-14. Reconstructed query URLs are marked as reconstructed. This does not independently authenticate the original download.
- Uploaded wetness preserves original NASA query URLs, UTC time standard and `NASA_POWER_WETNESS_FRACTION_NOT_SMAP` classification.
- Soil provider URL is a homepage reference because the original WCS query/retrieval date was not supplied. No missing metadata was fabricated.

## Database and migrations

Additive Alembic migration `0002` extends the existing database with:

- `environment_locations`: exact requested coordinates, study references and fetch state.
- `environment_values`: normalized parameter/date/value/unit/source/product/quality/provenance. Unique location/date/parameter/product key prevents duplicates; indexes support location/date queries.
- `soil_property_estimates`: original/sample positions, offset, depth, proxy classification, five unit-tagged properties and original metadata.
- `farmer_measurements`: farm-scoped variable/value/unit/depth/date/source/notes, retained separately from estimates.
- `ingestion_reports`: start/completion timestamps, status, per-file row counts, coverage, hashes, warnings and errors.

Existing tables and user records were not replaced. Startup updates source-registry metadata only; schema changes and dataset imports are not startup side effects. No production migration or publishing was performed.

## Implemented API

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/data/import` | Fixed-bundle import restricted to explicitly allowlisted operators; public sessions get 403 |
| GET | `/api/data/status` | Read-only ingestion audits and current row counts |
| GET | `/api/environment/summary` | Monthly/annual/seasonal climate, wetness, heat exposure, dry runs, anomalies and provenance |
| GET | `/api/environment/history` | Full unsampled daily records for a requested year |
| GET | `/api/environment/soil-wetness` | Modeled wetness history and classification |
| GET | `/api/environment/soil-properties` | Exact-reference soil proxy or explicit unavailable state |
| GET | `/api/environment/compare` | Four stored study regions, with real summary values |
| GET/POST | `/api/farms/{id}/measurements` | Owner-scoped measurements with dates, units, depths and self-reported source |
| GET | `/api/farms/{id}/features` | Consistent structured inference/training **inputs**, no labels or model |
| GET | `/api/sources` | Updated provenance registry |

Existing health, farm CRUD, case-study, geocoding and strategy routes remain. `/api/farms/{id}/environment` remains compatible using a daily-derived 2025 subset. FastAPI runtime documentation: `/api/docs`; frontend contract and clients were regenerated.

## Dashboard features

- Existing map retains worldwide search, manual coordinates, click selection and optional polygon geometry. “Explore environment” opens the selected coordinates before saving a farm.
- Monthly temperature means/highs/lows, precipitation totals, humidity, daily temperatures and extremes, annual comparisons and calendar-season profiles.
- Configurable heat and dry-day thresholds, strict `>30°C` / `>35°C` counts, observed longest dry runs and annual/monthly/seasonal historical comparisons.
- Rainfall and wetness departures from the available complete 2019–2025 reference periods, with reference counts available in API output.
- Surface/root-zone modeled wetness, monthly/seasonal comparisons and rainfall-versus-wetness displays. Units remain dimensionless fractions.
- Soil composition, pH, organic carbon, depth, original/sample coordinates, both distances where discrepant, source classification and required limitations notice.
- Farmer-measurement entry and history, self-reported laboratory distinction, saved values retained after reload, and a visible source-per-input panel.
- Optional profile fields preserve available water resources and agricultural constraints separately from water constraints.
- Regional comparison for four real study locations.
- Responsive charts/tooltips, dates/units, independent loading/error/retry states, null gaps, provenance and source audit.

## New-location NASA API

All requests run on the backend using NASA POWER's AG daily service. Climate and wetness are requested independently, so one product group can remain usable if the other fails. Live response units, fill values, parameter presence, dates and physical ranges are checked; original URLs, response metadata, requested coordinates, returned geometry and retrieval dates are stored.

Timeouts and transient failures have bounded retries. HTTP 422 is reported without switching products. TLS verification is not disabled. Per-process request limits and cross-worker same-point locks prevent excessive duplicate downloads; cached reads are concurrent.

**Real upstream check:** Paris **48.8566, 2.3522** was newly requested and returned all seven parameters for all 2,557 days: **17,899 additional real values**. At this check, total environmental storage was **89,495 values**, including that live verification point. Paris correctly has no SoilGrids proxy. No nearest-city measurements were substituted.

Caching uses exact requested coordinates to five decimal places rather than unverified spatial grid boundaries. This safely avoids cross-city reuse but is deliberately less efficient than a verified grid-cell cache.

## Automated and browser verification

- **52 automated Python tests passed**: parser/header/date/range/fill checks, unchanged ZIP extraction, missing data, monthly/annual totals and means, leap years, strict hot-day counts, dry-run resets, anomalies, source classification, soil ranges/texture, measurement units/depth, NASA response parsing, HTTP 422, bounded timeout/server retries, cached/new points, immutable conflicts, duplicate/repeated imports, ownership and matching-depth/unit input precedence.
- Database integration tests run inside rolled-back transactions and do not delete user records or touch production.
- A real NASA live new-location download succeeded separately from mocked failure tests.
- Browser journey verified exact map coordinates, actual chart/table values against API aggregates, farm creation, measurement save/reload, preservation of original proxy pH, invalid moisture blocking, four-region comparison, missing-soil state for Paris, and read-only import audit.
- Browser verification found concurrent cached requests could initially return 409; cached reads were corrected to bypass exclusive fetch locks and the same browser pass confirmed successful 200 responses afterward.
- Browser mobile check found the source audit overflowed on long hashes. Text wrapping and width constraints were corrected; a focused browser recheck confirmed document width equals the 390 px viewport, with no horizontal page overflow.
- TypeScript and Python static/build checks are included in the final verification.
- The Vite production build passes with the managed service's required `PORT`/`BASE_PATH` supplied. It emits non-blocking warnings about a UI-library sourcemap and a JavaScript chunk larger than 500 kB; bundle splitting remains a performance improvement, not a blocked workflow.

## Fully working, partial and deliberately absent

**Working:** validated import/reimport and audit, daily storage, daily-derived analyses, live global POWER retrieval/cache, dashboard/explorer/comparisons, measurement persistence and source-aware feature inputs, previous farm/map/planner workflows.

**Partial by data availability:** soil proxies exist only for the four exact reference coordinates; source climate metadata/time standard and original download dates are incomplete; uploaded climate/wetness daily alignment cannot be independently verified. POWER is coarse grid context, not parcel measurement. Seven years is not a 30-year climate normal. SoilGrids uncertainty bounds were not supplied and are not invented.

**Deliberately not implemented in Phase 2:** SMAP, MODIS, field-level satellite imagery, independent laboratory verification, account-based admin authentication, crop suitability labels, recommendations, yields, irrigation prescriptions, trained ML or AI explanations. Proxy observations are not ground-truth training labels. The input feature builder returns missing values and provenance; model status is `not_trained`, with labels `null`.

Anonymous signed-cookie ownership remains from Phase 1: clearing cookies loses access to that browser's farms. Public imports remain forbidden; the operator CLI is functional. Production publishing/data seeding and independent scientific/security review remain outside this implementation.

# Field Shift

**Evidence-aware crop-rotation planning with NASA POWER historical climate data**  
**Team:** ASTRA PETRA · **NASA Space Apps Challenge 2026**

**Try the application:** [Field Shift on Replit](https://99c0b8d5-1681-405c-9948-7d284359ce38-00-txmcsy55jxy8.pike.replit.dev/)  
**Source code:** [NASA-SPACE-APPS-2026 on GitHub](https://github.com/MohammadkGhuzlan/NASA-SPACE-APPS-2026)

> **Availability:** The Replit address above is a development/preview URL, not a verified permanent published deployment. Its availability can depend on the Replit project running. The GitHub repository is the more durable public project link.
>
> **Scope:** Field Shift is an independent educational prototype. It is **not endorsed by NASA**, is **not professional agronomic advice**, and does **not** provide validated ML crop-suitability predictions, field-specific yields or profit forecasts.

## What is Field Shift?

Farmers making crop-rotation decisions must interpret environmental history, soil observations and crop-specific requirements. Those inputs often come from separate tools, with different quality and geographic resolution. Field Shift brings this evidence into a single application so users can profile a farm, review historical climate context, draft rotation alternatives and request transparent, **conditional, reference-based** reports.

Field Shift's contribution is **traceability rather than unsupported certainty**: environmental estimates, farmer-entered information and published agronomic reference ranges are kept distinguishable. Screening flags are review points, not a prediction that a crop will succeed.

## Application features

| Module | Available behavior | Important boundary |
| --- | --- | --- |
| Farm profiles | Worldwide place search, map point selection, optional polygon boundary, manual coordinates, questionnaire, editing and persistence within the current anonymous browser session | Browser-session ownership is not an account system; polygons do not turn NASA POWER data into parcel-level measurements |
| Historical climate | On-demand NASA POWER daily historical retrieval for selected coordinates, caching, source metadata and 2019–2025 summaries | Gridded historical estimates; **not** real-time field sensors, weather forecasts or a 30-year normal |
| Environmental dashboards | Annual/monthly/seasonal temperature, rainfall, humidity and modeled wetness; dry-spell and heat-threshold context; cross-location comparison where data exist | Incomplete data remain missing, not silently replaced with zero |
| Farmer measurements | Farmer-entered measurements with dates, units, source descriptions and depths | Any “laboratory confirmed” statement is user reported, not independently verified |
| Rotation bench | Records the current crop/rotation and supports two persistent farmer-authored alternative drafts | Drafts are **not** scored or assessed recommendations |
| Reference library | Selected FAO ECOCROP plant reference ranges, FAO crop-water references where available and USDA NRCS conservation standards | Source ranges are general estimates, not field-specific tests |
| Conditional planning | Rule-based reference comparisons when required crop and water evidence are available; flags possible temperature, soil-pH and water conflicts; saves reports on request | No statistically validated ranking, precise local planting-window or crop-stage water balance |
| Provenance and import | Source registry, repeatable vetted CSV ingestion, SHA-256 tracking, audit records and versioned references | Imports are restricted; original CSV metadata can be incomplete |

The documented reference library includes **13 selected species** from an attributed ECOCROP export. A smaller set of six crop definitions is noted in the Phase 3 scope; these are not ML training labels. The application uses two separate farmer drafts, with any generated scenarios presented as conditional explorations rather than a farm-specific recommendation.

Some earlier application exports show a separate **experimental ML** surface with failed-validation or unavailable status. That surface is not an accepted model and is not used by the reference-based reports. The supplied project README documents **no operational trained ML model**. No site functionality should be described as delivering validated AI predictions without newer reproducible evidence.

## Typical user journey

1. **Select a place** using map search, a coordinate, or a geographic starting location; optionally draw a field outline.
2. **Create a farm profile** with crop history, irrigation context, planning priority and available soil information.
3. **Explore historical environment** from NASA POWER for the selected point, with the source and resolution warnings visible.
4. **Draft rotation alternatives** beside the farmer-reported rotation.
5. **Open the reference library and request a report** to see conditional scenarios, flags, supporting references and relevant evidence gaps.
6. **Revisit saved drafts and reports** from the same signed anonymous browser session.

## NASA data and scientific interpretation

Field Shift uses [NASA POWER](https://power.larc.nasa.gov/) agroclimatology historical data at point coordinates, including:

| POWER variable | Meaning in this project |
| --- | --- |
| `T2M` | Daily near-surface air temperature |
| `T2M_MAX` / `T2M_MIN` | Daily maximum/minimum air temperatures |
| `PRECTOTCORR` | Daily corrected precipitation |
| `RH2M` | Daily relative humidity |
| `GWETTOP` | Modeled wetness fraction for the upper soil layer (approximately 5 cm) |
| `GWETROOT` | Modeled root-zone wetness fraction (generally around 1 m) |

The documented historical period is **2019–2025**, or seven calendar years. The app calculates monthly means and precipitation totals from daily values, annual means weighted by actual day counts, heat-exposure counts and dry-spell statistics. Rainfall and wetness anomalies use complete matching reference periods within those seven years. A missing daily value invalidates the associated complete-period aggregate rather than being treated as zero.

**Important interpretation notes:**

- NASA POWER provides **gridded environmental estimates**, not measurements taken at the farm; adjacent point requests are not assumed to share the same authoritative cell.
- `GWETTOP` and `GWETROOT` are **dimensionless modeled wetness fractions**. They are **not** NASA SMAP retrievals and **not** farmer-measured volumetric soil moisture.
- Farm polygons are stored for context, but there is no field-boundary-averaged imagery or soil-water sensing.
- The 2019–2025 period is not a standard 30-year climate normal, and heat thresholds are not crop-specific damage estimates.
- The imported climate CSVs did not include all original retrieval times, provenance URLs, units or time standards. Unit mappings were checked against official NASA parameters, but this cannot retroactively prove full original-file provenance; reconstructed URLs are labeled accordingly.

NASA POWER documentation: [Home](https://power.larc.nasa.gov/) · [API documentation](https://power.larc.nasa.gov/docs/services/api/)

## Agricultural and mapping references

- **[FAO ECOCROP](https://www.fao.org/land-water/resources/tools/databases/ecocrop/en)** — attributed reference ranges and characteristics for crop screening. ECOCROP facts are expert estimates, not observed farm measurements.
- **[FAO Land & Water](https://www.fao.org/land-water/en/)** — agricultural water-requirement references where included in the curated source library.
- **[USDA NRCS Conservation Crop Rotation (328)](https://www.nrcs.usda.gov/resources/guides-and-instructions/conservation-crop-rotation-ac-328-conservation-practice-standard)** — general conservation rotation guidance.
- **[USDA NRCS Cover Crop (340)](https://www.nrcs.usda.gov/resources/guides-and-instructions/cover-crop-ac-340-conservation-practice-standard)** — cover-crop practice guidance.
- **[FAO GAEZ](https://www.fao.org/gaez/en)** — some previously exported app screens display published GAEZ suitability classes as *separately cited external evidence*. These are **not** training labels imported for Field Shift ML or model-generated local suitability predictions.
- **[ISRIC SoilGrids](https://soilgrids.org/)** — the documented set of four nearby 0–5 cm estimates is explicitly flagged `PROXY_DEMO_ONLY`; it is not independently confirmed farm soil data.
- **[OpenStreetMap](https://www.openstreetmap.org/copyright) / [Nominatim](https://nominatim.org/release-docs/latest/api/Overview/)** — map tiles and user-triggered place search; subject to provider usage policies.

This list reflects the attached README and previously exported project screens. Check the repository's `docs/` source registry for the exact versions and source URLs before asserting additional datasets. **SMAP and MODIS are not integrated data feeds in the documented implementation.**

## Architecture

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Tailwind CSS, Vite, Recharts |
| Map / search | Leaflet, OpenStreetMap and Nominatim |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Uvicorn |
| Storage | PostgreSQL, Alembic schema migrations |
| API contract | OpenAPI, generated TypeScript clients and React Query hooks |
| Hosting / development | Replit workflows and publishing |

The Replit artifact retains a small Node launcher for compatibility with its existing run commands, but **FastAPI handles application REST requests**; scaffolded Express endpoints are unused.

### Repository layout

```text
artifacts/
  field-shift/src/          # Frontend UI, maps, forms and charts
  api-server/
    backend/               # FastAPI, data validation and domain services
      environment/         # NASA POWER, imports, aggregates, provenance
      recommendation/      # Curated sources and conditional planning rules
      machine_learning/    # Reserved / experimental integration area
    migrations/            # Alembic history
lib/
  api-spec/openapi.yaml    # Frontend/backend API contract
  api-client-react/        # Generated React Query clients
data/imports/              # Vetted original climate files, where present
docs/                      # Scope and provenance reports
```

## Run locally in Replit

**Requirements:** the tracked Node and Python dependencies, a **development** PostgreSQL database and the Replit workflow configuration.

Set these server-side secrets in the Replit Secrets panel or an equivalent secure environment:

- `DATABASE_URL` — development PostgreSQL connection string
- `SESSION_SECRET` — strong signing secret for anonymous browser sessions

**Never commit secret values to Git.**

```bash
pnpm install
uv sync

# DEVELOPMENT DATABASE ONLY — do not execute against production automatically
uv run alembic -c artifacts/api-server/alembic.ini upgrade head

pnpm --filter @workspace/api-spec run codegen
```

Start the existing **API Server** and **Field Shift web** Replit workflows. They set the expected `PORT` and `BASE_PATH`; do not start duplicate servers on those ports.

API documentation is served at `/api/docs` on the running backend.

For managed production PostgreSQL, Replit publishing handles schema changes via its development-to-production schema diff. Do **not** add Alembic to the production startup or build hook. Starting the backend creates only missing source-registry reference rows, never farm observations, recommendations or ML models.

### Optional vetted data ingestion

```bash
# Use a migrated DEVELOPMENT database, not the production database
PYTHONPATH=artifacts/api-server uv run python -m backend.environment.importer

# Optional operator-selected bundle; still subject to the four-file whitelist
PYTHONPATH=artifacts/api-server uv run python -m backend.environment.importer --zip path/to/bundle.zip
```

The importer preserves original files, records SHA-256 digests and audits reruns. Identical observations are skipped; conflicts are reported without overwriting existing values. Monthly CSV inputs serve cross-checks rather than creating competing measurements. Moving to a new database requires an explicit import; migrations alone do not copy climate observations.

The `POST /api/data/import` route is disabled for ordinary browser sessions. If operators explicitly configure `FIELD_SHIFT_IMPORT_OPERATORS`, it allowlists trusted anonymous owner identifiers **without becoming a substitute for account authentication**. Prefer the CLI for imports.

### Relevant API routes

```text
/api/environment/summary
/api/environment/history
/api/environment/soil-wetness
/api/environment/soil-properties
/api/environment/compare
/api/data/status
/api/farms/{id}/measurements     GET / POST
/api/farms/{id}/features
/api/farms/{id}/environment      legacy daily-derived 2025 view
/api/docs                         interactive API docs
```

## Validation and testing

```bash
pnpm run typecheck
PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -v
uv run python -m compileall -q artifacts/api-server/backend artifacts/api-server/migrations
```

Tests require the migrated development database and vetted study data bundle. Integration tests use isolated rollback transactions; simulated NASA failure cases use mocked upstream responses. Refer to [`docs/PHASE_2_REPORT.md`](docs/PHASE_2_REPORT.md) and [`docs/PHASE_3_REFERENCE_PLANNING.md`](docs/PHASE_3_REFERENCE_PLANNING.md) for audited scope and validation notes. Running these tests does **not** establish agronomic accuracy, multi-user security or production readiness.

## Privacy, trust and known limitations

1. **No conventional accounts.** A signed HTTP-only, same-site anonymous cookie scopes farm data to a browser session. Clearing cookies can lose access; different browsers cannot share a profile. Avoid storing sensitive farm data in demonstration profiles.
2. **Historical environmental context only.** No weather forecasting, field-scale soil sensing, SMAP retrieval or MODIS vegetation product is integrated in the documented build.
3. **Conditional agriculture rules only.** No accepted validated ML model, calibrated local crop suitability prediction, quantified soil-health impact, statistical crop rankings, yield forecasts or profitability estimates.
4. **No location-specific agronomic guarantees.** Reference ranges and generic crop-cycle estimates do not implement validated local planting windows, crop-stage water balances, interpretation of arbitrary free-text constraints, or verification of on-farm irrigation delivery.
5. **Data quality is explicit.** Farmer reports and the four SoilGrids `PROXY_DEMO_ONLY` samples are not verified lab measurements. Source/UTC alignment limits remain documented in import reports.
6. **Scale and upstream constraints.** NASA POWER retrievals are cached and rate-limited. OpenStreetMap/Nominatim require network access and must follow provider policies before higher-traffic use.

**Any agricultural use requires independent local verification by qualified experts.**

## Use of AI assistance / Super Intelligence disclosure

ChatGPT and Replit Agent assisted with **implementation planning, code-development support, documentation and presentation preparation**. The project must disclose any generated or AI-assisted code/data in its relevant repository descriptions and metadata according to the NASA Space Apps Challenge rules. These development tools should **not** be confused with a deployed, validated AI crop-prediction service; none is claimed here. The NASA Space Apps submission must separately declare the exact SI use that occurred and label any SI-generated visuals or audio as required.

## Project and acknowledgments

Created by **Team ASTRA PETRA** for the **NASA Space Apps Challenge 2026**. It is an independent participant project, not a NASA-authored or NASA-endorsed service. NASA POWER, FAO, USDA NRCS, ISRIC SoilGrids and OpenStreetMap contributors retain their respective data and content rights. Consult their linked license and use policies.

**Project preview:** https://99c0b8d5-1681-405c-9948-7d284359ce38-00-txmcsy55jxy8.pike.replit.dev/  
**GitHub:** https://github.com/MohammadkGhuzlan/NASA-SPACE-APPS-2026

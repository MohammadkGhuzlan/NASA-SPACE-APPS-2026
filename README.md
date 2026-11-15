# Field Shift

A functional foundation for worldwide farm profiling and evidence-aware crop rotation planning, created for the requested NASA Space Apps 2026 concept. This is an independent prototype, not a NASA-endorsed agronomic advisory service.

## Phase 3: evidence-based agricultural planning foundation

The **Reference library** (`/knowledge`) includes 13 selected species from a
pinned, attributed FAO ECOCROP export, FAO crop-water references where available,
and USDA NRCS rotation/cover-crop standards. Each farm's **Rotation planner**
compares the farmer-reported rotation with two rule-based alternatives when enough
reference crops and water evidence are available.

Plans use exact-location NASA POWER historical monthly temperature, rainfall and
modeled wetness as context; farmer-entered crop history, priority, soil pH,
irrigation category and seasonal water are retained with source limits. Screening
flags possible EcoCrop temperature/pH/water conflicts for review. It is not a crop
suitability prediction. Generic cycle ranges support hypothetical dates only;
local planting windows, crop-stage water balances and free-text constraint
interpretation are not implemented. EcoCrop facts are expert estimates, not farm
measurements. No model has been trained, no GAEZ labels are imported, and no yield,
profitability or similar-region prediction is produced.

See [Phase 3 scope, references and limitations](docs/PHASE_3_REFERENCE_PLANNING.md).

## Stack

- React / TypeScript / Tailwind / Vite
- Python FastAPI / Pydantic / SQLAlchemy
- PostgreSQL and Alembic migrations
- Leaflet / OpenStreetMap and Recharts
- OpenAPI-generated TypeScript clients

The provided API artifact retains a tiny Node launcher so Replit's existing build/run commands remain valid. It launches Python Uvicorn; FastAPI handles all application REST requests. The scaffolded Express modules are unused.

## Run in Replit

Dependencies are tracked by `pnpm-lock.yaml`, `pyproject.toml`, and `uv.lock`. Required server environment variables: `DATABASE_URL` and `SESSION_SECRET`; never put their values in source code.

```sh
pnpm install
uv sync
# Apply migrations to the DEVELOPMENT database only:
uv run alembic -c artifacts/api-server/alembic.ini upgrade head
pnpm --filter @workspace/api-spec run codegen
```

Start the configured API Server and Field Shift web workflows in Replit. They supply `PORT` and `BASE_PATH`. Do not run a second server on those ports. API docs: `/api/docs`.

For managed production PostgreSQL, Replit Publish applies the development-to-production schema diff. Do not run Alembic as a production startup/build hook. The server idempotently inserts missing source-registry reference rows at startup (data only, no schema changes). It never seeds observations, profiles, recommendations or models.

## Project structure

- `artifacts/field-shift/src/`: user-facing pages, map, forms and visualizations
- `artifacts/api-server/backend/`: FastAPI routes, validation and database models
- `backend/environment/`: validated CSV ingestion, NASA POWER, aggregates, provenance and feature inputs
- `backend/recommendation/`: versioned reference library and deterministic conditional planning engine
- `backend/machine_learning/`: reserved future model integration
- `artifacts/api-server/migrations/`: Alembic schema history
- `lib/api-spec/openapi.yaml`: frontend API contract; regenerate after changes
- `lib/api-client-react/`: generated React Query hooks

## Implemented

Worldwide place search, interactive point/optional polygon selection, four geographic starting locations, manual coordinates, farm questionnaire, persistent browser-session-scoped profiles and edits, provenance registry, on-demand real NASA POWER climate retrieval with caching, and two persistent farmer-authored rotation drafts.

Soil moisture input uses volumetric water content (%); farm area uses hectares; soil pH is dimensionless. Coordinates and optional profile values are validated server-side.

## Data interpretation

NASA POWER daily `T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `GWETTOP` and `GWETROOT` cover 2019–2025. Monthly temperature/humidity/wetness are daily means; monthly rainfall sums daily precipitation. A missing day makes that aggregate null, never zero or invented. Annual means are day-weighted, including leap days. Heat exposure counts daily maximum temperature **strictly above** 30°C, 35°C or a configurable threshold, and is null for incomplete years. It is **not** crop-specific heat risk.

POWER is a gridded meteorological product, not a field sensor or parcel-level satellite reading. Imported historical points are immutable; live historical successes cache for 30 days and partial/failed requests back off for three minutes. Requests are server-side, TLS-verified, limited to two attempts per product group, two concurrent new-point downloads and twelve new-point requests per minute per process. PostgreSQL advisory locks coordinate same-point downloads across workers. No keys are needed for the public NASA endpoint.

`GWETTOP` (upper 5 cm) and `GWETROOT` (generally upper 1 m) are dimensionless modeled wetness fractions, **not SMAP or volumetric moisture**. SoilGrids estimates are four nearby `PROXY_DEMO_ONLY` records at 0–5 cm, never training labels or verified farm soil tests. Al Ain's supplied distance (7.073 km) differs from coordinate-derived distance (~6.451 km); both are preserved and flagged.

Point caching is deliberately conservative: coordinates rounded to five decimals, not nearest-city matching. The API's point geometry is not assumed to establish authoritative grid-cell boundaries. Different points—even nearby ones—are fetched separately rather than risking a wrong grid match. Field polygons are retained, but POWER is point/grid context, not polygon-averaged imagery.

The uploaded climate CSV lacks embedded units, time standard, source URLs and original retrieval dates. Unit mappings were checked against NASA's official AG parameter metadata; this does not independently prove the original file's download provenance. Reconstructed query URLs are explicitly marked. Uploaded wetness specifies UTC; climate/wetness daily alignment remains uncertain. An import timestamp is not an original NASA download date.

## Phase 2 data import

The four original CSVs are preserved byte-for-byte in `data/imports/`; their SHA-256 hashes are recorded in ingestion reports. The importer automatically extracts the fixed uploaded ZIP, validates each file and retains every audit run. It does not accept arbitrary public file paths or uploads.

```sh
PYTHONPATH=artifacts/api-server uv run python -m backend.environment.importer
# Optional operator-selected ZIP, still subject to the four-file whitelist:
PYTHONPATH=artifacts/api-server uv run python -m backend.environment.importer --zip path/to/bundle.zip
```

Reruns skip identical observations and report conflicts without overwriting them. Monthly CSV rows are cross-validation inputs, not a second competing set of measurements. Importing into a new database is an explicit operator step; deployment schema migration does **not** copy development observations.

`POST /api/data/import` is disabled for ordinary browser sessions. An operator can explicitly allowlist trusted anonymous owner IDs with the server configuration `FIELD_SHIFT_IMPORT_OPERATORS`. No public “become admin” route or import button exists. Prefer the server CLI; this allowlist is not a replacement for real account-based administrator authentication.

Data routes: `/api/environment/{summary,history,soil-wetness,soil-properties,compare}`, `/api/data/status`, `/api/farms/{id}/measurements` (GET/POST), `/api/farms/{id}/features`. The legacy `/api/farms/{id}/environment` response remains supported with a daily-derived 2025 view.

Farmer measurements retain dates, depths, original units, values and self-reported sources. “Laboratory confirmed” is a farmer assertion, not independently verified by this app. Input features prefer the latest recorded value only for matching parameter, units and exact 0–5 cm depth; estimated data remain untouched. Other depths/units and legacy profile inputs remain separate.

**Statistics:** rainfall/wetness anomalies use complete matching calendar periods within 2019–2025, including the current year; reference-year counts accompany anomalies. This is a seven-year reference, not a 30-year normal. Dry spells count observed consecutive days below a configurable precipitation threshold, with gaps breaking runs. Seasons are DJF/MAM/JJA/SON; DJF groups Jan/Feb/Dec of the **same calendar year**, not a cross-year winter or local crop season.

OpenStreetMap tiles and Nominatim require network availability. Nominatim requests are user-driven, cached and upstream-rate-limited to one per second. No systematic geocoding or autocomplete should be added. Respect provider terms before higher-traffic deployment.

## Deliberate placeholders

No SMAP moisture or MODIS vegetation products are connected. Six crop definitions and versioned reference facts are now curated from the sources listed above; they are not farm observations or training labels. Reference-based reports are saved only on user request. Local crop suitability, quantified soil-health impact, statistical crop rankings, ML predictions and AI explanations are **not implemented**. Manual rotation alternatives remain unassessed farmer drafts; generated scenarios are explicitly conditional reference explorations. No model has been trained or claimed operational.

## Privacy and scope

No account system was requested. Profiles are scoped to a signed, HTTP-only, same-site anonymous browser cookie. Clearing cookies loses access; another browser does not share the workspace. This is not account authentication. Add an approved identity provider before multi-device or production farm-data use. Never store personal or sensitive farm information in public demonstration profiles.

## Checks

```sh
pnpm run typecheck
PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -v
uv run python -m compileall -q artifacts/api-server/backend artifacts/api-server/migrations
```

The tests require the migrated development schema and imported study bundle. Database integration tests use rollback-isolated transactions, never delete user data, and do not contact production. NASA failure tests use mocked responses; the delivery report separately identifies real upstream checks. See `docs/PHASE_2_REPORT.md` for counts, verification and limitations. These checks do not establish agronomic validity or production security.

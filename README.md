# Field Shift

A functional foundation for worldwide farm profiling and evidence-aware crop rotation planning, created for the requested NASA Space Apps 2026 concept. This is an independent prototype, not a NASA-endorsed agronomic advisory service.

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
- `backend/data_ingestion/`: NASA POWER client and complete-month aggregation
- `backend/recommendation/`: reserved verified rules engine
- `backend/machine_learning/`: reserved future model integration
- `artifacts/api-server/migrations/`: Alembic schema history
- `lib/api-spec/openapi.yaml`: frontend API contract; regenerate after changes
- `lib/api-client-react/`: generated React Query hooks

## Implemented

Worldwide place search, interactive point/optional polygon selection, four geographic starting locations, manual coordinates, farm questionnaire, persistent browser-session-scoped profiles and edits, provenance registry, on-demand real NASA POWER climate retrieval with caching, and two persistent farmer-authored rotation drafts.

Soil moisture input uses volumetric water content (%); farm area uses hectares; soil pH is dimensionless. Coordinates and optional profile values are validated server-side.

## Data interpretation

NASA POWER daily `T2M`, `T2M_MAX` and `PRECTOTCORR` are retrieved for calendar year 2025. Monthly temperature is a daily mean; monthly rainfall sums mm/day over complete months. A missing day makes that monthly metric null, never zero or invented. Heat exposure is the number of days with maximum temperature ≥35°C, and is null for incomplete years. It is **not** crop-specific heat risk.

POWER is a gridded meteorological product incorporating satellite/model information, not a field sensor or parcel-level satellite reading. Successful retrieval is cached seven days; failed retrieval two minutes. Network outages show explicit unavailable states. No keys are needed for this public endpoint.

OpenStreetMap tiles and Nominatim require network availability. Nominatim requests are user-driven, cached and upstream-rate-limited to one per second. No systematic geocoding or autocomplete should be added. Respect provider terms before higher-traffic deployment.

## Deliberate placeholders

No SMAP moisture or MODIS vegetation products are connected. Crop definitions/verified requirements, model versions and recommendation results have database models but no invented seed values. Water suitability, soil health impact, crop-specific environmental risks, rules-based rankings, ML predictions and AI explanations are **not implemented**. Rotation alternatives are user drafts, not agricultural advice. No model has been trained or claimed operational.

## Privacy and scope

No account system was requested. Profiles are scoped to a signed, HTTP-only, same-site anonymous browser cookie. Clearing cookies loses access; another browser does not share the workspace. This is not account authentication. Add an approved identity provider before multi-device or production farm-data use. Never store personal or sensitive farm information in public demonstration profiles.

## Checks

`pnpm run typecheck` checks TypeScript. `uv run python -m compileall artifacts/api-server/backend` checks Python syntax. These are not a substitute for end-to-end, security and agronomic validation before real-world use.

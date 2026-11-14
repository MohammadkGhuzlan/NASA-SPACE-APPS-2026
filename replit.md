# Field Shift

Worldwide farm profiling and evidence-aware crop rotation planning. See README.md for setup, scope, data limitations, and privacy.

## Run & Operate

- Use the managed API and web workflows; they inject each service's port and base path.
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `uv run alembic -c artifacts/api-server/alembic.ini upgrade head` — apply development migrations
- `PYTHONPATH=artifacts/api-server uv run python -m backend.environment.importer` — validate/import the fixed historical bundle
- `PYTHONPATH=artifacts/api-server uv run python -m unittest discover -s artifacts/api-server/tests -v` — run rollback-isolated environmental tests
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Python FastAPI, launched through the managed Node service bootstrap
- DB: PostgreSQL + SQLAlchemy, Alembic migrations
- Validation: Python Pydantic on the server, OpenAPI-generated types in the client
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

See README.md for the project map. SQLAlchemy models and Alembic history own schema; do not use the unused Drizzle scaffold to push an empty schema.

## Architecture decisions

_Populate as you build — non-obvious choices a reader couldn't infer from the code (3-5 bullets)._

## Product

_Describe the high-level user-facing capabilities of this app once they exist._

## User preferences

Never invent NASA measurements, crop recommendations or suitability percentages. No model training at this stage. Missing observations must be explicit, not fabricated.

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details

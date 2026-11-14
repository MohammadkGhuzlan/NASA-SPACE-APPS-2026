#!/bin/bash
set -e
pnpm install --frozen-lockfile
uv sync --frozen
uv run alembic -c artifacts/api-server/alembic.ini upgrade head

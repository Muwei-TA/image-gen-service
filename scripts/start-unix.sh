#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

uv sync --extra dev
(cd frontend && npm ci && npm run build)

export IMAGE_GEN_SERVICE_ROOT="$PROJECT_ROOT"
export IMAGE_GEN_DATA_DIR="${IMAGE_GEN_DATA_DIR:-$PROJECT_ROOT/data}"
export IMAGE_GEN_DEFAULT_WORKDIR="${IMAGE_GEN_DEFAULT_WORKDIR:-$PROJECT_ROOT}"
export IMAGE_GEN_FRONTEND_DIST_DIR="$PROJECT_ROOT/frontend/dist"

exec uv run image-gen-service

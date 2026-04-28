#!/usr/bin/env sh
set -eu

APP_USER="${APP_USER:-imagegen}"
APP_GROUP="${APP_GROUP:-imagegen}"

mkdir -p \
  "${IMAGE_GEN_DATA_DIR:-/data/image-gen-service}/jobs" \
  "${IMAGE_GEN_DATA_DIR:-/data/image-gen-service}/uploads" \
  "${IMAGE_GEN_DEFAULT_WORKDIR:-/workspace}" \
  "${IMAGE_GEN_CODEX_HOME:-/data/codex-home}"

if [ ! -f "${IMAGE_GEN_DATA_DIR:-/data/image-gen-service}/state.json" ]; then
  printf '{"batches": {}, "jobs": {}, "uploads": {}}\n' > "${IMAGE_GEN_DATA_DIR:-/data/image-gen-service}/state.json"
fi

if [ "$(id -u)" = "0" ]; then
  chown -R "${APP_USER}:${APP_GROUP}" \
    "${IMAGE_GEN_DATA_DIR:-/data/image-gen-service}" \
    "${IMAGE_GEN_DEFAULT_WORKDIR:-/workspace}" \
    "${IMAGE_GEN_CODEX_HOME:-/data/codex-home}" \
    "${IMAGE_GEN_CODEX_USER_HOME:-/home/imagegen}"
  exec gosu "${APP_USER}:${APP_GROUP}" "$@"
fi

exec "$@"

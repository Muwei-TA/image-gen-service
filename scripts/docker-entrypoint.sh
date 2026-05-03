#!/usr/bin/env sh
set -eu

APP_USER="${APP_USER:-imagegen}"
APP_GROUP="${APP_GROUP:-imagegen}"
DATA_DIR="${IMAGE_GEN_DATA_DIR:-/data/image-gen-service}"
WORKDIR_PATH="${IMAGE_GEN_DEFAULT_WORKDIR:-/workspace}"
CODEX_HOME_PATH="${IMAGE_GEN_CODEX_HOME:-/data/codex-home}"
GENERATED_IMAGES_DIR="${IMAGE_GEN_GENERATED_IMAGES_DIR:-/data/codex-home/generated_images}"
CODEX_USER_HOME="${IMAGE_GEN_CODEX_USER_HOME:-/home/imagegen}"

mkdir -p \
  "${DATA_DIR}/jobs" \
  "${DATA_DIR}/uploads" \
  "${WORKDIR_PATH}" \
  "${CODEX_HOME_PATH}" \
  "${GENERATED_IMAGES_DIR}" \
  "${CODEX_USER_HOME}/.codex" || true

mkdir -p /root/.codex || true
if [ -d /root/.codex ] && [ ! -e /root/.codex/generated_images ]; then
  ln -sfn "${GENERATED_IMAGES_DIR}" /root/.codex/generated_images || true
fi
if [ ! -e "${CODEX_USER_HOME}/.codex/generated_images" ]; then
  ln -sfn "${GENERATED_IMAGES_DIR}" "${CODEX_USER_HOME}/.codex/generated_images"
fi

mkdir -p "${CODEX_USER_HOME}/.claude" || true
if [ -d "${CODEX_USER_HOME}/.claude" ] && [ ! -f "${CODEX_USER_HOME}/.claude/settings.json" ]; then
  printf '{"model": "gpt-5.4-mini"}\n' > "${CODEX_USER_HOME}/.claude/settings.json"
fi

if [ ! -f "${DATA_DIR}/state.json" ]; then
  printf '{"batches": {}, "jobs": {}, "uploads": {}}\n' > "${DATA_DIR}/state.json"
fi

# Force run as root and set umask
umask 000
exec "$@"

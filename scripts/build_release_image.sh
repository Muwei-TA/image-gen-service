#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-codex-image-studio:release}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_BIN="${CODEX_BIN:?Set CODEX_BIN to the Codex CLI executable path}"
CODEX_RUNTIME="${CODEX_RUNTIME:?Set CODEX_RUNTIME to the Codex runtime directory}"
RELEASE_CONTEXT="$PROJECT_DIR/release-context"

if [ ! -x "$CODEX_BIN" ]; then
  echo "Codex binary not found or not executable: $CODEX_BIN" >&2
  exit 1
fi

if [ ! -d "$CODEX_RUNTIME" ]; then
  echo "Codex runtime directory not found: $CODEX_RUNTIME" >&2
  exit 1
fi

rm -rf "$RELEASE_CONTEXT"
mkdir -p "$RELEASE_CONTEXT/codex-bin" "$RELEASE_CONTEXT/codex-runtime"
cp -a "$CODEX_RUNTIME"/. "$RELEASE_CONTEXT/codex-runtime/"
cat > "$RELEASE_CONTEXT/codex-bin/codex" <<'EOF'
#!/usr/bin/env sh
set -eu

runtime_dir="${CODEX_RUNTIME_DIR:-/opt/codex-runtime}"
for candidate in "$runtime_dir"/vendor/*/codex/codex "$runtime_dir"/codex; do
  if [ -x "$candidate" ]; then
    exec "$candidate" "$@"
  fi
done

echo "Codex runtime binary not found under CODEX_RUNTIME_DIR=$runtime_dir" >&2
exit 127
EOF
chmod +x "$RELEASE_CONTEXT/codex-bin/codex"

cp "$PROJECT_DIR/.dockerignore.release" "$PROJECT_DIR/.dockerignore"

docker build \
  -f "$PROJECT_DIR/Dockerfile.release" \
  -t "$IMAGE_NAME" \
  ${APP_HOME:+--build-arg APP_HOME="$APP_HOME"} \
  ${APP_DATA_DIR:+--build-arg APP_DATA_DIR="$APP_DATA_DIR"} \
  ${APP_WORKDIR:+--build-arg APP_WORKDIR="$APP_WORKDIR"} \
  ${CODEX_HOME:+--build-arg CODEX_HOME="$CODEX_HOME"} \
  ${CODEX_BIN_PATH:+--build-arg CODEX_BIN_PATH="$CODEX_BIN_PATH"} \
  ${CODEX_RUNTIME_DIR:+--build-arg CODEX_RUNTIME_DIR="$CODEX_RUNTIME_DIR"} \
  ${VITE_IMAGE_GEN_DEFAULT_WORKDIR:+--build-arg VITE_IMAGE_GEN_DEFAULT_WORKDIR="$VITE_IMAGE_GEN_DEFAULT_WORKDIR"} \
  "$PROJECT_DIR"

rm -rf "$RELEASE_CONTEXT"

echo "Built $IMAGE_NAME"
echo "This image intentionally excludes Codex auth files, task data, uploaded assets, and generated images."

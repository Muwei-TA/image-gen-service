# Agent Guide

Codex Image Studio is a Vue 3 + FastAPI application. Native Windows, macOS, and Linux execution is the default development path; Docker is optional.

## Safety boundaries

- Never print, copy, serve, or commit `auth.json`, `.codex`, API keys, login output containing credentials, uploads, logs, or generated images.
- The browser authentication API may expose only login state, the official verification URL, and a short-lived device code.
- Keep runtime data outside public images and source commits.
- Do not expose the service directly to the public internet without trusted access control.

## Native deployment

Prerequisites are Python 3.12+, uv, Node.js 20+, npm, and Codex CLI.

Windows:

```powershell
scripts\start-windows.ps1
```

macOS / Linux:

```bash
./scripts/start-unix.sh
```

The scripts install locked dependencies, build the Vue frontend, prepare runtime directories, and start FastAPI on port 8088. Windows development mode is available through `scripts\start-windows.ps1 -Dev`.

Do not instruct the user to copy Codex credentials. Ask them to open the UI, click the Codex login control, and complete the device authorization themselves.

## Verification

```bash
uv sync --extra dev
uv run pytest -q
cd frontend && npm ci && npm run lint && npm run build && cd ..
curl -fsS http://127.0.0.1:8088/health
```

Confirm that health and authentication responses contain only booleans and human-readable state. They must not contain credential file paths, access tokens, or refresh tokens.

The repository also contains a Streamable HTTP MCP adapter in `mcp/`. After backend changes, run its tests and verify `initialize` plus `tools/list` against a local backend.

## Docker

The standard `Dockerfile` builds the Vue frontend and installs the FastAPI application. `Dockerfile.release` is used by the release workflow that bundles a Codex binary. Persist data, workspace, Codex home, and generated images with mounted directories in production.

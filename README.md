# Image Gen Service

[中文文档](README.zh-CN.md) | [Agent guide](README_FOR_AGENT.md)

A local-first batch image generation workspace built with Vue 3 and FastAPI. It runs natively on Windows, macOS, and Linux, while Docker remains available as an optional deployment path.

## Highlights

- Vue 3 responsive workspace with prompt composition, reference uploads, queue, history, preview, and batch downloads.
- FastAPI backend with OpenAPI documentation at `/docs`.
- Browser-guided Codex device authentication. Credentials stay in the local Codex credential store and are never returned by the API.
- Direct cross-platform subprocess execution; no tmux or PTY dependency.
- Download every generated image as one ZIP, grouped by batch.
- Run up to 9 image-generation jobs concurrently; `IMAGE_GEN_MAX_CONCURRENCY` can lower the limit.
- Native launch scripts for Windows and Unix-like systems.
- Compatible Streamable HTTP MCP adapter in `mcp/`.

## Native quick start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+, and Codex CLI.

Windows:

```powershell
scripts\start-windows.ps1
```

Or double-click `scripts\start-windows.cmd`.

### Windows installer

GitHub Releases provide an x64 installer that bundles the Python runtime, built frontend, and official Codex CLI. It installs per-user without administrator privileges. Runtime data is stored under `%LOCALAPPDATA%\ImageGenService`, while Codex authentication remains in `%USERPROFILE%\.codex` and is never included in the installer.

The installer is currently unsigned, so Windows SmartScreen may show an unknown-publisher warning. Verify downloads with the included `SHA256SUMS.txt`.

macOS / Linux:

```bash
./scripts/start-unix.sh
```

Open `http://127.0.0.1:8088`, then use the Codex account card to sign in. The page displays a short-lived device code and opens the official authorization page; it never exposes the stored token.

For frontend/backend hot reload on Windows:

```powershell
scripts\start-windows.ps1 -Dev
```

The Vue dev server runs at `http://127.0.0.1:5173` and proxies API requests to FastAPI.

## Docker

Docker is optional. Build the refactored source locally before starting it:

```bash
docker build -t image-gen-service:local .
docker run --rm -p 8088:8088 image-gen-service:local
```

For production images that bundle a Codex binary, use the release build workflow and `Dockerfile.release`.

## Egress proxy

Set `IMAGE_GEN_PROXY_URL` to route Codex login, status checks, and image-generation processes through one outbound proxy. HTTP, HTTPS, SOCKS5, and SOCKS5H URLs are supported, including authenticated URLs. Use `IMAGE_GEN_NO_PROXY` for destinations that must stay direct.

```dotenv
IMAGE_GEN_PROXY_URL=http://user:password@proxy.example.com:7890
IMAGE_GEN_NO_PROXY=127.0.0.1,localhost,image-gen-service,image-gen-mcp
```

Docker Compose forwards both settings to the backend. Recreate the `image-gen` container after changing them. Health and auth responses expose only the proxy scheme, host, and port; credentials and the complete URL are never returned.

## Development

```bash
uv sync --extra dev
cd frontend && npm ci && npm run build && cd ..
uv run pytest -q
uv run uvicorn app.main:app --reload --port 8088
```

Useful endpoints:

- `GET /health`
- `GET /api/auth/status`
- `POST /api/auth/login/device`
- `GET /api/auth/login/device`
- `DELETE /api/auth/login/device`
- `POST /api/auth/logout`
- `GET /docs`

Runtime paths and limits can be configured with the `IMAGE_GEN_*` variables listed in `.env.example`.

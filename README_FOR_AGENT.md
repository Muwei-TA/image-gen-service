# Agent development guide

Use this runbook when changing or releasing Codex Image Studio. Read [AGENTS.md](AGENTS.md) first; deeper contracts live in [.context/CONTEXT.md](.context/CONTEXT.md), and unresolved risks are tracked in [.context/TODO.md](.context/TODO.md).

## Repository map

| Path | Responsibility |
| --- | --- |
| `app/` | FastAPI routes, settings, authentication, state, job orchestration, uploads, and result handling |
| `frontend/` | Vue 3 workspace, batch history, previews, uploads, and ZIP download controls |
| `mcp/` | Streamable HTTP MCP adapter and generated-image delivery |
| `packaging/` | Windows launcher and Inno Setup installer |
| `scripts/` | Native launchers and release-image helpers |
| `.github/workflows/windows-release.yml` | Windows application, installer, smoke test, checksums, and GitHub Release |
| `tests/` | Backend, proxy, API download, manager, and Windows launcher regression tests |

## Development setup

The Python package supports Python 3.11 or newer. The Windows release workflow uses Python 3.12. Native development also requires `uv`, Node.js 20 or newer, npm, and the official Codex CLI.

Windows:

```powershell
scripts\start-windows.ps1
```

Use `scripts\start-windows.ps1 -Dev` for FastAPI reload plus the Vite development server.

macOS or Linux:

```bash
./scripts/start-unix.sh
```

Both launchers install locked dependencies, build the frontend, prepare runtime directories, and start the backend on port 8088. Do not ask users to copy Codex credentials; device authorization must be completed by the user through the UI.

## Verification matrix

Run checks for every area touched. Before a release, run the complete matrix.

```bash
uv sync --extra dev
uv run pytest -q
uv run --with ruff ruff check --select E9,F .

cd frontend
npm ci
npm run lint
npm run build
cd ..

cd mcp
uv sync --frozen
uv run --with pytest pytest -q
cd ..
```

For a live native smoke test:

```bash
curl -fsS http://127.0.0.1:8088/api/health
```

Verify MCP changes against a running backend with Streamable HTTP `initialize` and `tools/list`; generation changes also require one real image result, not only a batch ID. Proxy changes must cover supported URL validation, subprocess environment injection, and credential redaction. Download changes must inspect ZIP contents and filenames. Windows launcher changes require `tests/test_windows_launcher.py` plus the workflow smoke test.

Dependency and publication checks:

```bash
uv run --with pip-audit pip-audit
git diff --check
git status --short
```

Before committing or publishing, scan staged content for private keys, API tokens, authenticated proxy URLs, `.codex` paths, `auth.json`, runtime data, logs, uploads, and generated images. Review the matches rather than applying an automatic deletion.

## Feature acceptance

- `IMAGE_GEN_MAX_CONCURRENCY` defaults to 9, accepts lower positive values, and remains capped at 9.
- Selecting a batch shows images produced by that batch; results must not be attributed from another concurrent batch.
- Single-batch and all-image downloads return valid ZIP files containing only allowed generated images.
- `IMAGE_GEN_PROXY_URL` supports HTTP, HTTPS, SOCKS5, and SOCKS5H. Login, status, and generation subprocesses share it, while health and auth APIs expose only a redacted endpoint.
- Cancel operations terminate native child processes and leave persisted batch counts consistent.
- MCP conversational generation waits for completion and returns actual image content or approved short-lived media URLs.

## Windows release procedure

1. Synchronize the version in `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`, `mcp/pyproject.toml`, `mcp/uv.lock`, `mcp/image_gen_mcp/__init__.py`, `app/main.py`, `packaging/windows-installer.iss`, and the workflow dispatch default.
2. Run the complete verification matrix and dependency audit. Do not cut a release with unresolved known vulnerabilities unless the risk is explicitly accepted.
3. Confirm the installer keeps its existing `AppId`, new installs use `%LOCALAPPDATA%\CodexImageStudio`, and upgrades can reuse `%LOCALAPPDATA%\ImageGenService`.
4. Tag the exact release commit as `v<version>` and push the tag to GitHub. The workflow builds and smoke-tests `CodexImageStudio-<version>-Setup-x64.exe`, creates `SHA256SUMS.txt`, and uploads both assets.
5. Verify the published checksum, tag, release title, and installer filename. The application is currently unsigned, so Windows SmartScreen may warn users.

Never include Codex credentials, generated images, uploads, proxy settings, or runtime data in an installer or release artifact.

## Docker and MCP

Docker is optional. The standard `Dockerfile` builds the frontend and backend; `Dockerfile.release` additionally expects a Codex binary. Persist application data, workspace, Codex home, and generated images with mounted directories.

The backend Compose service currently retains the published legacy image as its default while using the new service and container names. Build the current source explicitly when validating unreleased changes.

The MCP adapter defaults to `/mcp` with `/health` for health checks. Configure its backend through `IMAGE_GEN_MCP_BASE_URL`; media limits and cancellation controls use the `IMAGE_GEN_MCP_*` variables documented in `.env.example` and `mcp/README.md`.

## Security boundaries

- The packaged Windows launcher uses loopback. Source launches currently default to `0.0.0.0`; set `IMAGE_GEN_HOST=127.0.0.1` for local-only use and do not expose the unauthenticated backend directly to the public internet.
- A browser may receive login state, the official verification URL, and a short-lived device code, but never tokens or credential file locations.
- Serve files only from configured roots and only when their detected media type is an image.
- Keep runtime data outside source control and public container layers.
- Treat dependency-audit findings and the items in [.context/TODO.md](.context/TODO.md) as release decisions, not informational warnings.

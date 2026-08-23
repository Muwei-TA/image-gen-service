# Architecture and contracts

## System flow

The browser calls the FastAPI backend. The backend persists batches and jobs, launches one Codex CLI process per job, archives discovered images under the configured results directory, and serves only images beneath configured file roots. The MCP adapter calls the same HTTP backend and converts completed results into MCP image content or short-lived media URLs.

```text
Vue frontend -> FastAPI -> JobManager -> Codex CLI -> generated images
                    |          |
                    |          +-> StateStore -> state.json
                    +-> files/results

MCP client -> mcp/ adapter -> FastAPI
```

## Compatibility contracts

- HTTP clients rely on both unprefixed routes and their `/api` equivalents. Do not remove one form independently.
- Batch records persist in JSON and are read across restarts. Schema changes need defaults for older records and migration tests.
- `IMAGE_GEN_*` variables configure the backend. `IMAGE_GEN_MCP_*` variables configure the adapter. New product naming does not justify renaming these variables.
- The backend caps `IMAGE_GEN_MAX_CONCURRENCY` at 9 even if a larger value is supplied.
- Result paths must resolve beneath `IMAGE_GEN_FILE_ROOTS`, and file responses must remain image-only.
- Proxy configuration applies only to Codex login, login-status, and generation subprocesses. API responses contain the proxy scheme, host, and port but never credentials or the complete URL.
- The Python distribution and executable use `codex-image-studio`; the MCP distribution and executable use `codex-image-studio-mcp`. The MCP source package remains `image_gen_mcp` for import compatibility.

## Runtime and packaging

Native launchers build the frontend and start FastAPI. Windows packaged builds bind to `127.0.0.1`, store new runtime data under `%LOCALAPPDATA%\CodexImageStudio`, and reuse `%LOCALAPPDATA%\ImageGenService` when upgrading an existing installation.

Docker Compose service names use `codex-image-studio` and `codex-image-studio-mcp`. Until a renamed backend image is published, Compose deliberately defaults to `muwei517/image-gen-service:latest`; do not treat that legacy string as an accidental missed rename.

The Windows workflow bundles the official Codex CLI, builds `CodexImageStudio.exe`, installs it silently for a smoke test, checks `/api/health`, and publishes `CodexImageStudio-<version>-Setup-x64.exe` only for tags.

## Change boundaries

- Frontend behavior belongs in `frontend/src/`; backend orchestration belongs in `app/`; MCP transport and image-return behavior belong in `mcp/`.
- Do not duplicate backend generation logic in the MCP adapter. It should remain an HTTP client of the backend.
- Do not infer image ownership from unrelated global output when a job- or session-scoped result is available.
- Runtime data must stay in ignored or mounted directories, never inside built images or release artifacts.

# Codex Image Studio

This repository is a local-first image-generation workspace: Vue provides the UI, FastAPI owns jobs and files, Codex CLI performs generation, and `mcp/` adapts the backend to Streamable HTTP MCP. Docker is optional; native Windows, macOS, and Linux behavior is the primary product path.

## Rules that must survive changes

- Preserve the existing `/api` and compatibility routes, `IMAGE_GEN_*` environment variables, persisted batch schema, and the `image_gen_mcp` import path unless a migration is included.
- Generation concurrency is configurable downward but must never exceed 9.
- Treat `.codex`, `auth.json`, proxy credentials, device-login output, uploads, logs, runtime state, and generated images as private runtime data. Never print, commit, package, or publish them.
- Authentication and proxy status responses may expose state and a redacted proxy endpoint only; they must never return tokens, credential paths, usernames, passwords, or complete authenticated URLs.
- The packaged Windows launcher binds to `127.0.0.1`; source launches currently inherit the backend's `0.0.0.0` default. Do not describe an all-interface deployment as safe beyond a trusted local network without access control, restricted CORS, and a deliberate network boundary.
- Preserve the Windows installer `AppId` and legacy `%LOCALAPPDATA%\ImageGenService` data fallback so upgrades do not lose user state.
- Keep versions synchronized across Python packages, the frontend, installer defaults, and release workflow. A release tag must match the packaged version.
- Update tests and agent-facing documentation in the same change whenever a contract or workflow changes.

Read [README_FOR_AGENT.md](README_FOR_AGENT.md) before implementation or release work. Use [.context/CONTEXT.md](.context/CONTEXT.md) for architecture and contracts, and check [.context/TODO.md](.context/TODO.md) before modifying affected areas.

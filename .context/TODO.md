# Deferred engineering work

- `app/config.py`, `app/main.py`, `docker-compose.yml`: add authenticated access and restrictive CORS before treating a `0.0.0.0` deployment as safe beyond a trusted local network.
- `pyproject.toml`, `uv.lock`: upgrade FastAPI/Starlette and pytest to versions that clear the current dependency audit, then run the complete regression matrix.
- `app/store.py`: preserve a timestamped copy of unreadable state before initializing a new store; add corrupted-state recovery tests.
- `app/manager.py`: replace global generated-image fallback matching with deterministic job or Codex-session ownership; cover concurrent batches in tests.
- `app/manager.py`: cap jobs per batch, queued jobs, prompt size, and reference-image count to prevent unbounded disk and queue growth.
- `app/main.py`: replace in-memory ZIP assembly with a bounded temporary-file or streaming implementation.
- `app/auth.py`, `app/manager.py`, `frontend/src/App.vue`: cache or coalesce Codex login-status checks so polling and queue starts do not create redundant subprocesses.

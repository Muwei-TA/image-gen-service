from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote
import mimetypes
import zipfile

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.config import Settings
from app.manager import JobManager
from app.store import StateStore
from app.uploads import create_upload, delete_upload


settings = Settings.load()
settings.ensure_dirs()
store = StateStore(settings.data_dir / "state.json")
manager = JobManager(settings, store)
auth = manager.auth


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.reconcile_interrupted_jobs()
    yield
    auth.cancel_login()


app = FastAPI(
    title="Image Gen Service",
    version="0.2.0",
    description="Cross-platform Codex image generation workspace",
    lifespan=lifespan,
)
origins = [origin.strip() for origin in settings.cors_origin.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def _not_found(kind: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind} not found")


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


def platform_status() -> dict[str, Any]:
    import os
    import platform

    return {
        "os": platform.system().lower(),
        "native_windows": os.name == "nt",
        "docker": Path("/.dockerenv").exists(),
    }


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "platform": platform_status(), "codex": manager.codex_status()}


@app.get("/auth/status")
@app.get("/api/auth/status")
def auth_status() -> dict[str, Any]:
    return auth.status()


@app.post("/auth/login/device")
@app.post("/api/auth/login/device")
def start_device_login() -> dict[str, Any]:
    try:
        return auth.start_device_login()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/auth/login/device")
@app.get("/api/auth/login/device")
def device_login_state() -> dict[str, Any]:
    return auth.login_state()


@app.delete("/auth/login/device")
@app.delete("/api/auth/login/device")
def cancel_device_login() -> dict[str, Any]:
    return auth.cancel_login()


@app.post("/auth/logout")
@app.post("/api/auth/logout")
def logout() -> dict[str, Any]:
    try:
        return auth.logout()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/batches")
@app.get("/api/batches")
def list_batches() -> dict[str, Any]:
    return {"batches": manager.list_batches()}


@app.post("/batches", status_code=202)
@app.post("/api/batches", status_code=202)
def submit_batch(payload: dict[str, Any]) -> dict[str, Any]:
    return manager.submit_batch(payload)


@app.get("/batches/{batch_id}")
@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str) -> dict[str, Any]:
    try:
        return manager.get_batch(batch_id)
    except KeyError as exc:
        raise _not_found("batch") from exc


@app.post("/batches/{batch_id}/cancel")
@app.post("/api/batches/{batch_id}/cancel")
def cancel_batch(batch_id: str) -> dict[str, Any]:
    try:
        return manager.cancel_batch(batch_id)
    except KeyError as exc:
        raise _not_found("batch") from exc


@app.get("/jobs/{job_id}")
@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    try:
        return manager.get_job(job_id)
    except KeyError as exc:
        raise _not_found("job") from exc


@app.post("/jobs/{job_id}/cancel")
@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    try:
        return manager.cancel_job(job_id)
    except KeyError as exc:
        raise _not_found("job") from exc


@app.get("/uploads")
@app.get("/api/uploads")
def list_uploads() -> dict[str, Any]:
    return {"uploads": store.list_uploads()}


@app.post("/uploads", status_code=201)
@app.post("/api/uploads", status_code=201)
def upload(payload: dict[str, Any]) -> dict[str, Any]:
    return create_upload(payload, settings, store)


@app.get("/uploads/{image_id}")
@app.get("/api/uploads/{image_id}")
def get_upload(image_id: str) -> dict[str, Any]:
    value = store.get_upload(image_id)
    if not value:
        raise _not_found("upload")
    return value


@app.delete("/uploads/{image_id}")
@app.delete("/api/uploads/{image_id}")
def remove_upload(image_id: str) -> dict[str, Any]:
    try:
        return {"deleted": delete_upload(image_id, settings, store)}
    except KeyError as exc:
        raise _not_found("upload") from exc


def _allowed_image_path(value: str) -> Path:
    requested = Path(unquote(value)).resolve()
    allowed_roots = [root.resolve() for root in settings.file_roots]
    if not any(requested == root or root in requested.parents for root in allowed_roots):
        raise HTTPException(status_code=403, detail="file path is not allowed")
    if not requested.is_file():
        raise _not_found("file")
    content_type, _ = mimetypes.guess_type(str(requested))
    if not content_type or not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="only image files are supported")
    return requested


@app.get("/files")
@app.get("/api/files")
def get_file(path: str = Query(...)) -> FileResponse:
    requested = _allowed_image_path(path)
    content_type, _ = mimetypes.guess_type(str(requested))
    return FileResponse(requested, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/batches/{batch_id}/download")
@app.get("/api/batches/{batch_id}/download")
def download_batch(batch_id: str) -> StreamingResponse:
    try:
        batch = manager.get_batch(batch_id)
    except KeyError as exc:
        raise _not_found("batch") from exc
    buffer = BytesIO()
    used_names: set[str] = set()
    count = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for job in batch.get("jobs", []):
            for result_path in job.get("result_paths") or []:
                try:
                    path = _allowed_image_path(str(result_path))
                except HTTPException:
                    continue
                name = f"{int(job.get('index', count)) + 1:02d}_{path.name}"
                while name in used_names:
                    count += 1
                    name = f"{int(job.get('index', count)) + 1:02d}_{count}_{path.name}"
                used_names.add(name)
                archive.write(path, name)
                count += 1
    if not count:
        raise _not_found("generated image")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{batch_id}.zip"'},
    )


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> Response:
    dist_root = settings.frontend_dist_dir.resolve()
    if not dist_root.exists():
        raise _not_found("frontend")
    requested = (dist_root / path).resolve()
    if requested != dist_root and dist_root not in requested.parents:
        raise _not_found("file")
    if not requested.is_file():
        requested = dist_root / "index.html"
    if not requested.is_file():
        raise _not_found("frontend")
    return FileResponse(requested)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()

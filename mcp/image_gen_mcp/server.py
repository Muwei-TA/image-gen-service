from __future__ import annotations

import asyncio
from pathlib import PurePosixPath
import time
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .client import ImageGenClient, ImageGenServiceError
from .config import Settings
from .schemas import BATCH_ID_RE, JOB_ID_RE, CreateBatchInput, UploadReferenceImageInput

settings = Settings.load()

SERVER_INSTRUCTIONS = (
    "When the user explicitly asks to generate/edit images, draw, make posters, "
    "illustrations or visual drafts, call imagegen and put the full visual "
    "requirements into prompt. imagegen waits for Codex $imagegen to finish and "
    "returns images directly. Use create_batch only for large asynchronous batches; "
    "do not just explain how to generate images."
)

mcp = FastMCP(
    "image-gen-service",
    instructions=SERVER_INSTRUCTIONS,
    host=settings.host,
    port=settings.port,
    streamable_http_path=settings.mcp_path,
    stateless_http=True,
    json_response=True,
)

TERMINAL_BATCH_STATUSES = {"completed", "finished_with_errors"}


def _client() -> ImageGenClient:
    return ImageGenClient(Settings.load())


def _validated_id(value: str, pattern: Any, name: str) -> str:
    if not pattern.match(value):
        raise ValueError(f"invalid {name}")
    return value


async def _wait_for_batch(client: ImageGenClient, batch_id: str) -> dict[str, Any]:
    runtime = Settings.load()
    deadline = time.monotonic() + runtime.generation_timeout_seconds
    while True:
        batch = await client.get_batch(batch_id, redact=False)
        if batch.get("status") in TERMINAL_BATCH_STATUSES:
            return batch
        if time.monotonic() >= deadline:
            raise ImageGenServiceError(f"generation timed out for batch {batch_id}")
        await asyncio.sleep(runtime.poll_interval_seconds)


def _image_format(mime_type: str, result_path: str) -> str:
    subtype = mime_type.removeprefix("image/").lower()
    if subtype == "jpeg":
        return "jpeg"
    if subtype in {"png", "gif", "webp"}:
        return subtype
    suffix = PurePosixPath(result_path).suffix.lower().lstrip(".")
    return "jpeg" if suffix in {"jpg", "jpeg"} else suffix or "png"


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(str(error["msg"]) for error in exc.errors())


@mcp.custom_route("/health", methods=["GET"])
async def health_route(_: Request) -> JSONResponse:
    try:
        backend = await _client().health_check()
        ok = bool(backend.get("ok")) and bool((backend.get("codex") or {}).get("authenticated"))
        return JSONResponse({"ok": ok, "backend": backend}, status_code=200 if ok else 503)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@mcp.tool(
    name="imagegen",
    description=(
        "Generate or edit images with Codex $imagegen and return actual MCP image content. "
        "Use whenever the user asks for image generation, drawing, editing, posters, "
        "illustrations or visual drafts."
    ),
    structured_output=False,
)
async def imagegen(prompt: str, count: int = 1, reference_image_ids: list[str] | None = None) -> list[Any]:
    """Generate images synchronously and return the image bytes inline."""
    try:
        runtime = Settings.load()
        if count > runtime.max_inline_images:
            raise ValueError(f"count must be <= {runtime.max_inline_images}; use create_batch for larger batches")
        model = CreateBatchInput(prompt=prompt, count=count, reference_image_ids=reference_image_ids or [])
        client = ImageGenClient(runtime)
        created = await client.create_batch(model.to_payload())
        batch_id = str(created.get("batch_id") or "")
        if not batch_id:
            raise ImageGenServiceError("backend did not return batch_id")
        batch = await _wait_for_batch(client, batch_id)
        paths: list[str] = []
        errors: list[str] = []
        for job in sorted(batch.get("jobs") or [], key=lambda item: int(item.get("index", 0))):
            paths.extend(str(path) for path in job.get("result_paths") or [] if path)
            if job.get("error"):
                errors.append(str(job["error"]))
        if not paths:
            raise ImageGenServiceError("image generation failed: " + ("; ".join(errors) or "no image returned"))
        result: list[Any] = [f"Generated {len(paths)} image(s) (batch: {batch_id})."]
        for path in paths:
            data, mime_type = await client.download_generated_image(path)
            result.append(Image(data=data, format=_image_format(mime_type, path)))
        if errors:
            result.append("Some jobs failed: " + "; ".join(dict.fromkeys(errors)))
        return result
    except ValidationError as exc:
        raise ValueError(_validation_message(exc)) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check backend availability and Codex authentication."""
    return await _client().health_check()


@mcp.tool()
async def create_batch(
    prompt: str | None = None,
    prompts: list[str] | None = None,
    count: int = 1,
    reference_image_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create an asynchronous image generation batch."""
    try:
        model = CreateBatchInput(prompt=prompt, prompts=prompts, count=count, reference_image_ids=reference_image_ids or [])
        return await _client().create_batch(model.to_payload())
    except ValidationError as exc:
        raise ValueError(_validation_message(exc)) from exc


@mcp.tool()
async def get_batch(batch_id: str) -> dict[str, Any]:
    """Get batch state and safe result metadata."""
    return await _client().get_batch(_validated_id(batch_id, BATCH_ID_RE, "batch_id"))


@mcp.tool()
async def get_job(job_id: str) -> dict[str, Any]:
    """Get a single job state and safe result metadata."""
    return await _client().get_job(_validated_id(job_id, JOB_ID_RE, "job_id"))


@mcp.tool()
async def list_batches(limit: int = 20, status: str | None = None) -> dict[str, Any]:
    """List recent batches, optionally filtering by status."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    data = await _client().list_batches()
    batches = list(data.get("batches") or [])
    if status:
        batches = [batch for batch in batches if batch.get("status") == status]
    batches.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"batches": batches[:limit]}


@mcp.tool()
async def upload_reference_image(data: str, mime_type: str = "image/png", filename: str | None = None) -> dict[str, Any]:
    """Upload a base64/data-URL reference image and return its image_id."""
    try:
        model = UploadReferenceImageInput(data=data, mime_type=mime_type, filename=filename)
        return await _client().upload_reference_image(model.to_payload())
    except ValidationError as exc:
        raise ValueError(_validation_message(exc)) from exc


@mcp.tool()
async def list_uploads(limit: int = 50) -> dict[str, Any]:
    """List uploaded reference images."""
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    data = await _client().list_uploads()
    uploads = list(data.get("uploads") or [])
    uploads.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"uploads": uploads[:limit]}


if settings.enable_cancel_tools:

    @mcp.tool()
    async def cancel_batch(batch_id: str) -> dict[str, Any]:
        """Cancel a queued or running batch."""
        return await _client().cancel_batch(_validated_id(batch_id, BATCH_ID_RE, "batch_id"))

    @mcp.tool()
    async def cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel a queued or running job."""
        return await _client().cancel_job(_validated_id(job_id, JOB_ID_RE, "job_id"))


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

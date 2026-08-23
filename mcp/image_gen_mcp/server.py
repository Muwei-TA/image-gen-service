from __future__ import annotations

import asyncio
from pathlib import PurePosixPath
import time
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import CallToolResult, ResourceLink, TextContent
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .client import ImageGenClient, CodexImageStudioError
from .config import Settings
from .media import MediaStore
from .schemas import BATCH_ID_RE, JOB_ID_RE, CreateBatchInput, UploadReferenceImageInput

settings = Settings.load()

SERVER_INSTRUCTIONS = (
    "When the user explicitly asks to generate/edit images, draw, make posters, "
    "illustrations or visual drafts, call imagegen and put the full visual "
    "requirements into prompt. imagegen waits for Codex $imagegen to finish and "
    "returns images plus short-lived media URLs for isolated chat channels. "
    "Use the returned MEDIA URL when a channel needs an attachment. "
    "Use create_batch only for large asynchronous batches; "
    "do not just explain how to generate images."
)

mcp = FastMCP(
    "codex-image-studio",
    instructions=SERVER_INSTRUCTIONS,
    host=settings.host,
    port=settings.port,
    streamable_http_path=settings.mcp_path,
    stateless_http=True,
    json_response=True,
)

TERMINAL_BATCH_STATUSES = {"completed", "finished_with_errors"}
media_store = MediaStore()


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
            raise CodexImageStudioError(f"generation timed out for batch {batch_id}")
        await asyncio.sleep(runtime.poll_interval_seconds)


def _image_format(mime_type: str, result_path: str) -> str:
    subtype = mime_type.removeprefix("image/").lower()
    if subtype == "jpeg":
        return "jpeg"
    if subtype in {"png", "gif", "webp"}:
        return subtype
    suffix = PurePosixPath(result_path).suffix.lower().lstrip(".")
    return "jpeg" if suffix in {"jpg", "jpeg"} else suffix or "png"


def _image_filename(index: int, mime_type: str, result_path: str) -> str:
    image_format = _image_format(mime_type, result_path)
    suffix = "jpg" if image_format == "jpeg" else image_format
    return f"generated-{index}.{suffix}"


def _publish_media(
    runtime: Settings,
    data: bytes,
    mime_type: str,
    result_path: str,
    index: int,
) -> dict[str, Any] | None:
    if not runtime.media_base_url:
        return None
    filename = _image_filename(index, mime_type, result_path)
    token, _ = media_store.put(
        data,
        mime_type,
        filename,
        ttl_seconds=runtime.media_ttl_seconds,
        max_items=runtime.media_max_items,
        max_total_bytes=runtime.media_max_total_bytes,
    )
    return {
        "url": f"{runtime.media_base_url}/media/{token}",
        "mime_type": mime_type,
        "filename": filename,
        "size": len(data),
        "expires_in_seconds": runtime.media_ttl_seconds,
    }


def _media_result(
    batch_id: str,
    images: list[dict[str, Any]],
    *,
    inline_images: list[Image] | None = None,
    errors: list[str] | None = None,
) -> CallToolResult:
    generated_count = len(inline_images) if inline_images is not None else len(images)
    lines = [f"Generated {generated_count} image(s) (batch: {batch_id})."]
    content: list[Any] = []
    if images:
        lines.append("These random-token URLs are short-lived and can be downloaded or forwarded to chat channels:")
        for index, image in enumerate(images, start=1):
            lines.extend((f"{index}. {image['url']}", f"MEDIA:{image['url']}"))
    else:
        lines.append("IMAGE_GEN_MCP_MEDIA_BASE_URL is not configured; only inline MCP image content is returned.")
    if errors:
        lines.append("Some jobs failed: " + "; ".join(dict.fromkeys(errors)))
    content.append(TextContent(type="text", text="\n".join(lines)))
    for image in images:
        content.append(
            ResourceLink(
                type="resource_link",
                name=image["filename"],
                uri=image["url"],
                description="Short-lived generated image download URL",
                mimeType=image["mime_type"],
                size=image["size"],
            )
        )
    for image in inline_images or []:
        content.append(image.to_image_content())
    return CallToolResult(
        content=content,
        structuredContent={
            "batch_id": batch_id,
            "images": images,
            "media_delivery_enabled": bool(images),
            "errors": list(dict.fromkeys(errors or [])),
        },
    )


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(str(error["msg"]) for error in exc.errors())


@mcp.custom_route("/health", methods=["GET"])
async def health_route(_: Request) -> JSONResponse:
    try:
        backend = await _client().health_check()
        ok = bool(backend.get("ok")) and bool((backend.get("codex") or {}).get("authenticated"))
        return JSONResponse(
            {
                "ok": ok,
                "backend": backend,
                "media_delivery": {"enabled": bool(Settings.load().media_base_url)},
            },
            status_code=200 if ok else 503,
        )
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@mcp.custom_route("/media/{token}", methods=["GET", "HEAD"])
async def media_route(request: Request) -> Response:
    item = media_store.get(request.path_params["token"])
    if item is None:
        return JSONResponse({"error": "media not found or expired"}, status_code=404)
    remaining = media_store.remaining_seconds(item)
    headers = {
        "Cache-Control": f"private, max-age={remaining}",
        "Content-Disposition": f'inline; filename="{item.filename}"',
        "X-Content-Type-Options": "nosniff",
    }
    return Response(item.data, media_type=item.mime_type, headers=headers)


@mcp.tool(
    name="imagegen",
    description=(
        "Generate or edit images with Codex $imagegen and return actual MCP image content. "
        "Use whenever the user asks for image generation, drawing, editing, posters, "
        "illustrations or visual drafts."
    ),
    structured_output=False,
)
async def imagegen(prompt: str, count: int = 1, reference_image_ids: list[str] | None = None) -> CallToolResult:
    """Generate images and return inline content plus expiring channel-safe URLs."""
    try:
        runtime = Settings.load()
        if count > runtime.max_inline_images:
            raise ValueError(f"count must be <= {runtime.max_inline_images}; use create_batch for larger batches")
        model = CreateBatchInput(prompt=prompt, count=count, reference_image_ids=reference_image_ids or [])
        client = ImageGenClient(runtime)
        created = await client.create_batch(model.to_payload())
        batch_id = str(created.get("batch_id") or "")
        if not batch_id:
            raise CodexImageStudioError("backend did not return batch_id")
        batch = await _wait_for_batch(client, batch_id)
        paths: list[str] = []
        errors: list[str] = []
        for job in sorted(batch.get("jobs") or [], key=lambda item: int(item.get("index", 0))):
            paths.extend(str(path) for path in job.get("result_paths") or [] if path)
            if job.get("error"):
                errors.append(str(job["error"]))
        if not paths:
            raise CodexImageStudioError("image generation failed: " + ("; ".join(errors) or "no image returned"))
        published: list[dict[str, Any]] = []
        inline_images: list[Image] = []
        for index, path in enumerate(paths, start=1):
            data, mime_type = await client.download_generated_image(path)
            inline_images.append(Image(data=data, format=_image_format(mime_type, path)))
            media = _publish_media(runtime, data, mime_type, path, index)
            if media:
                published.append(media)
        return _media_result(batch_id, published, inline_images=inline_images, errors=errors)
    except ValidationError as exc:
        raise ValueError(_validation_message(exc)) from exc
    except CodexImageStudioError as exc:
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


@mcp.tool(
    description=(
        "Return completed batch images as short-lived HTTP URLs for delivery to isolated Agent channels "
        "such as Feishu or QQ."
    ),
    structured_output=False,
)
async def get_batch_images(batch_id: str) -> CallToolResult:
    """Publish a completed batch as expiring HTTP media URLs without exposing backend paths."""
    runtime = Settings.load()
    if not runtime.media_base_url:
        raise RuntimeError("IMAGE_GEN_MCP_MEDIA_BASE_URL is required for media URL delivery")
    client = ImageGenClient(runtime)
    safe_batch_id = _validated_id(batch_id, BATCH_ID_RE, "batch_id")
    batch = await client.get_batch(safe_batch_id, redact=False)
    if batch.get("status") not in TERMINAL_BATCH_STATUSES:
        raise RuntimeError(f"batch {safe_batch_id} is not complete")
    paths: list[str] = []
    errors: list[str] = []
    for job in sorted(batch.get("jobs") or [], key=lambda item: int(item.get("index", 0))):
        paths.extend(str(path) for path in job.get("result_paths") or [] if path)
        if job.get("error"):
            errors.append(str(job["error"]))
    if not paths:
        raise RuntimeError("batch has no generated images")
    published: list[dict[str, Any]] = []
    for index, path in enumerate(paths, start=1):
        data, mime_type = await client.download_generated_image(path)
        media = _publish_media(runtime, data, mime_type, path, index)
        if media:
            published.append(media)
    return _media_result(safe_batch_id, published, errors=errors)


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

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from .client import ImageGenClient, ImageGenServiceError
from .config import Settings
from .schemas import (
    CancelBatchInput,
    CancelJobInput,
    CreateBatchInput,
    GetBatchInput,
    GetJobInput,
    ListBatchesInput,
    ListUploadsInput,
    UploadReferenceImageInput,
)

mcp = FastMCP("image-gen-service")


def _client() -> ImageGenClient:
    return ImageGenClient(Settings.load())


def _validation_error(exc: ValidationError) -> ValueError:
    return ValueError("; ".join(error["msg"] for error in exc.errors()))


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check whether Image Gen Service and Codex authentication are available."""
    try:
        return await _client().health_check()
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
async def create_batch(
    prompt: str | None = None,
    prompts: list[str] | None = None,
    count: int = 1,
    reference_image_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create an image generation batch using prompts and uploaded reference image IDs only."""
    try:
        model = CreateBatchInput(
            prompt=prompt,
            prompts=prompts,
            count=count,
            reference_image_ids=reference_image_ids or [],
        )
        return await _client().create_batch(model.to_payload())
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
async def get_batch(batch_id: str) -> dict[str, Any]:
    """Get a batch, including queued/running/completed job state and generated result references."""
    try:
        model = GetBatchInput(batch_id=batch_id)
        return await _client().get_batch(model.batch_id)
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
async def get_job(job_id: str) -> dict[str, Any]:
    """Get a single image generation job state, error, and generated result references."""
    try:
        model = GetJobInput(job_id=job_id)
        return await _client().get_job(model.job_id)
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
async def list_batches(limit: int = 20, status: str | None = None) -> dict[str, Any]:
    """List recent image generation batches, optionally filtered by status."""
    try:
        model = ListBatchesInput(limit=limit, status=status)
        data = await _client().list_batches()
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc

    batches = list(data.get("batches") or [])
    if model.status:
        batches = [batch for batch in batches if batch.get("status") == model.status]
    batches.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"batches": batches[: model.limit]}


@mcp.tool()
async def list_uploads(limit: int = 50) -> dict[str, Any]:
    """List uploaded reference images by image ID for use with create_batch."""
    try:
        model = ListUploadsInput(limit=limit)
        data = await _client().list_uploads()
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc

    uploads = list(data.get("uploads") or [])
    uploads.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"uploads": uploads[: model.limit]}


@mcp.tool()
async def upload_reference_image(data: str, mime_type: str = "image/png", filename: str | None = None) -> dict[str, Any]:
    """Upload a base64/data-URL reference image and return an image_id. Local file paths are not accepted."""
    try:
        model = UploadReferenceImageInput(data=data, mime_type=mime_type, filename=filename)
        return await _client().upload_reference_image(model.to_payload())
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except ImageGenServiceError as exc:
        raise RuntimeError(str(exc)) from exc


_settings = Settings.load()
if _settings.enable_cancel_tools:

    @mcp.tool()
    async def cancel_batch(batch_id: str) -> dict[str, Any]:
        """Cancel a queued or running batch. This mutates in-progress generation work."""
        try:
            model = CancelBatchInput(batch_id=batch_id)
            return await _client().cancel_batch(model.batch_id)
        except ValidationError as exc:
            raise _validation_error(exc) from exc
        except ImageGenServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool()
    async def cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel a queued or running job. This mutates in-progress generation work."""
        try:
            model = CancelJobInput(job_id=job_id)
            return await _client().cancel_job(model.job_id)
        except ValidationError as exc:
            raise _validation_error(exc) from exc
        except ImageGenServiceError as exc:
            raise RuntimeError(str(exc)) from exc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

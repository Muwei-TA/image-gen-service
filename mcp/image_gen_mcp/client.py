from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .schemas import clean_response


class ImageGenServiceError(RuntimeError):
    pass


class ImageGenClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _request(self, method: str, path: str, *, redact: bool = True, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds, trust_env=False) as client:
                response = await client.request(method, f"{self.settings.base_url}{path}", **kwargs)
        except httpx.RequestError as exc:
            raise ImageGenServiceError(f"image-gen-service unavailable at {self.settings.base_url}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("error")
            except Exception:
                detail = response.text.strip() or response.reason_phrase
            raise ImageGenServiceError(f"image-gen-service HTTP {response.status_code}: {detail}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ImageGenServiceError("image-gen-service returned non-JSON response") from exc
        return clean_response(data, redact_paths=redact and self.settings.redact_paths)

    async def health_check(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def create_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/batches", json=payload)

    async def get_batch(self, batch_id: str, *, redact: bool = True) -> dict[str, Any]:
        return await self._request("GET", f"/batches/{batch_id}", redact=redact)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/jobs/{job_id}")

    async def list_batches(self) -> dict[str, Any]:
        return await self._request("GET", "/batches")

    async def list_uploads(self) -> dict[str, Any]:
        return await self._request("GET", "/uploads")

    async def upload_reference_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/uploads", json=payload)

    async def download_generated_image(self, result_path: str) -> tuple[bytes, str]:
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds, trust_env=False) as client:
                response = await client.get(f"{self.settings.base_url}/files", params={"path": result_path})
        except httpx.RequestError as exc:
            raise ImageGenServiceError("failed to download generated image") from exc
        if response.status_code >= 400:
            raise ImageGenServiceError(f"generated image download failed with HTTP {response.status_code}")
        mime_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if not mime_type.startswith("image/"):
            raise ImageGenServiceError(f"generated result is not an image: {mime_type or 'unknown'}")
        if len(response.content) > self.settings.max_inline_image_bytes:
            raise ImageGenServiceError("generated image exceeds inline MCP size limit")
        return response.content, mime_type

    async def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/batches/{batch_id}/cancel", json={})

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/jobs/{job_id}/cancel", json={})

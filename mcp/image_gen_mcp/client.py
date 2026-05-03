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

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.settings.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise ImageGenServiceError(
                f"Image generation service is unavailable at {self.settings.base_url}. Start the service and retry."
            ) from exc

        if response.status_code >= 400:
            try:
                detail = response.json().get("error")
            except Exception:
                detail = response.text.strip() or response.reason_phrase
            raise ImageGenServiceError(f"Image generation service returned HTTP {response.status_code}: {detail}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ImageGenServiceError("Image generation service returned non-JSON response") from exc
        return clean_response(data, redact_paths=self.settings.redact_paths)

    async def health_check(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def create_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/batches", json=payload)

    async def get_batch(self, batch_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/batches/{batch_id}")

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/jobs/{job_id}")

    async def list_batches(self) -> dict[str, Any]:
        return await self._request("GET", "/batches")

    async def list_uploads(self) -> dict[str, Any]:
        return await self._request("GET", "/uploads")

    async def upload_reference_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/uploads", json=payload)

    async def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/batches/{batch_id}/cancel", json={})

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/jobs/{job_id}/cancel", json={})

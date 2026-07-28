from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from mcp.types import ImageContent, ResourceLink

from image_gen_mcp.schemas import clean_response
from image_gen_mcp.server import _image_format, get_batch_images, imagegen, media_route, media_store, settings


class FakeClient:
    def __init__(self, settings):
        self.settings = settings

    async def create_batch(self, payload):
        return {"batch_id": "batch_abc123"}

    async def get_batch(self, batch_id, *, redact=True):
        return {"status": "completed", "jobs": [{"index": 0, "result_paths": ["/safe/result.png"], "error": ""}]}

    async def download_generated_image(self, path):
        return b"fake-png", "image/png"


def test_imagegen_returns_image_content():
    runtime = replace(settings, media_base_url="http://agent.test:8090")
    media_store.clear()
    with (
        patch("image_gen_mcp.server.Settings.load", return_value=runtime),
        patch("image_gen_mcp.server.ImageGenClient", FakeClient),
    ):
        result = asyncio.run(imagegen(prompt="draw an astronaut cat"))
    assert result.structuredContent is not None
    assert result.structuredContent["images"][0]["url"].startswith("http://agent.test:8090/media/")
    assert any(isinstance(item, ResourceLink) for item in result.content)
    assert any(isinstance(item, ImageContent) and item.mimeType == "image/png" for item in result.content)
    assert "MEDIA:http://agent.test:8090/media/" in result.content[0].text


def test_imagegen_keeps_inline_fallback_when_media_delivery_is_disabled():
    runtime = replace(settings, media_base_url=None)
    with (
        patch("image_gen_mcp.server.Settings.load", return_value=runtime),
        patch("image_gen_mcp.server.ImageGenClient", FakeClient),
    ):
        result = asyncio.run(imagegen(prompt="draw an astronaut cat"))
    assert result.structuredContent is not None
    assert result.structuredContent["images"] == []
    assert result.structuredContent["media_delivery_enabled"] is False
    assert "Generated 1 image(s)" in result.content[0].text
    assert any(isinstance(item, ImageContent) for item in result.content)


def test_get_batch_images_returns_url_without_inline_payload():
    runtime = replace(settings, media_base_url="http://agent.test:8090")
    media_store.clear()
    with (
        patch("image_gen_mcp.server.Settings.load", return_value=runtime),
        patch("image_gen_mcp.server.ImageGenClient", FakeClient),
    ):
        result = asyncio.run(get_batch_images(batch_id="batch_abc123"))
    assert result.structuredContent is not None
    assert len(result.structuredContent["images"]) == 1
    assert [item.type for item in result.content] == ["text", "resource_link"]


def test_media_route_returns_published_image():
    media_store.clear()
    token, _ = media_store.put(
        b"fake-png",
        "image/png",
        "generated-1.png",
        ttl_seconds=60,
        max_items=10,
        max_total_bytes=1024,
    )
    request = SimpleNamespace(path_params={"token": token})
    response = asyncio.run(media_route(request))
    assert response.status_code == 200
    assert response.body == b"fake-png"
    assert response.media_type == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_media_route_rejects_unknown_token():
    media_store.clear()
    request = SimpleNamespace(path_params={"token": "unknown"})
    response = asyncio.run(media_route(request))
    assert response.status_code == 404


def test_clean_response_redacts_paths():
    assert clean_response({"batch_id": "batch_abc", "result_paths": ["/secret.png"]}) == {"batch_id": "batch_abc"}


def test_image_format():
    assert _image_format("image/jpeg", "/tmp/a.jpg") == "jpeg"

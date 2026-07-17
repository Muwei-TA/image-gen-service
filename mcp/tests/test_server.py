from __future__ import annotations

import asyncio
from unittest.mock import patch

from mcp.server.fastmcp import Image

from image_gen_mcp.schemas import clean_response
from image_gen_mcp.server import _image_format, imagegen


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
    with patch("image_gen_mcp.server.ImageGenClient", FakeClient):
        result = asyncio.run(imagegen(prompt="draw an astronaut cat"))
    assert isinstance(result[1], Image)
    assert result[1].to_image_content().mimeType == "image/png"


def test_clean_response_redacts_paths():
    assert clean_response({"batch_id": "batch_abc", "result_paths": ["/secret.png"]}) == {"batch_id": "batch_abc"}


def test_image_format():
    assert _image_format("image/jpeg", "/tmp/a.jpg") == "jpeg"

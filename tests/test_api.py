from unittest.mock import patch
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app


def test_health_uses_fastapi_and_redacts_credential_path():
    status = {
        "available": True,
        "authenticated": True,
        "method": "chatgpt",
        "detail": "Logged in using ChatGPT",
        "max_concurrency": 4,
    }
    with patch("app.main.manager.codex_status", return_value=status):
        response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["codex"] == status
    assert "auth_path" not in response.text
    assert "auth.json" not in response.text
    assert '"bin"' not in response.text


def test_openapi_exposes_device_login_routes():
    payload = TestClient(app).get("/openapi.json").json()
    assert "/api/auth/login/device" in payload["paths"]
    assert "post" in payload["paths"]["/api/auth/login/device"]


def test_download_all_images_returns_one_zip(tmp_path: Path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")
    summaries = [
        {"batch_id": "batch_new", "created_at": "2026-08-23T10:00:00+00:00"},
        {"batch_id": "batch_old", "created_at": "2026-08-22T10:00:00+00:00"},
    ]
    batches = {
        "batch_new": {"batch_id": "batch_new", "jobs": [{"index": 0, "result_paths": [str(first)]}]},
        "batch_old": {"batch_id": "batch_old", "jobs": [{"index": 0, "result_paths": [str(second)]}]},
    }
    with (
        patch("app.main.manager.list_batches", return_value=summaries),
        patch("app.main.manager.get_batch", side_effect=lambda batch_id: batches[batch_id]),
        patch("app.main._allowed_image_path", side_effect=lambda value: Path(value)),
    ):
        response = TestClient(app).get("/api/downloads/images")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "image-gen-results.zip" in response.headers["content-disposition"]
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["001_batch_new/01_first.png", "002_batch_old/01_second.png"]

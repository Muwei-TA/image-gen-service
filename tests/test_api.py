from unittest.mock import patch

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

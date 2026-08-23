from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch
import os

import pytest

from app.config import Settings, validate_proxy_url
from app.process_runner import ProcessRunner, ProcessTarget


def test_max_concurrency_defaults_to_and_is_capped_at_nine() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("IMAGE_GEN_MAX_CONCURRENCY", None)
        assert Settings.load().max_concurrency == 9
    with patch.dict(os.environ, {"IMAGE_GEN_MAX_CONCURRENCY": "50"}):
        assert Settings.load().max_concurrency == 9


def test_validate_proxy_url_accepts_supported_schemes() -> None:
    assert validate_proxy_url("http://proxy.example:8080") == "http://proxy.example:8080"
    assert validate_proxy_url("socks5h://user:secret@proxy.example:1080").startswith("socks5h://")


@pytest.mark.parametrize("value", ["ftp://proxy.example:21", "http://", "http://proxy.example:not-a-port"])
def test_validate_proxy_url_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_proxy_url(value)


def test_proxy_status_never_exposes_credentials() -> None:
    settings = replace(
        Settings.load(),
        proxy_url="http://private-user:private-password@proxy.example:7890",
    )
    status = settings.proxy_status()
    assert status == {"enabled": True, "scheme": "http", "host": "proxy.example", "port": 7890}
    assert "private-user" not in repr(settings)
    assert "private-password" not in repr(settings)
    assert "private-user" not in repr(status)
    assert "private-password" not in repr(status)


def test_process_runner_injects_proxy_into_codex_process(tmp_path) -> None:
    settings = replace(
        Settings.load(),
        root=tmp_path,
        data_dir=tmp_path / "data",
        codex_home=tmp_path / ".codex",
        codex_user_home=tmp_path,
        proxy_url="socks5h://proxy.example:1080",
        proxy_no_proxy="localhost,127.0.0.1",
    )
    runner = ProcessRunner(settings)
    fake_proc = type("FakeProc", (), {})()
    with patch("app.process_runner.subprocess.Popen", return_value=fake_proc) as popen:
        assert runner.start(
            ProcessTarget("session", "window"),
            tmp_path,
            ["codex", "login", "status"],
            tmp_path / "codex.log",
        ) is fake_proc
    env = popen.call_args.kwargs["env"]
    assert env["HTTP_PROXY"] == "socks5h://proxy.example:1080"
    assert env["HTTPS_PROXY"] == "socks5h://proxy.example:1080"
    assert env["ALL_PROXY"] == "socks5h://proxy.example:1080"
    assert env["NO_PROXY"] == "localhost,127.0.0.1"
    assert env["http_proxy"] == env["HTTP_PROXY"]
    assert env["no_proxy"] == env["NO_PROXY"]

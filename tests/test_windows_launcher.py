from __future__ import annotations

import os
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "windows_launcher.py"
LAUNCHER_SPEC = importlib.util.spec_from_file_location("codex_image_studio_windows_launcher", LAUNCHER_PATH)
assert LAUNCHER_SPEC and LAUNCHER_SPEC.loader
windows_launcher = importlib.util.module_from_spec(LAUNCHER_SPEC)
LAUNCHER_SPEC.loader.exec_module(windows_launcher)
configure_environment = windows_launcher.configure_environment
open_workspace_when_ready = windows_launcher.open_workspace_when_ready


IMAGE_GEN_KEYS = (
    "IMAGE_GEN_SERVICE_ROOT",
    "IMAGE_GEN_DATA_DIR",
    "IMAGE_GEN_RESULTS_DIR",
    "IMAGE_GEN_DEFAULT_WORKDIR",
    "IMAGE_GEN_CODEX_BIN",
    "IMAGE_GEN_CODEX_HOME",
    "IMAGE_GEN_CODEX_USER_HOME",
    "IMAGE_GEN_GENERATED_IMAGES_DIR",
    "IMAGE_GEN_FRONTEND_DIST_DIR",
    "IMAGE_GEN_FILE_ROOTS",
    "IMAGE_GEN_HOST",
    "IMAGE_GEN_PORT",
    "IMAGE_GEN_MAX_CONCURRENCY",
)


def test_windows_launcher_reuses_legacy_data_directory(tmp_path: Path) -> None:
    user_home = tmp_path / "user"
    local_app_data = tmp_path / "local"
    legacy_data = local_app_data / "ImageGenService" / "data"
    legacy_data.mkdir(parents=True)
    with patch.dict(os.environ, {"USERPROFILE": str(user_home), "LOCALAPPDATA": str(local_app_data)}):
        for key in IMAGE_GEN_KEYS:
            os.environ.pop(key, None)
        configure_environment()
        assert os.environ["IMAGE_GEN_DATA_DIR"] == str(legacy_data)
        assert os.environ["IMAGE_GEN_RESULTS_DIR"] == str(legacy_data / "results")
        assert os.environ["IMAGE_GEN_HOST"] == "127.0.0.1"
        assert os.environ["IMAGE_GEN_MAX_CONCURRENCY"] == "9"


def test_windows_launcher_opens_configured_port() -> None:
    response = MagicMock()
    response.__enter__.return_value.status = 200
    with (
        patch.dict(os.environ, {"IMAGE_GEN_PORT": "19088"}),
        patch.object(windows_launcher.urllib.request, "urlopen", return_value=response) as urlopen,
        patch.object(windows_launcher.webbrowser, "open") as browser_open,
    ):
        open_workspace_when_ready()
    urlopen.assert_called_once_with("http://127.0.0.1:19088/api/health", timeout=1)
    browser_open.assert_called_once_with("http://127.0.0.1:19088")

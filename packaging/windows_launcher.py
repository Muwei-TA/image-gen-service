from __future__ import annotations

from pathlib import Path
from threading import Thread
import multiprocessing
import os
import sys
import time
import urllib.request
import webbrowser


def configure_environment() -> None:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    user_home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", str(user_home / "AppData" / "Local")))
    documents = Path(os.environ.get("USERPROFILE", str(user_home))) / "Documents"
    data_dir = local_app_data / "ImageGenService" / "data"
    codex_home = user_home / ".codex"
    generated_images = codex_home / "generated_images"

    defaults = {
        "IMAGE_GEN_SERVICE_ROOT": str(bundle_root),
        "IMAGE_GEN_DATA_DIR": str(data_dir),
        "IMAGE_GEN_RESULTS_DIR": str(data_dir / "results"),
        "IMAGE_GEN_DEFAULT_WORKDIR": str(documents),
        "IMAGE_GEN_CODEX_BIN": str(bundle_root / "codex.exe"),
        "IMAGE_GEN_CODEX_HOME": str(codex_home),
        "IMAGE_GEN_CODEX_USER_HOME": str(user_home),
        "IMAGE_GEN_GENERATED_IMAGES_DIR": str(generated_images),
        "IMAGE_GEN_FRONTEND_DIST_DIR": str(bundle_root / "frontend" / "dist"),
        "IMAGE_GEN_FILE_ROOTS": os.pathsep.join((str(data_dir), str(documents), str(generated_images))),
        "IMAGE_GEN_HOST": "127.0.0.1",
        "IMAGE_GEN_PORT": "8088",
        "IMAGE_GEN_MAX_CONCURRENCY": "9",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def open_workspace_when_ready() -> None:
    url = "http://127.0.0.1:8088"
    health_url = f"{url}/api/health"
    for _ in range(60):
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.5)


def main() -> None:
    multiprocessing.freeze_support()
    configure_environment()
    Thread(target=open_workspace_when_ready, daemon=True).start()
    from app.main import main as run_service

    run_service()


if __name__ == "__main__":
    main()

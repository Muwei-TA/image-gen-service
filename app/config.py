from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    codex_bin: Path
    codex_home: Path
    codex_user_home: Path
    terminal_bin: str
    tmux_bin: str
    host: str
    port: int
    batch_prefix: str
    default_workdir: Path
    job_timeout_seconds: int
    max_concurrency: int
    cors_origin: str
    frontend_dist_dir: Path
    file_roots: tuple[Path, ...]
    generated_images_dir: Path
    results_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        root = Path(os.environ.get("IMAGE_GEN_SERVICE_ROOT", str(Path(__file__).resolve().parents[1])))
        data_dir = Path(os.environ.get("IMAGE_GEN_DATA_DIR", str(root / "data")))
        codex_user_home = Path(os.environ.get("IMAGE_GEN_CODEX_USER_HOME", str(Path.home())))
        codex_home = Path(os.environ.get("IMAGE_GEN_CODEX_HOME", str(codex_user_home / ".codex")))
        default_workdir = Path(os.environ.get("IMAGE_GEN_DEFAULT_WORKDIR", str(root.parent)))
        generated_images_dir = Path(os.environ.get("IMAGE_GEN_GENERATED_IMAGES_DIR", str(codex_home / "generated_images")))
        results_dir = Path(os.environ.get("IMAGE_GEN_RESULTS_DIR", str(data_dir / "results")))
        file_roots_raw = os.environ.get("IMAGE_GEN_FILE_ROOTS")
        if file_roots_raw:
            file_roots = tuple(Path(part.strip()) for part in file_roots_raw.split(os.pathsep) if part.strip())
        else:
            file_roots = (data_dir, default_workdir, generated_images_dir)
        return cls(
            root=root,
            data_dir=data_dir,
            codex_bin=Path(os.environ.get("IMAGE_GEN_CODEX_BIN", "codex")),
            codex_home=codex_home,
            codex_user_home=codex_user_home,
            terminal_bin=os.environ.get("IMAGE_GEN_TERMINAL_BIN", "python3"),
            tmux_bin=os.environ.get("IMAGE_GEN_TMUX_BIN", "tmux"),
            host=os.environ.get("IMAGE_GEN_HOST", "0.0.0.0"),
            port=int(os.environ.get("IMAGE_GEN_PORT", "8088")),
            batch_prefix=os.environ.get("IMAGE_GEN_BATCH_PREFIX", "$imagegen"),
            default_workdir=default_workdir,
            job_timeout_seconds=int(os.environ.get("IMAGE_GEN_JOB_TIMEOUT_SECONDS", "1800")),
            max_concurrency=max(1, int(os.environ.get("IMAGE_GEN_MAX_CONCURRENCY", "2"))),
            cors_origin=os.environ.get("IMAGE_GEN_CORS_ORIGIN", "*").strip() or "*",
            frontend_dist_dir=Path(os.environ.get("IMAGE_GEN_FRONTEND_DIST_DIR", str(root / "frontend" / "dist"))),
            file_roots=file_roots,
            generated_images_dir=generated_images_dir,
            results_dir=results_dir,
        )

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "jobs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

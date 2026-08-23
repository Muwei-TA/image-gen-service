from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import signal
import subprocess

from app.config import Settings


@dataclass
class ProcessTarget:
    session_name: str
    window_name: str

    @property
    def target(self) -> str:
        return f"{self.session_name}:{self.window_name}"


@dataclass
class ProcessSnapshot:
    output: str


def _slug(text: str) -> str:
    out = []
    last_dash = False
    for char in text.lower():
        if char.isalnum():
            out.append(char)
            last_dash = False
        elif not last_dash:
            out.append("-")
            last_dash = True
    return ("".join(out).strip("-") or "image-gen")[:24]


class ProcessRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def names_for(self, batch_id: str, index: int) -> ProcessTarget:
        short = _slug(batch_id)
        return ProcessTarget(session_name=f"image-gen-{short}-{index + 1}", window_name=f"img-{index + 1}")

    def start(self, target: ProcessTarget, cwd: Path, command: list[str], log_path: Path) -> subprocess.Popen:
        del target
        env = os.environ.copy()
        env.update({
            "HOME": str(self.settings.codex_user_home),
            "CODEX_HOME": str(self.settings.codex_home),
            "TERM": "xterm-256color",
        })
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("ab", buffering=0)
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        log_handle.close()
        return proc

    def capture(self, log_path: Path) -> ProcessSnapshot:
        if not log_path.exists():
            return ProcessSnapshot(output="")
        return ProcessSnapshot(output=log_path.read_text(encoding="utf-8", errors="ignore"))

    @staticmethod
    def terminate(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from app.config import Settings


@dataclass
class TerminalTarget:
    session_name: str
    window_name: str

    @property
    def target(self) -> str:
        return f"{self.session_name}:{self.window_name}"


@dataclass
class TerminalSnapshot:
    output: str


def _slug(text: str) -> str:
    out = []
    last_dash = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            last_dash = False
        elif not last_dash:
            out.append("-")
            last_dash = True
    return ("".join(out).strip("-") or "image-gen")[:24]


class TerminalRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def names_for(self, batch_id: str, index: int) -> TerminalTarget:
        short = _slug(batch_id)
        return TerminalTarget(session_name=f"image-gen-{short}-{index + 1}", window_name=f"img-{index + 1}")

    def start(self, target: TerminalTarget, cwd: Path, command: str, log_path: Path) -> subprocess.Popen:
        worker = Path(__file__).resolve().parent / "pty_worker.py"
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(self.settings.codex_user_home),
                "CODEX_HOME": str(self.settings.codex_home),
                "TERM": "xterm-256color",
            }
        )
        return subprocess.Popen(
            [
                self.settings.terminal_bin,
                str(worker),
                "--cwd",
                str(cwd),
                "--log",
                str(log_path),
                "--timeout",
                str(self.settings.job_timeout_seconds),
                "--",
                command,
            ],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )

    def capture(self, log_path: Path) -> TerminalSnapshot:
        if not log_path.exists():
            return TerminalSnapshot(output="")
        return TerminalSnapshot(output=log_path.read_text(encoding="utf-8", errors="ignore"))

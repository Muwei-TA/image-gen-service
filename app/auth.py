from __future__ import annotations

from collections import deque
from threading import RLock, Thread
from typing import Any
import os
import re
import shutil
import subprocess
import time

from app.config import Settings


URL_RE = re.compile(r"https?://[^\s\x1b]+")
CODE_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4,6}\b")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class CodexAuthManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = RLock()
        self.proc: subprocess.Popen[str] | None = None
        self.lines: deque[str] = deque(maxlen=120)
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.exit_code: int | None = None

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(self.settings.codex_env())
        return env

    def _executable(self) -> str | None:
        value = str(self.settings.codex_bin)
        if self.settings.codex_bin.is_absolute():
            return value if self.settings.codex_bin.exists() else None
        return shutil.which(value)

    def status(self) -> dict[str, Any]:
        executable = self._executable()
        authenticated = False
        method = None
        detail = "Codex CLI 未安装"
        if executable:
            try:
                completed = subprocess.run(
                    [executable, "login", "status"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    env=self._env(),
                )
                output = (completed.stdout + "\n" + completed.stderr).strip()
                authenticated = completed.returncode == 0
                detail = output or ("已登录" if authenticated else "未登录")
                lowered = output.lower()
                if "chatgpt" in lowered:
                    method = "chatgpt"
                elif "api key" in lowered or "api_key" in lowered:
                    method = "api_key"
            except (OSError, subprocess.TimeoutExpired) as exc:
                detail = str(exc)
        return {
            "available": bool(executable),
            "authenticated": authenticated,
            "method": method,
            "detail": detail,
            "max_concurrency": self.settings.max_concurrency,
            "egress_proxy": self.settings.proxy_status(),
        }

    def start_device_login(self) -> dict[str, Any]:
        executable = self._executable()
        if not executable:
            raise RuntimeError("Codex CLI 未安装或不在 PATH 中")
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return self.login_state()
            self.lines.clear()
            self.started_at = time.time()
            self.finished_at = None
            self.exit_code = None
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self.proc = subprocess.Popen(
                [executable, "login", "--device-auth"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=self._env(),
                creationflags=creationflags,
                start_new_session=os.name != "nt",
            )
            Thread(target=self._capture_login, args=(self.proc,), daemon=True).start()
            return self.login_state()

    def _capture_login(self, proc: subprocess.Popen[str]) -> None:
        if proc.stdout:
            for line in proc.stdout:
                cleaned = line.strip()
                if cleaned:
                    with self.lock:
                        self.lines.append(cleaned)
        code = proc.wait()
        with self.lock:
            self.exit_code = code
            self.finished_at = time.time()

    def login_state(self) -> dict[str, Any]:
        with self.lock:
            output = ANSI_RE.sub("", "\n".join(self.lines))
            running = bool(self.proc and self.proc.poll() is None)
            urls = URL_RE.findall(output)
            code_match = CODE_RE.search(output)
            if code_match:
                message = "请在官方授权页输入设备码"
            elif running:
                message = "正在等待 Codex 提供设备码"
            elif self.finished_at is not None and self.exit_code == 0:
                message = "Codex 登录已完成"
            elif self.finished_at is not None:
                message = "Codex 登录未完成，请重试"
            else:
                message = "尚未开始登录"
            return {
                "running": running,
                "completed": self.finished_at is not None,
                "success": self.finished_at is not None and self.exit_code == 0,
                "verification_url": urls[-1].rstrip(".,)") if urls else None,
                "user_code": code_match.group(0) if code_match else None,
                "message": message,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }

    def cancel_login(self) -> dict[str, Any]:
        with self.lock:
            proc = self.proc
        if proc and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
            else:
                try:
                    os.killpg(proc.pid, 15)
                except ProcessLookupError:
                    pass
            try:
                code = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait(timeout=3)
            with self.lock:
                self.exit_code = code
                self.finished_at = self.finished_at or time.time()
        return self.login_state()

    def logout(self) -> dict[str, Any]:
        executable = self._executable()
        if not executable:
            raise RuntimeError("Codex CLI 未安装或不在 PATH 中")
        completed = subprocess.run(
            [executable, "logout"],
            capture_output=True,
            text=True,
            timeout=15,
            env=self._env(),
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "退出登录失败").strip())
        return self.status()

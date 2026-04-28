from __future__ import annotations

import argparse
import errno
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    from app.result_parser import RESULT_PATTERN
except ModuleNotFoundError:  # pragma: no cover - used when this file is executed as a script.
    from result_parser import RESULT_PATTERN

try:
    import pty
except ImportError:  # pragma: no cover - Windows can import this module for constants/tests.
    pty = None


TERMINAL_RESPONSES = {
    b"\x1b[6n": b"\x1b[1;1R",
    b"\x1b[c": b"\x1b[?1;2c",
    b"\x1b[>c": b"\x1b[>0;276;0c",
    b"\x1b]10;?\x1b\\": b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\",
    b"\x1b]11;?\x1b\\": b"\x1b]11;rgb:0000/0000/0000\x1b\\",
}
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a command inside a PTY and capture output.")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if len(args.command) != 1:
        parser.error("expected exactly one shell command after --")
    return args


def write_all(fd: int, payload: bytes) -> None:
    while payload:
        written = os.write(fd, payload)
        payload = payload[written:]


def maybe_respond(master_fd: int, output: bytes, responses_sent: set[bytes]) -> None:
    for query, response in TERMINAL_RESPONSES.items():
        if query in output:
            write_all(master_fd, response)
    lower = output.lower()
    if b"press enter to continue" in lower and b"sign in with" not in lower:
        key = b"press-enter"
        if key not in responses_sent:
            responses_sent.add(key)
            write_all(master_fd, b"\r")


def terminate(proc: subprocess.Popen, grace_seconds: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run() -> int:
    args = parse_args()
    if pty is None:
        raise RuntimeError("PTY worker requires a POSIX platform with the pty module")
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    env = os.environ.copy()
    env.setdefault("TERM", "xterm-256color")
    proc = subprocess.Popen(
        args.command[0],
        shell=True,
        cwd=args.cwd,
        env=env,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
        close_fds=True,
    )
    os.close(slave_fd)

    responses_sent: set[bytes] = set()
    deadline = time.monotonic() + max(1, args.timeout)
    timed_out = False
    saw_result = False
    exit_requested_at: float | None = None
    last_output_at = time.monotonic()

    with log_path.open("ab", buffering=0) as log:
        log.write(f"$ {args.command[0]}\n".encode("utf-8", errors="replace"))
        while True:
            if proc.poll() is not None:
                break
            now = time.monotonic()
            if time.monotonic() > deadline:
                timed_out = True
                log.write(f"\n[pty-worker] timeout after {args.timeout} seconds\n".encode())
                terminate(proc)
                break
            if saw_result and exit_requested_at is None:
                exit_requested_at = now
                log.write(b"\n[pty-worker] generated image detected; requesting CLI exit\n")
                write_all(master_fd, b"\x04")
            if exit_requested_at is not None and now - exit_requested_at > 10:
                log.write(b"\n[pty-worker] generated image detected; stopping idle CLI\n")
                terminate(proc)
                break
            readable, _, _ = select.select([master_fd], [], [], 0.25)
            if not readable:
                continue
            try:
                chunk = os.read(master_fd, 8192)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            last_output_at = time.monotonic()
            log.write(chunk)
            if RESULT_PATTERN.search(chunk.decode("utf-8", errors="ignore")):
                saw_result = True
            maybe_respond(master_fd, chunk, responses_sent)

    os.close(master_fd)
    if saw_result:
        return 0
    if timed_out:
        return 124
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(run())

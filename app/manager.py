from __future__ import annotations

from pathlib import Path
from threading import RLock, Thread
from typing import Any, Dict
from datetime import datetime, timezone
import os
import signal
import shutil
import time

from app.codex_runner import command_string, prepare_job
from app.config import Settings
from app.models import BatchRecord, JobRecord, new_id, now_iso
from app.result_parser import extract_result_paths
from app.store import StateStore
from app.tmux_runner import TerminalRunner


class JobManager:
    def __init__(self, settings: Settings, store: StateStore):
        self.settings = settings
        self.store = store
        self.terminal = TerminalRunner(settings)
        self.procs: dict[str, Any] = {}
        self.lock = RLock()

    def submit_batch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        prompts = request.get("prompts") or []
        base_prompt = (request.get("prompt") or "").strip()
        workdir = str(Path(request.get("workdir") or self.settings.default_workdir))
        reference_images = self._resolve_reference_images(request)
        if prompts:
            job_prompts = [str(p).strip() for p in prompts if str(p).strip()]
        else:
            count = max(1, int(request.get("count", 1)))
            if not base_prompt:
                raise ValueError("prompt is required when prompts is not provided")
            job_prompts = [base_prompt for _ in range(count)]
        if not job_prompts:
            raise ValueError("at least one prompt is required")

        batch_id = new_id("batch")
        batch = BatchRecord(
            batch_id=batch_id,
            created_at=now_iso(),
            base_prompt=base_prompt or job_prompts[0],
            total=len(job_prompts),
            queued=len(job_prompts),
        )
        batch_dict = batch.to_dict()
        batch_dict["job_ids"] = []
        self.store.create_batch(batch_dict)

        for index, prompt in enumerate(job_prompts):
            job_id = new_id("job")
            job_dir = self.settings.data_dir / "jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            target = self.terminal.names_for(batch_id, index)
            job = JobRecord(
                job_id=job_id,
                batch_id=batch_id,
                index=index,
                prompt=prompt,
                workdir=workdir,
                session_name=target.session_name,
                window_name=target.window_name,
                reference_images=reference_images,
                command="",
                log_path=str(job_dir / "codex.log"),
                last_message_path=str(job_dir / "last_message.txt"),
                exit_code_path=str(job_dir / "exitcode.txt"),
                script_path=str(job_dir / "run.sh"),
                prompt_path=str(job_dir / "prompt.txt"),
                queued_at=now_iso(),
            )
            job.command = command_string(job, self.settings)
            self.store.create_job(job.to_dict())
            prepare_job(job, self.settings)

        self._refresh_batch(batch_id)
        self._pump_queue()
        return self.get_batch(batch_id)

    def codex_status(self) -> Dict[str, Any]:
        executable = shutil.which(str(self.settings.codex_bin)) if not self.settings.codex_bin.is_absolute() else str(self.settings.codex_bin)
        bin_exists = bool(executable and Path(executable).exists())
        auth_path = self.settings.codex_home / "auth.json"
        return {
            "bin": str(self.settings.codex_bin),
            "available": bin_exists,
            "authenticated": auth_path.exists(),
            "auth_path": str(auth_path),
            "max_concurrency": self.settings.max_concurrency,
        }

    def _pump_queue(self) -> None:
        with self.lock:
            running = sum(1 for job in self.store.list_jobs() if job.get("status") == "running")
            available = max(0, self.settings.max_concurrency - running)
            if available <= 0:
                return

            queued_jobs: list[Dict[str, Any]] = []
            for batch in sorted(self.store.list_batches(), key=lambda item: item.get("created_at", "")):
                queued_jobs.extend(
                    sorted(
                        [job for job in self.store.list_jobs_for_batch(batch["batch_id"]) if job.get("status") == "queued"],
                        key=lambda item: int(item.get("index", 0)),
                    )
                )

            for job in queued_jobs[:available]:
                self._start_job(job)

    def _start_job(self, job: Dict[str, Any]) -> None:
        status = self.codex_status()
        if not status["available"]:
            self.store.update_job(
                job["job_id"],
                status="failed",
                stage="failed",
                finished_at=now_iso(),
                exit_code=127,
                error=f"Codex CLI is not available: {self.settings.codex_bin}",
            )
            self._refresh_batch(job["batch_id"])
            return
        if not status["authenticated"]:
            self.store.update_job(
                job["job_id"],
                status="failed",
                stage="waiting_login",
                finished_at=now_iso(),
                exit_code=126,
                error="Codex is not logged in. Run `codex` once before generating images.",
            )
            self._refresh_batch(job["batch_id"])
            return

        target = self.terminal.names_for(job["batch_id"], int(job["index"]))
        try:
            proc = self.terminal.start(
                target=target,
                cwd=Path(job["workdir"]),
                command=job["command"],
                log_path=Path(job["log_path"]),
            )
            self.procs[job["job_id"]] = proc
            self.store.update_job(job["job_id"], status="running", stage="starting", started_at=now_iso(), worker_pid=getattr(proc, "pid", None))
            self._refresh_batch(job["batch_id"])
            Thread(target=self._watch_job, args=(job["job_id"], proc), daemon=True).start()
        except Exception as exc:
            self.store.update_job(job["job_id"], status="failed", stage="failed", finished_at=now_iso(), error=str(exc))
            self._refresh_batch(job["batch_id"])

    def _resolve_reference_images(self, request: Dict[str, Any]) -> list[str]:
        images: list[str] = []
        seen: set[str] = set()
        for image_id in request.get("reference_image_ids") or []:
            upload = self.store.get_upload(str(image_id))
            if not upload:
                raise ValueError(f"reference image id not found: {image_id}")
            path = str(upload["path"])
            if path not in seen:
                seen.add(path)
                images.append(path)
        for path in request.get("reference_images") or []:
            text = str(path).strip()
            if text and text not in seen:
                seen.add(text)
                images.append(text)
        return images

    def _watch_job(self, job_id: str, proc) -> None:
        last_output = ""
        started_at = time.monotonic()
        while True:
            job = self.store.get_job(job_id)
            if not job:
                return
            if job.get("status") == "canceled":
                self._terminate_proc(proc)
                self.procs.pop(job_id, None)
                return
            snapshot = self.terminal.capture(Path(job["log_path"]))
            if snapshot.output and snapshot.output != last_output:
                last_output = snapshot.output
                result_paths = self._archive_results(job, extract_result_paths(snapshot.output))
                self.store.update_job(
                    job_id,
                    final_message=snapshot.output,
                    result_paths=result_paths,
                    stage="image_detected" if result_paths else "generating",
                )
            if time.monotonic() - started_at > self.settings.job_timeout_seconds + 15:
                final_output = last_output or self._safe_read(job["log_path"])
                result_paths = self._archive_results(job, extract_result_paths(final_output))
                self._terminate_proc(proc)
                self.store.update_job(
                    job_id,
                    status="succeeded" if result_paths else "failed",
                    stage="finished" if result_paths else "timeout",
                    finished_at=now_iso(),
                    exit_code=0 if result_paths else 124,
                    final_message=final_output,
                    result_paths=result_paths,
                    error="" if result_paths else f"Job exceeded timeout of {self.settings.job_timeout_seconds} seconds.",
                )
                self._refresh_batch(job["batch_id"])
                self.procs.pop(job_id, None)
                self._pump_queue()
                return
            if proc.poll() is not None:
                rc = proc.returncode if proc.returncode is not None else 1
                final_output = last_output or self._safe_read(job["log_path"])
                result_paths = self._archive_results(job, extract_result_paths(final_output))
                succeeded = rc == 0 or bool(result_paths)
                self.store.update_job(
                    job_id,
                    status="succeeded" if succeeded else "failed",
                    stage="finished" if succeeded else "failed",
                    finished_at=now_iso(),
                    exit_code=0 if succeeded else rc,
                    final_message=final_output,
                    result_paths=result_paths,
                    error="" if succeeded else job.get("error", ""),
                )
                self._refresh_batch(job["batch_id"])
                self.procs.pop(job_id, None)
                self._pump_queue()
                return
            time.sleep(1)

    def _archive_results(self, job: Dict[str, Any], paths: list[str]) -> list[str]:
        archived: list[str] = []
        seen: set[str] = set()
        for index, path in enumerate(paths):
            source = Path(path)
            target_path = source
            if source.exists() and source.is_file():
                suffix = source.suffix or ".png"
                target_dir = self.settings.results_dir / str(job["batch_id"])
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / f"{job['job_id']}_{index + 1}{suffix}"
                if not target_path.exists():
                    shutil.copy2(source, target_path)
            text = str(target_path)
            if text not in seen:
                seen.add(text)
                archived.append(text)
        return archived

    def _terminate_proc(self, proc) -> None:
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _kill_process_tree(self, pid: int) -> None:
        children: dict[int, list[int]] = {}
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                parts = (Path("/proc") / name / "stat").read_text(encoding="utf-8", errors="ignore").split()
                ppid = int(parts[3])
                children.setdefault(ppid, []).append(int(name))
            except Exception:
                continue
        stack = [pid]
        ordered: list[int] = []
        while stack:
            current = stack.pop()
            ordered.append(current)
            stack.extend(children.get(current, []))
        for target in reversed(ordered):
            try:
                os.kill(target, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(0.5)
        for target in reversed(ordered):
            try:
                os.kill(target, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def _safe_read(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _refresh_batch(self, batch_id: str) -> None:
        jobs = self.store.list_jobs_for_batch(batch_id)
        if not jobs:
            return
        queued = sum(1 for j in jobs if j.get("status") == "queued")
        running = sum(1 for j in jobs if j.get("status") == "running")
        succeeded = sum(1 for j in jobs if j.get("status") == "succeeded")
        failed = sum(1 for j in jobs if j.get("status") == "failed")
        canceled = sum(1 for j in jobs if j.get("status") == "canceled")
        if running:
            status = "running"
        elif queued:
            status = "queued"
        elif failed or canceled:
            status = "finished_with_errors"
        else:
            status = "completed"
        self.store.update_batch(batch_id, status=status, queued=queued, running=running, succeeded=succeeded, failed=failed, canceled=canceled)

    def _expire_timed_out_jobs(self, batch_id: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        batches = [self.store.get_batch(batch_id)] if batch_id else self.store.list_batches()
        for batch in [b for b in batches if b]:
            changed = False
            for job in self.store.list_jobs_for_batch(batch["batch_id"]):
                if job.get("status") != "running" or not job.get("started_at"):
                    continue
                try:
                    started = datetime.fromisoformat(str(job["started_at"]))
                except ValueError:
                    continue
                if (now - started).total_seconds() <= self.settings.job_timeout_seconds + 30:
                    continue
                final_output = self._safe_read(job.get("log_path", ""))
                result_paths = self._archive_results(job, extract_result_paths(final_output))
                self.store.update_job(
                    job["job_id"],
                    status="succeeded" if result_paths else "failed",
                    stage="finished" if result_paths else "timeout",
                    finished_at=now_iso(),
                    exit_code=0 if result_paths else 124,
                    final_message=final_output,
                    result_paths=result_paths,
                    error="" if result_paths else f"Job exceeded timeout of {self.settings.job_timeout_seconds} seconds.",
                )
                changed = True
            if changed:
                self._refresh_batch(batch["batch_id"])

    def get_batch(self, batch_id: str) -> Dict[str, Any]:
        self._expire_timed_out_jobs(batch_id)
        batch = self.store.get_batch(batch_id)
        if not batch:
            raise KeyError(batch_id)
        batch["jobs"] = self.store.list_jobs_for_batch(batch_id)
        return batch

    def list_batches(self) -> list[Dict[str, Any]]:
        self._expire_timed_out_jobs()
        return self.store.list_batches()

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job.get("status") not in {"queued", "running"}:
            return job
        proc = self.procs.pop(job_id, None)
        if proc is not None:
            self._terminate_proc(proc)
        worker_pid = job.get("worker_pid")
        if worker_pid:
            self._kill_process_tree(int(worker_pid))
        final_output = self._safe_read(job.get("log_path", ""))
        updated = self.store.update_job(
            job_id,
            status="canceled",
            stage="canceled",
            finished_at=now_iso(),
            exit_code=130,
            final_message=final_output,
            result_paths=self._archive_results(job, extract_result_paths(final_output)),
            error="Canceled by user.",
        )
        self._refresh_batch(job["batch_id"])
        self._pump_queue()
        return updated

    def cancel_batch(self, batch_id: str) -> Dict[str, Any]:
        batch = self.store.get_batch(batch_id)
        if not batch:
            raise KeyError(batch_id)
        for job in self.store.list_jobs_for_batch(batch_id):
            if job.get("status") in {"queued", "running"}:
                self.cancel_job(job["job_id"])
        return self.get_batch(batch_id)

    def get_job(self, job_id: str) -> Dict[str, Any]:
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job.get("batch_id"):
            self._expire_timed_out_jobs(job["batch_id"])
            job = self.store.get_job(job_id) or job
        return job

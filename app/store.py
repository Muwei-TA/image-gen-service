from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
import json
import os
import tempfile

from app.models import now_iso
from app.result_parser import extract_result_paths


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = Lock()
        self.state: Dict[str, Any] = {"batches": {}, "jobs": {}, "uploads": {}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
                self.state.setdefault("batches", {})
                self.state.setdefault("jobs", {})
                self.state.setdefault("uploads", {})
                return
            except Exception:
                pass
        self._save_locked()

    def _save_locked(self) -> None:
        fd, tmp = tempfile.mkstemp(prefix=self.path.name, dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def save(self) -> None:
        with self.lock:
            self._save_locked()

    def create_batch(self, batch: Dict[str, Any]) -> None:
        with self.lock:
            self.state["batches"][batch["batch_id"]] = batch
            self._save_locked()

    def create_job(self, job: Dict[str, Any]) -> None:
        with self.lock:
            self.state["jobs"][job["job_id"]] = job
            batch = self.state["batches"].get(job["batch_id"])
            if batch is not None:
                batch.setdefault("job_ids", []).append(job["job_id"])
            self._save_locked()

    def update_job(self, job_id: str, **updates: Any) -> Dict[str, Any]:
        with self.lock:
            job = self.state["jobs"][job_id]
            for key, value in updates.items():
                if value is not None:
                    job[key] = value
            self._save_locked()
            return dict(job)

    def update_job_if_status(self, job_id: str, expected_statuses: set[str], **updates: Any) -> Dict[str, Any]:
        with self.lock:
            job = self.state["jobs"][job_id]
            if job.get("status") not in expected_statuses:
                return dict(job)
            for key, value in updates.items():
                if value is not None:
                    job[key] = value
            self._save_locked()
            return dict(job)

    def update_batch(self, batch_id: str, **updates: Any) -> Dict[str, Any]:
        with self.lock:
            batch = self.state["batches"][batch_id]
            for key, value in updates.items():
                if value is not None:
                    batch[key] = value
            self._save_locked()
            return dict(batch)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            job = self.state["jobs"].get(job_id)
            return dict(job) if job else None

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            batch = self.state["batches"].get(batch_id)
            return dict(batch) if batch else None

    def list_batches(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(v) for v in self.state["batches"].values()]

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(v) for v in self.state["jobs"].values()]

    def list_jobs_for_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        with self.lock:
            batch = self.state["batches"].get(batch_id)
            if not batch:
                return []
            return [dict(self.state["jobs"][jid]) for jid in batch.get("job_ids", []) if jid in self.state["jobs"]]

    def create_upload(self, upload: Dict[str, Any]) -> None:
        with self.lock:
            self.state["uploads"][upload["image_id"]] = upload
            self._save_locked()

    def get_upload(self, image_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            upload = self.state["uploads"].get(image_id)
            return dict(upload) if upload else None

    def list_uploads(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(v) for v in self.state["uploads"].values()]

    def delete_upload(self, image_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            upload = self.state["uploads"].pop(image_id, None)
            if upload is not None:
                self._save_locked()
                return dict(upload)
            return None

    def reconcile_interrupted_jobs(self) -> None:
        with self.lock:
            changed = False
            for job in self.state["jobs"].values():
                if job.get("status") not in {"queued", "running"}:
                    continue
                result_paths = list(job.get("result_paths") or [])
                if not result_paths:
                    result_paths = extract_result_paths(str(job.get("final_message") or ""))
                if result_paths:
                    job["status"] = "succeeded"
                    job["exit_code"] = 0
                    job["result_paths"] = result_paths
                    job["error"] = ""
                else:
                    job["status"] = "failed"
                    job["exit_code"] = 130
                    job["error"] = job.get("error") or "Service restarted before this job finished."
                job["finished_at"] = job.get("finished_at") or now_iso()
                changed = True

            for batch in self.state["batches"].values():
                jobs = [self.state["jobs"][jid] for jid in batch.get("job_ids", []) if jid in self.state["jobs"]]
                if not jobs:
                    continue
                queued = sum(1 for job in jobs if job.get("status") == "queued")
                running = sum(1 for job in jobs if job.get("status") == "running")
                succeeded = sum(1 for job in jobs if job.get("status") == "succeeded")
                failed = sum(1 for job in jobs if job.get("status") == "failed")
                canceled = sum(1 for job in jobs if job.get("status") == "canceled")
                if running:
                    status = "running"
                elif queued:
                    status = "queued"
                elif failed or canceled:
                    status = "finished_with_errors"
                else:
                    status = "completed"
                batch.update(queued=queued, running=running, succeeded=succeeded, failed=failed, canceled=canceled, status=status)
                changed = True

            if changed:
                self._save_locked()

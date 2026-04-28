from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class BatchRequest:
    prompt: Optional[str] = None
    prompts: Optional[List[str]] = None
    count: int = 1
    workdir: Optional[str] = None
    reference_image_ids: List[str] = field(default_factory=list)
    reference_images: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchRequest":
        return cls(
            prompt=data.get("prompt"),
            prompts=data.get("prompts"),
            count=int(data.get("count", 1)),
            workdir=data.get("workdir"),
            reference_image_ids=list(data.get("reference_image_ids") or []),
            reference_images=list(data.get("reference_images") or []),
        )


@dataclass
class JobRecord:
    job_id: str
    batch_id: str
    index: int
    prompt: str
    workdir: str
    session_name: str
    window_name: str
    reference_images: List[str] = field(default_factory=list)
    status: str = "queued"
    command: str = ""
    log_path: str = ""
    last_message_path: str = ""
    exit_code_path: str = ""
    script_path: str = ""
    prompt_path: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    final_message: str = ""
    result_paths: List[str] = field(default_factory=list)
    error: str = ""
    worker_pid: Optional[int] = None
    queued_at: Optional[str] = None
    stage: str = "queued"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BatchRecord:
    batch_id: str
    created_at: str
    base_prompt: str
    status: str = "queued"
    job_ids: List[str] = field(default_factory=list)
    total: int = 0
    queued: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    canceled: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

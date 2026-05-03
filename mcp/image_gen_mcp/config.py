from __future__ import annotations

from dataclasses import dataclass
import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    base_url: str
    timeout_seconds: float
    max_batch_count: int
    max_prompts: int
    max_prompt_chars: int
    max_upload_bytes: int
    redact_paths: bool
    enable_cancel_tools: bool

    @classmethod
    def load(cls) -> "Settings":
        base_url = os.environ.get("IMAGE_GEN_MCP_BASE_URL", "http://127.0.0.1:8088").strip().rstrip("/")
        if not base_url:
            raise ValueError("IMAGE_GEN_MCP_BASE_URL cannot be empty")
        return cls(
            base_url=base_url,
            timeout_seconds=float(_int_env("IMAGE_GEN_MCP_TIMEOUT_SECONDS", 30, 1)),
            max_batch_count=_int_env("IMAGE_GEN_MCP_MAX_BATCH_COUNT", 50, 1),
            max_prompts=_int_env("IMAGE_GEN_MCP_MAX_PROMPTS", 50, 1),
            max_prompt_chars=_int_env("IMAGE_GEN_MCP_MAX_PROMPT_CHARS", 8000, 1),
            max_upload_bytes=_int_env("IMAGE_GEN_MCP_MAX_UPLOAD_BYTES", 10 * 1024 * 1024, 1),
            redact_paths=_bool_env("IMAGE_GEN_MCP_REDACT_PATHS", True),
            enable_cancel_tools=_bool_env("IMAGE_GEN_MCP_ENABLE_CANCEL_TOOLS", False),
        )

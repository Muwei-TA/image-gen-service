from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlsplit


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _optional_http_url(name: str) -> str | None:
    value = os.environ.get(name, "").strip().rstrip("/")
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute http(s) URL")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not contain a query or fragment")
    return value


@dataclass(frozen=True)
class Settings:
    base_url: str
    host: str
    port: int
    mcp_path: str
    timeout_seconds: int
    generation_timeout_seconds: int
    poll_interval_seconds: int
    max_batch_count: int
    max_prompts: int
    max_prompt_chars: int
    max_upload_bytes: int
    max_inline_images: int
    max_inline_image_bytes: int
    media_base_url: str | None
    media_ttl_seconds: int
    media_max_items: int
    media_max_total_bytes: int
    redact_paths: bool
    enable_cancel_tools: bool

    @classmethod
    def load(cls) -> "Settings":
        base_url = os.getenv("IMAGE_GEN_MCP_BASE_URL", "http://127.0.0.1:8088").strip().rstrip("/")
        path = os.getenv("IMAGE_GEN_MCP_PATH", "/mcp").strip()
        if not base_url:
            raise ValueError("IMAGE_GEN_MCP_BASE_URL cannot be empty")
        if not path.startswith("/"):
            path = f"/{path}"
        return cls(
            base_url=base_url,
            host=os.getenv("IMAGE_GEN_MCP_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=_int_env("IMAGE_GEN_MCP_PORT", 8090),
            mcp_path=path,
            timeout_seconds=_int_env("IMAGE_GEN_MCP_TIMEOUT_SECONDS", 30),
            generation_timeout_seconds=_int_env("IMAGE_GEN_MCP_GENERATION_TIMEOUT_SECONDS", 1800),
            poll_interval_seconds=_int_env("IMAGE_GEN_MCP_POLL_INTERVAL_SECONDS", 1),
            max_batch_count=_int_env("IMAGE_GEN_MCP_MAX_BATCH_COUNT", 50),
            max_prompts=_int_env("IMAGE_GEN_MCP_MAX_PROMPTS", 50),
            max_prompt_chars=_int_env("IMAGE_GEN_MCP_MAX_PROMPT_CHARS", 8000),
            max_upload_bytes=_int_env("IMAGE_GEN_MCP_MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
            max_inline_images=_int_env("IMAGE_GEN_MCP_MAX_INLINE_IMAGES", 8),
            max_inline_image_bytes=_int_env("IMAGE_GEN_MCP_MAX_INLINE_IMAGE_BYTES", 20 * 1024 * 1024),
            media_base_url=_optional_http_url("IMAGE_GEN_MCP_MEDIA_BASE_URL"),
            media_ttl_seconds=_int_env("IMAGE_GEN_MCP_MEDIA_TTL_SECONDS", 3600),
            media_max_items=_int_env("IMAGE_GEN_MCP_MEDIA_MAX_ITEMS", 100),
            media_max_total_bytes=_int_env("IMAGE_GEN_MCP_MEDIA_MAX_TOTAL_BYTES", 200 * 1024 * 1024),
            redact_paths=_bool_env("IMAGE_GEN_MCP_REDACT_PATHS", True),
            enable_cancel_tools=_bool_env("IMAGE_GEN_MCP_ENABLE_CANCEL_TOOLS", False),
        )

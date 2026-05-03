from __future__ import annotations

import base64
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import Settings

BATCH_ID_RE = re.compile(r"^batch_[A-Za-z0-9]+$")
JOB_ID_RE = re.compile(r"^job_[A-Za-z0-9]+$")
IMAGE_ID_RE = re.compile(r"^img_[A-Za-z0-9]+$")
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
PATH_FIELDS = {
    "auth_path",
    "path",
    "workdir",
    "log_path",
    "last_message_path",
    "exit_code_path",
    "script_path",
    "prompt_path",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBatchInput(StrictModel):
    prompt: str | None = None
    prompts: list[str] | None = None
    count: int = 1
    reference_image_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self) -> "CreateBatchInput":
        settings = Settings.load()
        if self.count < 1 or self.count > settings.max_batch_count:
            raise ValueError(f"count must be between 1 and {settings.max_batch_count}")

        prompt = self.prompt.strip() if self.prompt else None
        prompts = [item.strip() for item in self.prompts or [] if item.strip()]
        if prompt and prompts:
            raise ValueError("provide either prompt or prompts, not both")
        if not prompt and not prompts:
            raise ValueError("prompt or prompts is required")
        if prompt and len(prompt) > settings.max_prompt_chars:
            raise ValueError(f"prompt must be <= {settings.max_prompt_chars} characters")
        if prompts:
            if len(prompts) > settings.max_prompts:
                raise ValueError(f"prompts must contain <= {settings.max_prompts} items")
            for item in prompts:
                if len(item) > settings.max_prompt_chars:
                    raise ValueError(f"each prompt must be <= {settings.max_prompt_chars} characters")
        self.prompt = prompt
        self.prompts = prompts or None
        return self

    @field_validator("reference_image_ids")
    @classmethod
    def validate_image_ids(cls, value: list[str]) -> list[str]:
        for image_id in value:
            if not IMAGE_ID_RE.match(image_id):
                raise ValueError(f"invalid reference image id: {image_id}")
        return value

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"reference_image_ids": self.reference_image_ids}
        if self.prompts:
            payload["prompts"] = self.prompts
        else:
            payload["prompt"] = self.prompt
            payload["count"] = self.count
        return payload


class GetBatchInput(StrictModel):
    batch_id: str

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, value: str) -> str:
        if not BATCH_ID_RE.match(value):
            raise ValueError("invalid batch_id")
        return value


class GetJobInput(StrictModel):
    job_id: str

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        if not JOB_ID_RE.match(value):
            raise ValueError("invalid job_id")
        return value


class ListBatchesInput(StrictModel):
    limit: int = 20
    status: str | None = None

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("limit must be between 1 and 100")
        return value


class ListUploadsInput(StrictModel):
    limit: int = 50

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1 or value > 200:
            raise ValueError("limit must be between 1 and 200")
        return value


class UploadReferenceImageInput(StrictModel):
    data: str
    mime_type: str = "image/png"
    filename: str | None = None

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_MIME_TYPES:
            raise ValueError(f"mime_type must be one of {sorted(ALLOWED_MIME_TYPES)}")
        return normalized

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str | None) -> str | None:
        if not value:
            return value
        name = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not name or name in {".", ".."}:
            raise ValueError("filename is invalid")
        return name[:120]

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: str) -> str:
        settings = Settings.load()
        text = value.strip()
        if not text:
            raise ValueError("data is required")
        if text.startswith("/") or text.startswith("./") or text.startswith("../"):
            raise ValueError("data must be base64 or a data URL, not a file path")
        encoded = text.split(",", 1)[1] if text.startswith("data:") and "," in text else text
        if len(encoded) > ((settings.max_upload_bytes + 2) // 3) * 4 + 1024:
            raise ValueError(f"encoded image exceeds {settings.max_upload_bytes} bytes")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("data must be valid base64") from exc
        if len(decoded) > settings.max_upload_bytes:
            raise ValueError(f"decoded image exceeds {settings.max_upload_bytes} bytes")
        return text

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"data": self.data, "mime_type": self.mime_type}
        if self.filename:
            payload["filename"] = self.filename
        return payload


class CancelBatchInput(GetBatchInput):
    pass


class CancelJobInput(GetJobInput):
    pass


def clean_response(value: Any, *, redact_paths: bool = True) -> Any:
    if isinstance(value, list):
        return [clean_response(item, redact_paths=redact_paths) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if redact_paths and key in PATH_FIELDS:
                continue
            cleaned[key] = clean_response(item, redact_paths=redact_paths)
        return cleaned
    return value

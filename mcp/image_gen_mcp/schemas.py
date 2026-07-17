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
PATH_FIELDS = {"auth_path", "path", "workdir", "log_path", "last_message_path", "exit_code_path", "script_path", "prompt_path", "result_paths"}


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
        prompt = self.prompt.strip() if self.prompt else None
        prompts = [item.strip() for item in self.prompts or [] if item.strip()]
        if self.count < 1 or self.count > settings.max_batch_count:
            raise ValueError(f"count must be between 1 and {settings.max_batch_count}")
        if bool(prompt) == bool(prompts):
            raise ValueError("provide exactly one of prompt or prompts")
        for item in ([prompt] if prompt else prompts):
            if item and len(item) > settings.max_prompt_chars:
                raise ValueError(f"prompt must be <= {settings.max_prompt_chars} characters")
        if len(prompts) > settings.max_prompts:
            raise ValueError(f"prompts must contain <= {settings.max_prompts} items")
        self.prompt, self.prompts = prompt, prompts or None
        return self

    @field_validator("reference_image_ids")
    @classmethod
    def validate_image_ids(cls, values: list[str]) -> list[str]:
        if any(not IMAGE_ID_RE.match(value) for value in values):
            raise ValueError("invalid reference image id")
        return values

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"reference_image_ids": self.reference_image_ids}
        if self.prompts:
            payload["prompts"] = self.prompts
        else:
            payload.update(prompt=self.prompt, count=self.count)
        return payload


class UploadReferenceImageInput(StrictModel):
    data: str
    mime_type: str = "image/png"
    filename: str | None = None

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_MIME_TYPES:
            raise ValueError("unsupported image MIME type")
        return value

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str | None) -> str | None:
        if not value:
            return value
        return value.replace("\\", "/").rsplit("/", 1)[-1].strip()[:120]

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: str) -> str:
        settings = Settings.load()
        text = value.strip()
        if not text or text.startswith(("/", "./", "../")):
            raise ValueError("data must be base64 or a data URL")
        encoded = text.split(",", 1)[1] if text.startswith("data:") and "," in text else text
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("data must be valid base64") from exc
        if len(decoded) > settings.max_upload_bytes:
            raise ValueError("image exceeds upload limit")
        return text

    def to_payload(self) -> dict[str, Any]:
        payload = {"data": self.data, "mime_type": self.mime_type}
        if self.filename:
            payload["filename"] = self.filename
        return payload


def clean_response(value: Any, *, redact_paths: bool = True) -> Any:
    if isinstance(value, list):
        return [clean_response(item, redact_paths=redact_paths) for item in value]
    if isinstance(value, dict):
        return {key: clean_response(item, redact_paths=redact_paths) for key, item in value.items() if not (redact_paths and key in PATH_FIELDS)}
    return value

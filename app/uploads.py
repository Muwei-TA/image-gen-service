from __future__ import annotations

from pathlib import Path
from typing import Any
import base64
import binascii
import re
import shutil

from app.config import Settings
from app.models import new_id, now_iso
from app.store import StateStore


DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.]+/[-\w.+]+);base64,(?P<data>.*)$", re.DOTALL)
EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def create_upload(request: dict[str, Any], settings: Settings, store: StateStore) -> dict[str, Any]:
    raw_data = request.get("data") or request.get("image_base64")
    if not raw_data:
        raise ValueError("data or image_base64 is required")

    mime_type = str(request.get("mime_type") or "").strip().lower()
    encoded = str(raw_data).strip()
    match = DATA_URL_RE.match(encoded)
    if match:
        mime_type = match.group("mime").lower()
        encoded = match.group("data")
    if not mime_type:
        mime_type = "image/png"
    if mime_type not in EXTENSIONS:
        raise ValueError(f"unsupported image mime type: {mime_type}")

    if len(encoded) > ((MAX_UPLOAD_BYTES + 2) // 3) * 4 + 1024:
        raise ValueError(f"uploaded image is larger than {MAX_UPLOAD_BYTES} bytes")
    try:
        content = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("invalid base64 image data") from exc
    if not content:
        raise ValueError("uploaded image is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"uploaded image is larger than {MAX_UPLOAD_BYTES} bytes")

    image_id = new_id("img")
    filename = safe_filename(request.get("filename"), image_id, EXTENSIONS[mime_type])
    upload_dir = settings.data_dir / "uploads" / image_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / filename
    path.write_bytes(content)

    upload = {
        "image_id": image_id,
        "filename": filename,
        "mime_type": mime_type,
        "size": len(content),
        "path": str(path),
        "created_at": now_iso(),
    }
    store.create_upload(upload)
    return upload


def delete_upload(image_id: str, settings: Settings, store: StateStore) -> dict[str, Any]:
    upload = store.delete_upload(image_id)
    if not upload:
        raise KeyError(image_id)
    upload_dir = settings.data_dir / "uploads" / image_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    return upload


def safe_filename(value: Any, image_id: str, default_ext: str) -> str:
    if not value:
        return f"{image_id}{default_ext}"
    name = Path(str(value)).name.strip()
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:80].strip("._")
    if not stem:
        return f"{image_id}{default_ext}"
    if Path(stem).suffix.lower() not in set(EXTENSIONS.values()):
        stem += default_ext
    return stem

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import json
import sys
import mimetypes
import zipfile
from io import BytesIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.manager import JobManager
from app.store import StateStore
from app.uploads import create_upload, delete_upload


settings = Settings.load()
settings.ensure_dirs()
store = StateStore(settings.data_dir / "state.json")
store.reconcile_interrupted_jobs()
manager = JobManager(settings, store)


class Handler(BaseHTTPRequestHandler):
    server_version = "ImageGenService/0.1"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", settings.cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "codex": manager.codex_status()})
            return
        if path == "/files":
            self._send_file(parsed.query)
            return
        if path == "/batches":
            self._send_json(HTTPStatus.OK, {"batches": manager.list_batches()})
            return
        if path.startswith("/batches/") and path.endswith("/download"):
            batch_id = path.split("/", 3)[2]
            self._send_batch_zip(batch_id)
            return
        if path == "/uploads":
            self._send_json(HTTPStatus.OK, {"uploads": store.list_uploads()})
            return
        if path.startswith("/uploads/"):
            image_id = path.split("/", 2)[2]
            upload = store.get_upload(image_id)
            if upload:
                self._send_json(HTTPStatus.OK, upload)
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "upload not found"})
            return
        if path.startswith("/batches/"):
            batch_id = path.split("/", 2)[2]
            try:
                self._send_json(HTTPStatus.OK, manager.get_batch(batch_id))
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "batch not found"})
            return
        if path.startswith("/jobs/"):
            job_id = path.split("/", 2)[2]
            try:
                self._send_json(HTTPStatus.OK, manager.get_job(job_id))
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
            return
            
        # Fallback to serving frontend static files
        dist_dir = settings.frontend_dist_dir
        if not dist_dir.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        file_path = dist_dir / path.lstrip("/")
        if not file_path.exists() or file_path.is_dir():
            file_path = dist_dir / "index.html"
            
        if not file_path.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
            
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"
            
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_batch_zip(self, batch_id: str) -> None:
        try:
            batch = manager.get_batch(batch_id)
        except KeyError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "batch not found"})
            return

        buffer = BytesIO()
        count = 0
        used_names: set[str] = set()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for job in batch.get("jobs", []):
                for result_path in job.get("result_paths") or []:
                    path = Path(str(result_path)).resolve()
                    if not path.exists() or not path.is_file():
                        continue
                    content_type, _ = mimetypes.guess_type(str(path))
                    if not content_type or not content_type.startswith("image/"):
                        continue
                    name = f"{int(job.get('index', count)) + 1:02d}_{path.name}"
                    while name in used_names:
                        count += 1
                        name = f"{int(job.get('index', count)) + 1:02d}_{count}_{path.name}"
                    used_names.add(name)
                    archive.write(path, name)
                    count += 1

        if count == 0:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "no generated images found for this batch"})
            return

        body = buffer.getvalue()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{batch_id}.zip"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, query: str) -> None:
        values = parse_qs(query).get("path") or []
        if not values:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "path is required"})
            return
        requested = Path(unquote(values[0])).resolve()
        allowed_roots = [
            root.resolve() for root in settings.file_roots
        ]
        if not any(requested == root or root in requested.parents for root in allowed_roots):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "file path is not allowed"})
            return
        if not requested.exists() or not requested.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "file not found"})
            return
        content_type, _ = mimetypes.guess_type(str(requested))
        if not content_type or not content_type.startswith("image/"):
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "only image files are supported"})
            return
        body = requested.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/jobs/") and path.endswith("/cancel"):
            job_id = path.split("/")[2]
            try:
                self._send_json(HTTPStatus.OK, manager.cancel_job(job_id))
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if path.startswith("/batches/") and path.endswith("/cancel"):
            batch_id = path.split("/")[2]
            try:
                self._send_json(HTTPStatus.OK, manager.cancel_batch(batch_id))
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "batch not found"})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if path == "/uploads":
            try:
                upload = create_upload(self._read_json(), settings, store)
                self._send_json(HTTPStatus.CREATED, upload)
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
            except (TypeError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if path != "/batches":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            batch = manager.submit_batch(self._read_json())
            self._send_json(HTTPStatus.ACCEPTED, batch)
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
        except (TypeError, ValueError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/uploads/"):
            image_id = path.split("/", 2)[2]
            try:
                deleted = delete_upload(image_id, settings, store)
                self._send_json(HTTPStatus.OK, {"deleted": deleted})
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "upload not found"})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})


def main() -> None:
    server = ThreadingHTTPServer((settings.host, settings.port), Handler)
    print(f"listening on http://{settings.host}:{settings.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

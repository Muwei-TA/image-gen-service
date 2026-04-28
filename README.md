# Image Gen Service

Image Gen Service is a web tool for batch image generation through Codex CLI. Users can enter prompts, upload and reuse reference images, choose aspect ratio and count, watch queued jobs, cancel running work, and reuse generated images as references.

The service runs one PTY-backed Codex job per prompt. Runtime paths are configured through environment variables; the project should not depend on a developer-specific host path.

## Docker Quick Start

Do not publish an image created with `docker commit` from a running development container. That can include Codex credentials, prompts, uploaded references, logs, and generated images. Build release images with `Dockerfile.release` or `scripts/build_release_image.sh`.

Run the published image:

```bash
mkdir -p runtime/data runtime/workspace runtime/codex-home

docker run -d \
  --name image-gen-service \
  -p 8088:8088 \
  -e IMAGE_GEN_API_TOKEN="change-me" \
  -v "$PWD/runtime/data:/data/image-gen-service" \
  -v "$PWD/runtime/workspace:/workspace" \
  -v "$PWD/runtime/codex-home:/data/codex-home" \
  image-gen-service:release
```

Log in to Codex inside the container before submitting jobs:

```bash
docker exec -it --user imagegen image-gen-service codex
```

Open `http://localhost:8088`. If `IMAGE_GEN_API_TOKEN` is set, API clients must send:

```http
Authorization: Bearer change-me
```

## Features

- Prompt input, aspect ratio selection, image count, and reference image library.
- Batch generation with one independent Codex worker per prompt/image.
- Upload, select, reuse, and delete reference images.
- Reuse generated images as references.
- Persistent backend state for batches, jobs, uploads, logs, and generated paths.
- Cancel running jobs and release worker/Codex processes.
- Timeout handling for stuck jobs.
- Frontend served by the same Python HTTP service.
- Clean release image build without Codex login state or user task data.

## Runtime Configuration

All deployment-specific paths should be set through environment variables.

| Variable | Purpose | Default |
| --- | --- | --- |
| `IMAGE_GEN_HOST` | HTTP bind host | `0.0.0.0` |
| `IMAGE_GEN_PORT` | HTTP port | `8088` |
| `IMAGE_GEN_SERVICE_ROOT` | Application root | parent of `app/` |
| `IMAGE_GEN_DATA_DIR` | Persistent metadata, uploads, logs | `${IMAGE_GEN_SERVICE_ROOT}/data` |
| `IMAGE_GEN_DEFAULT_WORKDIR` | Workdir passed to Codex jobs when request omits `workdir` | parent of service root |
| `IMAGE_GEN_CODEX_BIN` | Codex CLI executable | `codex` |
| `IMAGE_GEN_CODEX_HOME` | Codex config/auth directory | `${HOME}/.codex` |
| `IMAGE_GEN_CODEX_USER_HOME` | `HOME` used for Codex subprocesses | current user home |
| `IMAGE_GEN_GENERATED_IMAGES_DIR` | Generated image directory | `${IMAGE_GEN_CODEX_HOME}/generated_images` |
| `IMAGE_GEN_RESULTS_DIR` | Archived result images managed by this service | `${IMAGE_GEN_DATA_DIR}/results` |
| `IMAGE_GEN_FRONTEND_DIST_DIR` | Built frontend directory | `${IMAGE_GEN_SERVICE_ROOT}/frontend/dist` |
| `IMAGE_GEN_FILE_ROOTS` | `os.pathsep` separated roots allowed by `/files` | data dir, default workdir, generated images dir |
| `IMAGE_GEN_JOB_TIMEOUT_SECONDS` | Max job runtime before timeout handling | `1800` |
| `IMAGE_GEN_MAX_CONCURRENCY` | Max number of Codex workers running at once | `2` |
| `IMAGE_GEN_BATCH_PREFIX` | Prompt prefix sent to Codex | `$imagegen` |
| `IMAGE_GEN_API_TOKEN` | Optional bearer token required for all endpoints except `/health` | unset |
| `IMAGE_GEN_CORS_ORIGIN` | Value for `Access-Control-Allow-Origin` | `*` |

Frontend build-time variable:

| Variable | Purpose |
| --- | --- |
| `VITE_IMAGE_GEN_DEFAULT_WORKDIR` | Optional default `workdir` sent by the frontend. If unset, the backend default is used. |

## Start

```bash
cd "$IMAGE_GEN_SERVICE_ROOT"
python3 -m app.main
```

Open the host/port configured by `IMAGE_GEN_HOST` and `IMAGE_GEN_PORT`.

## Security

The service can start Codex jobs and serve image files under `IMAGE_GEN_FILE_ROOTS`. Do not expose it directly to the public internet without access control. For shared or remote deployments, set `IMAGE_GEN_API_TOKEN`, restrict `IMAGE_GEN_CORS_ORIGIN`, and put the service behind a trusted reverse proxy with TLS.

Release images should not contain Codex authentication files or user task data. Keep these paths mounted as runtime volumes instead:

```text
${IMAGE_GEN_DATA_DIR}
${IMAGE_GEN_DEFAULT_WORKDIR}
${IMAGE_GEN_CODEX_HOME}
```

## Build Frontend

```bash
cd frontend
npm ci
npm run build
```

The Python server serves `IMAGE_GEN_FRONTEND_DIST_DIR`.

## API

### Health

```http
GET /health
```

### Upload Reference Image

```http
POST /uploads
Content-Type: application/json
```

```json
{
  "filename": "reference.png",
  "mime_type": "image/png",
  "data": "base64-image-data"
}
```

### List Uploads

```http
GET /uploads
```

### Delete Upload

```http
DELETE /uploads/{image_id}
```

This removes both metadata and the file under `IMAGE_GEN_DATA_DIR/uploads/{image_id}`.

### Submit Batch

```http
POST /batches
Content-Type: application/json
```

```json
{
  "prompt": "21:9 anime livestream screenshot, clean composition --ar 21:9",
  "count": 4,
  "reference_image_ids": ["img_abc123"]
}
```

You can pass `workdir` explicitly when needed:

```json
{
  "prompts": [
    "A neon-lit robot fox in a rainy alley --ar 16:9",
    "A tiny green triangle icon on a plain white background --ar 1:1"
  ],
  "workdir": "/path/inside/container",
  "reference_images": ["/path/inside/container/reference.png"]
}
```

Each prompt starts an independent Codex/PTU worker. Generated image paths are returned in each job's `result_paths`.

### List Batches

```http
GET /batches
```

### Get Batch Detail

```http
GET /batches/{batch_id}
```

### Get Job Detail

```http
GET /jobs/{job_id}
```

### Cancel Job

```http
POST /jobs/{job_id}/cancel
```

Cancellation marks the job as `canceled`, sets `exit_code` to `130`, and kills the worker/Codex process tree when available.

### Cancel Batch

```http
POST /batches/{batch_id}/cancel
```

Cancels all queued/running jobs in that batch.

### Serve Image File

```http
GET /files?path=/absolute/image/path.png
```

Only image files under `IMAGE_GEN_FILE_ROOTS` are served.

## Job States

Job statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`

Batch statuses:

- `queued`
- `running`
- `completed`
- `finished_with_errors`

Timeout handling:

- `pty_worker.py` has a total timeout.
- `manager.py` checks running jobs during API reads.
- If a job exceeds `IMAGE_GEN_JOB_TIMEOUT_SECONDS`, it is marked failed unless generated image paths already exist.

## Data Persistence

The current persistence layer is file-based:

```text
${IMAGE_GEN_DATA_DIR}/state.json
${IMAGE_GEN_DATA_DIR}/jobs/
${IMAGE_GEN_DATA_DIR}/uploads/
${IMAGE_GEN_GENERATED_IMAGES_DIR}/
```

Mount those directories as volumes if you want state to survive container recreation.

Recommended future improvement:

- Move `state.json` to SQLite.
- Add migrations.
- Add retention/cleanup policies for logs and generated images.
- Add backup/restore scripts.

## Clean Docker Release Image

Use the release build instead of `docker commit`. A direct commit can accidentally include Codex credentials, task logs, uploaded images, and generated outputs.

Build inputs must be provided through environment variables:

```bash
export CODEX_BIN=/path/to/codex
export CODEX_RUNTIME=/path/to/codex/runtime

./scripts/build_release_image.sh image-gen-service:release
```

Optional build args can also be provided as environment variables:

```bash
export APP_HOME=/opt/image-gen-service
export APP_DATA_DIR=/data/image-gen-service
export APP_WORKDIR=/workspace
export CODEX_HOME=/opt/codex-home
export CODEX_BIN_PATH=/usr/local/bin/codex
export CODEX_RUNTIME_DIR=/opt/codex-runtime
export VITE_IMAGE_GEN_DEFAULT_WORKDIR=/workspace
```

Run:

```bash
docker run -d \
  --name image-gen-service-release \
  -p 8088:8088 \
  -v image-gen-data:/data/image-gen-service \
  -v image-gen-workspace:/workspace \
  -v codex-home:/opt/codex-home \
  image-gen-service:release
```

After starting a clean image, log in to Codex again inside the container:

```bash
docker exec -it image-gen-service-release codex
```

## Docker Compose

`docker-compose.yml` is environment-driven. Set host paths through `.env`:

```env
HOST_DATA_DIR=./runtime/data
HOST_WORKDIR=./runtime/workspace
HOST_CODEX_HOME=./runtime/codex-home
IMAGE_GEN_PORT=8088
```

Then run:

```bash
docker compose up -d --build
```

## Security Notes

- Do not ship Codex auth files.
- Do not ship Codex logs, sessions, or history.
- Do not ship `data/uploads`, `data/jobs`, or generated images when publishing a reusable image.
- Configure served file roots with `IMAGE_GEN_FILE_ROOTS`.

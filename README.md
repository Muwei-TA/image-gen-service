# Image Gen Service

Image Gen Service is a browser-based batch image generation workspace powered by Codex CLI. It lets you enter prompts, choose aspect ratios and image counts, upload reference images, watch multiple jobs run in parallel, cancel stuck jobs, and download generated results.

The app is designed to run as a Docker service. Your Codex login, prompts, uploads, logs, and generated images stay in mounted runtime folders, not in the published image.

## What You Get

- Web UI for prompt-based image generation.
- Batch generation with one Codex worker per image.
- Aspect ratio and count controls.
- Reference image upload and reuse.
- Generated image reuse as future references.
- Job queue with running, completed, failed, and canceled states.
- Batch zip download.
- Docker image that does not include Codex credentials or user history.

## Quick Start

Create runtime folders:

```bash
mkdir -p runtime/data runtime/workspace runtime/codex-home runtime/images
```

Start the service:

```bash
docker run -d \
  --name image-gen-service \
  -p 8088:8088 \
  -v "$PWD/runtime/data:/data/image-gen-service" \
  -v "$PWD/runtime/workspace:/workspace" \
  -v "$PWD/runtime/codex-home:/data/codex-home" \
  -v "$PWD/runtime/images:/data/codex-home/generated_images" \
  muwei517/image-gen-service:latest
```

Log in to Codex inside the container:

```bash
docker exec -it --user imagegen image-gen-service codex
```

Open:

```text
http://localhost:8088
```

## Docker Compose

Create `docker-compose.yml`:

```yaml
services:
  image-gen-service:
    image: muwei517/image-gen-service:latest
    container_name: image-gen-service
    ports:
      - "8088:8088"
    environment:
      IMAGE_GEN_MAX_CONCURRENCY: "2"
    volumes:
      - ./runtime/data:/data/image-gen-service
      - ./runtime/workspace:/workspace
      - ./runtime/codex-home:/data/codex-home
      - ./runtime/images:/data/codex-home/generated_images
    restart: unless-stopped
```

Run:

```bash
mkdir -p runtime/data runtime/workspace runtime/codex-home runtime/images
docker compose up -d
docker exec -it --user imagegen image-gen-service codex
```

## Using The App

1. Open the web UI.
2. Confirm the Codex status banner is clear. If it says Codex is not logged in, run the login command above.
3. Enter a prompt.
4. Choose an aspect ratio and count.
5. Optionally upload or select reference images.
6. Submit the batch.
7. Watch each image job complete independently.
8. Reuse generated images as references or download a batch zip.

Prompts can include normal image instructions and aspect ratio hints. The UI appends the selected aspect ratio before submitting the job.

## Runtime Folders

These folders should be mounted if you want data to survive container updates:

| Host folder | Container path | Contains |
| --- | --- | --- |
| `./runtime/data` | `/data/image-gen-service` | batches, jobs, uploads, archived results, service state |
| `./runtime/workspace` | `/workspace` | default Codex working directory |
| `./runtime/codex-home` | `/data/codex-home` | Codex login and settings |
| `./runtime/images` | `/data/codex-home/generated_images` | generated images |

Back up these folders if the generated work matters to you.

## Configuration

Most users only need these variables:

| Variable | Default | Description |
| --- | --- | --- |
| `IMAGE_GEN_MAX_CONCURRENCY` | `2` | Maximum number of Codex jobs running at once. Lower this if your machine or account quota is limited. |
| `IMAGE_GEN_JOB_TIMEOUT_SECONDS` | `1800` | Maximum job runtime before timeout handling. |
| `IMAGE_GEN_CORS_ORIGIN` | `*` | CORS origin. Restrict this behind a reverse proxy if needed. |
| `IMAGE_GEN_PORT` | `8088` | Port used inside the container. Usually leave this unchanged and map host ports with Docker. |

Advanced variables:

| Variable | Default in image | Description |
| --- | --- | --- |
| `IMAGE_GEN_DATA_DIR` | `/data/image-gen-service` | Persistent service state. |
| `IMAGE_GEN_DEFAULT_WORKDIR` | `/workspace` | Workdir passed to Codex jobs when the request omits `workdir`. |
| `IMAGE_GEN_CODEX_BIN` | `/usr/local/bin/codex` | Codex CLI executable. |
| `IMAGE_GEN_CODEX_HOME` | `/data/codex-home` | Codex auth/config directory. |
| `IMAGE_GEN_CODEX_USER_HOME` | `/home/imagegen` | `HOME` used for Codex subprocesses. |
| `IMAGE_GEN_GENERATED_IMAGES_DIR` | `/data/codex-home/generated_images` | Codex generated image directory. |
| `IMAGE_GEN_RESULTS_DIR` | `${IMAGE_GEN_DATA_DIR}/results` | Service-managed result archive. |
| `IMAGE_GEN_FILE_ROOTS` | data, workspace, generated images | Allowed roots for serving image files through `/files`. |
| `IMAGE_GEN_FRONTEND_DIST_DIR` | `/opt/image-gen-service/frontend/dist` | Built frontend directory. |
| `IMAGE_GEN_BATCH_PREFIX` | `$imagegen` | Prefix sent to Codex for each image job. |

## Updating

Pull the latest image and restart:

```bash
docker pull muwei517/image-gen-service:latest
docker stop image-gen-service
docker rm image-gen-service

docker run -d \
  --name image-gen-service \
  -p 8088:8088 \
  -v "$PWD/runtime/data:/data/image-gen-service" \
  -v "$PWD/runtime/workspace:/workspace" \
  -v "$PWD/runtime/codex-home:/data/codex-home" \
  -v "$PWD/runtime/images:/data/codex-home/generated_images" \
  muwei517/image-gen-service:latest
```

Mounted runtime folders keep your data.

## Security

Do not expose this service directly to the public internet. The service can start Codex jobs and serve image files under configured file roots. Put it behind a trusted reverse proxy, VPN, or other access control if remote access is needed.

Recommended for remote deployments:

- Use HTTPS through a trusted reverse proxy.
- Restrict `IMAGE_GEN_CORS_ORIGIN`.
- Keep `/data/codex-home` private.
- Do not publish mounted runtime folders.

The published Docker image is intended to exclude:

- Codex `auth.json`
- Codex logs, sessions, and history
- uploaded reference images
- generated images
- job logs and previous prompts

## Troubleshooting

### The UI says Codex is not logged in

Run:

```bash
docker exec -it --user imagegen image-gen-service codex
```

Then refresh the web UI.

### Jobs stay queued or run slowly

Lower concurrency:

```bash
-e IMAGE_GEN_MAX_CONCURRENCY=1
```

Also check your Codex account limits and network access.

### Generated images do not show

Make sure the generated image path is under one of the allowed roots in `IMAGE_GEN_FILE_ROOTS`. The default Docker image allows:

```text
/data/image-gen-service
/workspace
/data/codex-home/generated_images
```

### Container cannot write to mounted folders

The entrypoint tries to fix permissions for mounted folders. If your host filesystem blocks ownership changes, create writable folders manually or use Docker named volumes.

## HTTP API

Common endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service and Codex status. |
| `POST` | `/batches` | Submit a batch. |
| `GET` | `/batches` | List batches. |
| `GET` | `/batches/{batch_id}` | Batch detail and jobs. |
| `GET` | `/batches/{batch_id}/download` | Download generated images as zip. |
| `GET` | `/jobs/{job_id}` | Job detail. |
| `POST` | `/jobs/{job_id}/cancel` | Cancel a job. |
| `POST` | `/batches/{batch_id}/cancel` | Cancel queued/running jobs in a batch. |
| `POST` | `/uploads` | Upload a reference image. |
| `GET` | `/uploads` | List uploaded reference images. |
| `DELETE` | `/uploads/{image_id}` | Delete an uploaded reference image. |
| `GET` | `/files?path=/absolute/image/path.png` | Serve an allowed image file. |

Submit a batch:

```bash
curl -X POST http://localhost:8088/batches \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A small robot painting a sunset --ar 16:9",
    "count": 2
  }'
```

Upload a reference image:

```json
{
  "filename": "reference.png",
  "mime_type": "image/png",
  "data": "base64-image-data"
}
```

## Development

Run backend tests:

```bash
python3 -m unittest discover -s tests
```

Build the frontend:

```bash
cd frontend
npm ci
npm run build
```

Run the Python service directly:

```bash
python3 -m app.main
```

## Building A Release Image

Use the release build instead of `docker commit`. A direct commit can accidentally include Codex credentials, task logs, uploaded images, and generated outputs.

Build inputs:

```bash
export CODEX_BIN=/path/to/codex
export CODEX_RUNTIME=/path/to/codex/runtime

./scripts/build_release_image.sh image-gen-service:release
```

Optional build arguments can be provided as environment variables:

```bash
export APP_HOME=/opt/image-gen-service
export APP_DATA_DIR=/data/image-gen-service
export APP_WORKDIR=/workspace
export CODEX_HOME=/data/codex-home
export CODEX_BIN_PATH=/usr/local/bin/codex
export CODEX_RUNTIME_DIR=/opt/codex-runtime
export VITE_IMAGE_GEN_DEFAULT_WORKDIR=/workspace
```

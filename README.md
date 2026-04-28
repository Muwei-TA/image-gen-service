# Image Gen Service

[中文文档](README.zh-CN.md) | [Agent deployment guide](README_FOR_AGENT.md)

Image Gen Service is a browser-based batch image generation workspace powered by Codex CLI. It lets you enter prompts, choose aspect ratios and image counts, upload reference images, watch multiple jobs run in parallel, cancel stuck jobs, and download generated results.

The app is designed to run as a Docker service. Your Codex login, prompts, uploads, logs, and generated images stay in mounted runtime folders, not in the published image.

The current published image does not require a service API token. If an endpoint returns `unauthorized`, make sure you are not running an old container, an old image, or a reverse proxy that adds its own authentication.

If you want an AI agent or automation tool to deploy this service for you, give it [README_FOR_AGENT.md](README_FOR_AGENT.md). The regular README is focused on end-user deployment and usage of the published Docker image.

## What You Get

- Web UI for prompt-based image generation.
- Batch generation with one Codex worker per image.
- Aspect ratio and count controls. The UI supports `1-50` images per batch.
- Reference image upload and reuse.
- Multiple reference images per batch.
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
      IMAGE_GEN_MAX_CONCURRENCY: "8"
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

Reference images can be uploaded in the UI, selected from previous uploads, or reused from generated results. When reference images are selected, each Codex job receives the prompt plus `--image` arguments for the selected images.

The image count is not the same as concurrency. A batch can contain more images than the current concurrency limit. `IMAGE_GEN_MAX_CONCURRENCY` only controls how many Codex jobs run at the same time.

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
| `IMAGE_GEN_MAX_CONCURRENCY` | `8` | Maximum number of Codex jobs running at once. Lower this if your machine or account quota is limited. |
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

User runtime data lives in the mounted folders. Do not publish, share, or bake those folders into a public image.

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

### API returns unauthorized

The current service image does not require an API token. If you see `{"error":"unauthorized"}`, check that:

- the container was recreated from `muwei517/image-gen-service:latest`;
- the browser is not hitting an old container on the same port;
- a reverse proxy, gateway, or cached frontend is not adding its own authentication flow.

Useful checks:

```bash
docker pull muwei517/image-gen-service:latest
docker inspect image-gen-service --format '{{.Config.Image}}'
curl -i http://127.0.0.1:8088/health
```

### Jobs fail with no generated image detected

The service marks a job as successful only after it finds an output image. Check:

```bash
docker logs --tail 200 image-gen-service
docker exec image-gen-service codex --version
curl -fsS http://127.0.0.1:8088/health
```

Common causes:

- Codex is not logged in inside the mounted `/data/codex-home`.
- Codex exits without generating an image.
- The generated image is not written under `/data/codex-home/generated_images`.
- Mounted folders are not writable by the container.
- Concurrency is too high for the host or account quota.

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
    "count": 4
  }'
```

Submit a batch with uploaded reference image IDs:

```bash
curl -X POST http://localhost:8088/batches \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a cinematic product image --ar 16:9",
    "count": 4,
    "reference_image_ids": ["upload_id_1", "upload_id_2"]
  }'
```

Submit a batch with existing image paths:

```bash
curl -X POST http://localhost:8088/batches \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Use the references for composition and color --ar 1:1",
    "count": 6,
    "reference_images": [
      "/data/codex-home/generated_images/reference-1.png",
      "/data/codex-home/generated_images/reference-2.png"
    ]
  }'
```

`reference_images` paths must be under an allowed `IMAGE_GEN_FILE_ROOTS` directory.

Upload a reference image:

```json
{
  "filename": "reference.png",
  "mime_type": "image/png",
  "data": "base64-image-data"
}
```

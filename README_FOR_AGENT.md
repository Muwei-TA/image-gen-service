# README For Agent

This document is for AI coding agents or automation agents that need to deploy Image Gen Service with Docker for a user.

The goal is to deploy the published Docker image, preserve user data in mounted folders, complete Codex login, verify service health, and avoid leaking credentials, local development files, documentation-only files, runtime state, or generated content.

## Agent Goal

Deploy a working Image Gen Service instance:

- Docker image: `muwei517/image-gen-service:latest`
- Web port: `8088` by default
- Runtime data persisted under a user-chosen directory
- Codex login stored in a mounted `codex-home` directory
- Generated images stored in a mounted `images` directory at `/data/codex-home/generated_images`
- Health endpoint verified
- User given the final URL and Codex login instructions
- Published image contents kept separate from user runtime data and local-only development work

## Safety Rules

Follow these rules before running commands:

- Do not use `docker commit` to publish or preserve this app.
- Do not copy a user's existing `/root/.codex`, `.codex`, generated images, uploads, logs, `.env` files, `runtime/`, or `data/` into a public image.
- Do not print DockerHub tokens, GitHub tokens, sudo passwords, or Codex auth files.
- Do not publish local `mcp/` development work or documentation-only files into the release image.
- Prefer mounted runtime folders over data stored inside the container.
- Do not expose this service directly to the public internet. Use a trusted reverse proxy, VPN, or external access control for remote use.

## Inputs To Collect

Ask or infer these values:

| Input | Default | Notes |
| --- | --- | --- |
| Deploy directory | `./image-gen-service` | Host folder that will contain runtime data. |
| Host port | `8088` | Change if occupied. |
| Max concurrency | `50` | The published image defaults to 50, matching the UI maximum. Use `1-2` on low-resource machines or quota-limited accounts. |
| Docker Compose available | auto-detect | Prefer compose when available. |

## Preflight Checks

Run:

```bash
docker --version
docker compose version
```

Check port availability:

```bash
ss -tulpn | grep ':8088' || true
```

If port `8088` is occupied, choose another host port and keep the container port `8088`.

Pull image:

```bash
docker pull muwei517/image-gen-service:latest
```

## Recommended Docker Compose Deployment

Create runtime folders:

```bash
mkdir -p image-gen-service/runtime/data \
         image-gen-service/runtime/workspace \
         image-gen-service/runtime/codex-home \
         image-gen-service/runtime/images
```

Create `image-gen-service/docker-compose.yml`:

```yaml
services:
  image-gen-service:
    image: muwei517/image-gen-service:latest
    container_name: image-gen-service
    ports:
      - "${IMAGE_GEN_HOST_PORT:-8088}:8088"
    environment:
      IMAGE_GEN_MAX_CONCURRENCY: "${IMAGE_GEN_MAX_CONCURRENCY:-50}"
      IMAGE_GEN_CORS_ORIGIN: "${IMAGE_GEN_CORS_ORIGIN:-*}"
    volumes:
      - ./runtime/data:/data/image-gen-service
      - ./runtime/workspace:/workspace
      - ./runtime/codex-home:/data/codex-home
      - ./runtime/images:/data/codex-home/generated_images
    restart: unless-stopped
```

Create `image-gen-service/.env`:

```env
IMAGE_GEN_HOST_PORT=8088
IMAGE_GEN_MAX_CONCURRENCY=50
IMAGE_GEN_CORS_ORIGIN=*
```

Start:

```bash
cd image-gen-service
docker compose up -d
```

## Docker Run Deployment

Use this when Docker Compose is unavailable:

```bash
mkdir -p image-gen-service/runtime/data \
         image-gen-service/runtime/workspace \
         image-gen-service/runtime/codex-home \
         image-gen-service/runtime/images

docker run -d \
  --name image-gen-service \
  -p 8088:8088 \
  -e IMAGE_GEN_MAX_CONCURRENCY="50" \
  -v "$PWD/image-gen-service/runtime/data:/data/image-gen-service" \
  -v "$PWD/image-gen-service/runtime/workspace:/workspace" \
  -v "$PWD/image-gen-service/runtime/codex-home:/data/codex-home" \
  -v "$PWD/image-gen-service/runtime/images:/data/codex-home/generated_images" \
  muwei517/image-gen-service:latest
```

## Codex Login

After the container is running, the user must log in to Codex inside the container:

```bash
docker exec -it --user imagegen image-gen-service codex
```

If the environment does not support interactive commands, stop and ask the user to run this command manually.

Do not attempt to copy Codex auth from another machine unless the user explicitly requests it and understands the risk.

## Verification

Check container status:

```bash
docker ps --filter name=image-gen-service
```

Check health:

```bash
curl -fsS http://127.0.0.1:8088/health
```

Expected healthy shape:

```json
{
  "ok": true,
  "codex": {
    "available": true,
    "authenticated": true,
    "auth_path": "/data/codex-home/auth.json",
    "max_concurrency": 50
  }
}
```

Before Codex login, `authenticated` can be `false`. That means Docker deployment is working but Codex login is still needed.

Check API access:

```bash
curl -i http://127.0.0.1:8088/batches
```

The request should return `200`.

## Final Response To User

Provide:

- URL: `http://<host>:<port>`
- Codex login command
- Runtime directory path
- Basic management commands:

```bash
docker logs -f image-gen-service
docker restart image-gen-service
docker stop image-gen-service
```

## Upgrade Procedure

For Compose:

```bash
cd image-gen-service
docker compose pull
docker compose up -d
```

For Docker run:

```bash
docker pull muwei517/image-gen-service:latest
docker stop image-gen-service
docker rm image-gen-service
```

Then rerun the original `docker run` command with the same volume mounts.

Never delete the runtime folders unless the user explicitly asks to remove all data.

## Backup

Back up:

```text
image-gen-service/runtime/data
image-gen-service/runtime/workspace
image-gen-service/runtime/codex-home
image-gen-service/runtime/images
```

The most sensitive folder is:

```text
image-gen-service/runtime/codex-home
```

It contains Codex authentication after login.

## Troubleshooting

### Port already in use

Use another host port:

```yaml
ports:
  - "18088:8088"
```

Then open `http://localhost:18088`.

### Codex unavailable

Check:

```bash
docker exec image-gen-service codex --version
```

If the command is missing, the wrong image may be running.

### Codex not authenticated

Run:

```bash
docker exec -it --user imagegen image-gen-service codex
```

### Permission errors on mounted folders

The container entrypoint tries to `chown` mounted folders. Some NAS or network filesystems block ownership changes. Use Docker named volumes or choose a local filesystem path with write access.

### Jobs fail or timeout

Check logs:

```bash
docker logs --tail 200 image-gen-service
```

Lower concurrency:

```env
IMAGE_GEN_MAX_CONCURRENCY=1
```

Restart:

```bash
docker restart image-gen-service
```

### Images do not render in the UI

Ensure generated image paths are under allowed roots:

```text
/data/image-gen-service
/workspace
/data/codex-home/generated_images
```

If custom roots are needed, set `IMAGE_GEN_FILE_ROOTS` with colon-separated paths.

## Publishing Or Rebuilding

Only use the release build process:

```bash
export CODEX_BIN=/path/to/codex
export CODEX_RUNTIME=/path/to/codex/runtime
./scripts/build_release_image.sh image-gen-service:release
```

Do not publish images made from a running user container. The release build context must exclude docs, local `.env` files, runtime folders, Codex auth material, uploaded/generated images, and local `mcp/` development work.

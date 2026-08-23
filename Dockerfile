# image-gen-service - self-contained image (Vue frontend + FastAPI + Codex CLI)
#
# One command builds a fully working image, including the Codex image-generation
# runtime. No external context or pre-built Codex runtime required.
#
#   docker build -t image-gen-service:latest .
#
# Codex CLI is downloaded from the official openai/codex GitHub release. Pin the
# version with --build-arg CODEX_VERSION=... if you want a specific release.

# ---- Stage 1: build the Vue frontend ----
FROM node:22-bookworm AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime ----
FROM python:3.12-slim

ARG CODEX_VERSION=0.128.0
ARG CODEX_TRIPLE=x86_64-unknown-linux-musl
ARG CODEX_URL=https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-${CODEX_TRIPLE}.tar.gz

ENV PYTHONUNBUFFERED=1 \
    IMAGE_GEN_HOST=0.0.0.0 \
    IMAGE_GEN_PORT=8088 \
    IMAGE_GEN_SERVICE_ROOT=/opt/image-gen-service \
    IMAGE_GEN_DATA_DIR=/data/image-gen-service \
    IMAGE_GEN_DEFAULT_WORKDIR=/workspace \
    IMAGE_GEN_FRONTEND_DIST_DIR=/opt/image-gen-service/frontend/dist \
    IMAGE_GEN_CODEX_HOME=/data/codex-home \
    IMAGE_GEN_CODEX_BIN=/usr/local/bin/codex \
    IMAGE_GEN_CODEX_USER_HOME=/root \
    IMAGE_GEN_GENERATED_IMAGES_DIR=/data/codex-home/generated_images \
    IMAGE_GEN_FILE_ROOTS=/data/image-gen-service:/workspace:/data/codex-home/generated_images \
    HOME=/root

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/image-gen-service

COPY pyproject.toml ./
COPY app ./app
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN pip install --no-cache-dir .

# Codex CLI (official single-file static musl binary from GitHub releases)
RUN set -eux \
    && curl -fsSL -o /tmp/codex.tar.gz "${CODEX_URL}" \
    && tar -xzf /tmp/codex.tar.gz -C /tmp \
    && mv "/tmp/codex-${CODEX_TRIPLE}" /usr/local/bin/codex \
    && chmod 755 /usr/local/bin/codex \
    && /usr/local/bin/codex --version \
    && rm -f /tmp/codex.tar.gz

EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/health', timeout=3)"
CMD ["image-gen-service"]

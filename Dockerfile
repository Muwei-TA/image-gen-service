FROM node:22-bookworm AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    IMAGE_GEN_HOST=0.0.0.0 \
    IMAGE_GEN_PORT=8088 \
    IMAGE_GEN_SERVICE_ROOT=/opt/image-gen-service \
    IMAGE_GEN_DATA_DIR=/data/image-gen-service \
    IMAGE_GEN_DEFAULT_WORKDIR=/workspace \
    IMAGE_GEN_FRONTEND_DIST_DIR=/opt/image-gen-service/frontend/dist

WORKDIR /opt/image-gen-service
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/health', timeout=3)"
CMD ["image-gen-service"]

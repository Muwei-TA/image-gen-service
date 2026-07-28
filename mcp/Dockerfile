FROM python:3.12.11-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/Muwei-TA/image-gen-service" \
      org.opencontainers.image.title="image-gen-service-mcp" \
      org.opencontainers.image.description="Streamable HTTP MCP adapter for Image Gen Service"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY image_gen_mcp ./image_gen_mcp
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 mcp
USER mcp

EXPOSE 8090

HEALTHCHECK --interval=20s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)"

ENTRYPOINT ["image-gen-service-mcp"]

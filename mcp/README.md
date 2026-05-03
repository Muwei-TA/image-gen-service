# Image Gen Service MCP Wrapper

This directory contains an independent MCP server that wraps the existing `image-gen-service` HTTP API.

The MCP server is intentionally a thin adapter:

- It calls the running HTTP service over `IMAGE_GEN_MCP_BASE_URL`.
- It does not import or mutate the backend internals directly.
- It does not expose shell access, arbitrary file reads, raw `/files?path=...`, raw `workdir`, or raw local reference image paths.
- Reference images are uploaded through the service and then used by `image_id`.

## Install

```bash
cd /home/sever/image-gen-service/mcp
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Run

Start the existing image generation service first, then run:

```bash
IMAGE_GEN_MCP_BASE_URL=http://127.0.0.1:8088 image-gen-service-mcp
```

## Claude Code MCP config example

```json
{
  "mcpServers": {
    "image-gen-service": {
      "command": "/home/sever/image-gen-service/mcp/.venv/bin/image-gen-service-mcp",
      "env": {
        "IMAGE_GEN_MCP_BASE_URL": "http://127.0.0.1:8088"
      }
    }
  }
}
```

## Default tools

- `health_check`
- `create_batch`
- `get_batch`
- `get_job`
- `list_batches`
- `list_uploads`
- `upload_reference_image`

Cancel tools are disabled by default. Enable them with:

```bash
IMAGE_GEN_MCP_ENABLE_CANCEL_TOOLS=true
```

This adds:

- `cancel_batch`
- `cancel_job`

## Configuration

| Variable | Default |
| --- | --- |
| `IMAGE_GEN_MCP_BASE_URL` | `http://127.0.0.1:8088` |
| `IMAGE_GEN_MCP_TIMEOUT_SECONDS` | `30` |
| `IMAGE_GEN_MCP_MAX_BATCH_COUNT` | `50` |
| `IMAGE_GEN_MCP_MAX_PROMPTS` | `50` |
| `IMAGE_GEN_MCP_MAX_PROMPT_CHARS` | `8000` |
| `IMAGE_GEN_MCP_MAX_UPLOAD_BYTES` | `10485760` |
| `IMAGE_GEN_MCP_REDACT_PATHS` | `true` |
| `IMAGE_GEN_MCP_ENABLE_CANCEL_TOOLS` | `false` |

## Safety boundaries

The first version intentionally does not expose:

- arbitrary file access
- shell execution
- raw `/files?path=...`
- upload deletion
- batch zip binary download
- raw `workdir`
- raw `reference_images` local paths

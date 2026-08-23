# Codex Image Studio MCP Wrapper

Streamable HTTP MCP server that wraps the `codex-image-studio` HTTP API into MCP tools.

## Endpoints

- `POST /mcp` - Streamable HTTP MCP
- `GET /health` - Service and backend Codex auth status
- `GET /media/{token}` - Short-lived generated image download

## Default tools

- `imagegen` - Synchronous generation with inline ImageContent and optional channel-safe media URLs
- `health_check` - Check backend availability and Codex authentication
- `create_batch` - Create an asynchronous image generation batch
- `get_batch` - Get batch state and safe result metadata
- `get_job` - Get a single job state and safe result metadata
- `get_batch_images` - Publish completed batch images as short-lived HTTP URLs
- `list_batches` - List recent batches, optionally filtered by status
- `upload_reference_image` - Upload a base64/data-URL reference image
- `list_uploads` - List uploaded reference images

Cancel tools are disabled by default. Enable with:

```bash
IMAGE_GEN_MCP_ENABLE_CANCEL_TOOLS=true
```

This adds `cancel_batch` and `cancel_job`.

## Channel media delivery

Set `IMAGE_GEN_MCP_MEDIA_BASE_URL` to an MCP service root URL that the Agent
runtime can reach:

```env
IMAGE_GEN_MCP_MEDIA_BASE_URL=http://codex-image-studio-mcp:8090
IMAGE_GEN_MCP_MEDIA_TTL_SECONDS=3600
```

When enabled, `imagegen` keeps the standard inline MCP image and also returns:

- a standard MCP `resource_link`;
- `structuredContent.images[].url`;
- a `MEDIA:<url>` text fallback for chat-channel adapters.

After an asynchronous `create_batch`, call `get_batch_images(batch_id)` for the
same URL-only delivery format. Some MCP gateways may drop `structuredContent`;
the `resource_link` and `MEDIA:<url>` carry the same URL.

URLs use 256-bit random capability tokens, expire after one hour by default,
and never expose backend paths. The in-memory cache defaults to 100 images and
200 MiB; restarting the MCP container invalidates all URLs.

## Local run

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
IMAGE_GEN_MCP_BASE_URL=http://127.0.0.1:8088 .venv/bin/codex-image-studio-mcp
```

Test:

```bash
curl http://127.0.0.1:8090/health
```

## Docker

The MCP server is included in the root `docker-compose.yml`. When both containers
are on `mcp-net`, the upstream address is:

```text
http://codex-image-studio:8088
```

Gateway config example:

```toml
[[servers.proxied.streamable_http]]
name = "imagegen"
url = "http://codex-image-studio-mcp:8090/mcp"
protocol = "streamable-http"
timeout = 1800
reconnect_on_failure = true
auto_start = true
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `IMAGE_GEN_MCP_BASE_URL` | `http://127.0.0.1:8088` | Backend codex-image-studio URL |
| `IMAGE_GEN_MCP_HOST` | `0.0.0.0` | MCP server bind host |
| `IMAGE_GEN_MCP_PORT` | `8090` | MCP server port |
| `IMAGE_GEN_MCP_PATH` | `/mcp` | MCP endpoint path |
| `IMAGE_GEN_MCP_TIMEOUT_SECONDS` | `30` | HTTP client timeout |
| `IMAGE_GEN_MCP_GENERATION_TIMEOUT_SECONDS` | `1800` | Max wait for image generation |
| `IMAGE_GEN_MCP_POLL_INTERVAL_SECONDS` | `1` | Poll interval for batch completion |
| `IMAGE_GEN_MCP_MAX_BATCH_COUNT` | `50` | Max images per batch |
| `IMAGE_GEN_MCP_MAX_PROMPTS` | `50` | Max prompts in multi-prompt batch |
| `IMAGE_GEN_MCP_MAX_PROMPT_CHARS` | `8000` | Max prompt length |
| `IMAGE_GEN_MCP_MAX_UPLOAD_BYTES` | `10485760` | Max upload size |
| `IMAGE_GEN_MCP_MAX_INLINE_IMAGES` | `8` | Max inline images for `imagegen` |
| `IMAGE_GEN_MCP_MAX_INLINE_IMAGE_BYTES` | `20971520` | Max inline image download size |
| `IMAGE_GEN_MCP_MEDIA_BASE_URL` | empty | Agent-reachable MCP root URL; enables media delivery |
| `IMAGE_GEN_MCP_MEDIA_TTL_SECONDS` | `3600` | Media URL lifetime |
| `IMAGE_GEN_MCP_MEDIA_MAX_ITEMS` | `100` | Max cached media items |
| `IMAGE_GEN_MCP_MEDIA_MAX_TOTAL_BYTES` | `209715200` | Max media cache bytes |
| `IMAGE_GEN_MCP_REDACT_PATHS` | `true` | Redact filesystem paths in responses |
| `IMAGE_GEN_MCP_ENABLE_CANCEL_TOOLS` | `false` | Enable cancel tools |

## Safety boundaries

The MCP server does not expose:

- Arbitrary file access
- Shell execution
- Raw `/files?path=...` endpoints
- Upload deletion
- Batch zip binary download
- Raw `workdir` or `reference_images` local paths

# Image Gen Service

[English README](README.md) | [智能体说明](README_FOR_AGENT.md)

Image Gen Service 是一个基于 **Vue 3 + FastAPI + Codex CLI** 的本地优先生图工作台，支持 Windows、macOS 和 Linux 原生运行，也保留 Docker 构建能力。

## 主要能力

- 全新的响应式 Vue 工作台：提示词、比例、数量、参考图、队列、历史、预览和批量下载集中在一个界面。
- FastAPI 后端和 OpenAPI 文档，不再依赖 tmux 或 POSIX PTY。
- 用户可在网页发起 Codex 设备码登录；浏览器只接收官方授权地址和一次性代码，不会接触本地凭证。
- 作品流支持把全部已生成图片按批次打包为一个 ZIP 下载。
- 生图任务最高并发量为 9，可通过 `IMAGE_GEN_MAX_CONCURRENCY` 调低。
- Windows 原生启动、任务终止和批量取消。
- 保留原有批次、任务、上传、文件和 MCP 接口兼容性。

## Windows 原生运行

请先安装：

- Python 3.11 或更高版本
- [uv](https://docs.astral.sh/uv/)
- Node.js 20 或更高版本
- Codex CLI

然后在 PowerShell 中运行：

```powershell
git clone https://github.com/Muwei-TA/image-gen-service.git
cd image-gen-service
.\scripts\start-windows.ps1
```

也可以双击 `scripts\start-windows.cmd`。启动后打开 `http://127.0.0.1:8088`。

开发模式：

```powershell
.\scripts\start-windows.ps1 -Dev
```

此时 Vue 位于 `http://127.0.0.1:5173`，API 请求会代理到 FastAPI。

## macOS / Linux 原生运行

```bash
./scripts/start-unix.sh
```

## Codex 网页登录

1. 打开工作台中的“Codex 账户”卡片。
2. 点击“连接 Codex”。
3. 复制页面显示的一次性设备码。
4. 打开页面提供的 OpenAI 官方授权地址并输入设备码。
5. 授权完成后，工作台会自动刷新登录状态。

认证由本机 Codex CLI 完成并保存在 Codex 自己的凭证存储中。服务不会读取凭证内容，也不会通过 API 返回凭证文件路径或令牌。

## Docker

Docker 是可选部署方式。要测试当前源码，请先本地构建：

```bash
docker build -t image-gen-service:local .
docker run --rm -p 8088:8088 image-gen-service:local
```

标准 `Dockerfile` 构建 Vue 与 FastAPI 服务；需要在镜像内生成图片时，还必须提供可执行的 Codex CLI。正式发布流程使用 `Dockerfile.release` 把 Codex 运行时加入镜像。不要把本机 `.codex`、令牌、上传内容或生成图写入公开镜像。

## 开发与验证

```bash
uv sync --extra dev
cd frontend
npm ci
npm run lint
npm run build
cd ..
uv run pytest -q
uv run uvicorn app.main:app --reload --port 8088
```

关键接口：

- `GET /health`
- `GET /api/auth/status`
- `POST /api/auth/login/device`
- `GET /api/auth/login/device`
- `DELETE /api/auth/login/device`
- `POST /api/auth/logout`
- `GET /docs`

环境变量示例见 `.env.example`。运行数据默认写入 `data/`，生成结果与 Codex 配置位置可以通过 `IMAGE_GEN_*` 变量修改。

## 出口代理

设置 `IMAGE_GEN_PROXY_URL` 后，Codex 的登录、登录状态检查和图片生成进程会统一通过该出口代理访问网络。支持 `http://`、`https://`、`socks5://` 和 `socks5h://`，代理 URL 可以包含用户名和密码：

```dotenv
IMAGE_GEN_PROXY_URL=http://user:password@proxy.example.com:7890
IMAGE_GEN_NO_PROXY=127.0.0.1,localhost,image-gen-service,image-gen-mcp
```

Docker Compose 会自动把这两个变量传入后端。修改后需要重新创建 `image-gen` 容器。工作台状态栏会标记代理已启用；`/api/health` 和 `/api/auth/status` 只返回脱敏后的代理协议、主机和端口，不会返回凭据或完整 URL。未设置时不会主动覆盖进程原有的网络环境。

## MCP

`mcp/` 内保留 Streamable HTTP MCP 适配器，默认端点为 `/mcp`，健康检查为 `/health`。后端地址由 `IMAGE_GEN_MCP_BASE_URL` 指定，详细说明见 `mcp/README.md`。

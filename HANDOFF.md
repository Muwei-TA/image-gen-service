# Image Gen Service Handoff

## 当前目标
在 `/vol1/1000/docker/ubuntu/workspace/image-gen-service` 提供一个批量生图服务：HTTP 提交任务、按 job 启动独立 Codex 终端、执行 `$imagegen`/Image Gen 请求、回写状态和结果。

## 当前实现状态
### 服务入口
- `app/main.py` 提供 HTTP 接口：
  - `GET /health`
  - `POST /batches`
  - `GET /batches/{id}`
  - `GET /jobs/{id}`
- 容器内服务监听端口：`8088`。
- 容器内 `curl http://127.0.0.1:8088/health` 已确认正常。

### 执行链路
- `app/codex_runner.py`
  - 拼接 `codex` prompt，默认前缀是 `$imagegen`。
  - 命令显式使用 `HOME=/home/imagegen`、`CODEX_HOME=/data/codex-home`、`TERM=xterm-256color`。
  - 默认 Codex 路径：`/vol1/1000/docker/ubuntu/bin/codex`。
- `app/tmux_runner.py`
  - 保留历史类名 `TerminalRunner`，但不再依赖 tmux/script。
  - 启动 `app/pty_worker.py`，由 Python PTY worker 执行实际命令。
- `app/pty_worker.py`
  - 使用标准库 `pty` 创建可读写伪终端。
  - 对 Codex TUI 的基础终端查询做响应，例如 cursor position、device attributes、OSC 颜色查询。
  - 检测 `generated_images/*.png` 结果路径。
  - 生成结果出现后发送 EOF 请求 CLI 退出；如果 TUI 空闲不退出，会停止 CLI 并返回成功。
- `app/manager.py`
  - 提交 batch 时创建 job 状态记录。
  - 启动 worker 子进程并轮询日志/进程状态。
  - 子进程返回 0 时把 job 标记为 `succeeded`，并刷新 batch 计数。
- `app/result_parser.py`
  - 优先从 Codex TUI 日志中提取 `generated_images/*.png` 路径，若日志未打印路径，则扫描 `CODEX_HOME/generated_images` 作为兜底。
- `app/uploads.py`
  - 支持 `POST /uploads` 上传 base64 图片，保存到 `data/uploads/{image_id}/...`。
  - batch 可通过 `reference_image_ids` 引用上传图，也可通过 `reference_images` 直接传容器路径或 URL。

## 关键文件
- `app/main.py` — HTTP 服务入口。
- `app/manager.py` — batch/job 编排与状态回写。
- `app/codex_runner.py` — Codex 命令拼装。
- `app/tmux_runner.py` — TerminalRunner，当前负责启动 PTY worker。
- `app/pty_worker.py` — 实际伪终端执行器。
- `app/result_parser.py` — 结果路径提取。
- `app/uploads.py` — 上传图片保存和元数据记录。
- `app/models.py` — batch/job 数据结构。
- `app/store.py` — 本地 JSON 状态存储。
- `tests/test_manager.py` — 命令拼装、终端命名、PTY worker 和结果路径检测测试。

## 已验证
- `python3 -m unittest discover -s tests -v` 通过，当前 6 个测试。
- 容器内健康检查通过：
  - `curl http://127.0.0.1:8088/health`
- 新 batch 验证通过：
  - `batch_3e5f1c97e226`
  - `job_191322c28c68`
  - prompt: `draw a tiny green triangle icon on a plain white background`
  - job 状态：`succeeded`
  - batch 状态：`completed`
  - 结果路径出现在日志中：
    - `/data/codex-home/generated_images/019db5f5-02ef-7c71-8706-bf368fcc2ca8/ig_0604ef258a15d2ea0169e8f2f63c0c8194b404f6976716ec4d.png`
- 批量 prompts 验证通过：
  - `batch_5ff5b3e8d140`
  - 两个 job 同时启动，状态均为 `succeeded`
  - batch 状态：`completed`
  - 每个 job 都回写了 `result_paths`
- 参考图能力：
  - `POST /uploads` 保存图片并返回 `image_id` / `path`
  - `POST /batches` 支持 `reference_image_ids` 和 `reference_images`
  - 同一批 prompts 会共用这些参考图，每个 job 的命令里都会包含 Reference images 列表

## 已解决的问题
1. 旧的 `script -qefc ...` 方式只启动伪终端，不能响应 Codex 的终端探测，容易卡住。
2. 旧命令强制 `HOME=/home/muwei`、`CODEX_HOME=/home/muwei/.codex`，但容器内认证目录已经统一到 `/data/codex-home`，会触发登录提示。
3. Codex TUI 生成图片后不一定自动退出；现在 worker 会检测结果路径并主动收尾。
4. 批量提交多个提示词时，会为每个提示词启动独立 PTY/Codex job，并发运行。
5. 上传图片、多图参考、批量 prompts 共用参考图已实现。

## 仍需注意
- `final_message` 目前保存的是原始 Codex TUI 输出，包含 ANSI 控制序列，API 返回很长且可读性差。现在已有结构化 `result_paths`，后续仍建议增加清洗后的短摘要字段。
- `data/state.json` 里有历史运行留下的 `queued`/`running` 旧记录，部分没有真实进程。当前新任务链路已经可用，但如果要展示生产状态，建议增加一次性状态清理或启动时 reconciliation。
- 从本机访问 `http://192.168.50.77:8088` 时曾看到另一个旧实例/旧路径行为；本次验证使用的是容器内 `127.0.0.1:8088`。如果需要对外提供服务，需要确认 NAS/容器端口映射指向当前容器内服务。

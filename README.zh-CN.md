# Image Gen Service 中文文档

[English README](README.md) | [AI 智能体部署文档](README_FOR_AGENT.md)

Image Gen Service 是一个基于 Codex CLI 的浏览器批量生图工作台。它支持输入提示词、选择比例、批量生成、上传参考图、多图参考、并行任务、取消任务、复用生成图作为参考图，以及下载整批结果。

这个项目主要以 Docker 服务方式运行。Codex 登录信息、提示词、上传图、日志、生成图都会保存在宿主机挂载目录里，不会写进公开发布的 Docker 镜像。

当前公开镜像不需要服务 API token。如果接口返回 `unauthorized`，通常是旧容器、旧镜像、反向代理鉴权或浏览器访问到了旧服务。

如果你希望让 AI 智能体或自动化工具帮你部署，请直接把 [README_FOR_AGENT.md](README_FOR_AGENT.md) 交给它。普通 README 只面向用户部署和使用公开 Docker 镜像。

## 功能

- Web UI 生图工作台。
- 每张图对应一个独立 Codex 任务。
- 支持比例和数量控制，UI 单批支持 `1-50` 张。
- 支持上传参考图。
- 支持多张参考图。
- 支持把生成图再次作为参考图。
- 支持任务队列、运行中、完成、失败、取消状态。
- 支持取消单个任务或整批任务。
- 支持批量下载 zip。
- 公开 Docker 镜像不包含 Codex 凭证、用户历史、上传图或生成图。

## 快速开始

创建运行目录：

```bash
mkdir -p runtime/data runtime/workspace runtime/codex-home runtime/images
```

启动服务：

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

进入容器登录 Codex：

```bash
docker exec -it --user imagegen image-gen-service codex
```

打开浏览器：

```text
http://localhost:8088
```

## Docker Compose 部署

创建 `docker-compose.yml`：

```yaml
services:
  image-gen-service:
    image: muwei517/image-gen-service:latest
    container_name: image-gen-service
    ports:
      - "8088:8088"
    environment:
      IMAGE_GEN_MAX_CONCURRENCY: "8"
      IMAGE_GEN_CORS_ORIGIN: "*"
    volumes:
      - ./runtime/data:/data/image-gen-service
      - ./runtime/workspace:/workspace
      - ./runtime/codex-home:/data/codex-home
      - ./runtime/images:/data/codex-home/generated_images
    restart: unless-stopped
```

启动：

```bash
mkdir -p runtime/data runtime/workspace runtime/codex-home runtime/images
docker compose up -d
docker exec -it --user imagegen image-gen-service codex
```

## 使用方式

1. 打开 Web UI。
2. 确认页面没有提示 Codex 未登录。
3. 输入提示词。
4. 选择画面比例和生成数量。
5. 可选：上传或选择参考图。
6. 提交任务。
7. 每张图会作为独立任务运行。
8. 生成完成后可以下载，也可以继续把生成图作为参考图。

UI 会把选择的比例追加到提示词后，例如 `--ar 16:9`。如果选择了参考图，后端会用 `codex exec` 运行任务，并把参考图作为 `--image` 参数传给 Codex。

生成数量和并发不是一回事。单批可以提交多张图，`IMAGE_GEN_MAX_CONCURRENCY` 只控制同时运行的 Codex 任务数量。默认并发是 `8`，机器资源或账号额度有限时可以调低。

## 挂载目录

这些目录建议保持挂载，方便升级容器后保留数据：

| 宿主机目录 | 容器目录 | 内容 |
| --- | --- | --- |
| `./runtime/data` | `/data/image-gen-service` | 批次、任务、上传图、归档结果、服务状态 |
| `./runtime/workspace` | `/workspace` | Codex 默认工作目录 |
| `./runtime/codex-home` | `/data/codex-home` | Codex 登录信息和配置 |
| `./runtime/images` | `/data/codex-home/generated_images` | Codex 生成图片目录 |

如果生成结果重要，请备份这些目录。最敏感的是 `./runtime/codex-home`，登录 Codex 后里面会包含认证信息。

## 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `IMAGE_GEN_MAX_CONCURRENCY` | `8` | 同时运行的 Codex 任务数量。资源或额度有限时建议设为 `1-2`。 |
| `IMAGE_GEN_JOB_TIMEOUT_SECONDS` | `1800` | 单个任务超时时间。 |
| `IMAGE_GEN_CORS_ORIGIN` | `*` | CORS 来源。公网或反代部署时建议限制。 |
| `IMAGE_GEN_PORT` | `8088` | 容器内端口，通常不用改，宿主机端口通过 Docker 映射。 |
| `IMAGE_GEN_GENERATED_IMAGES_DIR` | `/data/codex-home/generated_images` | Codex 生成图片目录。 |
| `IMAGE_GEN_FILE_ROOTS` | data、workspace、generated images | `/files` 允许读取的路径根目录。 |

## 更新镜像

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

只要继续使用同一组挂载目录，历史数据和 Codex 登录状态会保留。

## 安全说明

不要把服务直接暴露到公网。这个服务可以启动 Codex 任务，并能读取 `IMAGE_GEN_FILE_ROOTS` 下的图片文件。远程访问时建议放在可信反向代理、VPN 或其他访问控制后面。

公开 Docker 镜像设计上不包含：

- Codex `auth.json`
- Codex 日志、会话和历史
- 上传的参考图
- 生成图片
- 任务日志和历史提示词

这些内容存在宿主机挂载目录里。不要把运行目录打进镜像，也不要公开分享运行目录。

## HTTP API

常用接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 服务和 Codex 状态 |
| `POST` | `/batches` | 提交批量任务 |
| `GET` | `/batches` | 批次列表 |
| `GET` | `/batches/{batch_id}` | 批次详情和任务列表 |
| `GET` | `/batches/{batch_id}/download` | 下载整批图片 zip |
| `GET` | `/jobs/{job_id}` | 任务详情 |
| `POST` | `/jobs/{job_id}/cancel` | 取消单个任务 |
| `POST` | `/batches/{batch_id}/cancel` | 取消整批任务 |
| `POST` | `/uploads` | 上传参考图 |
| `GET` | `/uploads` | 参考图列表 |
| `DELETE` | `/uploads/{image_id}` | 删除上传的参考图 |
| `GET` | `/files?path=/absolute/image/path.png` | 读取允许目录下的图片 |

提交普通批次：

```bash
curl -X POST http://localhost:8088/batches \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A small robot painting a sunset --ar 16:9",
    "count": 4
  }'
```

使用已上传参考图：

```bash
curl -X POST http://localhost:8088/batches \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a cinematic product image --ar 16:9",
    "count": 4,
    "reference_image_ids": ["upload_id_1", "upload_id_2"]
  }'
```

使用已有图片路径作为参考图：

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

`reference_images` 必须位于 `IMAGE_GEN_FILE_ROOTS` 允许的目录下。

上传参考图的 JSON 格式：

```json
{
  "filename": "reference.png",
  "mime_type": "image/png",
  "data": "base64-image-data"
}
```

## 故障排查

### 页面提示 Codex 未登录

运行：

```bash
docker exec -it --user imagegen image-gen-service codex
```

登录完成后刷新页面。

### 接口返回 unauthorized

当前镜像不需要 API token。请检查：

- 是否已经重新拉取 `muwei517/image-gen-service:latest`；
- 是否删除并重建了旧容器；
- 浏览器或反向代理是否仍然访问旧服务；
- 反向代理是否加了自己的鉴权。

检查命令：

```bash
docker pull muwei517/image-gen-service:latest
docker inspect image-gen-service --format '{{.Config.Image}}'
curl -i http://127.0.0.1:8088/health
```

### 任务失败：没有检测到输出图片

服务只有在检测到输出图片后才会把任务标记为成功。请检查：

```bash
docker logs --tail 200 image-gen-service
docker exec image-gen-service codex --version
curl -fsS http://127.0.0.1:8088/health
```

常见原因：

- 容器内 Codex 没有完成登录；
- Codex 运行成功但没有实际生成图片；
- 图片没有写入 `/data/codex-home/generated_images`；
- 挂载目录权限不足；
- 并发过高，导致 Codex 失败、超时或被账号额度限制。

### 图片不显示

确认图片路径在允许目录内。默认允许：

```text
/data/image-gen-service
/workspace
/data/codex-home/generated_images
```

如果你自定义了生成目录，需要同步设置 `IMAGE_GEN_FILE_ROOTS`。

### 挂载目录无法写入

容器入口脚本会尝试修复挂载目录权限。如果宿主机文件系统阻止 `chown`，请换成本地可写目录或 Docker named volume。

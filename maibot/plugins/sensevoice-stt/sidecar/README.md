# SenseVoice STT Sidecar — 独立部署

SenseVoice 语音转文字 HTTP 服务，基于 FunASR SenseVoiceSmall 模型。

支持语言：中文 / 英文 / 粤语 / 日语 / 韩语（自动检测）。

如果 MaiBot 是源码安装或一键包安装，从“纯 Python 手动运行”开始；不需要 Docker。

## 纯 Python 手动运行

适用于 MaiBot 源码安装或一键包安装场景。本路径不需要 Docker。建议把 sidecar 放在独立 Python 虚拟环境中，不要和 MaiBot 主环境混装模型推理依赖。

### 系统依赖

需要 `ffmpeg`。安装方式取决于系统发行版，例如 Debian/Ubuntu：

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

### Python 依赖

建议先创建独立虚拟环境：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
```

CPU 推理推荐安装 PyTorch CPU 版：

```bash
python -m pip install --force-reinstall \
  torch==2.6.0+cpu torchaudio==2.6.0+cpu \
  --index-url https://download.pytorch.org/whl/cpu

python -m pip install -U \
  funasr modelscope fastapi "uvicorn[standard]" python-multipart jieba
```

国内网络可按需使用可信镜像源。

### 启动服务

保持虚拟环境处于激活状态，在 `sidecar/` 目录执行：

```bash
export MODELSCOPE_CACHE="${MODELSCOPE_CACHE:-./models}"
uvicorn server:app --host 127.0.0.1 --port 50000
```

MaiBot 插件配置使用：

```toml
[stt]
endpoint_url = "http://127.0.0.1:50000/v1/audio/transcriptions"
```

### 检查就绪

```bash
curl -sS http://127.0.0.1:50000/health
# → {"status":"ready"}
```

## Docker 快速启动

仅适用于 MaiBot 本身通过 Docker/Compose 部署，或你明确希望单独容器化 sidecar 的场景。

### 构建镜像

```bash
cd plugin-src/sensevoice-stt/sidecar
docker build -t sensevoice-stt:latest .
```

### 启动容器

```bash
docker run -d \
  --name sensevoice-stt \
  -p 127.0.0.1:50000:50000 \
  -v sensevoice-models:/models \
  --memory 2g \
  sensevoice-stt:latest
```

首次启动时自动从 ModelScope 下载模型（约 1GB），缓存在 `sensevoice-models` volume 中。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查，返回 `{"status":"ready"}` |
| `/v1/audio/transcriptions` | POST | 语音转文字 |

### POST /v1/audio/transcriptions

**Content-Type**：`multipart/form-data`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file` | file | 是 | — | 音频文件（WAV/MP3/OGG/FLAC） |
| `language` | string | 否 | `auto` | 语言：`auto`/`zh`/`en`/`yue`/`ja`/`ko` |

**响应**：

```json
{"text": "转录文本"}
```

**示例**：

```bash
curl -sS -F "file=@audio.wav" -F "language=auto" \
  http://127.0.0.1:50000/v1/audio/transcriptions
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODELSCOPE_CACHE` | `/models` | 模型缓存目录 |

## 常见问题

| 现象 | 处理 |
|------|------|
| 首页卡片显示 `unreachable/connection` | sidecar 没启动，或 `stt.endpoint_url` 不是 MaiBot 可访问的地址 |
| 首页卡片显示 `loading/not_ready` | 模型仍在加载或首次下载，稍后再检查 `/health` |
| `ffmpeg` 相关报错 | 确认系统已安装 `ffmpeg` 并在 PATH 中 |
| 首次启动很慢 | 首次运行会下载 SenseVoiceSmall 模型，后续会使用 `MODELSCOPE_CACHE` 缓存 |
| 不想使用 Docker | 使用“纯 Python 手动运行”章节即可，Docker 章节不是源码安装/一键包安装的必需步骤 |

## GPU 加速（可选）

默认使用 CPU 推理（约 2GB RAM）。如需 GPU 加速：

```dockerfile
# 将 Dockerfile 中的 torch 改为 CUDA 版本
RUN pip install torch==2.6.0+cu118 torchaudio==2.6.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# 修改 server.py 中的 device 参数
model = AutoModel(model="iic/SenseVoiceSmall", device="cuda")
```

启动时添加 `--gpus all`：

```bash
docker run -d --gpus all --name sensevoice-stt ...
```

## 内存占用

| 配置 | 模型大小 | 运行时内存 |
|------|---------|-----------|
| CPU（默认） | ~1GB（磁盘） | ~1.5-2GB RAM |
| GPU | ~1GB（磁盘） | ~1GB VRAM |

## License

MIT — 与父插件 `sensevoice-stt` 一致。

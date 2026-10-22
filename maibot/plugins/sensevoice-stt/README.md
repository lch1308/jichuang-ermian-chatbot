# maibot-sensevoice-stt

麦麦（MaiBot）SenseVoice 语音识别 STT 插件

## 插件信息

版本：0.3.0
分类：媒体处理
图标：🎙️
插件 ID：dmjxmj.sensevoice-stt

## 先读这个

插件市场或 WebUI Git URL 只会安装 MaiBot 插件本体，不会自动安装 SenseVoice 模型服务。

SenseVoice sidecar 是一个独立的本地 HTTP 模型服务：它负责加载 SenseVoiceSmall 模型并提供转录接口，MaiBot 插件本体只负责把语音发过去并接收文字。

安装插件后，还需要单独启动这个模型服务，并在 WebUI 插件配置中确认 `stt.endpoint_url` 能被 MaiBot 访问。sidecar 就绪后，首页卡片会显示 `后端健康 = ready`。

如果你的 MaiBot 是源码安装或一键包安装，推荐 sidecar 也使用纯 Python 部署，不需要 Docker；Docker 说明仅面向 Docker/Compose 用户。

## 功能

- `transcribe_voice_segments`：在消息到达 LLM 前拦截语音段，调用 SenseVoice sidecar 转录为文字并原地替换为文本段。
- `sensevoice_stt_status`：WebUI 首页状态卡片，显示插件状态、endpoint、后端健康、成功率、连续失败和最近错误类型。
- 支持多段语音并发转录；sidecar 不可用时静默降级为 `[voice]` 占位符，不阻断消息流。

## 安装路径

### WebUI / 插件市场安装

1. 在 MaiBot WebUI 插件管理中通过 Git URL 安装本仓库。
2. 安装完成后打开插件配置。
3. 根据 MaiBot 部署方式设置 `stt.endpoint_url`。
4. 启动 sidecar 后，检查首页卡片中的后端健康状态。

### 源码安装

源码安装 MaiBot 时，按 [sidecar/README.md#纯-python-手动运行](sidecar/README.md#纯-python-手动运行) 启动 sidecar。推荐使用独立 Python 虚拟环境运行模型服务；本场景不需要 Docker，也不要把模型推理依赖装进 MaiBot 主环境。

sidecar 与 MaiBot 在同一台机器上时，把 endpoint 改为：

```toml
[stt]
endpoint_url = "http://127.0.0.1:50000/v1/audio/transcriptions"
```

插件运行环境只需要能导入 `aiohttp`。模型推理依赖放在 sidecar 的独立 Python 环境中。

### 一键包安装

一键包用户同样按 [sidecar/README.md#纯-python-手动运行](sidecar/README.md#纯-python-手动运行) 启动 sidecar；本场景不需要 Docker。若 sidecar 与 MaiBot 在同一台机器上，endpoint 通常使用：

```toml
[stt]
endpoint_url = "http://127.0.0.1:50000/v1/audio/transcriptions"
```

如果 sidecar 在另一台机器上，把 `127.0.0.1` 改为 MaiBot 能访问的内网地址，并确保只在可信网络内开放端口。

一键包目录结构可能因发行包而异；插件本体仍通过 WebUI/插件市场安装，sidecar 作为独立 Python 进程运行即可。

### Docker / Docker Compose

仅当 MaiBot 本身通过 Docker/Compose 部署时使用本路径。Docker/Compose 环境通常可以保留默认配置：

```toml
[stt]
endpoint_url = "http://sensevoice:50000/v1/audio/transcriptions"
```

Maibot-Napcat 环境的 sidecar 服务由 Compose 管理，健康检查地址为：

```bash
curl -sS http://127.0.0.1:50000/health
```

## 配置

默认配置位于 `config.toml`，也可通过 MaiBot WebUI 插件配置页修改。

- `plugin.enabled`：是否启用语音转文字。
- `plugin.config_version`：插件配置版本，当前为 `"0.3.0"`。
- `stt.endpoint_url`：SenseVoice sidecar 转录接口地址。
- `stt.timeout_seconds`：转录请求超时，单位为秒（默认 30）。
- `stt.language`：识别语言，支持 `auto` / `zh` / `en` / `yue` / `ja` / `ko`（默认 `"auto"`）。

修改 `config.toml` 后，MaiBot 会自动调用 `on_config_update()` 应用新配置。

## 隐私与安全

- **转录文本不记日志**：sidecar 和插件日志仅记录 `text_length`（字符数），不记录完整文本内容。
- **本地处理**：音频文件仅发送到你配置的 SenseVoice sidecar，不上传任何云端服务。
- **临时文件清理**：转录完成后立即删除临时 WAV 文件。

## 已知限制

- 仅处理入站消息的 voice segment，不涉及 TTS 输出。
- sidecar 不可用时，转录静默失败，voice segment 回退为 `[voice]` 占位符。
- SenseVoiceSmall 模型仅支持中文、英文、粤语、日语、韩语。
- 插件市场安装不会自动部署 sidecar。非 Docker MaiBot 用户按 [sidecar/README.md#纯-python-手动运行](sidecar/README.md#纯-python-手动运行) 单独启动模型服务。

## 许可证

MIT

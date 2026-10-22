# Changelog

## [0.3.0] — 2026-07-09

### 插件市场安装体验

- Manifest 版本升级至 `0.3.0`，插件类型改为 `media`
- Manifest 只声明插件本体依赖 `aiohttp>=3.9.0`，不把 `torch`、`funasr`、`modelscope` 等 sidecar 推理依赖安装进 MaiBot 主环境
- 描述从 Docker-only 语义调整为本地或远程 SenseVoice sidecar

### WebUI 配置与自诊断

- 配置模型增加 WebUI 分组标题、图标、排序和 endpoint placeholder
- HomeCard 增加 endpoint、后端健康、最近错误类型等诊断信息
- 新增 sidecar `/health` 轻量探测；sidecar 不可达时不阻塞插件加载或消息流

### 非 Docker 纯 Python 部署文档

- README 增加插件市场安装、源码安装、一键包安装、Docker/Compose 四种路径，非 Docker 路径优先指向纯 Python 部署
- sidecar README 将纯 Python 手动运行前置，补充依赖清单、启动命令、健康检查和常见问题
- 明确 Docker sidecar 仅面向 Docker/Compose 用户或明确希望容器化 sidecar 的场景
- 情绪/事件/语言富元数据转录延后到后续版本

## [0.2.0] — 2026-07-08

### 插件封装正式化

- 插件源码从 `docs/todolist/staging/` 迁移至 `plugin-src/sensevoice-stt/` 独立目录
- 新增 `requirements.txt` 声明 `aiohttp` 依赖
- 新增 `README.md` 面向用户的安装配置文档
- 新增 `CHANGELOG.md`

### 可观测性增强

- `stt_client.py`：新增 `TranscriptionResult` dataclass（`text`/`success`/`error_type`/`attempt`）；内置 2 次重试 + 错误分类（`timeout`/`connection`/`http_error`）
- `plugin.py`：统计追踪（`total_requests`/`total_success`/`total_failure`/`consecutive_failures`）；连续失败 ≥3 次记 WARNING
- 新增 `@HomeCard` — WebUI 首页状态卡片
- ~~`@Command` `/stt`~~ — 已移除。SDK 无管理员鉴权，无法安全暴露设置入口。状态查看改为 `@HomeCard` + `docker compose logs`

### 并发转录

- 同一消息包含 ≥2 个语音段时，使用 `asyncio.gather` 并发调用 sidecar
- 单段时保持直接调用，无额外开销

### Sidecar 独立化

- Sidecar 源码纳入 `sidecar/` 子目录（`server.py` + `Dockerfile` + `.dockerignore`）
- 新增 `sidecar/README.md` — 独立部署说明（`docker build`/`docker run`、GPU 加速选配）
- 主 `docker-compose.yml` sensevoice 服务段增加指向独立部署的注释

### 测试覆盖

- 新增 4 个测试文件，共 40 个测试用例
- `test_audio_utils.py`：base64 编解码、临时文件创建/清理（7 tests）
- `test_config.py`：模块可导入性（2 tests）
- `test_stt_client.py`：`TranscriptionResult`、HTTP 200/500、超时重试、连接拒绝（7 tests）
- `test_plugin.py`：生命周期、Hook 转录、HomeCard、统计追踪（24 tests）

### Bug 修复（自 0.1.0 起累计 13 项）

| # | 问题 | 修复 |
|---|------|------|
| 1 | manifest 校验失败（缺必填字段） | 补全 `author.url`, `urls`, `i18n` |
| 2 | sidecar 容器 crash（缺 torch） | Dockerfile 加 `torch==2.6.0+cpu` |
| 3 | sidecar 容器 crash（缺 jieba） | Dockerfile 加 `jieba` |
| 4 | 配置版本非法（缺 config_version） | `config.toml` 加 `[plugin].config_version` |
| 5 | 模型 provider 不存在 | 回退 `model_config.toml` 中误加的 sensevoice 模型定义 |
| 6 | `[plugin].enabled` 不生效 | 新增 `PluginSection` 配置模型 |
| 7 | STT 客户端文件句柄泄漏风险 | `FormData` 中 `open()` 改为 `with open(...)` 包裹 |
| 8 | sidecar 日志可能泄露转录文本 | 日志改为只记录 `text_length` |
| 9 | sidecar 临时文件名污染风险 | uuid 命名替代上传文件名拼接 |
| 10 | sidecar 启动后反复重启（缺 modelscope） | Dockerfile 加 `modelscope` |
| 11 | sidecar 加载后仍重启（funasr-onnx 导出循环） | 改用 FunASR `AutoModel` 直接加载 SenseVoiceSmall |
| 12 | sidecar POST 200 但 core 仍报转录失败 | Hook 返回值改为 `{"action":"continue","modified_kwargs":{...}}` |
| 13 | sidecar 转录日志未出现在 compose logs | 改用 `uvicorn.error` logger |

## [0.1.0] — 初始开发

- 首次实现：`@HookHandler("chat.receive.before_process")` 拦截 voice 段
- base64 WAV 解码 → SenseVoice Docker sidecar 转录 → text segment 替换
- 配置文件 `config.toml` + Pydantic 配置模型
- SenseVoice Fine 侧车（FunASR SenseVoiceSmall，CPU 推理）
- Docker Compose 集成

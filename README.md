# 极创二面-聊天机器人

基于 **MaiBot、Open-LLM-VTuber 与自编 Heart 插件**的持续角色 Agent 实验项目。目标是让角色拥有可持续的记忆、可观察的心情、真实工具行动，以及与内部状态联动的 Live2D 和语音表现。

本仓库是截至 **2026-10-22** 的阶段源码快照，供学习、面试展示和后续协作。它包含上游框架和我们的集成修改，不将第三方框架宣称为自研。真实运行配置、密钥和用户数据均不在交付范围内。

> **先区分当前版本与后续计划：** 已有 StoryRoom 0.4 跑团原型使用有限世界线及“最终物语”规则子集。**COC 7、MapTool、BCDice 和地图／Live2D 单窗口整合尚未实施**，设计见 [COC7 升级方案](docs/COC7路线与单窗口方案.md)。后续测试顺序已确定为先真人 KP，再接入 AI KP。

## 项目如何工作

```text
QQ／Live2D 文字与语音输入
        ↓
MaiBot：角色设定、规划、记忆、工具、回复
        ↕
Heart：记忆管理、心情状态、实时协调、行为审计
        ↓
文字回复＋Live2D 表情／动作＋可选语音

跑团使用独立 StoryRoom：两个 MaiBot 玩家＋主持＋隔离的故事经历
```

语言模型负责理解与表达，程序负责保存状态、执行工具和校验结果。提出计划、调用成功、实际发送和实际播放分别记录，不把“机器人说自己做了”当成系统真的执行了。

## 已有功能与边界

| 模块 | 当前源码包含的能力 | 需要注意 |
| --- | --- | --- |
| 多轮角色对话 | 复用 MaiBot 的人设、上下文、规划与记忆能力 | 各上游模块有自己的配置，不是单一提示词程序 |
| 记忆管理 | 主动记住、候选审核、冲突与查重、更新、忘记、按来源查询与审计 | 增强原生记忆；检索命中不等于模型最终采用 |
| 心情 | 持久心情、临时情绪、评估与模型选择、展示风格联动 | 心情与跑团 SAN 不混用；表情取决于模型资源 |
| 工具行动 | 记忆查询、天气查询及原生工具接入 | 可用范围由实际启用的工具和权限决定 |
| 语音输入 | QQ 语音转文字、Live2D 录音识别与临时转写接入 | 识别模型、运行环境需自行准备；QQ 仍以文字回复 |
| 实时对话 | 说话期间的只读查询、可开关的提前草稿、停止／插话取消、点名反馈、有限澄清与证据更正 | 提前草稿不一定复用，可能额外计费；不宣称完整自然电话交流 |
| Live2D／语音 | 生成期间提前表情、动态模型映射、文字与语音播放观察、语音风格记录 | 不附模型、Cubism Core、声纹样本或权重；不同资源需实测 |
| 可观测性 | 工具输入与结果、记忆来源、状态变化、插件开关、草稿采用与否、实际输出与播放阶段 | 易读日志与结构化审计分开；不公开真实用户记录 |
| StoryRoom 0.4 | 双 AI 玩家、独立 AI GM、人工主持接管、暂停、检查点回溯、分支剧本、游戏记忆隔离、双形象舞台 | 现有规则是子集；跨两台真实电脑和供应商的验收需单独完成 |

“有代码”“离线测试通过”“本机人工验证”“异地真实使用”是不同层次。本仓库不把历史模拟测试等同于所有场景验收，当前发布检查见 [VALIDATION.md](VALIDATION.md)。

## 目录

```text
maibot/                  MaiBot 1.2.5 核心源码快照与 Heart 宿主接入
  plugins/               记忆、心情、实时、天气、语音识别、跑团等插件
  heart_shared/          行为记录、易读日志与共享状态代码
  dashboard/             管理界面源码（构建资源另行准备）
vtuber/                  Open-LLM-VTuber 1.2.1 源码与 Heart 接缝
voice/                   本地 Qwen3-TTS 服务胶水代码，不含模型和声音样本
storyroom/               StoryRoom 0.4 主机、配套 PC 插件、网页与离线测试
docs/                    安装边界、路线计划和维护说明
scripts/                 发布文件检查与文件指纹校验
licenses/                从协作交付中保留的上游许可说明
SOURCE_MANIFEST.json     发布文件的 SHA-256 指纹
```

该仓库不是把工作电脑整个目录打包。无 Git 历史、虚拟环境、数据库、录音、截图、私聊、真实配置、模型素材、安装包及缓存。大体积依赖和受单独许可约束的素材由使用者自行准备。

## 从哪里开始

### 先体验不需要收费模型的 StoryRoom 主持界面

建议使用 Python 3.12 和 uv，在新目录中操作。`maibot` 与 `vtuber` 依赖约束不同，必须分别创建环境，不能把两者所有依赖装进同一个环境。

```powershell
cd storyroom
uv run --python 3.12 --with-requirements requirements.txt python run.py --port 8791
```

打开 `http://127.0.0.1:8791/`。首次运行生成本机数据和主持凭据，具体入口见 [StoryRoom 使用说明](storyroom/README.md)。未连接 PC 时，不会获得真实角色回复；未配置模型时，可先检查房间、主持、暂停与存档界面。

双 Live2D 还需要你已有且获许可的 Open-LLM-VTuber 模型资源；前端库缺失时，按 StoryRoom 说明使用 `scripts/setup_vendor.py` 获取固定版本依赖。仓库不附 Cubism Core 或人物模型。

请使用隔离测试房间。**不要将本快照直接覆盖正在运行的机器人或同伴主机。** 现有安装需要先备份、比较源文件、核对宿主版本，再合并；拉取仓库不等于已经安装。

### 连接两台 MaiBot

1. 按 [MaiBot 上游说明](maibot/UPSTREAM_README.md)准备独立环境，核对 SDK 和插件清单兼容性。
2. 使用 `storyroom/plugins/storyroom_pc` 这一套与主机配套的 PC 插件；与 `maibot/plugins/storyroom_pc` 比较后再安装，不重复加载两个副本。
3. 两位真人分别获得主持身份；每个机器人使用自己的玩家连接凭据。
4. 每台电脑配置真实可访问的主机地址，不能把另一台电脑的 `127.0.0.1` 当成远程地址。
5. 先由真人主持短场景，检查讨论、提案、裁决、记忆与表情；后续再测试 AI 主持。

主机与 PC 的模型配置彼此独立。普通 QQ、日常 Live2D 与跑团记忆需要保持范围隔离，不应为了跑团而启用无关的 QQ 账号或群。

### 日常 Live2D 与实时插件

先阅读 [实时插件说明](maibot/plugins/heart-realtime/README.md)及 [安装边界](docs/安装与配置边界.md)。实时插件依赖 MaiBot、日志层和 VT 接缝，不能只复制一个插件文件夹就获得全部功能。

普通录音识别与流式临时识别是不同服务。开启提前生成不代表机器人一定提前插嘴；草稿在确认前隐藏，是否采用需通过一致性检查。若没有足够证据，角色仍应等正式输入再回复。

## 配置与隐私

- 本仓库只有示例配置。API Key、管理密码、玩家密钥和本地语音令牌只保存在自己电脑，不能填回示例文件后提交。
- 模型列表及任务选择由使用者自行配置；心情评估、记忆流、记忆查重、规划与回复可能使用不同任务。
- Live2D 模型与声音资源需自行提供并确认授权。尤其不要将声音参考录音当成普通源码上传。
- 已排除插件的 `settings.json`、`runtime-location.json`、`facts.json` 和真实 `config.toml`。管理员本地事实表应从空示例开始配置。
- `.gitignore` 只是第一道防线；发布前仍应运行检查，检查本次暂存文件及新增历史。

发布检查工具不会读取原始录音或请求模型。若发现真实凭据已经进入 Git 历史，应先停止推送，处理凭据有效性及历史；不要只删除当前文件后继续发布。

## 验证

```powershell
python scripts/check_public.py
```

它检查文件指纹、明显凭据模式与不应交付的文件。发布整理还额外与原电脑配置中的真实密钥做本地比对；真实密钥不写入仓库或扫描报告。自动扫描不能替代人工检查新增内容。

StoryRoom 的离线测试入口：

```powershell
cd storyroom
python -B -m unittest discover -s tests -p "test_*.py" -q
node --test tests/test_audio.mjs tests/test_author.mjs tests/test_media.mjs tests/test_stage.mjs tests/test_visual.mjs tests/test_runtime.mjs
```

部分插件兼容测试需要已有 MaiBot 环境和 SDK，参见对应测试与 StoryRoom 说明。本次实际执行的范围和结果记录于 [VALIDATION.md](VALIDATION.md)，不要求为了读源码先接入付费模型。

## 后续路线

1. 按 COC 7 审核角色卡、规则选项与测试场景。
2. 验证 MapTool 与 BCDice 接入，确认规则结果、秘密过滤和状态一致性。
3. 将地图、双 Live2D 和主持操作整合到同一个窗口；先验证渲染与交互兼容性。
4. 真人 KP 跑通闭环后，依次测试 AI KP 草案、辅助主持与独立短局主持。
5. 持续改善插件兼容性、安装流程和可读日志。

目前没有选定正式 COC 模组，也没有将这些设计当成已实现成果。

## 来源与许可

主要上游包括 [MaiBot](https://github.com/Mai-with-u/MaiBot)、[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)、[MaiBot SDK](https://github.com/Mai-with-u/maibot-plugin-sdk)、[SenseVoice](https://github.com/FunAudioLLM/SenseVoice)及各插件所列项目。协作来源包含 [Silverynn/yubao-maibot](https://github.com/Silverynn/yubao-maibot)。

各子目录保留自身许可证，详见 [第三方说明](THIRD_PARTY.md)。公开源码不改变上游许可，也不赋予使用者传播 Live2D 模型、声纹、规则书、模组或第三方素材的权利。本仓库未将这些资源打包。

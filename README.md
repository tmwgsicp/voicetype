<div align="center">

# VoiceType

### 灵活可控的 AI 语音输入工具

**本地离线 | 云端高精度 | 声纹识别 | 关键词唤醒 | 完全开源**

[![GitHub stars](https://img.shields.io/github/stars/tmwgsicp/voicetype?style=for-the-badge&logo=github)](https://github.com/tmwgsicp/voicetype/stargazers)
[![License](https://img.shields.io/badge/License-AGPL%203.0-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-FFC131?style=for-the-badge&logo=tauri&logoColor=white)](https://tauri.app/)

[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/tmwgsicp/voicetype/releases)
[![macOS](https://img.shields.io/badge/macOS-Intel%20%7C%20Apple%20Silicon-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/tmwgsicp/voicetype/releases)

</div>

---

## 功能特性

### 🎯 核心优势

- **🆓 完全免费，真开源**
  - 本地模式零成本运行，无需任何 API Key
  - AGPL-3.0 协议，代码完全公开
  - 支持私有化部署，数据完全可控

- **🔒 隐私优先**
  - 本地 ASR 模型，语音数据不出本机
  - 声纹特征本地存储，不上传任何服务器
  - 可完全断网使用（本地模式）

- **⚡ 高性能低延迟**
  - 实时流式识别，边说边出字
  - 本地模式延迟 50-80ms
  - CPU 友好

- **🎛️ 灵活可控**
  - 双模式切换：本地离线 / 云端高精度
  - 多 ASR 提供商：Sherpa-ONNX、阿里云、腾讯云
  - 多 LLM 后处理：Qwen、GPT、DeepSeek、GLM
  - 支持场景识别和自定义规则引擎

### 🚀 主要功能

- **双模式 ASR，自由选择**
  - **本地离线模式** — Sherpa-ONNX 中英双语模型，完全本地运行，隐私保护，零 API 成本
  - **云端高精度模式** — 支持阿里云 Qwen3-ASR、腾讯云等主流服务，识别准确率更高（95%+）
  
- **声纹识别，防止误触**
  - 本地 ONNX 模型，3 轮声纹注册，实时验证说话人身份
  - 数据完全本地存储（`~/.config/voicetype/voiceprints/`）
  - 可调节阈值，适应不同环境

- **关键词唤醒（KWS），免按键输入**
  - 自定义唤醒词（如"语音输入""开始输入"）
  - 支持热更新，无需重启
  - 适合无障碍场景（残疾人、老年人）

- **LLM 智能优化**
  - 支持阿里云 Qwen、OpenAI GPT、DeepSeek、智谱 GLM 等多种大模型
  - 自动优化识别文本：纠错、标点、格式化、口语转书面语

- **场景与规则引擎**
  - 自动识别活动窗口（IDE、Office、浏览器、聊天工具）
  - 根据场景应用不同的规则和提示词
  - 支持自定义规则（应用名称、窗口标题、替换规则）

- **全局快捷键**
  - F9 开始/停止录音
  - 空格键临时降噪（说话时按下）
  - 支持自定义按键

- **跨平台桌面应用**
  - 基于 Tauri 2.0 + Vue 3 + FastAPI
  - 原生体验，支持 Windows 10/11
  - macOS 支持（Intel & Apple Silicon，测试中）

- **实时悬浮窗**
  - 通过颜色和动画效果显示不同录音状态
  - 可拖拽位置，支持自定义透明度

---

## 快速开始

### 方式一:下载安装包(推荐)

前往 [Releases](https://github.com/tmwgsicp/voicetype/releases) 下载最新版本:

- **Windows 10/11 (x64)**: `VoiceType_x.x.x_x64-setup.exe` (约 600MB)
- **macOS (Intel/Apple Silicon)**: `VoiceType_x.x.x_x64.dmg` / `VoiceType_x.x.x_aarch64.dmg` (约 600MB，测试中）

安装后即可使用,所有必需的 AI 模型已内置(双语 ASR、声纹识别、关键词唤醒)。

> **macOS 用户注意**: macOS 版本代码已适配,但未经充分测试。如遇问题请提交 Issue 反馈,感谢!

### 方式二:开发者部署

#### 第一步:克隆项目

```bash
git clone https://github.com/tmwgsicp/voicetype.git
cd voicetype
```

#### 第二步:安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖(如需修改 UI)
cd src-ui && npm install && cd ..
```

#### 第三步:下载 AI 模型

```bash
# 下载所有必需模型(双语 ASR + 声纹识别 + 关键词唤醒)
python scripts/download_models.py --all

# 或按需下载
python scripts/download_models.py --asr      # 仅下载 ASR 模型(530MB)
python scripts/download_models.py --voiceprint  # 仅下载声纹模型(25MB)
python scripts/download_models.py --kws      # 仅下载 KWS 模型(36MB)
```

#### 第四步:配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env,根据需要配置
# 本地模式无需 API Key,云端模式需填写对应服务的 API Key
```

#### 第五步:启动服务

```bash
# 启动后端服务
python -m voicetype.main

# (可选)启动前端开发服务器
cd src-ui && npm run dev
```

服务启动后:
- 按 `F9` 开始录音
- 再按 `F9` 停止录音并输出文本
- 访问 `http://localhost:5173` 打开设置界面

---

## 核心功能详解

### 双模式 ASR

#### 本地离线模式 (默认)

- **模型**: Sherpa-ONNX 中英双语模型 (530MB)
- **优势**: 完全本地运行，无需联网，隐私保护，零 API 成本
- **延迟**: 50-80ms (实时流式识别)
- **准确率**: 中文 90%+，中英混合识别良好
- **适用场景**: 日常办公、代码输入、即时通讯、隐私敏感场景

**配置方式**:
```bash
# .env
ASR_PROVIDER=sherpa
SHERPA_MODEL_DIR=models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20
```

#### 云端高精度模式

- **支持服务**: 阿里云 Qwen3-ASR(推荐)、腾讯云
- **优势**: 识别准确率更高(95%+)，专业术语识别更准
- **延迟**: 100-200ms (含网络传输)
- **适用场景**: 专业写作、技术文档、复杂表达、方言输入

**配置方式**:
```bash
# .env
ASR_PROVIDER=aliyun  # 或 tencent_cloud、xunfei
ASR_API_KEY=sk-your_api_key
ASR_MODEL=qwen3-asr-flash-realtime  # 阿里云推荐模型
```

### 声纹识别

本地声纹验证,防止误触发录音或他人声音干扰。

**工作原理**:
1. **注册阶段**: 3 轮录音(每轮 3-5 秒),提取声纹特征并计算平均 embedding,保存到本地
2. **验证阶段**: 实时录音时,先进行声纹比对,通过后才执行 ASR 识别
3. **数据存储**: 声纹特征存储在 `~/.config/voicetype/voiceprints/`,不上传云端

**技术特点**:
- 基于 ONNX Runtime 的轻量级声纹模型(25MB)
- 余弦相似度评分(0-1),默认阈值 0.4(建议 0.3-0.5)
- 低阈值(如 0.3):识别更宽松,适合嘈杂环境
- 高阈值(如 0.5):识别更严格,适合安静环境

**如何使用**:
1. 打开设置界面 → 声纹识别
2. 点击"注册声纹",完成 3 轮录音
3. 调整阈值(可选),点击"测试验证"确认
4. 启用后,每次录音前会自动验证声纹

### 关键词唤醒 (KWS)

自定义唤醒词实现免按键语音输入,适合无障碍场景(残疾人、老年人)。

**工作原理**:
1. 后台持续监听麦克风音频
2. 检测到唤醒词(如"语音输入")后,自动开始 ASR 识别
3. 识别完成后自动输出文本,并重新进入监听状态

**配置方式**:
```bash
# .env
SHERPA_KWS_ENABLED=true
SHERPA_KEYWORDS=["语音输入", "开始输入"]  # 支持多个唤醒词
```

或通过 Web UI → 设置 → 关键词唤醒 → 自定义唤醒词(支持热更新,无需重启)

**注意事项**:
- 唤醒词建议 3-5 个汉字,过短易误触发,过长识别率下降
- 默认使用拼音分词模型,支持中文唤醒词
- KWS 模型 36MB,首次使用需下载

### 场景与规则引擎

根据活动窗口自动切换识别策略和提示词。

**内置场景**:
- **IDE/编辑器** (VS Code、PyCharm、Sublime Text):识别代码注释、变量名、下划线命名
- **Office 文档** (Word、Excel、PowerPoint):优化长篇文本、标点符号
- **浏览器** (Chrome、Firefox):识别 URL、搜索关键词
- **聊天工具** (微信、钉钉):口语化表达,自动添加标点

**自定义规则**:
1. 打开设置界面 → 规则管理
2. 添加规则:输入应用名称、窗口标题关键词、替换规则
3. 示例:
   - 应用名称: `code.exe` (VS Code)
   - 窗口标题: `*.py` (Python 文件)
   - 替换规则: `下划线` → `_`, `点` → `.`

### LLM 智能优化

使用大语言模型对 ASR 识别结果进行后处理,提升可用性。

**支持的 LLM 提供商**:
- 阿里云 Qwen (qwen-turbo、qwen-plus、qwen-max)
- OpenAI GPT (gpt-3.5-turbo、gpt-4、gpt-4o)
- DeepSeek (deepseek-chat)
- 智谱 GLM (glm-4、glm-4-flash)

**优化功能**:
- 智能纠错(拼音错误、同音词)
- 添加标点符号
- 格式化代码片段
- 口语转书面语
- 根据场景调整提示词

**配置方式**:
```bash
# .env
LLM_API_KEY=sk-your_llm_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 阿里云
LLM_MODEL=qwen-turbo
```

---

## 配置说明

VoiceType 支持三种配置方式(按优先级从低到高):

```
代码默认值 < .env 文件 < config.json < 运行时 API 更新
```

### 主要配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ASR_PROVIDER` | ASR 提供商 (`sherpa`/`aliyun`/`tencent_cloud`/`xunfei`) | `sherpa` |
| `ASR_API_KEY` | 云端 ASR 的 API Key | - |
| `SHERPA_MODEL_DIR` | 本地 ASR 模型路径 | `models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20` |
| `SHERPA_KWS_ENABLED` | 是否启用关键词唤醒 | `true` |
| `SHERPA_KEYWORDS` | 自定义唤醒词 | `["语音输入", "开始输入"]` |
| `VOICEPRINT_ENABLED` | 是否启用声纹识别 | `true` |
| `VOICEPRINT_THRESHOLD` | 声纹识别阈值 (0-1) | `0.4` |
| `LLM_API_KEY` | LLM API Key | - |
| `LLM_MODEL` | LLM 模型名称 | `qwen-turbo` |
| `ASR_VAD_THRESHOLD` | VAD 语音活动检测阈值 | `0.5` |

---

## 推荐配置

- **日常使用**: 本地 Sherpa-ONNX 模式，足够满足办公、代码输入需求
- **专业写作**: 云端高精度模式（阿里云 Qwen3-ASR 推荐），专业术语识别更准
- **隐私敏感**: 本地模式 + 声纹识别
- **无障碍场景**: 本地模式 + 关键词唤醒

---

## 打包桌面应用

### 快速打包步骤

```bash
# 1. 下载模型文件
python scripts/download_models.py --all

# 2. 构建前端
cd src-ui && npm run build && cd ..

# 3. 打包 Python 后端
pyinstaller voicetype-server.spec

# 4. 构建 Tauri 桌面应用
cd src-ui && npm run tauri:build
```

打包产物:
- Windows: `src-tauri/target/release/bundle/nsis/VoiceType_x.x.x_x64-setup.exe` (~600MB)
- macOS: `src-tauri/target/release/bundle/dmg/VoiceType_x.x.x_x64.dmg` (~600MB，测试中）

**包含内容**:
- Tauri 桌面框架(系统托盘 + 设置界面 + 悬浮窗)
- Python 后端服务(自动启动,用户无感)
- Sherpa-ONNX 双语 ASR 模型(530MB)
- 声纹识别模型(25MB)
- 关键词唤醒模型(36MB)
- 所有运行时依赖

> 注: macOS 版本代码已完成,但未经充分测试。欢迎 macOS 用户协助测试并反馈问题。

---

## 项目结构

```
voicetype/
├── voicetype/                  # Python 后端
│   ├── api/                    # FastAPI 路由
│   │   ├── config_routes.py    # 配置管理 API
│   │   ├── scene_routes.py     # 场景管理 API
│   │   ├── rule_routes.py      # 规则管理 API
│   │   └── voiceprint_routes.py # 声纹管理 API
│   ├── pipeline/               # 语音处理流程
│   │   ├── voice_pipeline.py   # 主流程:VAD → ASR → LLM
│   │   ├── voiceprint_filter.py # 声纹验证过滤器
│   │   └── rule_replacer.py    # 规则替换引擎
│   ├── platform/               # 平台相关
│   │   ├── scene_manager.py    # 场景识别(窗口标题检测)
│   │   ├── keyboard_output.py  # 键盘输出(剪贴板粘贴)
│   │   └── voiceprint/         # 声纹识别服务
│   ├── voiceforge/             # 语音处理扩展
│   │   └── extensions/         # ASR/KWS 扩展
│   │       ├── sherpa/         # Sherpa-ONNX 本地 ASR
│   │       └── providers/      # 云端 ASR(阿里云/腾讯云)
│   ├── config.py               # 配置管理
│   ├── engine.py               # 核心引擎(录音 → 识别 → 输出)
│   └── main.py                 # FastAPI 入口
├── src-ui/                     # Vue 3 前端
│   ├── src/
│   │   ├── views/
│   │   │   └── SettingsView.vue  # 设置界面
│   │   ├── components/
│   │   │   ├── FloatingWidget.vue  # 悬浮窗
│   │   │   ├── SceneManager.vue    # 场景管理
│   │   │   ├── RuleManager.vue     # 规则管理
│   │   │   └── VoiceprintManager.vue # 声纹管理
│   │   ├── composables/
│   │   │   ├── useApi.ts          # API 封装
│   │   │   └── useWebSocket.ts    # WebSocket 实时通信
│   │   └── main.ts
│   └── package.json
├── src-tauri/                  # Tauri 桌面框架
│   ├── src/
│   │   ├── main.rs             # Rust 主程序
│   │   └── sidecar.rs          # Python 后端进程管理
│   └── tauri.conf.json
├── scripts/                    # 工具脚本
│   └── download_models.py      # 统一模型下载脚本
├── models/                     # AI 模型存储目录
├── .env.example                # 环境变量示例
├── requirements.txt            # Python 依赖
├── pyproject.toml              # Python 项目配置
└── README.md
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **桌面框架** | Tauri 2.0 (Rust + WebView2) |
| **前端** | Vue 3 + TypeScript + Vite + ElementPlus |
| **后端** | FastAPI + Uvicorn |
| **本地 ASR** | Sherpa-ONNX (C++ 推理引擎 + ONNX Runtime) |
| **云端 ASR** | 阿里云 DashScope / 腾讯云 / 讯飞 |
| **声纹识别** | ONNX Runtime + 自定义声纹模型 |
| **LLM** | OpenAI API 兼容接口(支持阿里云/OpenAI/DeepSeek/GLM) |
| **音频采集** | sounddevice (跨平台 PortAudio) |
| **键盘输出** | pynput (剪贴板 + 模拟粘贴) |
| **配置管理** | python-dotenv + JSON |
| **打包工具** | PyInstaller (Python) + Tauri (桌面) |

---

## 开源协议

本项目采用 **AGPL 3.0** 协议开源,**所有功能代码完整公开,私有化部署完全免费**。

| 使用场景 | 是否允许 |
|---------|---------|
| 个人学习和研究 | ✅ 允许,免费使用 |
| 企业内部使用 | ✅ 允许,免费使用 |
| 私有化部署 | ✅ 允许,免费使用 |
| 修改后对外提供网络服务 | ⚠️ 需开源修改后的代码 |
| 商业授权(闭源) | 📧 联系作者获取商业授权 |

### 商业授权

如需闭源商用或定制开发,请联系:
- **邮箱**: creator@waytomaster.com
- **微信**: 见下方二维码

详见 [LICENSE](LICENSE) 文件。

### 免责声明

- 本软件按"原样"提供,不提供任何形式的担保
- 本项目仅供学习和研究目的
- 使用者对自己的操作承担全部责任
- 因使用本软件导致的任何损失,开发者不承担责任

---

## 参与贡献

由于个人精力有限,目前**暂不接受 PR**,但非常欢迎:

- **提交 Issue** — 报告 Bug、提出功能建议
- **Fork 项目** — 自由修改和定制
- **Star 支持** — 给项目点 Star,让更多人看到

---

## 常见问题

<details>
<summary><b>声纹识别是否必须启用?</b></summary>

不是必须的,声纹识别主要用于:
- 防止误触发录音(如电脑外放音频)
- 多人环境下只识别指定人声音
- 隐私保护场景

如果你是单人使用且环境安静,可以关闭声纹识别。
</details>

<details>
<summary><b>关键词唤醒是否影响性能?</b></summary>

KWS 在后台持续监听麦克风,但:
- CPU 占用极低(<5%)
- 内存占用 ~50MB
- 不影响正常使用

如不需要免按键输入,可以关闭 KWS。
</details>

<details>
<summary><b>如何重置所有配置?</b></summary>

删除配置文件即可:
- Windows: `C:\Users\<用户名>\AppData\Roaming\VoiceType\config.json`
- macOS: `~/Library/Application Support/VoiceType/config.json`
- Linux: `~/.config/voicetype/config.json`

重启后会使用默认配置。
</details>

---

## 联系方式

<table>
  <tr>
    <td align="center">
      <img src="assets/qrcode/wechat.jpg" width="200"><br>
      <b>个人微信</b><br>
      <em>技术交流 · 商务合作</em>
    </td>
    <td align="center">
      <img src="assets/qrcode/sponsor.jpg" width="200"><br>
      <b>赞赏支持</b><br>
      <em>开源不易,感谢支持</em>
    </td>
  </tr>
</table>

- **GitHub Issues**: [提交问题](https://github.com/tmwgsicp/voicetype/issues)
- **邮箱**: creator@waytomaster.com

---

## 致谢

- [Sherpa-ONNX](https://k2-fsa.github.io/sherpa/onnx/index.html) — 高性能本地 ASR 推理引擎
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架
- [Tauri](https://tauri.app/) — 现代化跨平台桌面框架
- [Vue 3](https://vuejs.org/) — 渐进式 JavaScript 框架
- [ElementPlus](https://element-plus.org/) — Vue 3 组件库
- [ONNX Runtime](https://onnxruntime.ai/) — 跨平台机器学习推理引擎

---

<div align="center">

**如果觉得项目有用,请给个 Star 支持一下!**

[![Star History Chart](https://api.star-history.com/svg?repos=tmwgsicp/voicetype&type=Date)](https://star-history.com/#tmwgsicp/voicetype&Date)

Made with ❤️ by [tmwgsicp](https://github.com/tmwgsicp)

</div>

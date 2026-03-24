<div align="center">

<h1>VoiceType</h1>

<h3>🎙️ 带知识库的 AI 语音输入工具</h3>

<p>
<b>开源 · 实时流式 · 本地知识库 · 专业术语纠正 · 数据不出境</b><br><br>
按下快捷键说话，VoiceType 实时将语音转为干净、准确的书面文字，直接输出到当前窗口。<br>
自动去除口头禅、纠正 ASR 错字、补全标点，还能通过<b>本地知识库纠正专业术语</b>。
</p>

[![GitHub stars](https://img.shields.io/github/stars/tmwgsicp/voicetype?style=for-the-badge&logo=github)](https://github.com/tmwgsicp/voicetype/stargazers)
[![License](https://img.shields.io/badge/License-AGPL%203.0-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=for-the-badge)]()

</div>

---

## ✨ 核心特色

<table>
<tr>
<td width="33%" align="center">

### 🧠 知识库 RAG

**导入项目文档，AI 自动理解你的项目**

不只是纠正发音错误，更是：
- 📚 **项目知识库**：导入 API 文档、架构设计、技术规范
- 🎯 **自动适配**：换个项目，自动学习新术语和命名规范
- 🔍 **语义检索**：理解上下文，无需穷举错误发音

**示例：**
```
# 导入你的 API 文档
POST /api/users/create {username, email, phone_number}

# 语音输入
"创建用户接口需要用户名邮箱和电话号码"

# 智能输出
"创建用户接口需要 username、email 和 phone_number"
↑ 自动使用 API 文档中的标准参数名
```

</td>
<td width="33%" align="center">

### ⚡ 极速响应

**端到端延迟 < 1 秒**

WebSocket 实时流式识别，边说边出。

LLM 处理 ~600ms，关闭录音 ~100ms。

比打字快 4 倍。

</td>
<td width="33%" align="center">

### 🎯 场景感知

**智能识别窗口，自动切换风格**

代码注释、终端命令、正式邮件、日常聊天 -- 同一句话，不同场景，不同输出。

零配置，开箱即用。

</td>
</tr>
</table>

---

## 📚 详细功能

<table>
<tr>
<td width="50%" valign="top">

### 知识库 RAG

导入项目文档，VoiceType 自动学习项目术语和命名规范。

**VS 简单方案：**
- ❌ **热词替换**：需要穷举所有错误发音
- ❌ **20句上下文**：只记住刚才的对话，无法理解项目
- ✅ **RAG 知识库**：导入整个项目文档，长期记忆，自动适配

**示例：**
```json
// 导入你的 API 文档到知识库
{"endpoint": "/api/orders/create",
 "params": ["order_id", "customer_id", "total_amount"]}
```

```
你说：  "订单创建接口需要订单ID客户ID和总金额"
输出：  "订单创建接口需要 order_id、customer_id 和 total_amount"
       ↑ 自动对齐 API 文档中的标准命名
```

Web 界面支持上传 PDF/Word/TXT/Markdown，自动切分、嵌入、索引。

</td>
<td width="50%" valign="top">

### 实时流式

WebSocket 实时流式识别，边说边出。每句话立刻识别、清理、输出到当前窗口，不需要等录音结束。

说话速度约 220 词/分钟，键盘约 45 词/分钟 -- 语音输入效率约为打字的 4 倍。

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 场景感知

实时检测当前活动窗口，自动切换输出风格：

| 场景 | 检测窗口 | 输出策略 |
|------|---------|---------|
| 代码 | VS Code / JetBrains | 保留技术术语 |
| 终端 | PowerShell / Terminal | 保留命令格式 |
| 邮件 | Outlook / Gmail | 正式书面语 |
| 聊天 | 微信 / Slack | 口语简洁 |
| 文档 | Word / Notion | 完整书面语 |
| 翻译 | 指定窗口 | 中→英 |

</td>
<td width="50%" valign="top">

### 数据安全

知识库存储在本机，语音数据走国内服务器。

| 环节 | 处理方式 |
|------|----------|
| 语音识别 | 国内模型厂商（阿里云） |
| 知识库 | 本地 Qdrant，不上传 |
| 向量嵌入 | 本地 BGE 模型，不出网 |
| 场景检测 | 本地窗口 API |
| 安全过滤 | 本地规则引擎 |

全链路数据不出境，知识库完全私有，适合对数据合规有要求的团队。

</td>
</tr>
</table>

---

## 安全防护

语音输入直连 LLM 存在 Prompt 注入风险。VoiceType 内置三层防护：

| 层 | 功能 | 实现 |
|----|------|------|
| **L1 预过滤** | 拦截已知注入模式 | 中英文正则匹配 20+ 种注入话术 |
| **L2 Prompt 加固** | 限制 LLM 行为边界 | XML 结构化 Prompt，禁止翻译/改写/执行指令 |
| **L3 输出验证** | 检测异常输出 | 与原文比对，偏离过大则回退到 ASR 原文 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                        VoiceType                         │
├──────────┬──────────┬───────────┬───────────┬───────────┤
│  麦克风   │  快捷键   │  窗口监听  │  系统托盘  │  Web 配置  │
│ sounddev │ pynput   │ win32/NS  │ pystray   │ FastAPI   │
├──────────┴──────────┴───────────┴───────────┴───────────┤
│                     Engine 协调层                         │
├─────────────────┬───────────────┬───────────────────────┤
│   ASR Extension │ RAG Extension │    Voice Pipeline     │
│ ┌─────────────┐ │ ┌───────────┐ │ ┌─────────────────┐   │
│ │ Qwen3-ASR   │ │ │ BGE 嵌入  │ │ │ 场景分类         │   │
│ │ (WebSocket) │ │ │ Qdrant 检索│ │ │ LLM 意图还原     │   │
│ │             │ │ │ (本地服务) │ │ │ 三层安全过滤     │   │
│ └─────────────┘ │ └───────────┘ │ │ 剪贴板输出       │   │
│                 │               │ └─────────────────┘   │
├─────────────────┴───────────────┴───────────────────────┤
│   VoiceForge 核心框架（自研，支持知识库的超低延迟语音交互）  │
│         生命周期管理 · 错误处理 · 配置管理 · 即将开源       │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
按 F9 → 麦克风采集 → ASR (WebSocket 实时流) → 原始文本
                                                  ↓
                                          ┌───────────────┐
窗口监听 → 场景分类 ──────────────────────→│               │
                                          │  LLM 意图还原  │→ 安全验证 → 剪贴板 → 粘贴到当前窗口
知识库 (Qdrant) → 术语上下文 ─────────────→│               │
                                          └───────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| **核心框架** | VoiceForge（自研，即将开源）-- Extension 架构、生命周期管理 |
| **语音识别** | 阿里云 Qwen3-ASR / 腾讯云实时语音识别（WebSocket，服务端 VAD，响应快 ~100ms） |
| **文本清理** | OpenAI 兼容 LLM（**Qwen-turbo 推荐**，~600ms / DeepSeek / 混元 / Ollama） |
| **知识库** | 本地 BGE-small-zh + Qdrant（首次启动自动下载，零配置） |
| **Web 服务** | FastAPI + Uvicorn |
| **桌面集成** | pynput（快捷键）、pystray（托盘）、ctypes/pyobjc（窗口检测） |
| **运行环境** | Python 3.10+，Windows / macOS / Linux |

---

## 开始使用

### 🚀 即将发布

VoiceType 正在准备首个公开版本，敬请期待！

**现在可以：**
- ⭐ Star 本项目，关注发布动态
- 📖 查看源码，了解技术实现
- 🔧 从源码运行体验（开发者，见下方）

---

### 源码运行

**前提：** Python 3.10+

```bash
# 克隆项目
git clone https://github.com/tmwgsicp/voicetype.git
cd voicetype

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 安装依赖
pip install -r requirements.txt
pip install pywin32             # Windows 必需
# pip install pyobjc-framework-Cocoa  # macOS 必需

# 配置
cp .env.example .env
# 编辑 .env，填入阿里云百炼平台 API Key

# 启动
python -m voicetype
```

**配置说明：**
1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/) 获取 API Key
2. 打开配置界面：http://localhost:18233
3. 填写 API Key 并保存
4. 按 **F9** 开始录音

---

## 配置

VoiceType 使用两层配置系统：

### 1. 环境变量配置（`.env` 文件）

用于初始配置和 API Key：

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，填入必需的 API Key
ASR_API_KEY=sk-your-dashscope-key
LLM_API_KEY=sk-your-dashscope-key  # 可与 ASR 共用
```

### 2. Web 界面配置

启动后访问 http://localhost:18233 进行配置：
- API Key 配置
- 模型选择
- 快捷键设置
- 知识库管理

**配置持久化：** Web 界面的修改会保存到：
- **Windows**: `%APPDATA%\VoiceType\config.json`
- **macOS**: `~/Library/Application Support/VoiceType/config.json`
- **Linux**: `~/.config/voicetype/config.json`

重启后自动加载，无需重新配置。

### 主要配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ASR_PROVIDER` | `aliyun` | ASR 提供商：`aliyun`（默认） 或 `tencent` |
| `ASR_API_KEY` | -- | 阿里云 DashScope API Key 或腾讯云 SecretId（必需） |
| `ASR_SECRET_KEY` | -- | 腾讯云 SecretKey（仅 `tencent` 需要） |
| `ASR_MODEL` | `qwen3-asr-flash-realtime` | 识别模型，阿里云：`qwen3-asr-*`，腾讯云：`16k_zh`（纯中文）/ `16k_zh_en`（中英混合） |
| `ASR_MAX_SILENCE_MS` | `1200` | VAD 静音断句时间（毫秒，可选，默认 1200） |
| `LLM_API_KEY` | -- | OpenAI 兼容 API Key（可与 ASR 共用） |
| `LLM_MODEL` | `qwen3.5-flash` | 文本清理模型 |
| `LLM_BASE_URL` | DashScope | 可替换为 DeepSeek / 腾讯云等 |
| `HOTKEY` | `<f9>` | 录音快捷键 |
| `RAG_ENABLED` | `true` | 启用知识库 |
| `RAG_SCORE_THRESHOLD` | `0.6` | 知识库匹配阈值 |

**支持的 ASR 提供商：**
- **阿里云 DashScope**（默认）：Qwen3-ASR，服务端 VAD，静默不计费，免费额度充足
- **腾讯云**：实时语音识别，内置 VAD，每月免费 5 小时
  - 推荐模型：`16k_zh`（纯中文）、`16k_zh_en`（中英混合）、`16k_en`（纯英文）
  - 详细模型说明见 [docs/ASR_TENCENT_MODELS.md](docs/ASR_TENCENT_MODELS.md)

完整配置见 [.env.example](.env.example) 和 [docs/ASR_PROVIDERS.md](docs/ASR_PROVIDERS.md)。

### 配置文件优先级

1. **环境变量** (`.env` 文件)：用于 API Key 等敏感信息
2. **配置文件** (`%APPDATA%\VoiceType\config.json`)：用于其他参数
3. **Web 界面修改**：保存到 `config.json`，下次启动生效

> **注意**：在 Web 界面修改配置不会同步到 `.env` 文件。API Key 建议在 `.env` 中配置，其他参数可以在 Web 界面调整。

---

## 项目结构

```
voicetype/
├── voicetype/
│   ├── api/              # FastAPI 路由（状态、配置、知识库管理）
│   ├── context/          # 窗口检测 + 场景分类器
│   ├── pipeline/         # ASR → LLM 意图还原 → 安全过滤
│   ├── platform/         # 快捷键、剪贴板、麦克风、窗口监听、Qdrant 进程管理
│   ├── voiceforge/       # VoiceForge 核心框架（超低延迟语音交互 + 知识库）
│   ├── web/              # Web 配置界面
│   ├── config.py         # 分层配置管理
│   ├── engine.py         # 中央协调器
│   └── main.py           # 入口（FastAPI + 系统托盘）
├── models/               # 本地 Embedding 模型（BGE-small-zh）
└── vendor/qdrant/        # Qdrant 二进制（首次启动自动下载）
```

---

## 常见问题

<details>
<summary><b>需要安装 Qdrant 吗？</b></summary>
不需要手动安装。首次启动时自动下载 Qdrant 二进制文件（~40MB）到 <code>vendor/qdrant/</code>。<br>
向量数据默认存储在：<code>%APPDATA%\VoiceType\qdrant_data\</code>（Windows）/ <code>~/Library/Application Support/VoiceType/qdrant_data/</code>（macOS）/ <code>~/.config/voicetype/qdrant_data/</code>（Linux）。
</details>

<details>
<summary><b>API 费用？</b></summary>
约 1 元/天。Qwen3-ASR 带服务端 VAD，静默时不计费。
</details>

<details>
<summary><b>支持其他 LLM 吗？</b></summary>
支持。任何 OpenAI 兼容接口均可，包括 DeepSeek、腾讯云混元、本地 Ollama。
</details>

<details>
<summary><b>中英混合输入？</b></summary>
已专项优化，英文术语不会被翻译，剪贴板操作兼容 Unicode。
</details>

<details>
<summary><b>快捷键冲突？</b></summary>
在 .env 或 Web 界面修改 HOTKEY，支持任意组合键。
</details>

---

## 开源协议

**AGPL-3.0** | 基于 VoiceForge 框架（自研，支持知识库的超低延迟语音交互，即将开源）

| 使用场景 | 是否允许 |
|---------|---------|
| 个人 / 企业内部使用 | 允许 |
| 私有化部署 | 允许 |
| 修改后对外提供网络服务 | 需开源修改后的代码 |
| 商业授权（闭源使用） | 联系我们 |

详见 [LICENSE](LICENSE)。

### 免责声明

- 本软件按"原样"提供，不提供任何形式的担保
- 语音数据会发送至 ASR/LLM 服务商处理，请确认符合您的数据合规要求
- 使用者对自己的操作承担全部责任

---

## 参与贡献

欢迎参与 VoiceType 的改进！

**简单贡献（无需了解框架）：**
- Bug 修复
- Prompt 优化
- 新增场景规则
- 文档改进

**核心功能开发：**
- 基于 VoiceForge 框架（自研，支持知识库的超低延迟语音交互）
- 统一的生命周期管理和配置系统
- 详细技术文档将随框架开源一起发布

- **Star** -- 让更多人看到
- **Issue** -- 报告 Bug、提出建议
- **PR** -- 修复问题、优化 Prompt、新增场景
- **Fork** -- 自由定制

---

## 联系方式

<table>
  <tr>
    <td align="center">
      <img src="assets/qrcode/wechat.jpg" width="200"><br>
      <b>个人微信</b><br>
      <em>技术交流 / 商务合作</em>
    </td>
    <td align="center">
      <img src="assets/qrcode/sponsor.jpg" width="200"><br>
      <b>赞赏支持</b><br>
      <em>开源不易，感谢支持</em>
    </td>
  </tr>
</table>

- **GitHub Issues**: [提交问题](https://github.com/tmwgsicp/voicetype/issues)
- **邮箱**: creator@waytomaster.com

---

## 致谢

- [阿里云 DashScope](https://dashscope.aliyun.com/) -- Qwen3-ASR / Qwen-turbo
- [Qdrant](https://qdrant.tech/) -- 向量数据库
- [sentence-transformers](https://www.sbert.net/) -- BGE 中文嵌入模型
- [FastAPI](https://fastapi.tiangolo.com/) -- Web 框架

---

<div align="center">

**如果觉得项目有用，请给个 Star**

[![Star History Chart](https://api.star-history.com/svg?repos=tmwgsicp/voicetype&type=Date)](https://star-history.com/#tmwgsicp/voicetype&Date)

Made with ❤️ by [tmwgsicp](https://github.com/tmwgsicp)

</div>

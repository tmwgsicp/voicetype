<div align="center">

<h1>VoiceType</h1>

<h3>🎙️ 场景自适应的 AI 语音输入工具</h3>

<p>
<b>开源 · 实时流式 · 场景自适应 · 术语可控 · 声纹识别</b><br><br>
按下快捷键说话，VoiceType 自动识别当前应用场景，<br>
将语音转为干净、准确的文字，直接输入到当前窗口。
</p>

[![GitHub stars](https://img.shields.io/github/stars/tmwgsicp/voicetype?style=flat-square&logo=github&color=yellow)](https://github.com/tmwgsicp/voicetype/stargazers)
[![License](https://img.shields.io/badge/License-AGPL%203.0-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org/)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-FFC131?style=flat-square&logo=tauri&logoColor=white)](https://tauri.app/)

</div>

---

## ✨ 核心特色

**🎯 场景自适应**
- 自动识别应用（Cursor/Word/微信等），切换对应场景
- 支持自定义场景：提示词 + 快捷键 + 应用绑定
- 编程场景保留术语原样，文档场景补全标点

**🔧 术语可控**
- 规则替换：`克劳德库德` → `Claude Code`
- 锁定标签：`<lock>API</lock>` 防止 LLM 过度纠正
- 批量导入：支持 CSV 自定义规则

**🔒 声纹识别**
- 本地 ONNX 模型，完全离线
- 3轮录入，智能过滤非授权语音
- 隐私优先，数据不出境

**⚡ 实时流式**
- WebSocket 流式识别，边说边出
- 端到端延迟 < 1 秒
- LLM 处理 ~600ms

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 16+（用于构建前端）
- 阿里云 API Key（ASR + LLM）

### 安装运行

```bash
# 1. 克隆仓库
git clone https://github.com/tmwgsicp/voicetype.git
cd voicetype

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. （可选）下载声纹识别模型
python scripts/download_voiceprint_model.py

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的阿里云 API Key：
#   ASR_API_KEY=sk-xxx
#   LLM_API_KEY=sk-xxx

# 5. 启动服务
python -m voicetype.main

# 6. 打开桌面应用
# 双击运行 VoiceType.exe (Windows) 或 VoiceType.app (macOS)
# 或访问 http://localhost:18233（开发模式）
```

---

## 📖 使用说明

### 基础使用

1. 启动 VoiceType（系统托盘显示图标）
2. 按 `F9` 开始录音
3. 说话（实时显示识别文字）
4. 再按 `F9` 停止，文字自动输入到当前窗口

**示例**:
```
输入: "创建用户接口需要用户名和邮箱，然后返回用户ID"
输出: "创建用户接口需要 username 和 email，然后返回 user_id。"
```

---

### 场景管理

#### 内置场景

**编程 💻**
- 自动识别: Cursor、VSCode、PyCharm、IDEA
- 保留技术术语原样（API、user_id、callback）

**文档 📝**
- 自动识别: Word、WPS、Notion、Obsidian
- 正式书面语，补全标点，注意段落结构

**终端 ⌨️**
- 自动识别: CMD、PowerShell、Terminal
- 保留命令原样，不加标点

**聊天 💬**
- 自动识别: 微信、QQ、钉钉、Slack
- 保持口语化和简洁

**中译英 🌐**
- 快捷键: `Ctrl+Shift+1`
- 将中文口述翻译成地道英文

**通用 📄**
- 其他应用默认场景
- 基础清理

#### 自定义场景

打开设置 → 场景管理 → 新建场景，配置:
- 名称、图标
- 提示词（如何处理识别文本）
- 快捷键（可选）
- 绑定应用（可选）

---

### 术语规则

#### 添加规则

设置 → 术语规则 → 添加规则:
```
错误发音: 点击up
正确写法: ClickUp
分类: 产品名
```

#### 批量导入

准备 CSV 文件:
```csv
wrong,correct,category
点击up,ClickUp,产品名
诺讯,Notion,产品名
哥哥,GitHub,平台名
```

设置 → 术语规则 → 导入 CSV

#### 锁定标签

在文本中使用 `<lock>` 标签防止 LLM 修改:
```
<lock>Claude Code</lock> 的识别效果很好
```

---

### 声纹识别

#### 启用步骤

1. 设置 → 声纹识别 → 开启
2. 点击"注册声纹"
3. 录制 3 轮语音（每轮 3-5 秒）
4. 完成后自动启用验证

**工作原理**:
- 录音时实时提取声纹特征
- 与注册声纹对比相似度
- 通过阈值判断是否授权

**注意事项**:
- 首次使用需下载模型（~30MB）
- 声纹数据存储在本地，不上传云端
- 可随时重新注册

---

## 🔧 配置

### 环境变量

编辑 `.env` 文件:

```bash
# ASR 配置
ASR_PROVIDER=aliyun
ASR_API_KEY=sk-your_aliyun_api_key
ASR_MODEL=qwen3-asr-flash-realtime-2026-02-10
ASR_MAX_SILENCE_MS=1200

# LLM 配置
LLM_API_KEY=sk-your_llm_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo

# 声纹识别
VOICEPRINT_PROVIDER=LOCAL_ONNX
VOICEPRINT_THRESHOLD=0.5

# 快捷键
HOTKEY=<f9>

# 服务端口
PORT=18233
```

### 配置文件

运行时配置存储位置:
- **Windows**: `%APPDATA%\VoiceType\config.json`
- **macOS**: `~/Library/Application Support/VoiceType/config.json`
- **Linux**: `~/.config/voicetype/config.json`

---

## 🏗️ 技术架构

```
┌───────────────────────────────┐
│  Tauri Desktop App            │
│  - 系统托盘 + 浮动窗口          │
│  - 全局快捷键监听              │
│  - Vue 3 设置界面              │
└───────────────────────────────┘
           ↕ HTTP/WebSocket
┌───────────────────────────────┐
│  Python Backend (FastAPI)     │
│  ├─ ASR (阿里云 WebSocket)     │
│  ├─ 规则替换 (本地 JSON)       │
│  ├─ LLM (OpenAI-compatible)   │
│  ├─ 声纹识别 (本地 ONNX)       │
│  └─ 键盘输出 (Clipboard+Paste) │
└───────────────────────────────┘
```

**技术栈**:
- 后端: Python 3.10 + FastAPI
- 前端: Vue 3 + TypeScript
- 桌面: Tauri 2.0 + Rust
- ASR/LLM: 阿里云 DashScope
- 声纹: sherpa-onnx (本地 ONNX)

---

## 🔨 开发指南

### 项目结构

```
voicetype/
├── voicetype/              # Python 后端
│   ├── api/                # API 路由
│   ├── pipeline/           # ASR → LLM → 输出
│   ├── platform/           # 平台相关（声纹、场景、快捷键）
│   └── main.py             # 入口
├── src-ui/                 # Vue 3 前端
│   └── src/                # 组件和页面
├── src-tauri/              # Tauri 桌面应用
│   └── src/                # Rust 代码
└── scripts/                # 工具脚本
```

### 本地开发

```bash
# 后端
python -m voicetype.main

# 前端（开发模式，另一个终端）
cd src-ui
npm install
npm run dev
# 访问 http://localhost:5173
```

### 构建前端

```bash
cd src-ui
npm run build
# 输出到 src-ui/dist/
```

### 打包桌面应用

```bash
# 1. 构建前端
cd src-ui && npm run build && cd ..

# 2. 打包 Python 后端
pyinstaller voicetype-server.spec

# 3. 构建 Tauri 应用
cd src-tauri && npm run tauri build
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

**贡献方向**:
- ASR/LLM 提供商接入（讯飞、腾讯云、DeepSeek）
- UI/UX 优化
- 声纹识别优化
- 文档完善

---

## 📄 开源协议

AGPL-3.0 License

---

## 🙏 致谢

- [Tauri](https://tauri.app/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue 3](https://vuejs.org/)
- [阿里云 DashScope](https://dashscope.aliyun.com/)
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)

---

<div align="center">

Made with ❤️ by the VoiceType Community

</div>

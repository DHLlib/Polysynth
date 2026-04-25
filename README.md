# Polysynth

<p align="center">
  <b>Multi-LLM Agent Collaborative Discussion Simulator</b><br>
  <b>多 LLM Agent 协作讨论模拟器</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/React-18-61dafb.svg" alt="React 18">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-async-orange.svg" alt="SQLite Async">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
</p>

---

## English

Polysynth is a multi-LLM Agent collaborative discussion simulator that enables multiple AI roles to engage in structured, multi-round discussions around a single topic. It simulates real team collaboration scenarios, helping users analyze problems from different perspectives and reach comprehensive conclusions.

**Supported Modes:**
- **Six Thinking Hats** — Six roles (Facts, Emotion, Critical, Optimistic, Creative, Host) collaborate in multi-round discussions
- **Debate** — Pro team (4 speakers) vs Con team (4 speakers), moderator controls, fixed 4 rounds

### Features

- **Dual-Mode Runtime**: CLI terminal mode + Web UI mode share the same core engine
- **Real-time Streaming**: WebSocket transmits LLM streaming tokens; character-by-character display
- **File Upload**: Supports txt/md/pdf/docx/xlsx/pptx; AI extracts summaries and injects into all roles' prompts
- **Agent Tools**: DuckDuckGo search with two-phase calling and query optimization
- **Multi-Model Routing**: Each role independently configurable (DeepSeek, Kimi, Anthropic, etc.)
- **Provider Management**: Dynamic API Key / Base URL configuration via Web UI or CLI
- **Session Persistence**: SQLite + JSONL dual-write; historical sessions browsable and replayable
- **API Key Masking**: GET returns masked keys; PATCH ignores masked values to prevent accidental overwrites

### Quick Start

#### CLI Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Interactive mode
python backend/main.py

# With arguments
python backend/main.py run --mode six_hat --topic "Will AI replace programmers?" --rounds 3

# List history
python backend/main.py list

# View/modify configuration
python backend/main.py status
python backend/main.py config host --set-name "Host"
python backend/main.py config participants six_hat --role-key white --set-model "deepseek/deepseek-chat"
```

#### Web Mode

```bash
# Backend
pip install fastapi uvicorn sqlalchemy aiosqlite websockets python-multipart
pip install PyMuPDF python-docx openpyxl python-pptx  # Optional
.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy 2.0 (async), aiosqlite |
| LLM | LiteLLM (DeepSeek, Kimi, Anthropic, OpenAI-compatible) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Zustand, TanStack Query |
| Tools | DuckDuckGo search, file parsing (txt/md/pdf/docx/xlsx/pptx) |

---

## 中文

Polysynth 是一个多 LLM Agent 协作讨论模拟器，让多个 AI 角色围绕同一话题进行结构化多轮讨论，模拟真实团队协作场景，帮助用户从不同角度深入分析问题，获得更全面的结论。

**支持模式：**
- **六顶思考帽** — 六种思维角色（白帽·事实、红帽·情感、黑帽·批判、黄帽·乐观、绿帽·创意、蓝帽·主持人）多轮协作
- **辩论赛** — 正方四辩 vs 反方四辩，主持人控场，固定四轮

### 功能特性

- **双模式运行**：CLI 终端模式 + Web UI 模式共享同一套核心引擎
- **实时流式交互**：WebSocket 传输 LLM 流式 token，逐字显示
- **文件上传**：支持 txt/md/pdf/docx/xlsx/pptx，AI 提取摘要注入所有角色 prompt
- **Agent 工具**：DuckDuckGo 搜索，双阶段调用，关键词 AI 优化
- **多模型路由**：每个角色独立配置模型（DeepSeek、Kimi、Anthropic 等）
- **供应商管理**：通过 Web UI 或 CLI 动态配置 API Key / Base URL
- **会话持久化**：SQLite + JSONL 双写，历史会话可浏览、可回放
- **API Key 掩码**：GET 返回掩码值，PATCH 忽略掩码值防止误覆盖

### 快速开始

#### CLI 模式

```bash
# 安装依赖
pip install -r requirements.txt

# 交互式模式（缺失参数时提示输入）
python backend/main.py

# 带参数运行
python backend/main.py run --mode six_hat --topic "AI 会取代程序员吗？" --rounds 3

# 查看历史
python backend/main.py list

# 查看/修改配置
python backend/main.py status
python backend/main.py config host --set-name "主持人"
python backend/main.py config participants six_hat --role-key white --set-model "deepseek/deepseek-chat"
```

#### Web 模式

```bash
# 后端
pip install fastapi uvicorn sqlalchemy aiosqlite websockets python-multipart
pip install PyMuPDF python-docx openpyxl python-pptx  # 可选：文件解析

# Windows
.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000
# macOS/Linux
.venv/bin/python -m uvicorn backend.api.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev  # http://localhost:5173
```

浏览器打开 `http://localhost:5173`，选择模式、输入话题、点击开始即可实时观看多 Agent 讨论。

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, FastAPI, SQLAlchemy 2.0 (异步), aiosqlite |
| LLM | LiteLLM（DeepSeek、Kimi、Anthropic、OpenAI 兼容） |
| 前端 | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Zustand, TanStack Query |
| 工具 | DuckDuckGo 搜索、文件解析（txt/md/pdf/docx/xlsx/pptx） |

---

## Architecture / 架构

```
Browser (React)        CLI (Terminal)
     |                       |
     |  WS / REST            |  Session.run()
     v                       v
FastAPI ---------------+  TerminalOutputHandler
  |  WebSocket handler  |
  |  RuntimeConfig.from_db()  |
  v                       |
Session (Orchestrator) <-----+
  |
  +-- ModeRunner (six_hat / debate)
  |       +-- call_llm() via LiteLLM
  |       +-- StreamEvent yield
  |
  +-- SQLite (messages, sessions, config)
  +-- JSONL (runtime backup)
```

See [docs/architecture.md](docs/architecture.md) for detailed documentation.

---

## Documentation / 文档

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | System architecture, data flow, extension guide |
| [docs/features.md](docs/features.md) | Feature overview, usage scenarios, configuration reference |
| [docs/api-contract.md](docs/api-contract.md) | REST API, WebSocket protocol, component interfaces |

---

## Configuration / 配置

Before first run, create `backend/config/secrets.json`:

```json
{
  "deepseek_api_key": "sk-your-deepseek-key",
  "kimi_api_key": "sk-your-kimi-key",
  "kimi_base_url": "https://api.kimi.com/coding"
}
```

The first backend startup automatically seeds the database from JSON config files. After that, all configuration can be modified via Web UI or CLI `config` commands.

---

## License / 许可证

MIT License

# Polysynth

**Polysynth** is a multi-LLM Agent collaborative discussion simulator. Multiple AI roles (e.g., Six Thinking Hats, debate teams) engage in structured multi-round discussions around a single topic, simulating real team collaboration to help users analyze problems from different angles and reach comprehensive conclusions.

**Polysynth** 是一个多 LLM Agent 协作讨论模拟器。多个 AI 角色（如六顶思考帽、辩论双方）围绕同一话题进行结构化多轮讨论，模拟真实团队协作场景，帮助用户从不同角度深入分析问题，获得更全面的结论。

---

## Features / 功能特性

- **Dual Discussion Modes / 双讨论模式**
  - **Six Thinking Hats / 六顶思考帽**: White (facts), Red (emotion), Black (critical), Yellow (optimistic), Green (creative), Blue (host) — structured thinking from six perspectives.
  - **Debate / 辩论赛**: Host, Pro, Con — structured attack and defense around a proposition.

- **Multi-Model Routing / 多模型路由**
  - Each role can be configured with a different LLM (DeepSeek, Kimi, etc.) via LiteLLM.
  - Model-provider mapping is maintained in the database and configurable through the Web UI.

- **File Upload & AI Summarization / 文件上传与 AI 摘要**
  - Support `txt`, `md`, `pdf`, `docx`, `xlsx`, `pptx` (max 20MB per file, up to 5 files).
  - File contents are extracted, summarized by AI, and injected into all roles' system prompts as background material.

- **Agent Tools / Agent 工具**
  - DuckDuckGo search tool with dual fallback (`html` / `lite`) for China network compatibility.
  - Two-phase tool calling: Phase 1 detects `tool_calls` → executes search → Phase 2 streams the final answer based on results.

- **Streaming Real-Time Output / 流式实时输出**
  - Web UI: Typewriter-like token-by-token display via WebSocket.
  - CLI: Colored terminal output with banners and role colors.

- **Session Persistence / 会话持久化**
  - SQLite database (`polysynth.db`) stores sessions, messages, attachments, and configurations.
  - JSONL backup files in `sessions/` for debugging.

- **Web UI + CLI Dual Mode / Web UI + CLI 双模式**
  - **Web Mode**: React + FastAPI + SQLite, real-time viewing in browser.
  - **CLI Mode**: Terminal output, no additional dependencies.

- **Configuration Panel / 配置面板**
  - Edit role models, names, colors, system prompts, and tool enablement via the Web UI slider panel.

---

## Tech Stack / 技术栈

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), aiosqlite, LiteLLM |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query |
| LLM | DeepSeek, Kimi (via LiteLLM) |
| Database | SQLite (async via aiosqlite) |
| Tools | DuckDuckGo Search |

---

## Quick Start / 快速开始

### Prerequisites / 环境要求

- Python 3.11+
- Node.js 18+
- API Keys for at least one LLM provider (DeepSeek or Kimi)

### 1. Clone & Setup / 克隆与初始化

```bash
git clone <repository-url>
cd Polysynth_v2
```

Create `backend/config/secrets.json` with your API keys:

```json
{
  "deepseek_api_key": "sk-xxx",
  "kimi_api_key": "sk-xxx",
  "kimi_base_url": "https://api.kimi.com/coding"
}
```

### 2. Backend / 后端

```bash
# Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn sqlalchemy aiosqlite websockets python-multipart
pip install PyMuPDF python-docx openpyxl python-pptx  # optional, for file upload

# Start server
python -m uvicorn backend.api.main:app --reload --port 8000
```

The backend will:
- Initialize SQLite database (`polysynth.db`)
- Seed default mode configurations from JSON files
- Start FastAPI server at `http://localhost:8000`

### 3. Frontend / 前端

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 4. CLI Mode / CLI 模式 (Optional)

```bash
# Windows
.venv\Scripts\activate
python backend/main.py

# The topic and mode can be configured in backend/config/app.json
```

---

## Usage / 使用方式

### Web UI

1. **Select Mode**: Choose `six_hat` or `debate` from the dropdown in the header.
2. **Set Rounds**: Adjust rounds (1-10 for six_hat, fixed 4 for debate).
3. **Upload Files** (Optional): Drag and drop or click to upload files as background material.
4. **Enter Topic**: Type your discussion topic in the input box.
5. **Start**: Click the "开始" button to launch the discussion.
6. **Watch**: Real-time streaming messages appear in the chat area.
7. **Configure**: Click the gear icon to open the configuration panel and edit role parameters.
8. **History**: Switch between past sessions via the left sidebar.

### CLI

1. Edit `backend/config/app.json`:
   ```json
   {
     "topic": "AI时代下，软件测试工程师的发展趋势如何？",
     "rounds": 3,
     "default_mode": "six_hat"
   }
   ```
2. Run `python backend/main.py`.
3. Watch colored terminal output in real-time.

---

## Project Structure / 项目结构

```
Polysynth_v2/
├── backend/
│   ├── api/                    # FastAPI web service
│   ├── core/                   # Core engine (Session, LLM, tools, modes)
│   ├── datebase/               # SQLAlchemy ORM + CRUD
│   ├── config/                 # JSON configs (modes, models, secrets)
│   └── main.py                 # CLI entry point
├── frontend/
│   └── src/
│       ├── api/                # Axios client + API functions
│       ├── components/         # React UI components
│       ├── hooks/              # WebSocket + data hooks
│       └── stores/             # Zustand state management
├── sessions/                   # Runtime JSONL backups
├── uploads/                    # Uploaded files
├── logs/                       # Application logs
└── polysynth.db                # SQLite database
```

---

## Configuration / 配置说明

| File | Purpose | Git |
|------|---------|-----|
| `backend/config/app.json` | CLI mode: topic, rounds, default_mode | Yes |
| `backend/config/models.json` | Default role configurations | Yes |
| `backend/config/modes/*.json` | Mode rules (speaking order, templates) | Yes |
| `backend/config/secrets.json` | API keys | **No** (gitignored) |
| `polysynth.db` | Runtime SQLite database | **No** (gitignored) |

Web-mode configurations are stored in `polysynth.db` and editable via the UI configuration panel.

---

## Screenshots / 截图

*(To be added before GitHub release)*

---

## License / 许可证

MIT

# Polysynth Feature Documentation

## 1. Product Overview

Polysynth is a multi-LLM Agent collaborative discussion simulator. Multiple AI roles engage in structured discussions around a single topic, simulating real team collaboration scenarios and helping users analyze problems from different perspectives to reach comprehensive conclusions.

Supports **CLI Terminal Mode** and **Web UI Mode**, sharing the same core engine.

---

## 2. Feature Summary

| Feature | Description |
|---------|-------------|
| **Six Thinking Hats** | Six thinking roles (White·Facts, Red·Emotion, Black·Critical, Yellow·Optimistic, Green·Creative, Blue·Host) collaborate in multi-round discussions |
| **Debate** | Pro team (4 speakers) vs Con team (4 speakers), moderator controls, fixed 4 rounds (opening, deepening, attacking, concluding) |
| **Real-time Streaming** | WebSocket transmits LLM streaming tokens; browser displays character-by-character |
| **Participant Configuration** | Each role independently configurable: model, name, color, system prompt; Hex <-> ANSI color conversion |
| **Provider Management** | Multi-LLM provider dynamic configuration (API Key, Base URL), model-provider binding, runtime auto-routing |
| **File Upload** | Supports txt/md/pdf/docx/xlsx/pptx; AI extracts summaries and injects into all roles' system prompts |
| **Agent Tools** | DuckDuckGo search with dual-fallback (html/lite), two-phase calling, results written to history |
| **Round Control** | Metadata-driven: `configurable` flag controls frontend adjustability (Six Hats: 1-10 rounds, Debate: fixed 4 rounds) |
| **Session History** | Sidebar shows all historical sessions; click to review full records; history merges with real-time events on switch |
| **Dual-Mode Runtime** | Web mode (React + FastAPI + SQLite) and CLI mode share the same core engine |
| **Data Persistence** | SQLite async storage + JSON config files as default seed + `.jsonl` runtime backup |
| **CLI Subcommands** | `run`/`list`/`replay`/`status`/`config` with interactive prompts when arguments are missing |
| **API Key Masking** | GET returns masked keys (`sk-****xxxx`); PATCH ignores masked values to prevent accidental overwrites |

---

## 3. Discussion Modes

### 3.1 Six Thinking Hats (`six_hat`)

Based on Edward de Bono's "Six Thinking Hats" methodology:

| Role | Color | Thinking Angle | Responsibility |
|------|-------|---------------|----------------|
| Blue·Host | Blue | Global control | Opening introduction, round summaries, final conclusion |
| White·Facts | White | Objective facts | Provide data, statistics, known information |
| Red·Emotion | Red | Emotional intuition | Express feelings, concerns, expectations |
| Black·Critical | Gray | Critical skepticism | Point out risks, flaws, negative consequences |
| Yellow·Optimistic | Yellow | Optimistic value | Find opportunities, benefits, positive aspects |
| Green·Creative | Green | Innovation | Propose new ideas, unconventional solutions |

**Flow**:
1. Blue Hat opening (introduces topic and rules)
2. Each round: White → Red → Black → Yellow → Green
3. Blue Hat summary after each round
4. Final Blue Hat conclusion after last round

### 3.2 Debate (`debate`)

Structured debate simulation:

| Role | Color | Responsibility |
|------|-------|---------------|
| Moderator | Cyan | Opening, guiding attacks/defenses, objective commentary |
| Pro_1 | Green | Pro position establishment |
| Pro_2 | Dark Green | Pro position deepening |
| Pro_3 | Green | Pro attack/defense |
| Pro_4 | Dark Green | Pro conclusion |
| Con_1 | Red | Con position establishment |
| Con_2 | Dark Red | Con position deepening |
| Con_3 | Red | Con attack/defense |
| Con_4 | Dark Red | Con conclusion |

**Flow**:
1. Moderator opening
2. Each round: Pro → Con
3. Moderator summary after each round
4. Final moderator judgment

### 3.3 Mode Switching

**Web Mode**: Select mode from frontend dropdown, enter topic, click Start.

**CLI Mode**:
```bash
# Specify mode via command line
python backend/main.py run --mode debate --topic "AI是否会取代程序员" --rounds 2

# Or interactively
python backend/main.py run
# > 可用模式: six_hat, debate
# > 请选择模式 [six_hat]: debate
# > 请输入讨论话题: AI是否会取代程序员
# > 请输入轮次 [4]: 2
```

---

## 4. Core Features

### 4.1 Multi-Model Routing

Support multiple LLM providers simultaneously via LiteLLM:

- **DeepSeek**: `deepseek/deepseek-chat` (general), `deepseek/deepseek-reasoner` (reasoning)
- **Kimi**: `openai/moonshot-v1-8k` (OpenAI-compatible)
- **Anthropic**: `anthropic/claude-opus-4-7`, etc.

Each role can be configured with a different model. E.g., Host/Blue Hat uses stronger reasoning models while others use chat models.

### 4.2 Streaming Output

All LLM responses are streamed in real time:

- **CLI Mode**: Terminal prints tokens in real time with role colors
- **Web Mode**: Browser character-by-character display, ChatGPT-like typing effect

### 4.3 Shared History

All roles share the same discussion history. Each round sees all previous content, enabling true multi-Agent collaboration. Tool results (e.g., search summaries) are also injected into history with `【工具调用记录】` markers.

### 4.4 Session Persistence

Each discussion generates a Session, automatically persisted to multiple locations:

- **SQLite Database** (`polysynth.db`):
  - `sessions` table: Session metadata
  - `messages` table: Full utterance records
- **File System** (backup/debug):
  - `sessions/{id}.jsonl`: Complete utterance log
  - `sessions/{id}.state.json`: Runtime state

Supports breakpoint recovery and post-analysis.

### 4.5 Event Stream System

All output flows through typed events:

| Event Type | Trigger | Purpose |
|------------|---------|---------|
| `TurnStartEvent` | Role starts speaking | Print banner, set color, show role name |
| `TokenEvent` | Streaming token received | Real-time print, character display |
| `TurnEndEvent` | Role finishes speaking | Update history + persist jsonl + write DB |
| `BannerEvent` | Round/stage transition | Stage banner, centered prompt |
| `SessionEndEvent` | Discussion ends | Closing message, mark complete |
| `ToolStartEvent` | Tool execution begins | Notify which tool is being used |
| `ToolEndEvent` | Tool execution completes | Show tool result preview |

Easily extensible for different output targets (terminal, WebSocket, file, etc.).

### 4.6 Agent Tools (Search)

Roles can enable tool calling via `tools_enabled` JSON array (e.g., `["search"]`):

- **DuckDuckGo Search**: Free search API with dual fallback (`backend="html"` and `"lite"`) for China mainland network compatibility
- **Two-Phase Calling**: Phase 1 (non-streaming, temp=0.3) detects `tool_calls` → executes search → Phase 2 (streaming, temp=0.8, `tool_choice="none"`) outputs final answer based on search results
- **Search Query Optimization**: Before calling search, the current role's model generates optimized keywords from topic + history
- **Tool Results in History**: Search summaries are appended to `session.add_history()` so subsequent roles can see prior search records, avoiding duplicate searches

### 4.7 Web UI

React frontend referencing mainstream AI Chat UIs (ChatGPT/Claude):

- **Left Sidebar**: Historical Session list showing topic, mode badge, status dot, timestamp
- **Top Toolbar**: Mode selector, topic input, round display, settings gear, file upload zone
- **Main Chat Area**:
  - Centered banners for stage transitions
  - Role message bubbles with colored borders
  - Real-time streaming token display
  - History messages merged with live events
- **Config Panel** (slide-out): Edit participant model, name, color, system_prompt
- **File Upload** (drag/drop or click): txt/md/pdf/docx/xlsx/pptx, single file 20MB, max 5 files
  - Text extraction → AI structured summary → injected into all roles' system prompts as `【背景资料】`

### 4.8 Configuration Management

Role configurations and default rounds are persisted to the database and user-modifiable:

**Web UI**:
- Open config panel → edit role parameters → save
- Next Session automatically reads latest configuration

**CLI**:
```bash
# View current config
python backend/main.py status

# Modify global host
python backend/main.py config host --set-name "主持人" --set-model "deepseek/deepseek-reasoner"

# Modify participant
python backend/main.py config participants six_hat --role-key white --set-model "deepseek/deepseek-chat"

# Modify provider
python backend/main.py config providers --provider deepseek --set-key "sk-xxx" --add-model "deepseek/deepseek-chat"
```

### 4.9 Terminal Color Output

CLI mode uses independent ANSI colors per role for intuitive visual distinction.

### 4.10 API Key Security

- **GET Masking**: `ProviderOut` serializes `api_key` as `sk-****xxxx` format
- **PATCH Protection**: `patch_provider` detects `"****"` in incoming `api_key` and skips update, preventing frontend from accidentally overwriting real keys with masked values
- **Database Storage**: API keys are stored in SQLite (local), never exposed in JSON config files to git

---

## 5. Configuration Files

### 5.1 app.json (CLI Defaults)

```json
{
  "topic": "讨论话题",
  "rounds": 3,
  "default_mode": "six_hat"
}
```

| Field | Description |
|-------|-------------|
| `topic` | Default discussion topic |
| `rounds` | Default round count |
| `default_mode` | Default mode (`six_hat` or `debate`) |

### 5.2 models.json (Seed Source)

```json
{
  "six_hat": {
    "blue": {
      "model": "deepseek/deepseek-reasoner",
      "name": "蓝帽·主持人",
      "color": "[94m"
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `model` | LiteLLM model name |
| `name` | Display name (can include emoji) |
| `color` | ANSI terminal color code |

Auto-imported to DB on first backend startup; modifiable via Web UI or CLI afterwards.

### 5.3 modes/*.json

```json
{
  "opening": {
    "speaker": "blue",
    "extra_instruction": "Opening prompt template"
  },
  "rounds": {
    "speaking_order": ["white", "red", "black", "yellow", "green"],
    "summary": {
      "speaker": "blue",
      "mid_template": "Mid-round summary template",
      "final_template": "Final summary template"
    }
  }
}
```

### 5.4 secrets.json

```json
{
  "deepseek_api_key": "sk-xxx",
  "kimi_api_key": "sk-xxx",
  "kimi_base_url": "https://api.kimi.com/coding"
}
```

This file is in `.gitignore` and will not be committed.

---

## 6. Running the Application

### 6.1 CLI Terminal Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Interactive mode (prompts for missing arguments)
python backend/main.py

# With arguments
python backend/main.py run --mode six_hat --topic "AI的未来" --rounds 3

# List history
python backend/main.py list

# Replay a session
python backend/main.py replay <session_id>

# View configuration
python backend/main.py status

# Modify configuration
python backend/main.py config host --set-name "主持人"
python backend/main.py config participants six_hat --role-key white --set-model "deepseek/deepseek-chat"
python backend/main.py config providers --provider deepseek --set-key "sk-xxx"
```

### 6.2 Web UI Mode

**Start Backend**:

```bash
pip install fastapi uvicorn sqlalchemy aiosqlite websockets python-multipart
pip install PyMuPDF python-docx openpyxl python-pptx  # Optional: file parsing

# Windows
.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000

# Unix/macOS
.venv/bin/python -m uvicorn backend.api.main:app --reload --port 8000
```

**Start Frontend**:

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

Open browser at `http://localhost:5173`, select mode, enter topic, click Start to watch the multi-Agent discussion in real time.

### 6.3 API Connectivity Test

```bash
python test_kimi_code.py
```

Validates Kimi/DeepSeek API availability.

---

## 7. Use Cases

| Scenario | Recommended Mode | Explanation |
|----------|-----------------|-------------|
| Product Design Review | six_hat | Multi-dimensional evaluation from facts, emotion, risks, value, and creativity |
| Technology Selection | six_hat | Comprehensive analysis of pros and cons |
| Debate Preparation | debate | Simulate pro/con attacks and defenses to refine arguments |
| Decision Analysis | six_hat | Structured thinking, avoiding cognitive bias |
| Creative Brainstorming | six_hat (Green Hat focus) | Stimulate unconventional ideas |
| Academic Discussion | six_hat | Rigorous multi-angle analysis |

---

## 8. Output Examples

### CLI Terminal Output (Six Thinking Hats)

```
════════════════════════════════════════════════════════════
  Six Thinking Hats Discussion Starting
════════════════════════════════════════════════════════════

Topic: Will vibe coding really make programming easier?
Rounds: 3

────────────────────────────────────────────────────────────
  Blue Hat · Host
────────────────────────────────────────────────────────────
Today's discussion topic is... [Blue Hat opening]

════════════════════════════════════════════════════════════
  Round 1
════════════════════════════════════════════════════════════

... [Subsequent role speeches]
```

Full record saved to `sessions/{session_id}.jsonl` and `polysynth.db`.

### Web UI Output

- Left sidebar shows historical Session list
- Main area displays Banner → Role speech (streaming tokens) → Round transition → End
- Each message has role-colored border and avatar
- Config panel editable role parameters

---

## 9. Future Roadmap

| Feature | Priority | Status |
|---------|----------|--------|
| Web UI | High | ✅ Completed |
| File Upload | High | ✅ Completed (6 formats + AI summary injection) |
| Agent Tools (Search) | High | ✅ Completed (DuckDuckGo dual-fallback) |
| CLI Subcommands | Medium | ✅ Completed (run/list/replay/status/config) |
| API Key Masking | Medium | ✅ Completed |
| Anthropic Compatibility | Medium | ✅ Completed |
| More Modes | Medium | 🔄 Planned: SWOT Analysis, Brainstorming, Delphi Method |
| History Summarization | Medium | 🔄 Planned: Auto-compress long history to prevent token overflow |
| Concurrent Speaking | Low | 🔄 Planned: Multiple roles speak simultaneously |
| Export Results | Low | 🔄 Planned: Export to Markdown, PDF reports |
| Custom Roles | Low | 🔄 Planned: User-defined new roles and prompts |

---

*Document Version: 2026-04-25*

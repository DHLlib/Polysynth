# Polysynth Architecture

## 1. System Overview

Polysynth is a multi-LLM Agent collaborative discussion simulator. The system enables multiple AI roles (e.g., Six Thinking Hats, debate teams) to engage in structured multi-round discussions around a single topic, producing collaborative conclusions.

**Core Design Principles:**

- **Session-centric**: Session is the orchestration hub, managing configuration, history, event routing, and persistence.
- **Pluggable Modes**: New discussion modes only need to implement the `ModeRunner` Protocol.
- **Unified Event Stream**: All output flows through typed `StreamEvent`s; consumers handle rendering independently.
- **Pure Data Configuration**: Roles, prompts, and rules are externalized to JSON — switch modes without touching code.
- **Frontend/Backend Decoupling**: FastAPI provides REST API + WebSocket; React frontend consumes the event stream in real time.
- **Dual-Mode Runtime**: CLI terminal mode and Web UI mode share the same core engine.

---

## 2. Directory Structure

```
Polysynth_v2/
├── backend/
│   ├── main.py                    # CLI entry: argparse subcommands (run/list/replay/status/config)
│   ├── Prompts.py                 # System Prompt repository, grouped by mode
│   ├── config/
│   │   ├── app.json               # Global defaults: topic, rounds, default_mode
│   │   ├── models.json            # Participant defaults by mode (seed source)
│   │   ├── secrets.json           # API Keys (gitignored)
│   │   └── modes/
│   │       ├── six_hat.json       # Six Thinking Hats rules
│   │       └── debate.json        # Debate rules
│   ├── api/                       # FastAPI Web service
│   │   ├── main.py                # FastAPI app, lifespan, CORS
│   │   ├── deps.py                # DB session dependency
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── routers/
│   │       ├── sessions.py        # POST/GET /api/sessions, WS /ws/{id}
│   │       ├── config.py          # GET/PATCH config endpoints (with API key masking)
│   │       └── modes.py           # GET /api/modes
│   ├── core/                      # Core engine
│   │   ├── session.py             # Session driver: history, handlers, persistence
│   │   ├── agent_generator.py     # LLM call layer via LiteLLM (pure IO)
│   │   ├── config.py              # Config file singleton (CLI fallback)
│   │   ├── runtime_config.py      # RuntimeConfig from DB (Web mode)
│   │   ├── output_handlers.py     # TerminalOutputHandler + WebSocketOutputHandler
│   │   ├── logger.py              # Unified logging (console + rotating file, anti-uvicorn)
│   │   ├── file_parser.py         # Text extraction (txt/md/pdf/docx/xlsx/pptx)
│   │   ├── summarizer.py          # AI file summary generator
│   │   ├── tools/                 # Agent tool layer
│   │   │   ├── __init__.py
│   │   │   ├── schema.py          # ToolSchema dataclass
│   │   │   ├── registry.py        # Tool registry
│   │   │   └── search.py          # DuckDuckGo search tool
│   │   └── modes/
│   │       ├── base.py            # ModeRunner Protocol
│   │       ├── registry.py        # Mode registry
│   │       ├── six_hat.py         # SixHatRunner
│   │       └── debate.py          # DebateRunner
│   └── datebase/                  # Data layer
│       ├── stream_events.py       # StreamEvent type definitions
│       ├── models.py              # SQLAlchemy ORM models
│       ├── engine.py              # Async engine + session factory
│       └── crud.py                # CRUD + seed initialization
├── frontend/                      # React frontend
│   ├── src/
│   │   ├── api/                   # Axios client + types + API functions
│   │   ├── components/            # UI components (Sidebar, ChatView, Header, FileUploadZone, ConfigPanel)
│   │   ├── hooks/                 # useWebSocket, useSessions
│   │   ├── stores/                # Zustand UI state
│   │   ├── lib/                   # Utilities (ANSI <-> Hex color conversion)
│   │   ├── App.tsx                # Root layout
│   │   └── main.tsx               # React root + QueryClient
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.app.json
├── sessions/                      # Runtime: jsonl + state.json
├── logs/                          # Runtime logs (gitignored)
├── uploads/                       # Uploaded files (gitignored)
├── polysynth.db                   # SQLite database (runtime, gitignored)
├── docs/                          # Documentation
└── test_kimi_code.py              # API connectivity test
```

---

## 3. Core Components

### 3.1 Config (File Singleton)

**File**: `backend/core/config.py`

- Loads `app.json` + `models.json` + `secrets.json` + `modes/*.json` + `Prompts.py`
- Filters `participants` and `prompts` by `default_mode`
- Provides singleton access via `Config.get()`, supports `Config.reload()` for hot updates

**Used in CLI mode as fallback** when `runtime_config` is not provided.

### 3.2 RuntimeConfig (Database-Backed)

**File**: `backend/core/runtime_config.py`

A non-frozen, non-singleton dataclass with the same fields as `Config`:

- `from_db(db, mode_name, topic)`: queries `ModeConfig` + `Participant` list from DB
- Injects `GlobalHost` configuration (overrides `name`/`model`/`color`, **preserves** `system_prompt`)
- `Session.get_config()` prefers `runtime_config`, falls back to `Config.get()`

### 3.3 Session (Orchestration Hub)

**File**: `backend/core/session.py`

| Method | Description |
|--------|-------------|
| `add_history(role, content)` | Append LLM message to in-memory history |
| `get_history()` | Return full history copy as `[{role, content}, ...]` |
| `register_output_handler(handler)` | Register an async event consumer |
| `run()` | Main driver: resolve `ModeRunner`, iterate events, forward to handlers, auto-persist |
| `append_message(entry)` | Append to `.jsonl` message log |
| `get_config()` | Prefer `runtime_config`, else `Config.get()` |
| `load(key)` / `save(key, value)` | Read/write `.state.json` |

**Duplicate Detection**: When tool calling is active, `call_llm` may already append tool results to history. `TurnEndEvent` logic detects duplicates via `"【工具调用记录】"` content check to avoid double-writing.

### 3.4 ModeRunner (Protocol)

**File**: `backend/core/modes/base.py`

```python
class ModeRunner(Protocol):
    mode_name: str
    async def run(self, session: Session) -> AsyncIterator[StreamEvent]: ...
```

Implementations (`six_hat.py`, `debate.py`):
- Read mode rules from `session.get_config()`
- Orchestrate speaking order (opening -> rounds -> summary)
- Build system prompts (including attachment summaries and tool instructions)
- Call `call_llm(session, model, messages, cfg, tools)`
- Yield `StreamEvent`s (no printing, no logging, no history management)

### 3.5 Logger

**File**: `backend/core/logger.py`

- Dual output: console `StreamHandler` + `logs/app.log` (`TimedRotatingFileHandler`, daily rotation, 7-day retention)
- `LOG_LEVEL` environment variable support (default: INFO)
- `restore_loggers()` defense against uvicorn's `dictConfig(disable_existing_loggers=True)`

### 3.6 call_llm (LLM Call Layer)

**File**: `backend/core/agent_generator.py`

Pure IO function via LiteLLM:

- **Dynamic Temperature**: Phase 1 / with tools → `0.3`; Phase 2 / normal chat → `0.8`
- **Two-Phase Tool Calling**: Phase 1 (non-streaming) detects `tool_calls` → executes tools → Phase 2 (streaming) outputs final answer with `tool_choice="none"` (except R1)
- **Anthropic Compatibility**: Phase 2 passes `tools` parameter even though `tool_choice="none"` prevents re-invocation, satisfying Anthropic's requirement that messages containing `tool_calls` must also include `tools`
- **DSML Filtering**: Strips DeepSeek DSML tags (`<｜DSML｜tool_calls>`) and XML tool call formats from final output
- **Provider Resolution**: `_resolve_provider(model)` queries DB for `api_key` + `base_url`, with process-level `_provider_cache`; `clear_provider_cache()` invalidates on config changes
- **Search Query Optimization**: `_summarize_search_query()` uses the current role's model to generate optimized search keywords from topic + history

### 3.7 Output Handlers

**File**: `backend/core/output_handlers.py`

| Handler | Purpose | Used In |
|---------|---------|---------|
| `TerminalOutputHandler` | Terminal color printing, banners, newline reset | CLI mode |
| `WebSocketOutputHandler` | Serialize events to JSON over WebSocket | Web mode |

### 3.8 File Parsing & Summarization

| Module | Purpose |
|--------|---------|
| `file_parser.py` | Extract text from 6 formats: txt, md, pdf, docx, xlsx, pptx |
| `summarizer.py` | Call LLM (temperature 0.3) to generate structured summaries, truncated to 15,000 chars |

Attachment flow: file saved to `uploads/` → text extracted → AI summary generated → stored in `attachments` table → injected into all roles' system prompts as `【背景资料】` at discussion start.

### 3.9 Database Layer

**Files**: `backend/datebase/models.py`, `engine.py`, `crud.py`

SQLAlchemy 2.0 + aiosqlite, async ORM.

| Table | Purpose |
|-------|---------|
| `mode_configs` | Mode metadata (name, display_name, mode_json, default_rounds) |
| `participants` | Role definitions per mode (role_key, model, name, color, system_prompt, tools_enabled) |
| `sessions` | Session records (id, mode, topic, rounds, status, created_at, completed_at) |
| `messages` | Utterances (session_id, role_key, role, name, content, model, ts) |
| `attachments` | Uploaded files (session_id, filename, file_type, file_size, storage_path, summary) |
| `providers` | LLM providers (name, api_key, base_url) |
| `provider_models` | Model-provider bindings (model_name, provider_id) |
| `global_hosts` | Global host config (name, model, system_prompt, color) |

Initialization: `seed_db_from_files()` idempotently imports defaults from JSON config files.

---

## 4. Data Flow

### 4.1 CLI Mode

```
backend/main.py (argparse: run/list/replay/status/config)
    |
    v
Session.run() ────────► get_config() -> RuntimeConfig.from_db() (or Config.get() fallback)
    |
    |-- Resolve ModeRunner from registry
    |       `-- SixHatRunner / DebateRunner
    |
    v
ModeRunner.run(session)
    |
    |-- Orchestrate speaking order
    |-- Build system prompt (with attachment summaries + tool instructions)
    |-- Read session.get_history()
    |
    v
call_llm(session, model, messages, cfg, tools)
    |
    |-- _resolve_provider(model) -> DB query (cached)
    v
LiteLLM --> DeepSeek API / Kimi API / Anthropic API / etc.
    |
    v
StreamEvent (yield)
    |
    |-- TurnStartEvent --> TerminalOutputHandler (banner + color)
    |-- TokenEvent     --> TerminalOutputHandler (real-time print)
    |-- TurnEndEvent   --> Session (update history + persist jsonl + DB callback)
    |-- BannerEvent    --> TerminalOutputHandler (stage banner)
    |-- ToolStartEvent --> TerminalOutputHandler (tool usage notice)
    |-- ToolEndEvent   --> TerminalOutputHandler (tool result preview)
    `-- SessionEndEvent --> TerminalOutputHandler (completion message)
```

### 4.2 Web Mode

```
Browser (React)
    |
    | POST /api/sessions {mode, topic, files} (multipart)
    | Returns {id, status: "pending"}
    v
FastAPI
    |-- Validate files -> Create DB session record
    |-- Extract text -> AI summary -> Store Attachment
    |-- Frontend connects WS /api/sessions/ws/{id}
    v
WebSocket handler
    |-- Validate -> status="running" -> RuntimeConfig.from_db()
    |-- Inject attachment summaries into system prompts
    |-- Create Session(id, runtime_config=cfg, db_callback=...)
    |-- Register WebSocketOutputHandler(websocket)
    |-- asyncio.create_task(session.run()) in background
    v
Session.run()
    |-- Forward events to WebSocketOutputHandler
    |-- WebSocketOutputHandler sends JSON to browser
    |-- TurnEndEvent: jsonl + DB dual-write
    v
Browser (React ChatView)
    |-- Load history messages + merge with real-time events
    |-- turn_start --> Show role name + color border
    |-- token     --> Append char-by-char to current message
    |-- turn_end  --> Solidify message, clear stream state
    |-- banner    --> Center stage prompt
    |-- session_end --> Mark complete, refresh sidebar
```

---

## 5. Configuration Layers

| Source | Purpose | Mutable at Runtime | Git Tracked |
|--------|---------|-------------------|-------------|
| `config/app.json` | CLI defaults: topic, rounds, default_mode | No | Yes |
| `config/models.json` | Default role config (seed DB) | No | Yes |
| `config/modes/*.json` | Mode rules: speaking order, templates | No | Yes |
| `config/secrets.json` | API Keys | No | No (gitignore) |
| `Prompts.py` | System Prompt repository | No | Yes |
| `polysynth.db` | Web/CLI runtime authoritative config | Yes (via Web UI / CLI config) | No (gitignore) |

In Web mode, frontend only sends `mode` + `topic`; `participants` and `rounds` are read from DB (user-modifiable).

In CLI mode, `config` subcommands modify DB directly; `run` without args enters interactive prompt mode.

---

## 6. Extension Guide

### 6.1 Add a New Discussion Mode

1. Define participants in `config/models.json`
2. Create `config/modes/{mode_name}.json` with rules
3. Add prompts in `Prompts.py` under `SYSTEM_PROMPTS`
4. Implement `backend/core/modes/{mode_name}.py` implementing `ModeRunner`
5. Register in `registry.py` `_REGISTRY`
6. Restart backend to auto-seed DB

### 6.2 Add a New Output Handler

Implement `async def __call__(self, event: StreamEvent)` and register:

```python
session.register_output_handler(MyHandler())
```

### 6.3 Add a New LLM Provider

Add models via Web UI or CLI:

```bash
python backend/main.py config providers --provider <name> --set-key "sk-xxx" --add-model "provider/model-name"
```

Or seed from `secrets.json` on first startup.

---

## 7. Known Limitations

1. **Token Growth**: `_run_role()` embeds full history in the system prompt. Token count grows linearly with rounds. Future: pass history as `messages` instead of stuffing into system prompt.
2. **Monotonic History**: `discussion_history` only grows; long sessions may exceed context limits.
3. **No Parallel Speaking**: `call_llm()` is sequential; parallel role speaking requires additional implementation.
4. **Single WebSocket Viewer**: Only one client can watch a running session at a time.

---

*Document Version: 2026-04-25*
*Corresponding Commit: CLI mode refactoring + API security + Anthropic compatibility*

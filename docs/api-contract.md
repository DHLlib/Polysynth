# Polysynth API Contract

> This document describes all interface contracts between Polysynth frontend and backend, including REST API, WebSocket protocol, frontend component Props, and backend core module interfaces.

---

## 1. REST API

Base URL: `http://localhost:8000`

### 1.1 Session Management

#### `POST /api/sessions`

Create a new discussion Session (supports file upload).

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes | Discussion mode: `"six_hat"` / `"debate"` |
| `topic` | string | Yes | Discussion topic |
| `rounds` | int | No | Round count (only effective when `mode_json.rounds.configurable=true`) |
| `files` | File[] | No | Attachment files, max 5, single file max 20MB |

**Response:** `201 Created` — `SessionOut`

```json
{
  "id": "9cae5b334e0743ba8e516dd57d6ffd89",
  "mode": "six_hat",
  "topic": "Does an e-commerce company need self-built RAG?",
  "rounds": 3,
  "status": "pending",
  "created_at": "2026-04-24T00:31:00"
}
```

**Errors:**
- `400` — File count exceeds 5, or unsupported file type
- `413` — Single file exceeds 20MB

---

#### `GET /api/sessions`

Get Session list.

**Query Params:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Offset |

**Response:** `200 OK` — `SessionOut[]`

---

#### `GET /api/sessions/{session_id}`

Get single Session detail (with message list).

**Response:** `200 OK` — `SessionDetailOut`

```json
{
  "id": "...",
  "mode": "six_hat",
  "topic": "...",
  "rounds": 3,
  "status": "completed",
  "created_at": "...",
  "messages": [
    {
      "id": 1,
      "role_key": "blue",
      "role": "assistant",
      "name": "Blue Hat · Host",
      "content": "...",
      "model": "deepseek/deepseek-reasoner",
      "ts": "2026-04-24T00:31:00"
    }
  ]
}
```

**Errors:**
- `404` — Session not found

---

#### `GET /api/sessions/{session_id}/attachments`

Get Session attachment list.

**Response:** `200 OK` — `AttachmentOut[]`

```json
[
  {
    "id": 1,
    "filename": "report.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "summary": "This file mainly discusses...",
    "created_at": "2026-04-24T00:31:00"
  }
]
```

---

### 1.2 Configuration Management

#### `GET /api/config/modes`

Get all mode configurations (including participant lists).

**Response:** `200 OK` — `ModeConfigOut[]`

```json
[
  {
    "id": 1,
    "name": "six_hat",
    "display_name": "Six Thinking Hats",
    "description": "...",
    "default_rounds": 3,
    "mode_json": { "opening": {...}, "rounds": {...} },
    "participants": [
      {
        "id": 1,
        "role_key": "blue",
        "name": "Blue Hat · Host",
        "model": "deepseek/deepseek-reasoner",
        "color": "[94m",
        "system_prompt": "...",
        "sort_order": 0,
        "tools_enabled": null
      }
    ]
  }
]
```

---

#### `PATCH /api/config/modes/{mode_name}`

Update mode configuration.

**Body:** `ModeConfigUpdate`

```json
{ "default_rounds": 5 }
```

**Response:** `200 OK` — `ModeConfigOut`

**Errors:**
- `404` — Mode not found

---

#### `PATCH /api/config/participants/{participant_id}`

Update participant configuration.

**Body:** `dict` (supports partial updates)

```json
{
  "name": "Blue Hat · Host",
  "model": "deepseek/deepseek-chat",
  "color": "[94m",
  "system_prompt": "...",
  "tools_enabled": "[\"search\"]"
}
```

> Pass `""` for `tools_enabled` to clear (set to `null`).

**Response:** `200 OK` — Updated Participant

**Errors:**
- `404` — Participant not found

---

#### `GET /api/config/providers`

Get all LLM provider list.

**Response:** `200 OK` — `ProviderOut[]`

```json
[
  {
    "id": 1,
    "name": "deepseek",
    "base_url": null,
    "api_key": "sk-****abcd",
    "models": [
      { "id": 1, "model_name": "deepseek/deepseek-chat" }
    ]
  }
]
```

> `api_key` is automatically masked as `sk-****xxxx` format.

---

#### `POST /api/config/providers`

Create a provider.

**Body:** `ProviderCreate`

```json
{
  "name": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-xxx"
}
```

**Response:** `201 Created` — `ProviderOut`

---

#### `PATCH /api/config/providers/{provider_id}`

Update a provider.

**Body:** `ProviderUpdate`

```json
{
  "name": "openai",
  "base_url": "https://...",
  "api_key": "sk-new"
}
```

> If `api_key` contains `"****"`, it will be ignored (masked value protection).

**Response:** `200 OK` — `ProviderOut`

**Errors:**
- `404` — Provider not found

---

#### `DELETE /api/config/providers/{provider_id}`

Delete a provider.

**Response:** `204 No Content`

---

#### `POST /api/config/providers/{provider_id}/models`

Add a model to a provider.

**Body:** `ProviderModelCreate`

```json
{ "model_name": "gpt-4" }
```

**Response:** `200 OK` — `ProviderOut`

**Errors:**
- `404` — Provider not found

---

#### `DELETE /api/config/providers/{provider_id}/models/{model_id}`

Delete a model from a provider.

**Response:** `204 No Content`

**Errors:**
- `404` — Model not found

---

#### `GET /api/config/host`

Get global host configuration.

**Response:** `200 OK` — `GlobalHostOut`

```json
{
  "id": 1,
  "name": "Host",
  "model": "deepseek/deepseek-reasoner",
  "system_prompt": "...",
  "color": "[34m"
}
```

---

#### `PUT /api/config/host`

Update global host configuration.

**Body:** `GlobalHostUpdate`

```json
{
  "name": "Host",
  "model": "deepseek/deepseek-reasoner",
  "system_prompt": "..."
}
```

> `color` field cannot be modified.

**Response:** `200 OK` — `GlobalHostOut`

> After update, automatically syncs to all modes' participants whose role_key matches opening/summary speaker (only overrides `name`/`model`, preserves `system_prompt`).

---

### 1.3 Mode Registry

#### `GET /api/modes`

Get all available mode list.

**Response:** `200 OK`

```json
[
  { "name": "six_hat", "description": "Six Thinking Hats mode" },
  { "name": "debate", "description": "Debate mode" }
]
```

---

## 2. WebSocket Interface

### `WS /api/sessions/ws/{session_id}`

Establish real-time streaming connection with a Session.

#### Connection Flow

1. Frontend connects WebSocket
2. Backend validates Session exists and `status != "running"`
3. Backend updates `status` to `"running"`
4. Backend builds `RuntimeConfig`, creates `Session`, starts background task
5. Backend pushes `StreamEvent` through WebSocket in real time
6. On frontend disconnect or Session end, backend updates `status` to `"completed"` or `"error"`

#### Heartbeat

Frontend may send `"ping"`, backend replies `"pong"`.

#### Event Protocol (Server -> Client)

All events are JSON with unified structure:

```typescript
interface WSEvent {
  type: "turn_start" | "token" | "turn_end" | "banner" | "session_end" | "tool_start" | "tool_end" | "error";
  payload: Record<string, any>;
}
```

| Event Type | Payload | Description |
|------------|---------|-------------|
| `banner` | `{ text: string }` | Round/stage transition banner |
| `turn_start` | `{ role_key, role_name, color, round_num }` | Role starts speaking |
| `token` | `{ role_key, token: string }` | Streaming token |
| `turn_end` | `{ role_key, full_content: string }` | Role finishes speaking |
| `session_end` | `{}` | Discussion ends |
| `tool_start` | `{ role_key, tool_name: string }` | Tool execution begins |
| `tool_end` | `{ role_key, tool_name, preview: string }` | Tool execution completes |
| `error` | `{ message: string }` | Error (Session not found, already running, etc.) |

#### Event Sequence Example

```
banner       "Six Thinking Hats Discussion Starting"
turn_start   blue  "Blue Hat · Host"
token        blue  "T"
token        blue  "o"
... (continuous tokens)
turn_end     blue  "Today's discussion topic is..."
banner       "Round 1"
tool_start   white "search"
tool_end     white "search" "Found 5 results about AI..."
turn_start   white "White Hat · Facts"
token        white  "A"
... (continuous tokens)
turn_end     white "According to existing data..."
... (other roles)
session_end
```

---

## 3. Frontend Component Props

### `App`

Root component, no external Props. Internal state:

| State | Type | Description |
|-------|------|-------------|
| `modes` | `ModeConfig[]` | Mode configuration list |
| `selectedMode` | `string` | Currently selected mode |
| `rounds` | `number` | Current round count |
| `historyMessages` | `StreamingMessage[] \| null` | Historical session messages (loaded from DB) |
| `displayTopic` | `string` | Display topic |
| `topicKey` | `number` | Forces TopicInput reset |
| `isSubmitting` | `boolean` | Prevent duplicate clicks |

### `Header`

```typescript
interface HeaderProps {
  modes: ModeConfig[];
  selectedMode: string;
  onModeChange: (mode: string) => void;
  onTopicSubmit: (topic: string, files: File[]) => void;
  onToggleSidebar: () => void;
  onOpenConfig: () => void;
  isRunning: boolean;
  isSubmitting?: boolean;
  topicValue?: string;
  topicKey?: number;
  rounds: number;
  onRoundsChange: (r: number) => void;
}
```

### `TopicInput`

```typescript
interface TopicInputProps {
  onSubmit: (topic: string, files: File[]) => void;
  disabled: boolean;
  value?: string;
}
```

### `FileUploadZone`

```typescript
interface FileUploadZoneProps {
  files: File[];
  onChange: (files: File[]) => void;
}
```

### `Sidebar`

```typescript
interface SidebarProps {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
}
```

### `ChatView`

```typescript
interface ChatViewProps {
  events: WSEvent[];
  historyMessages?: StreamingMessage[];
}
```

### `ModeSelector`

```typescript
interface ModeSelectorProps {
  modes: ModeConfig[];
  value: string;
  onChange: (mode: string) => void;
}
```

### `ConfigPanel`

```typescript
interface ConfigPanelProps {
  mode: ModeConfig | null;
  open: boolean;
  onClose: () => void;
}
```

### `MessageBubble`

```typescript
interface MessageBubbleProps {
  name: string;
  color: string;
  content: string;
  isStreaming?: boolean;
}
```

---

## 4. Backend Core Module Interfaces

### 4.1 ModeRunner Protocol

All discussion modes must implement this interface.

```python
class ModeRunner(Protocol):
    mode_name: str
    async def run(self, session: Session) -> AsyncIterator[StreamEvent]: ...
```

**Implementations:**

| Class | File | mode_name |
|-------|------|-----------|
| `SixHatRunner` | `core/modes/six_hat.py` | `"six_hat"` |
| `DebateRunner` | `core/modes/debate.py` | `"debate"` |

**Responsibilities:**
- Read mode rules from `session.get_config()`
- Orchestrate speaking order (opening -> rounds -> summary)
- Build system prompt (including attachment summaries and tool instructions via `_build_tool_system_msg()`)
- Call `call_llm(session, model, messages, cfg, tools)`
- Yield `StreamEvent` (no printing, no logging, no history management)

---

### 4.2 Session Driver

```python
class Session:
    def __init__(
        self,
        session_id: str,
        runtime_config: RuntimeConfig | None = None,
        db_callback: Callable[[dict], Awaitable[None]] | None = None,
    )

    def get_config(self) -> RuntimeConfig | Config
    def add_history(self, role: str, content: str) -> None
    def get_history(self) -> list[dict]
    def load(self, key: str) -> Any
    def save(self, key: str, value: Any) -> None
    def register_output_handler(self, handler: Callable) -> None
    def append_message(self, entry: dict) -> None
    def get_messages(self) -> list[dict]
    def get_full_history(self) -> list[dict]

    async def run(self) -> AsyncIterator[StreamEvent]
```

**Event Routing Logic:**
- `run()` resolves `ModeRunner`, iterates event stream
- Each event forwarded to all registered `OutputHandler`s
- `TurnEndEvent`: update memory history + persist jsonl + call optional `db_callback`
- Duplicate detection: checks if last history entry already contains tool context

---

### 4.3 call_llm

```python
async def call_llm(
    session: Session,
    model: str,
    messages: list[dict],
    cfg: RuntimeConfig | Config | None = None,
    tools: list[dict] | None = None,
    role_key: str = "",
) -> AsyncIterator[str | ToolStartEvent | ToolEndEvent]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session` | `Session` | For topic, history (search query optimization), and writing tool results |
| `model` | `str` | LiteLLM model name, e.g. `"deepseek/deepseek-chat"` |
| `messages` | `list[dict]` | LLM message list `[{role, content}, ...]` |
| `cfg` | `RuntimeConfig \| Config \| None` | Config object; `None` falls back to `Config.get()` |
| `tools` | `list[dict] \| None` | OpenAI function schema list; enables tool calling when passed |
| `role_key` | `str` | Role identifier for tool events |

**Behavior:**
- No `tools`: Normal streaming call, temperature=0.8
- With `tools`: Two-phase calling
  - Phase 1 (non-streaming, temperature=0.3): Detect `tool_calls`
  - If tool_calls found: Execute tools → Phase 2 (streaming, temperature=0.8, `tool_choice="none"` for non-R1 models) output final answer
  - If no tool_calls: Stream directly
- Phase 2 appends explicit user message to prevent short-context confusion
- Phase 2 passes `tools` parameter for Anthropic compatibility (messages with `tool_calls` require `tools` param)
- Auto-resolves provider (api_key, base_url) from DB with caching; falls back to empty dict if DB unavailable
- Search query optimization before calling search tool

**Yields:** Each streaming token (`str`) or tool events (`ToolStartEvent`, `ToolEndEvent`)

---

### 4.4 OutputHandler

```python
class TerminalOutputHandler:
    async def __call__(self, event: StreamEvent) -> None

class WebSocketOutputHandler:
    def __init__(self, websocket)
    async def __call__(self, event: StreamEvent) -> None
```

---

### 4.5 RuntimeConfig

Runtime configuration dynamically loaded from database in Web mode.

```python
@dataclass
class RuntimeConfig:
    topic: str
    rounds: int
    default_mode: str
    participants: dict[str, dict]
    mode_config: dict[str, Any]
    secrets: dict[str, str]
    prompts: dict[str, str]

    @property
    def deepseek_api_key -> str
    @property
    def kimi_api_key -> str
    @property
    def kimi_base_url -> str

    @classmethod
    async def from_db(db: AsyncSession, mode_name: str, topic: str) -> RuntimeConfig
```

**`from_db` Behavior:**
1. Load `ModeConfig` + `Participant` list from DB
2. Inject `GlobalHost` config (overrides `name`/`model`/`color`, **preserves** `system_prompt` and `tools_enabled`)
3. Return `RuntimeConfig` instance

---

### 4.6 StreamEvent Types

```python
@dataclass(frozen=True)
class TurnStartEvent:
    role_key: str
    role_name: str
    color: str
    round_num: int | None = None

@dataclass(frozen=True)
class TokenEvent:
    role_key: str
    token: str

@dataclass(frozen=True)
class TurnEndEvent:
    role_key: str
    full_content: str

@dataclass(frozen=True)
class BannerEvent:
    text: str

@dataclass(frozen=True)
class SessionEndEvent:
    pass

@dataclass(frozen=True)
class ToolStartEvent:
    role_key: str
    tool_name: str

@dataclass(frozen=True)
class ToolEndEvent:
    role_key: str
    tool_name: str
    preview: str

StreamEvent = Union[
    TurnStartEvent, TokenEvent, TurnEndEvent,
    BannerEvent, SessionEndEvent,
    ToolStartEvent, ToolEndEvent,
]
```

---

## 5. Database Model Interfaces

### 5.1 Schema

| Table | Core Fields | Relations |
|-------|-------------|-----------|
| `mode_configs` | `name`, `display_name`, `mode_json`, `default_rounds` | 1:N `participants` |
| `participants` | `mode_name`, `role_key`, `model`, `name`, `color`, `system_prompt`, `sort_order`, `tools_enabled` | N:1 `mode_configs` |
| `sessions` | `id`, `mode`, `topic`, `rounds`, `status`, `created_at`, `completed_at` | 1:N `messages`, 1:N `attachments` |
| `messages` | `session_id`, `role_key`, `role`, `name`, `content`, `model`, `ts` | N:1 `sessions` |
| `attachments` | `session_id`, `filename`, `file_type`, `file_size`, `storage_path`, `summary` | N:1 `sessions` |
| `providers` | `name`, `api_key`, `base_url` | 1:N `provider_models` |
| `provider_models` | `provider_id`, `model_name` | N:1 `providers` |
| `global_hosts` | `name`, `model`, `system_prompt`, `color` | Global singleton |

### 5.2 Status Flow

```
pending -> running -> completed
                    -> error
```

- `pending`: Just created, not started
- `running`: WebSocket connected, discussion in progress
- `completed`: Normal end or WebSocket disconnect (user-initiated)
- `error`: Exception during execution

---

## 6. Configuration Layers

| Source | Purpose | Runtime Mutable | Git Tracked |
|--------|---------|----------------|-------------|
| `config/app.json` | CLI defaults: topic, rounds, default_mode | No | Yes |
| `config/models.json` | Default role config (seed DB) | No | Yes |
| `config/modes/*.json` | Mode rules: speaking order, templates | No | Yes |
| `config/secrets.json` | API Keys | No | No (gitignore) |
| `polysynth.db` | Web/CLI runtime authoritative config | Yes (via Web UI / CLI) | No (gitignore) |

---

## 7. Call Chain Example

### Web Mode: Creating a Discussion

```
Browser
  | POST /api/sessions {mode, topic, files} (multipart)
  v
FastAPI sessions.py::create_new_session()
  |-- Validate files -> Create DB session record -> Extract text -> AI summary -> Store Attachment
  v
  | Returns {id, status: "pending"}
  v
Browser
  | WS /api/sessions/ws/{id}
  v
FastAPI sessions.py::session_websocket()
  |-- Validate -> status="running" -> RuntimeConfig.from_db() -> Session()
  |-- Register WebSocketOutputHandler -> create_task(session.run())
  v
Session.run()
  |-- get_runner(cfg.default_mode) -> SixHatRunner.run(session)
  v
SixHatRunner.run()
  |-- Orchestrate order -> _run_role() -> call_llm(session, model, messages, cfg, tools)
  v
call_llm()
  |-- _resolve_provider(model) -> acompletion() -> yield token
  v
SixHatRunner.run()
  |-- yield TokenEvent -> yield TurnEndEvent
  v
Session.run()
  |-- Forward to WebSocketOutputHandler -> Send JSON
  |-- TurnEndEvent: add_history() + append_message(jsonl) + db_callback(DB)
  v
Browser ChatView
  |-- Receive token -> Character display -> turn_end solidify message
```

---

*Document Version: 2026-04-25*
*Corresponding Commit: CLI mode refactoring + API security + Anthropic compatibility*

# Polysynth 接口契约文档

> 本文档描述 Polysynth 前后端之间的所有接口契约，包括 REST API、WebSocket 协议、前端组件 Props、以及后端核心模块间的接口。

---

## 1. REST API 接口

Base URL: `http://localhost:8000`

### 1.1 Session 管理

#### `POST /api/sessions`

创建新讨论 Session（支持文件上传）。

**Content-Type:** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 是 | 讨论模式：`"six_hat"` / `"debate"` |
| `topic` | string | 是 | 讨论话题 |
| `rounds` | int | 否 | 轮次数（仅在 `mode_json.rounds.configurable=true` 时生效） |
| `files` | File[] | 否 | 附件文件，最多 5 个，单个最大 20MB |

**Response:** `201 Created` — `SessionOut`

```json
{
  "id": "9cae5b334e0743ba8e516dd57d6ffd89",
  "mode": "six_hat",
  "topic": "电商企业是否需要自建RAG",
  "rounds": 3,
  "status": "pending",
  "created_at": "2026-04-24T00:31:00"
}
```

**Errors:**
- `400` — 文件数量超过 5 个，或不支持的文件类型
- `413` — 单个文件超过 20MB

---

#### `GET /api/sessions`

获取 Session 列表。

**Query Params:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 50 | 分页大小 |
| `offset` | int | 0 | 偏移量 |

**Response:** `200 OK` — `SessionOut[]`

---

#### `GET /api/sessions/{session_id}`

获取单个 Session 详情（含消息列表）。

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
      "name": "蓝帽·主持人",
      "content": "...",
      "model": "deepseek/deepseek-reasoner",
      "ts": "2026-04-24T00:31:00"
    }
  ]
}
```

**Errors:**
- `404` — Session 不存在

---

#### `GET /api/sessions/{session_id}/attachments`

获取 Session 的附件列表。

**Response:** `200 OK` — `AttachmentOut[]`

```json
[
  {
    "id": 1,
    "filename": "report.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "summary": "该文件主要讨论了...",
    "created_at": "2026-04-24T00:31:00"
  }
]
```

---

### 1.2 配置管理

#### `GET /api/config/modes`

获取所有模式配置（含参与者列表）。

**Response:** `200 OK` — `ModeConfigOut[]`

```json
[
  {
    "id": 1,
    "name": "six_hat",
    "display_name": "六顶思考帽",
    "description": "...",
    "default_rounds": 3,
    "mode_json": { "opening": {...}, "rounds": {...} },
    "participants": [
      {
        "id": 1,
        "role_key": "blue",
        "name": "蓝帽·主持人",
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

更新模式配置。

**Body:** `ModeConfigUpdate`

```json
{ "default_rounds": 5 }
```

**Response:** `200 OK` — `ModeConfigOut`

**Errors:**
- `404` — 模式不存在

---

#### `PATCH /api/config/participants/{participant_id}`

更新参与者配置。

**Body:** `dict`（支持部分字段更新）

```json
{
  "name": "蓝帽·主持人",
  "model": "deepseek/deepseek-chat",
  "color": "[94m",
  "system_prompt": "...",
  "tools_enabled": "[\"search\"]"
}
```

> `tools_enabled` 传 `""` 表示清空（设为 `null`）。

**Response:** `200 OK` — 更新后的 Participant

**Errors:**
- `404` — 参与者不存在

---

#### `GET /api/config/providers`

获取所有 LLM 供应商列表。

**Response:** `200 OK` — `ProviderOut[]`

```json
[
  {
    "id": 1,
    "name": "deepseek",
    "base_url": null,
    "api_key": "sk-***",
    "models": [
      { "id": 1, "model_name": "deepseek/deepseek-chat" }
    ]
  }
]
```

---

#### `POST /api/config/providers`

创建供应商。

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

更新供应商。

**Body:** `ProviderUpdate`

```json
{
  "name": "openai",
  "base_url": "https://...",
  "api_key": "sk-new"
}
```

**Response:** `200 OK` — `ProviderOut`

**Errors:**
- `404` — 供应商不存在

---

#### `DELETE /api/config/providers/{provider_id}`

删除供应商。

**Response:** `204 No Content`

---

#### `POST /api/config/providers/{provider_id}/models`

为供应商添加模型。

**Body:** `ProviderModelCreate`

```json
{ "model_name": "gpt-4" }
```

**Response:** `200 OK` — `ProviderOut`

**Errors:**
- `404` — 供应商不存在

---

#### `DELETE /api/config/providers/{provider_id}/models/{model_id}`

删除供应商下的模型。

**Response:** `204 No Content`

**Errors:**
- `404` — 模型不存在

---

#### `GET /api/config/host`

获取全局主持人配置。

**Response:** `200 OK` — `GlobalHostOut`

```json
{
  "id": 1,
  "name": "主持人",
  "model": "deepseek/deepseek-reasoner",
  "system_prompt": "...",
  "color": "[34m"
}
```

---

#### `PUT /api/config/host`

更新全局主持人配置。

**Body:** `GlobalHostUpdate`

```json
{
  "name": "主持人",
  "model": "deepseek/deepseek-reasoner",
  "system_prompt": "..."
}
```

> `color` 字段不允许修改。

**Response:** `200 OK` — `GlobalHostOut`

> 更新后会自动同步到所有模式中 role_key 为开场/总结发言者的参与者（只覆盖 `name`/`model`，不覆盖 `system_prompt`）。

---

### 1.3 模式注册表

#### `GET /api/modes`

获取所有可用模式列表。

**Response:** `200 OK`

```json
[
  { "name": "six_hat", "description": "六顶思考帽模式" },
  { "name": "debate", "description": "辩论赛模式" }
]
```

---

## 2. WebSocket 接口

### `WS /api/sessions/ws/{session_id}`

与指定 Session 建立实时流式连接。

#### 连接流程

1. 前端连接 WebSocket
2. 后端校验 Session 存在且 `status != "running"`
3. 后端将 `status` 更新为 `"running"`
4. 后端构建 `RuntimeConfig`，创建 `DiscussionSession`，启动后台任务
5. 后端通过 WebSocket 实时推送 `StreamEvent`
6. 前端断开或 Session 结束时，后端将 `status` 更新为 `"completed"` 或 `"error"`

#### 心跳机制

前端可发送 `"ping"`，后端回复 `"pong"`。

#### 事件协议（Server -> Client）

所有事件为 JSON 格式，统一结构：

```typescript
interface WSEvent {
  type: "turn_start" | "token" | "turn_end" | "banner" | "session_end" | "error";
  payload: Record<string, any>;
}
```

| 事件类型 | Payload | 说明 |
|----------|---------|------|
| `banner` | `{ text: string }` | 轮次/阶段切换横幅 |
| `turn_start` | `{ role_key, role_name, color, round_num }` | 角色开始发言 |
| `token` | `{ role_key, token: string }` | 流式 token |
| `turn_end` | `{ role_key, full_content: string }` | 角色发言结束 |
| `session_end` | `{}` | 整场讨论结束 |
| `error` | `{ message: string }` | 错误（如 Session 不存在、已在运行） |

#### 事件时序示例

```
banner       "六顶思考帽讨论开始"
turn_start   blue  "蓝帽·主持人"
token        blue  "今"
token        blue  "天"
...（持续 token）
turn_end     blue  "今天的讨论话题是..."
banner       "第 1 轮讨论"
turn_start   white "白帽·事实"
token        white "根"
...（持续 token）
turn_end     white "根据现有数据..."
...（其他角色）
session_end
```

---

## 3. 前端组件 Props 接口

### `App`

根组件，无外部 Props。内部状态：

| 状态 | 类型 | 说明 |
|------|------|------|
| `modes` | `ModeConfig[]` | 模式配置列表 |
| `selectedMode` | `string` | 当前选中模式 |
| `rounds` | `number` | 当前轮次数 |
| `historyMessages` | `StreamingMessage[] \| null` | 历史会话消息（数据库加载） |
| `displayTopic` | `string` | 显示的话题 |
| `topicKey` | `number` | 用于强制重置 TopicInput |
| `isSubmitting` | `boolean` | 是否正在提交（防重复点击） |

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
  isSubmitting?: boolean;   // true 时禁用 TopicInput
  topicValue?: string;      // 非 undefined 时 TopicInput 进入只读模式
  topicKey?: number;        // 变化时强制重置 TopicInput
  rounds: number;
  onRoundsChange: (r: number) => void;
}
```

### `TopicInput`

```typescript
interface TopicInputProps {
  onSubmit: (topic: string, files: File[]) => void;
  disabled: boolean;        // true 时禁用输入和按钮
  value?: string;           // 非 undefined 时进入只读模式（显示值）
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
  historyMessages?: StreamingMessage[];  // 与 events 合并渲染
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
  color: string;           // ANSI 颜色码
  content: string;
  isStreaming?: boolean;   // true 时显示"正在发言..."
}
```

---

## 4. 后端核心模块接口

### 4.1 ModeRunner 协议

所有讨论模式必须实现此接口。

```python
class ModeRunner(Protocol):
    mode_name: str

    async def run(self, session: Session) -> AsyncIterator[StreamEvent]:
        ...
```

**现有实现：**

| 类 | 文件 | mode_name |
|----|------|-----------|
| `SixHatRunner` | `core/modes/six_hat.py` | `"six_hat"` |
| `DebateRunner` | `core/modes/debate.py` | `"debate"` |

**职责：**
- 从 `session.get_config()` 读取模式规则
- 编排发言顺序（opening -> rounds -> summary）
- 构建 system prompt（含附件摘要注入、工具提示词）
- 调用 `call_llm(session, model, messages, cfg, tools)`
- yield `StreamEvent`（不处理打印、不记录、不管理历史）

---

### 4.2 Session 驱动中心

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
    def get_history(self) -> list[dict]          # [{role, content}, ...]
    def load(self, key: str) -> Any              # 从 .state.json 读取
    def save(self, key: str, value: Any) -> None # 写入 .state.json
    def register_output_handler(self, handler: Callable) -> None
    def append_message(self, entry: dict) -> None  # 追加到 .jsonl
    def get_messages(self) -> list[dict]           # 从 .jsonl 读取
    def get_full_history(self) -> list[dict]       # 从 .jsonl 读取完整元数据

    async def run(self) -> AsyncIterator[StreamEvent]
```

**事件路由逻辑：**
- `run()` 获取 `ModeRunner`，迭代事件流
- 每个事件转发给所有注册的 `OutputHandler`
- `TurnEndEvent` 时：更新内存历史 + 持久化 jsonl + 调用可选的 `db_callback`

---

### 4.3 call_llm

```python
async def call_llm(
    session: Session,
    model: str,
    messages: list[dict],
    cfg: RuntimeConfig | Config | None = None,
    tools: list[dict] | None = None,
) -> AsyncIterator[str]
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session` | `Session` | 用于读取 topic、history（搜索关键词优化）和写入 tool results |
| `model` | `str` | LiteLLM 模型名，如 `"deepseek/deepseek-chat"` |
| `messages` | `list[dict]` | LLM 消息列表 `[{role, content}, ...]` |
| `cfg` | `RuntimeConfig \| Config \| None` | 配置对象，为 `None` 时 fallback 到 `Config.get()` |
| `tools` | `list[dict] \| None` | OpenAI function schema 列表，传入时启用工具调用 |

**行为：**
- 无 `tools`：普通流式调用，temperature=0.8
- 有 `tools`：双阶段调用
  - Phase 1（非流式，temperature=0.3）：检测 `tool_calls`
  - 如有 tool_calls：执行工具 → Phase 2（流式，temperature=0.8，`tool_choice="none"`）输出最终答案
  - 如无 tool_calls：直接流式输出
- 自动从数据库解析 provider（api_key, base_url），fallback 到 `cfg` 的硬编码密钥

**yield:** 每个流式 token（`str`）

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

Web 模式下从数据库动态加载的运行时配置。

```python
@dataclass
class RuntimeConfig:
    topic: str
    rounds: int
    default_mode: str
    participants: dict[str, dict]    # {role_key: {model, name, color, tools_enabled}}
    mode_config: dict[str, Any]      # 模式规则 JSON
    secrets: dict[str, str]
    prompts: dict[str, str]          # {role_key: system_prompt}

    @property
    def deepseek_api_key -> str
    @property
    def kimi_api_key -> str
    @property
    def kimi_base_url -> str

    @classmethod
    async def from_db(db: AsyncSession, mode_name: str, topic: str) -> RuntimeConfig
```

**`from_db` 行为：**
1. 从 DB 加载 `ModeConfig` + `Participant` 列表
2. 注入全局主持人配置（覆盖 `name`/`model`/`color`，**不覆盖** `system_prompt`）
3. 返回 `RuntimeConfig` 实例

---

### 4.6 StreamEvent 事件类型

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

StreamEvent = Union[TurnStartEvent, TokenEvent, TurnEndEvent, BannerEvent, SessionEndEvent]
```

---

## 5. 数据库模型接口

### 5.1 表结构

| 表 | 核心字段 | 关系 |
|----|---------|------|
| `mode_configs` | `name`, `display_name`, `mode_json`, `default_rounds` | 1:N `participants` |
| `participants` | `mode_name`, `role_key`, `model`, `name`, `color`, `system_prompt`, `sort_order`, `tools_enabled` | N:1 `mode_configs` |
| `sessions` | `id`, `mode`, `topic`, `rounds`, `status`, `created_at`, `completed_at` | 1:N `messages`, 1:N `attachments` |
| `messages` | `session_id`, `role_key`, `role`, `name`, `content`, `model`, `ts` | N:1 `sessions` |
| `attachments` | `session_id`, `filename`, `file_type`, `file_size`, `storage_path`, `summary` | N:1 `sessions` |
| `providers` | `name`, `api_key`, `base_url` | 1:N `provider_models` |
| `provider_models` | `provider_id`, `model_name` | N:1 `providers` |
| `global_hosts` | `name`, `model`, `system_prompt`, `color` | 全局单例 |

### 5.2 状态流转

```
pending -> running -> completed
                    -> error
```

- `pending`：刚创建，未启动
- `running`：WebSocket 已连接，讨论进行中
- `completed`：正常结束 或 WebSocket 断开（用户主动断开）
- `error`：运行过程中发生异常

---

## 6. 配置分层

| 配置源 | 用途 | 运行时修改 |
|--------|------|-----------|
| `config/app.json` | CLI 模式：topic, rounds, default_mode | 否 |
| `config/models.json` | 默认角色配置（seed DB 用） | 否 |
| `config/modes/*.json` | 模式规则（发言顺序、模板） | 否 |
| `config/secrets.json` | API Keys（seed DB 用） | 否（gitignore） |
| `polysynth.db` | Web 模式运行时权威配置 | 是（通过 Web UI） |

---

## 7. 调用链路示例

### Web 模式创建讨论完整链路

```
浏览器
  │ POST /api/sessions {mode, topic, files} (multipart)
  ▼
FastAPI sessions.py::create_new_session()
  │-- 校验文件 -> 创建 DB session 记录 -> 提取文本 -> AI 摘要 -> 存 Attachment
  ▼
  │ 返回 {id, status: "pending"}
  ▼
浏览器
  │ WS /api/sessions/ws/{id}
  ▼
FastAPI sessions.py::session_websocket()
  │-- 校验 -> status="running" -> RuntimeConfig.from_db() -> DiscussionSession()
  │-- 注册 WebSocketOutputHandler -> create_task(session.run())
  ▼
Session.run()
  │-- get_runner(cfg.default_mode) -> SixHatRunner.run(session)
  ▼
SixHatRunner.run()
  │-- 编排发言顺序 -> _run_role() -> call_llm(session, model, messages, cfg, tools)
  ▼
call_llm()
  │-- _resolve_provider(model) -> acompletion() -> yield token
  ▼
SixHatRunner.run()
  │-- yield TokenEvent -> yield TurnEndEvent
  ▼
Session.run()
  │-- 转发给 WebSocketOutputHandler -> 发送 JSON
  │-- TurnEndEvent: add_history() + append_message(jsonl) + db_callback(DB)
  ▼
浏览器 ChatView
  │-- 接收 token -> 逐字显示 -> turn_end 固化消息
```

---

*文档版本: 2026-04-24*
*对应代码 commit: `2e7eb80`*

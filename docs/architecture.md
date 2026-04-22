# Polysynth 架构文档

## 1. 系统概述

Polysynth 是一个多 LLM Agent 协作讨论模拟器。系统通过"角色扮演"的方式，让多个 AI 角色（如六顶思考帽、辩论双方）围绕同一话题进行结构化多轮讨论，最终输出协作结论。

核心设计理念：

- **Session 驱动**：Session 是调度中心，管理配置、历史、事件路由和持久化
- **模式可插拔**：新增讨论模式只需实现 `ModeRunner` 协议
- **事件流统一**：所有输出通过类型化事件流（`StreamEvent`）传递，消费方自行处理
- **纯数据配置**：角色、Prompt、规则全部外置到 JSON，无需改代码即可切换模式
- **前后端分离**：FastAPI 提供 REST API + WebSocket，React 前端实时消费事件流
- **双模运行**：CLI 终端模式与 Web UI 模式共存，共享同一套核心引擎

## 2. 目录结构

```
Polysynth_v2/
├── backend/
│   ├── main.py                    # CLI 入口：创建 Session + TerminalOutputHandler
│   ├── Prompts.py                 # System Prompt 仓库，按模式分组
│   ├── config/
│   │   ├── app.json               # 全局配置：topic, rounds, default_mode
│   │   ├── models.json            # 按模式分组的参与者配置
│   │   ├── secrets.json           # API Keys（gitignore）
│   │   └── modes/
│   │       ├── six_hat.json       # 六顶思考帽规则
│   │       └── debate.json        # 辩论赛规则
│   ├── api/                       # FastAPI Web 服务
│   │   ├── main.py                # FastAPI app, lifespan, CORS
│   │   ├── deps.py                # DB session dependency
│   │   ├── schemas.py             # Pydantic 请求/响应模型
│   │   └── routers/
│   │       ├── sessions.py        # POST/GET /api/sessions, WS /ws/{id}
│   │       ├── config.py          # GET /api/config/modes, PATCH /participants/{id}
│   │       └── modes.py           # GET /api/modes
│   ├── core/                      # 核心引擎
│   │   ├── session.py             # Session 驱动中心
│   │   ├── agent_generator.py     # LLM 调用层（纯 IO）
│   │   ├── config.py              # Config 文件单例（CLI 兼容）
│   │   ├── runtime_config.py      # RuntimeConfig 运行时配置（Web 模式）
│   │   ├── output_handlers.py     # TerminalOutputHandler + WebSocketOutputHandler
│   │   └── modes/
│   │       ├── base.py            # ModeRunner Protocol
│   │       ├── registry.py        # 模式注册表
│   │       ├── six_hat.py         # SixHatRunner
│   │       └── debate.py          # DebateRunner
│   └── datebase/                  # 数据层
│       ├── stream_events.py       # StreamEvent 事件类型定义
│       ├── models.py              # SQLAlchemy ORM 模型
│       ├── engine.py              # 异步引擎 + session 工厂
│       └── crud.py                # CRUD 操作 + seed 初始化
├── frontend/                      # React 前端
│   ├── src/
│   │   ├── api/                   # axios client + types + API 函数
│   │   ├── components/            # UI 组件（Sidebar, ChatView, Header 等）
│   │   ├── hooks/                 # useWebSocket, useSessions
│   │   ├── stores/                # zustand UI 状态
│   │   ├── App.tsx                # 根布局
│   │   └── main.tsx               # React root + QueryClient
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.app.json
├── sessions/                      # 运行时生成：jsonl + state.json
├── polysynth.db                   # SQLite 数据库（运行时生成）
├── docs/                          # 本文档
└── test_kimi_code.py              # API 连通性测试
```

## 3. 核心组件

### 3.1 Config（配置单例）

**文件**：`backend/core/config.py`

职责：

- 加载 `app.json` + `models.json` + `secrets.json` + `modes/*.json` + `Prompts.py`
- 根据 `default_mode` 自动过滤当前模式的 `participants` 和 `prompts`
- 提供单例访问 `Config.get()`，支持 `Config.reload()` 热更新

**CLI 模式下使用**。Web 模式下由 `RuntimeConfig.from_db()` 替代。

### 3.2 RuntimeConfig（运行时配置）

**文件**：`backend/core/runtime_config.py`

`RuntimeConfig` 是 `Config` 的运行时版本（非 frozen、非单例）：

- `from_db(db, mode_name, topic)`：从数据库查询 mode_config + participants 构建
- 字段与 `Config` 一致，Web 模式下 `Session` 通过 `get_config()` 优先返回 `RuntimeConfig`

### 3.3 Session（驱动中心）

**文件**：`backend/core/session.py`

职责：

- 拥有 `discussion_history`（LLM 消息列表），取代旧全局变量
- 管理运行时状态，持久化到 `.state.json` 和 SQLite `messages` 表
- 注册输出处理器（`OutputHandler`），统一路由事件流
- 自动管理历史追加和持久化（jsonl + DB 双写）
- `get_config()` 优先 `runtime_config`，否则 fallback 到 `Config.get()`

关键方法：

| 方法 | 说明 |
|------|------|
| `add_history(role, content)` | 追加 LLM 消息到内存历史 |
| `get_history()` | 返回完整历史副本 |
| `register_output_handler(handler)` | 注册事件处理器 |
| `run()` | 主驱动：获取 ModeRunner，迭代事件流，转发处理器，自动持久化 |
| `append_message(entry)` | 追加到 `.jsonl` 消息日志 |
| `get_config()` | 优先 runtime_config，否则 Config 单例 |

### 3.4 ModeRunner（模式执行器协议）

**文件**：`backend/core/modes/base.py`

所有讨论模式必须实现：

```python
class ModeRunner(Protocol):
    mode_name: str
    async def run(self, session: Session) -> AsyncIterator[StreamEvent]: ...
```

职责：

- 从 `session.get_config()` 读取模式规则
- 编排发言顺序（opening -> rounds -> summary）
- 构建 system prompt（`Prompts.py` + `extra_instruction`）
- 调用 `call_llm()` 获取 token
- yield `StreamEvent`（不处理打印、不记录、不管理历史）

现有实现：

| 模式 | 文件 | 说明 |
|------|------|------|
| six_hat | `backend/core/modes/six_hat.py` | 六顶思考帽 |
| debate | `backend/core/modes/debate.py` | 辩论赛 |

注册：新增模式需在 `registry.py` 的 `_REGISTRY` 中注册。

### 3.5 StreamEvent（事件流）

**文件**：`backend/datebase/stream_events.py`

| 事件类型 | 触发时机 | 用途 |
|----------|----------|------|
| `TurnStartEvent` | 角色开始发言 | 打印横幅/设置颜色/前端显示角色名 |
| `TokenEvent` | 收到流式 token | 实时打印/前端逐字显示 |
| `TurnEndEvent` | 角色发言结束 | 更新历史 + 持久化 jsonl + 写入 DB |
| `BannerEvent` | 轮次/阶段切换 | 打印大横幅/前端显示阶段提示 |
| `SessionEndEvent` | 整场讨论结束 | 打印结束语/前端标记完成 |

### 3.6 call_llm（LLM 调用层）

**文件**：`backend/core/agent_generator.py`

纯 IO 函数，只负责：

- 通过 LiteLLM 流式调用 LLM
- yield token

接受 `cfg` 参数读取 API keys（`RuntimeConfig` 或 `Config` 均可）。

### 3.7 OutputHandler（输出处理器）

**文件**：`backend/core/output_handlers.py`

消费 `StreamEvent`，执行实际输出：

| 处理器 | 用途 | 使用场景 |
|--------|------|----------|
| `TerminalOutputHandler` | 终端颜色打印、banner、换行重置 | CLI 模式 |
| `WebSocketOutputHandler` | 将事件序列化为 JSON 通过 WebSocket 发送 | Web 模式 |

### 3.8 数据库层

**文件**：`backend/datebase/models.py`, `engine.py`, `crud.py`

SQLAlchemy 2.0 + aiosqlite，异步 ORM。

| 表 | 用途 |
|---|---|
| `mode_configs` | 模式元数据（name, display_name, mode_json, default_rounds） |
| `participants` | 每模式的角色定义（role_key, model, name, color, system_prompt） |
| `sessions` | Session 记录（id, mode, topic, rounds, status, created_at） |
| `messages` | 发言记录（session_id, role_key, role, name, content, model, ts） |

初始化：`seed_db_from_files()` 从 JSON 配置文件幂等导入默认数据。

## 4. 数据流

### 4.1 CLI 模式

```
backend/main.py
    |
    v
Session.run() ──────────────────────► get_config() -> Config.get() (文件单例)
    |
    |-- 从 registry 获取 ModeRunner
    |       `-- SixHatRunner / DebateRunner
    |
    v
ModeRunner.run(session)
    |
    |-- 按规则编排发言顺序
    |-- 构建 system prompt
    |-- 读取 session.get_history()
    |
    v
call_llm(session, model, messages, cfg)
    |
    v
LiteLLM --> DeepSeek API / Kimi API
    |
    v
StreamEvent (yield)
    |
    |-- TurnStartEvent --> TerminalOutputHandler (打印横幅)
    |-- TokenEvent     --> TerminalOutputHandler (实时打印)
    |-- TurnEndEvent   --> Session (更新历史 + 持久化 jsonl)
    |-- BannerEvent    --> TerminalOutputHandler (阶段横幅)
    `-- SessionEndEvent --> TerminalOutputHandler (结束)
```

### 4.2 Web 模式

```
浏览器 (React)
    |
    | POST /api/sessions {mode, topic}
    | 返回 {id, status: "pending"}
    v
后端 (FastAPI)
    |-- 创建 DB session 记录
    |-- 前端连接 WS /api/sessions/ws/{id}
    v
WebSocket handler
    |-- 从 DB 加载 mode_config + participants
    |-- RuntimeConfig.from_db()
    |-- 创建 Session(id, runtime_config=cfg, db_callback=...)
    |-- 注册 WebSocketOutputHandler(websocket)
    |-- asyncio.create_task(session.run()) 后台运行
    v
Session.run()
    |-- 转发事件给 WebSocketOutputHandler
    |-- WebSocketOutputHandler 发送 JSON 到浏览器
    |-- TurnEndEvent 时：jsonl + DB 双写
    v
浏览器 (React ChatView)
    |-- turn_start --> 显示角色名 + 颜色边框
    |-- token     --> 逐字追加到当前消息
    |-- turn_end  --> 固化消息，清空流状态
    |-- banner    --> 居中显示阶段提示
    |-- session_end --> 标记完成，刷新历史列表
```

## 5. 配置分层

| 文件 | 职责 | 是否提交 git |
|------|------|-------------|
| `config/app.json` | 全局：topic, rounds, default_mode | 是 |
| `config/models.json` | 模式参与者：model, name, color | 是 |
| `config/modes/*.json` | 模式规则：发言顺序、模板 | 是 |
| `config/secrets.json` | API Keys | 否 (gitignore) |
| `Prompts.py` | System Prompt 仓库 | 是 |
| `polysynth.db` | SQLite 运行时数据库 | 否 (gitignore) |

Web 模式下，前端运行时只传 `mode` + `topic`，`participants` 和 `rounds` 从数据库读取（用户可修改）。

切换模式：前端选择模式，或修改 `app.json` 中的 `default_mode`（CLI 模式）。

## 6. 扩展指南

### 6.1 新增讨论模式

1. **定义参与者**：在 `config/models.json` 新增模式分组
2. **定义规则**：创建 `config/modes/{mode_name}.json`
3. **定义 Prompts**：在 `Prompts.py` 的 `SYSTEM_PROMPTS` 新增模式分组
4. **实现执行器**：创建 `backend/core/modes/{mode_name}.py`，实现 `ModeRunner`
5. **注册**：在 `registry.py` 的 `_REGISTRY` 中添加映射
6. **Seed DB**：重启后端自动从 JSON 导入新配置

### 6.2 新增输出处理器

实现 `async def __call__(self, event: StreamEvent)` 接口，注册到 Session：

```python
session.register_output_handler(MyWebSocketHandler())
```

### 6.3 新增 LLM 供应商

在 `call_llm()` 中添加供应商前缀判断和对应的 kwargs 注入。

## 7. 已知限制

1. **Token 超限风险**：`_run_role()` 将完整历史作为 system prompt 的一部分传入。当讨论轮数增多时，token 数会线性增长。未来应将历史作为 `messages` 参数而非 system prompt 传入。
2. **Session 历史单向增长**：当前 `discussion_history` 只增不减，长会话可能超限。
3. **无并发控制**：`call_llm()` 同步调用 LiteLLM，多角色并行发言需额外实现。

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

这是一个基于"六顶思考帽"方法的多 LLM Agent 讨论模拟器。六顶不同颜色的"帽子"代表不同思维角色（白帽·事实、红帽·情感、黑帽·批判、黄帽·乐观、绿帽·创意、蓝帽·主持人），通过多个 LLM 角色对同一话题进行多轮协作讨论。

目前已扩展为**多模式全栈架构**：
- 支持 `six_hat`（六顶思考帽）和 `debate`（辩论赛）两种讨论模式
- **CLI 终端模式**：`python backend/main.py`，终端彩色输出
- **Web UI 模式**：React 前端 + FastAPI 后端 + SQLite 数据库，浏览器实时观看讨论流
- 两种模式共享同一套核心引擎（Session + ModeRunner + call_llm）

## Development Commands

### 后端启动（Web 模式）

```bash
# Windows
.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000

# Unix/macOS
.venv/bin/python -m uvicorn backend.api.main:app --reload --port 8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

### CLI 模式

```bash
# Windows
.venv\Scripts\activate
python backend/main.py

# Unix/macOS
source .venv/bin/activate
python backend/main.py
```

### 依赖安装

后端新增依赖：
```bash
pip install fastapi uvicorn sqlalchemy aiosqlite websockets
```

前端依赖（已包含在 package.json）：
```bash
cd frontend && npm install
```

项目没有配置测试框架、lint 或格式化工具。可通过以下命令快速测试 Kimi API 连通性：

```bash
python test_kimi_code.py
```

## Architecture

### 目录结构

```
Polysynth_v2/
├── backend/                    # 核心业务代码
│   ├── main.py                 # CLI 入口：Session + TerminalOutputHandler
│   ├── Prompts.py              # System Prompt 仓库，按模式分组
│   ├── config/                 # JSON 配置
│   │   ├── app.json            # topic, rounds, default_mode
│   │   ├── models.json         # 按模式分组的参与者配置（seed DB 用）
│   │   ├── secrets.json        # API Keys（gitignore）
│   │   └── modes/              # 模式规则定义
│   │       ├── six_hat.json
│   │       └── debate.json
│   ├── api/                    # FastAPI Web 服务
│   │   ├── main.py             # FastAPI app, lifespan, CORS
│   │   ├── deps.py             # DB session dependency
│   │   ├── schemas.py          # Pydantic 请求/响应模型
│   │   └── routers/
│   │       ├── sessions.py     # REST CRUD + WebSocket /ws/{id}
│   │       ├── config.py       # GET/ PATCH config endpoints
│   │       └── modes.py        # Registry list
│   ├── core/                   # 核心引擎
│   │   ├── session.py          # Session 驱动中心
│   │   ├── agent_generator.py  # LLM 调用层：call_llm()，纯 IO
│   │   ├── config.py           # Config 文件单例（CLI 兼容）
│   │   ├── runtime_config.py   # RuntimeConfig 运行时配置（Web 模式）
│   │   ├── output_handlers.py  # TerminalOutputHandler + WebSocketOutputHandler
│   │   ├── logger.py           # 统一日志配置（console + 文件轮转）
│   │   ├── tools/              # Agent 工具层
│   │   │   ├── __init__.py     # 导出 get_tool_schemas, execute_tool
│   │   │   ├── schema.py       # ToolSchema dataclass
│   │   │   ├── registry.py     # 工具注册表
│   │   │   └── search.py       # DuckDuckGo 搜索工具
│   │   └── modes/              # 模式执行器
│   │       ├── base.py         # ModeRunner Protocol
│   │       ├── registry.py     # 模式注册表 get_runner(mode_name)
│   │       ├── six_hat.py      # SixHatRunner
│   │       └── debate.py       # DebateRunner
│   └── datebase/               # 数据层
│       ├── stream_events.py    # StreamEvent 事件类型定义
│       ├── models.py           # SQLAlchemy ORM 模型
│       ├── engine.py           # 异步引擎 + session 工厂
│       └── crud.py             # CRUD 操作 + seed 初始化
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── api/                # axios client + types + API 函数
│   │   ├── components/         # UI 组件（ConfigPanel, ChatView, Sidebar 等）
│   │   ├── hooks/              # useWebSocket, useSessions
│   │   ├── stores/             # zustand UI 状态
│   │   ├── lib/                # 工具函数
│   │   │   └── colors.ts       # ANSI ↔ Hex 颜色转换
│   │   ├── App.tsx             # 根布局
│   │   └── main.tsx            # React root + QueryClient
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.app.json
├── sessions/                   # 运行时生成（session jsonl + state）
├── logs/                       # 运行时日志（gitignore）
└── polysynth.db                # SQLite 数据库（运行时生成，gitignore）
```

### 数据流

**CLI 模式**：
```
backend/main.py
    │
    ▼
Session.run() ──────────────────────► get_config() -> Config.get() (文件单例)
    │                                    从 registry 获取 ModeRunner
    ▼
ModeRunner.run(session) ────────────► 按模式规则编排发言顺序
    │                                    构建 system prompt
    │                                    调用 call_llm()
    ▼
call_llm() ─────────────────────────► LiteLLM → DeepSeek / Kimi API
    │
    ▼
StreamEvent (yield) ────────────────► Session.run() 接收事件
    │                                    转发给 TerminalOutputHandler
    │                                    TurnEndEvent 时更新历史 + 持久化 jsonl
    │
    ▼
TerminalOutputHandler ──────────────► 终端颜色打印 + banner
```

**Web 模式**：
```
浏览器 (React)
    │
    │ POST /api/sessions {mode, topic}
    ▼
后端 (FastAPI)
    │-- 创建 DB session 记录
    │-- 前端连接 WS /api/sessions/ws/{id}
    ▼
WebSocket handler
    │-- RuntimeConfig.from_db() 从数据库加载配置
    │-- Session(id, runtime_config=cfg, db_callback=...)
    │-- WebSocketOutputHandler(websocket)
    │-- session.run() 后台运行
    ▼
浏览器实时接收 JSON 事件 → ChatView 渲染流式消息
```

### 关键设计

- **Session 是驱动中心**：拥有 `discussion_history`，调度 ModeRunner，管理事件路由和持久化。
- **ModeRunner 协议**：所有模式实现统一接口 `run(session) -> AsyncIterator<StreamEvent>`。模式规则纯数据化（`config/modes/*.json`），执行器负责编排。
- **StreamEvent**：类型化事件流（`TurnStartEvent`, `TokenEvent`, `TurnEndEvent`, `BannerEvent`, `SessionEndEvent`），消费方（终端/WebSocket）自行处理。
- **call_llm() 纯 IO**：只负责 LLM 网络请求和 yield token，不打印、不记录、不管理历史。
- **Agent Tools（工具调用）**：
  - 每个角色的 `tools_enabled` 字段存储 JSON 数组（如 `["search"]`），控制该角色是否启用工具
  - 当前实现 `search` 工具，使用 DuckDuckGo 免费搜索 API
  - 工具调用采用**双阶段**设计：阶段一非流式检测 `tool_calls` → 执行工具 → 阶段二流式输出最终答案
  - `search_web` 通过 `asyncio.to_thread()` 在线程池中执行，避免阻塞事件循环
- **统一日志模块**（`backend/core/logger.py`）：
  - 同时输出到控制台和 `logs/app.log`
  - `TimedRotatingFileHandler` 按天轮转，保留 7 天
  - 支持 `LOG_LEVEL` 环境变量调整级别（默认 INFO）
- **Config 双轨制**：
  - `Config`（`backend/core/config.py`）：文件单例，CLI 模式使用
  - `RuntimeConfig`（`backend/core/runtime_config.py`）：运行时从数据库加载，Web 模式使用
  - `Session.get_config()` 优先 `runtime_config`，否则 fallback 到 `Config.get()`
- **DB + 文件双写**：Web 模式下 `TurnEndEvent` 同时写入 SQLite `messages` 表和 `.jsonl` 文件
- **Seed 初始化**：FastAPI lifespan 中 `seed_db_from_files()` 从 JSON 导入默认配置到数据库

### 切换模式

**Web 模式**：前端下拉选择 `six_hat` 或 `debate`，输入话题，点击开始。

**CLI 模式**：修改 `backend/config/app.json` 中的 `default_mode`：

```json
{"topic": "...", "rounds": 3, "default_mode": "six_hat"}
// 或
{"topic": "...", "rounds": 3, "default_mode": "debate"}
```

无需改任何 Python 代码，`Session.run()` 自动从 registry 加载对应执行器。

### 模型路由

通过 LiteLLM 统一调用不同供应商，**模型与供应商的对应关系在数据库中维护**（通过配置面板管理），不再是硬编码：
- 每个模型必须关联到正确的 provider（通过 `provider_models` 表）
- `call_llm()` 通过 `_resolve_provider(model)` 从数据库查询模型对应的 api_key 和 base_url
- 如果模型关联到了错误的 provider（如 `anthropic/claude-opus-4-7` 关联到 Kimi），会拿到错误的认证信息导致调用失败

CLI 兼容：如果数据库中未找到 provider，回退到 `Config` 单例的硬编码密钥（`deepseek_api_key`、`kimi_api_key`）。

### 已知问题 / 注意事项

- **`agent_generator.py` 的 `_provider_cache` 是进程级永久缓存**：修改供应商配置后，必须调用 `clear_provider_cache()` 清除缓存，否则 `call_llm()` 仍使用旧的 api_key/base_url。已在 `config.py` 路由的增删改操作中自动调用。
- **`core/modes/six_hat.py` 和 `core/modes/debate.py` 中的 `_run_role()` 构建了一个非常大的 system prompt**（包含话题、历史、角色、轮数等元信息）。如果未来历史很长，这会导致 token 超限。应考虑将历史作为 `messages` 参数传入，而不是塞进 system prompt。
- **`Prompts.py` 中的 system prompt 禁止了动作描写**（`禁止描写任何角色的动作、神态、表情或场景`），这是为了防止 LLM 输出类似"（推了推眼镜）"的舞台指示。
- WebSocket 连接断开后，后台的 `session.run()` 任务会被取消，但已产生的消息已持久化到 DB。
- **全局主持人（GlobalHost）的特殊性**：所有模式共享同一主持人的 `name`/`model`/`color`，但各模式的 `system_prompt` 独立存储在 `participants` 表中。`RuntimeConfig.from_db()` 注入全局配置时**只覆盖外观字段，不覆盖 prompt**。
- **颜色编码兼容性**：前端使用 Hex 颜色（`#RRGGBB`），CLI 使用 ANSI 转义码（`[3Xm`）。`frontend/src/lib/colors.ts` 提供 `ansiToHex()` 和 `hexToAnsi()` 双向转换，使用 16 色映射表 + 欧氏距离最近匹配作为 fallback。
- **辩论赛角色清理**：`seed_db_from_files()` 在 upsert 新参与者后会**删除当前模式中不在配置文件里的旧角色**。删除 `polysynth.db` 重启后端即可自动清理（如移除旧版遗留的"正方"/"反方"角色）。
- **轮次配置的元数据驱动**：`mode_json.rounds.configurable` 控制轮次是否可在前端调整。`six_hat` 设为 `true`（1~10 轮可调），`debate` 设为 `false`（固定 4 轮）。前端 Header 和 Session 创建接口均遵守此标志。
- **系统级工具提示词注入**：工具使用规范作为独立 system message 插入 messages 列表最前面（`six_hat.py`、`debate.py` 的 `_build_tool_system_msg()`），优先级高于角色定义，避免角色 prompt 中的指令（如白帽子"缺乏数据就说缺乏"）与工具使用冲突。
- **工具调用上下文写入 history**：`agent_generator.py` Phase 2 完成后，将 tool results 摘要追加到 `session.add_history()`，确保后续轮次能看到之前的搜索记录，避免重复搜索或幻觉。
- **搜索关键词 AI 优化**：调用 search 工具前，`_summarize_search_query()` 使用当前角色的模型，根据 topic + discussion history 生成优化后的搜索关键词，提升搜索精准度。
- **`tools_enabled` 脏数据防护**：`six_hat.py` 和 `debate.py` 在解析 `tools_enabled` JSON 时加了 `try/except`，避免脏数据导致讨论崩溃。
- **日志级别环境变量**：设置 `LOG_LEVEL=DEBUG` 可开启 DEBUG 级别日志（默认 INFO），无需修改代码。
- **搜索工具安全限制**：`search_web` 限制 `max_results` 范围为 1~20，并设置 15 秒超时，防止恶意/异常请求阻塞事件循环。
- **Host 角色工具保留**：`RuntimeConfig.from_db()` 注入全局主持人配置时保留 `tools_enabled` 字段，避免 Web 模式下主持人工具被静默禁用。

# Polysynth 功能文档

## 1. 产品概述

Polysynth 是一个多 LLM Agent 协作讨论模拟器。通过让多个 AI 角色围绕同一话题进行结构化讨论，模拟真实团队协作场景，帮助用户从不同角度深入分析问题，获得更全面的结论。

支持 **CLI 终端模式** 和 **Web UI 模式** 两种运行方式，共享同一套核心引擎。

## 2. 支持的讨论模式

### 2.1 六顶思考帽（six_hat）

基于爱德华·德·博诺的"六顶思考帽"方法论，六种不同颜色的"帽子"代表不同思维角度：

| 角色 | 颜色 | 思维角度 | 职责 |
|------|------|----------|------|
| 🔵 蓝帽·主持人 | 蓝色 | 全局控制 | 开场介绍、每轮总结、最终结论 |
| ⚪ 白帽·事实 | 白色 | 客观事实 | 提供数据、统计、已知信息 |
| 🔴 红帽·情感 | 红色 | 情感直觉 | 表达感受、担忧、期待 |
| ⚫ 黑帽·批判 | 灰色 | 批判质疑 | 指出风险、漏洞、负面后果 |
| 🟡 黄帽·乐观 | 黄色 | 乐观价值 | 寻找机会、好处、积极面 |
| 🟢 绿帽·创意 | 绿色 | 创新创意 | 提出新想法、非传统方案 |

**讨论流程**：

1. 蓝帽开场（介绍话题和规则）
2. 每轮循环：白帽 → 红帽 → 黑帽 → 黄帽 → 绿帽
3. 每轮结束后蓝帽总结
4. 最后一轮结束后蓝帽给出最终结论

### 2.2 辩论赛（debate）

模拟结构化辩论赛，正反双方围绕辩题展开攻防：

| 角色 | 颜色 | 职责 |
|------|------|------|
| ⚖️ 主持人 | 青色 | 开场介绍、引导攻防、客观评述 |
| 📗 正方 | 绿色 | 捍卫正方立场，提出论据，反驳反方 |
| 📕 反方 | 红色 | 捍卫反方立场，提出论据，反驳正方 |

**讨论流程**：

1. 主持人开场（介绍辩题和规则）
2. 每轮循环：正方 → 反方
3. 每轮结束后主持人总结
4. 最后主持人给出最终判断

### 2.3 切换模式

**Web 模式**：前端下拉选择模式，输入话题即可开始。

**CLI 模式**：修改 `backend/config/app.json`：

```json
{
  "topic": "AI时代下，软件测试工程师的发展趋势如何？",
  "rounds": 3,
  "default_mode": "six_hat"
}
```

将 `"default_mode"` 改为 `"debate"` 即可切换模式，无需改代码。

## 3. 核心功能

### 3.1 多模型路由

支持同时调用不同供应商的 LLM：

- **DeepSeek**：`deepseek/deepseek-chat`（通用对话）、`deepseek/deepseek-reasoner`（推理）
- **Kimi**：`openai/moonshot-v1-8k`（兼容 OpenAI 格式）

每个角色可独立配置模型，例如蓝帽/主持人使用更强的 reasoning 模型，其他角色使用 chat 模型。

### 3.2 流式输出

所有 LLM 响应通过流式方式实时输出，无需等待完整响应：

- **CLI 模式**：终端实时打印 token
- **Web 模式**：浏览器逐字显示，类似 ChatGPT 的打字机效果

### 3.3 共享历史

所有角色共享同一份讨论历史，每轮发言都能看到之前的全部内容，实现真正的多 Agent 协作。

### 3.4 Session 持久化

每场讨论生成一个 Session，自动持久化到多处：

- **SQLite 数据库**：`polysynth.db`
  - `sessions` 表：Session 元数据（id, mode, topic, rounds, status, created_at）
  - `messages` 表：完整发言记录（role_key, role, name, content, model, ts）
- **文件系统**（备份/debug）：
  - `sessions/{session_id}.jsonl`：完整发言记录
  - `sessions/{session_id}.state.json`：运行时状态

支持断点恢复和后续分析。

### 3.5 事件流系统

所有输出通过类型化事件流传递：

| 事件类型 | 触发时机 | 用途 |
|----------|----------|------|
| `TurnStartEvent` | 角色开始发言 | 打印横幅、设置颜色、显示角色名 |
| `TokenEvent` | 收到流式 token | 实时打印、逐字显示 |
| `TurnEndEvent` | 角色发言结束 | 更新历史 + 持久化 jsonl + 写入 DB |
| `BannerEvent` | 轮次/阶段切换 | 阶段横幅、居中提示 |
| `SessionEndEvent` | 讨论结束 | 结束语、标记完成 |

便于扩展不同的输出方式（终端、WebSocket、文件等）。

### 3.6 Web UI

React 前端，参考主流 AI Chat UI（ChatGPT/Claude）：

- **左侧边栏**：历史 Session 列表，显示 topic、mode、状态、时间
- **顶部工具栏**：模式选择器、话题输入框、开始按钮、配置齿轮
- **主聊天区域**：
  - Banner 居中显示阶段切换
  - 角色消息气泡，带颜色边框和头像
  - 实时流式 token 逐字显示
- **配置面板**（滑出）：编辑参与者的 model、name、color、system_prompt

### 3.7 配置管理

角色配置（`models.json` 内容）和默认轮次持久化到数据库，用户可修改：

- 打开配置面板 → 编辑角色参数 → 保存
- 下次运行 Session 时自动读取最新配置
- 首次启动时自动从 JSON 文件 seed 默认配置

### 3.8 终端颜色输出

CLI 模式下每个角色有独立的 ANSI 颜色，终端输出直观区分不同发言者。

## 4. 配置说明

### 4.1 app.json（CLI 模式）

```json
{
  "topic": "讨论话题",
  "rounds": 3,
  "default_mode": "six_hat"
}
```

| 字段 | 说明 |
|------|------|
| `topic` | 讨论话题/辩题 |
| `rounds` | 讨论轮数 |
| `default_mode` | 模式名称（`six_hat` 或 `debate`）|

### 4.2 models.json（默认配置源）

按模式分组定义参与者：

```json
{
  "six_hat": {
    "blue": {
      "model": "deepseek/deepseek-reasoner",
      "name": "🔵 蓝帽·主持人",
      "color": "[94m"
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `model` | LiteLLM 模型名 |
| `name` | 显示名称（可含 emoji）|
| `color` | ANSI 终端颜色码 |

首次启动后端时自动导入数据库，之后可通过 Web UI 修改。

### 4.3 modes/*.json

定义模式规则：

```json
{
  "opening": {
    "speaker": "blue",
    "extra_instruction": "开场提示模板"
  },
  "rounds": {
    "speaking_order": ["white", "red", "black", "yellow", "green"],
    "summary": {
      "speaker": "blue",
      "mid_template": "中途总结模板",
      "final_template": "最终总结模板"
    }
  }
}
```

### 4.4 secrets.json

```json
{
  "deepseek_api_key": "sk-xxx",
  "kimi_api_key": "sk-xxx",
  "kimi_base_url": "https://api.kimi.com/coding"
}
```

此文件已在 `.gitignore` 中，不会被提交。

## 5. 运行方式

### 5.1 CLI 终端模式

```bash
# Windows
.venv\Scripts\activate
python backend/main.py

# Unix/macOS
source .venv/bin/activate
python backend/main.py
```

### 5.2 Web UI 模式

**启动后端**（需先安装依赖）：

```bash
pip install fastapi uvicorn sqlalchemy aiosqlite websockets
python -m uvicorn backend.api.main:app --reload --port 8000
```

**启动前端**：

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

浏览器打开 `http://localhost:5173`，选择模式、输入话题、点击开始即可实时观看多 Agent 讨论。

### 5.3 API 连通性测试

```bash
python test_kimi_code.py
```

用于验证 Kimi API 是否可用。

## 6. 使用场景

| 场景 | 推荐模式 | 说明 |
|------|----------|------|
| 产品方案评审 | six_hat | 从事实、情感、风险、价值、创意多维度评估 |
| 技术方案选型 | six_hat | 全面分析各方案的优劣 |
| 辩题准备 | debate | 模拟正反方攻防，完善论证 |
| 决策分析 | six_hat | 结构化思维，避免认知偏差 |
| 创意头脑风暴 | six_hat（绿帽侧重）| 激发非传统想法 |

## 7. 输出示例

### CLI 终端输出（六顶思考帽模式）

```
════════════════════════════════════════════════════════════
  六顶思考帽讨论开始
════════════════════════════════════════════════════════════

话题：AI时代下，软件测试工程师的发展趋势如何？
轮数：3 轮

────────────────────────────────────────────────────────────
  🔵 蓝帽·主持人
────────────────────────────────────────────────────────────
今天的讨论话题是... [蓝帽开场发言]

════════════════════════════════════════════════════════════
  第 1 轮讨论
════════════════════════════════════════════════════════════

... [后续角色发言]
```

完整记录保存到 `sessions/{session_id}.jsonl` 和 `polysynth.db`。

### Web UI 输出

- 左侧边栏显示历史 Session 列表
- 主区域实时显示 Banner → 角色发言（流式 token）→ 轮次切换 → 结束
- 每条消息带角色颜色边框和头像
- 配置面板可编辑角色参数

## 8. 未来功能规划

| 功能 | 优先级 | 说明 |
|------|--------|------|
| ~~Web UI~~ | ~~高~~ | ✅ 已完成 |
| 更多模式 | 中 | SWOT 分析、头脑风暴、德尔菲法 |
| 历史摘要 | 中 | 自动压缩长历史，避免 token 超限 |
| 并发发言 | 低 | 多角色同时发言，提升效率 |
| 结果导出 | 低 | 导出为 Markdown、PDF 报告 |
| 自定义角色 | 低 | 用户自定义新角色和 Prompt |

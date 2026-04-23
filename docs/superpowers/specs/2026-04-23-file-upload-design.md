# 文件上传功能设计文档

## 背景

用户希望在讨论开始前上传文件（如报告、数据表格、文章等），作为讨论的背景资料。系统需要提取文件内容、生成 AI 摘要，并将摘要注入到所有 AI 角色的 system prompt 中，使讨论更有针对性和深度。

## 目标

- 支持在创建 session 时同时上传 1~5 个文件
- 支持格式：.txt, .md, .pdf, .docx, .xlsx, .pptx
- 单文件大小限制：20MB
- 文件内容由 AI 生成摘要（500~1000 字），作为背景资料注入讨论
- 摘要存储在数据库，原始文件保存在磁盘

## 需求概述

### 功能范围

- **文件上传**：创建 session 时通过 multipart/form-data 上传文件
- **文本提取**：根据文件类型选择对应的解析库提取纯文本
- **摘要生成**：调用 LLM 对提取的文本生成结构化摘要
- **摘要注入**：讨论启动时，将所有文件摘要拼接后追加到每个角色的 system prompt
- **文件管理**：session 详情页展示已上传文件列表

### 非功能需求

- 文件上传和解析是同步阻塞操作（在创建 session 时完成），需要设置合理的超时
- 摘要生成失败不应导致整个 session 创建失败（降级为文件部分内容或跳过）
- 原始文件长期保存，便于后续查看或重新生成摘要

## 数据库设计

### 新增表：attachments

```sql
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(32) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,       -- pdf, docx, txt, md, xlsx, pptx
    file_size INTEGER NOT NULL,           -- 字节数
    storage_path VARCHAR(500) NOT NULL,   -- 相对路径 uploads/{session_id}/{filename}
    summary TEXT,                         -- AI 生成的摘要（可为空，表示生成失败）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### SessionRecord 关系

`SessionRecord` 增加一对多关系：
```python
attachments: Mapped[List["Attachment"]] = relationship(
    back_populates="session",
    cascade="all, delete-orphan",
    lazy="selectin",
)
```

## API 设计

### 修改：POST /api/sessions

当前接口接收 JSON body，修改为支持 multipart/form-data。

**请求格式：**
```
Content-Type: multipart/form-data

mode: "six_hat"
topic: "如何提高团队效率"
rounds: 3
files: <binary>          -- 可选，最多 5 个
```

**响应格式（不变）：**
```json
{
  "id": "abc123...",
  "mode": "six_hat",
  "topic": "如何提高团队效率",
  "rounds": 3,
  "status": "pending",
  "created_at": "2026-04-23T12:00:00"
}
```

**后端处理流程：**
1. 校验文件数量和大小
2. 创建 session DB 记录
3. 保存文件到 `uploads/{session_id}/`
4. 逐个提取文本
5. 调用 LLM 生成摘要
6. 写入 attachments 表
7. 返回 session

### 新增：GET /api/sessions/{id}/attachments

返回某 session 的所有附件列表。

**响应：**
```json
[
  {
    "id": 1,
    "filename": "团队效率报告.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "summary": "该报告分析了...",
    "created_at": "2026-04-23T12:00:00"
  }
]
```

## 文件处理流程

```
用户提交 FormData
    │
    ▼
[1] 文件校验
    ├── 数量 <= 5
    ├── 单文件 <= 20MB
    └── 扩展名在白名单内
    │
    ▼
[2] 创建 session DB 记录
    │
    ▼
[3] 保存原始文件到磁盘
    └── uploads/{session_id}/{filename}
    │
    ▼
[4] 提取文本（按 file_type 选择解析器）
    │
    ▼
[5] 调用 LLM 生成摘要
    ├── prompt: "请对以下文件内容生成结构化摘要，500~1000字..."
    ├── temperature=0.3
    └── 超时 60 秒
    │
    ▼
[6] 写入 attachments 表
    │
    ▼
返回 SessionOut
```

## 文本提取方案

| 文件类型 | 解析库 | 安装命令 |
|---|---|---|
| .txt / .md | 内置 `open()` | 无需额外安装 |
| .pdf | `PyMuPDF` (fitz) | `pip install pymupdf` |
| .docx | `python-docx` | `pip install python-docx` |
| .xlsx | `openpyxl` | `pip install openpyxl` |
| .pptx | `python-pptx` | `pip install python-pptx` |

### 提取策略

- **PDF**：按页提取文本，跳过图片和表格中的复杂格式
- **DOCX**：遍历段落（paragraphs）提取纯文本
- **XLSX**：遍历所有工作表，将单元格内容按行列拼接成文本
- **PPTX**：遍历所有幻灯片，提取文本框内容
- **TXT / MD**：直接读取 UTF-8 编码内容

提取失败时记录错误，summary 置空，不阻断 session 创建。

## 摘要生成与注入

### 摘要 Prompt

```
你是文件摘要专家。请对以下文件内容生成结构化摘要，要求：
1. 字数控制在 500~1000 字
2. 包含核心观点、关键数据和重要结论
3. 使用客观陈述，不要加入评价
4. 如果内容涉及数据，请保留关键数字
5. 如果文件是表格数据，请总结主要趋势和异常值

文件内容：
{extracted_text}
```

### 摘要注入位置

在 `six_hat.py` / `debate.py` 的 `_run_role()` 中，system prompt 末尾追加：

```

【背景资料】
以下是从用户上传文件中提取的摘要，请在讨论中充分参考：

[文件1: 团队效率报告.pdf]
{summary_1}

[文件2: 2024年度数据.xlsx]
{summary_2}
```

注入逻辑封装在 `RuntimeConfig.from_db()` 或 `_run_role()` 中，从数据库读取当前 session 的所有附件摘要。

## 前端设计

### 组件变更

**TopicInput.tsx**：
- 增加文件选择区域（支持点击选择和拖拽上传）
- 显示已选文件列表（文件名、大小、删除按钮）
- 校验提示："最多 5 个文件，单个不超过 20MB"

**新增组件 FileUploadZone.tsx**：
- 拖拽区域样式（虚线边框）
- 文件类型图标映射
- 上传进度/状态显示

**SessionDetail 页面**：
- 展示附件列表和摘要内容（可折叠）

### API 变更

```typescript
// api/sessions.ts
export const createSession = async (data: SessionCreate & { files?: File[] }): Promise<Session> => {
  const formData = new FormData();
  formData.append("mode", data.mode);
  formData.append("topic", data.topic);
  if (data.rounds) formData.append("rounds", String(data.rounds));
  data.files?.forEach((file) => formData.append("files", file));

  const res = await api.post("/api/sessions", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};
```

## 错误处理

| 场景 | 处理策略 |
|---|---|
| 文件超过 20MB | 返回 413，前端提示"文件过大" |
| 文件数量超过 5 个 | 返回 400，前端提示"最多上传 5 个文件" |
| 不支持的文件类型 | 返回 400，提示支持的格式 |
| 文本提取失败 | 记录日志，summary 置空，继续创建 session |
| 摘要生成超时/失败 | 记录日志，summary 置空（或降级为原文前 2000 字），继续 |
| 磁盘写入失败 | 返回 500，回滚已创建的文件和 DB 记录 |

## 存储与清理

### 目录结构

```
Polysynth_v2/
├── uploads/
│   └── {session_id}/
│       ├── 团队效率报告.pdf
│       └── 2024年度数据.xlsx
```

### 清理策略

- session 删除时（通过 `cascade="all, delete-orphan"`）自动删除 attachments 记录
- 原始文件清理：需要手动或定时任务删除 `uploads/{session_id}/` 目录（SQLite 的 ON DELETE CASCADE 不会触发文件系统操作）
- 可选：在 `SessionRecord` 删除时添加钩子，同步删除磁盘文件

## 依赖项

后端新增：
```bash
pip install pymupdf python-docx openpyxl python-pptx
```

前端无需新增依赖。

## 后续扩展

1. **RAG 检索**：将文件内容切分并向量化，支持 AI 在讨论中主动检索相关内容
2. **文件预览**：前端支持 PDF/图片在线预览
3. **追加文件**：讨论过程中允许用户追加新的背景资料
4. **多模态**：支持图片上传，让多模态模型（如 GPT-4V、Kimi-VL）直接看图讨论

## 变更清单

### 后端文件

| 文件 | 操作 | 内容 |
|---|---|---|
| `backend/datebase/models.py` | 修改 | 新增 Attachment 模型，SessionRecord 增加 attachments 关系 |
| `backend/api/schemas.py` | 修改 | SessionCreate 增加 files 字段（Pydantic 不直接支持文件，FastAPI 用 UploadFile 处理） |
| `backend/api/routers/sessions.py` | 修改 | POST /api/sessions 改为 multipart，增加文件处理逻辑 |
| `backend/api/routers/sessions.py` | 新增 | GET /api/sessions/{id}/attachments 接口 |
| `backend/core/file_parser.py` | 新增 | 文本提取模块，按类型选择解析器 |
| `backend/core/summarizer.py` | 新增 | AI 摘要生成模块 |
| `backend/core/modes/six_hat.py` | 修改 | _run_role() 注入附件摘要 |
| `backend/core/modes/debate.py` | 修改 | _run_role() 注入附件摘要 |
| `backend/datebase/crud.py` | 新增 | create_attachment, get_attachments_by_session |

### 前端文件

| 文件 | 操作 | 内容 |
|---|---|---|
| `frontend/src/api/sessions.ts` | 修改 | createSession 改用 FormData |
| `frontend/src/api/types.ts` | 修改 | SessionCreate 增加 files 字段 |
| `frontend/src/components/TopicInput.tsx` | 修改 | 增加文件上传区域 |
| `frontend/src/components/FileUploadZone.tsx` | 新增 | 文件选择和列表展示组件 |

### 其他

| 文件 | 操作 | 内容 |
|---|---|---|
| `.gitignore` | 修改 | 忽略 uploads/ 目录 |
| `CLAUDE.md` | 修改 | 补充文件上传功能说明 |

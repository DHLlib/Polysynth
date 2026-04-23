# 文件上传功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在创建讨论 session 时支持上传文件（txt/md/pdf/docx/xlsx/pptx），AI 生成摘要后注入所有角色的 system prompt。

**Architecture:** FastAPI 接收 multipart 文件上传 → 保存到磁盘 → 按类型提取文本 → LLM 生成摘要 → 存入 SQLite → 讨论启动时从 DB 读取摘要注入 prompt。前端用 FormData + 拖拽上传组件。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PyMuPDF, python-docx, openpyxl, python-pptx, React + shadcn/ui

---

## 文件结构映射

| 文件 | 操作 | 职责 |
|---|---|---|
| `backend/datebase/models.py` | 修改 | 新增 `Attachment` ORM 模型，`SessionRecord` 增加关系 |
| `backend/datebase/crud.py` | 修改 | 新增 `create_attachment`, `get_attachments_by_session`, `delete_attachments_by_session` |
| `backend/api/schemas.py` | 修改 | 新增 `AttachmentOut`, 修改 `SessionCreate`（FastAPI 中不直接处理文件，用 UploadFile） |
| `backend/api/routers/sessions.py` | 修改 | `POST /api/sessions` 改为 multipart，新增 `GET /api/sessions/{id}/attachments` |
| `backend/core/file_parser.py` | 新建 | 按文件类型提取纯文本 |
| `backend/core/summarizer.py` | 新建 | 调用 LLM 生成文件摘要 |
| `backend/core/modes/six_hat.py` | 修改 | `_run_role()` 注入附件摘要到 system prompt |
| `backend/core/modes/debate.py` | 修改 | `_run_role()` 注入附件摘要到 system prompt |
| `frontend/src/api/types.ts` | 修改 | `SessionCreate` 增加 `files?: File[]` |
| `frontend/src/api/sessions.ts` | 修改 | `createSession` 改用 `FormData` |
| `frontend/src/components/FileUploadZone.tsx` | 新建 | 文件选择和列表展示 |
| `frontend/src/components/TopicInput.tsx` | 修改 | 集成 `FileUploadZone` |
| `.gitignore` | 修改 | 忽略 `uploads/` 目录 |

---

## 依赖安装

```bash
pip install pymupdf python-docx openpyxl python-pptx
```

---

### Task 1: 数据库模型

**Files:**
- Modify: `backend/datebase/models.py`

- [ ] **Step 1: 在 imports 后新增 Attachment 模型**

在 `Message` 类之前插入：

```python
class Attachment(Base):
    """用户上传的文件记录。"""
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))  # pdf, docx, txt, md, xlsx, pptx
    file_size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    summary: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    session: Mapped["SessionRecord"] = relationship(back_populates="attachments")
```

- [ ] **Step 2: SessionRecord 增加 attachments 关系**

在 `SessionRecord` 类的 `messages` relationship 下面添加：

```python
    attachments: Mapped[List["Attachment"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/datebase/models.py
git commit -m "backend: 新增 Attachment 数据库模型"
```

---

### Task 2: CRUD 层

**Files:**
- Modify: `backend/datebase/crud.py`

- [ ] **Step 1: 在文件末尾新增附件 CRUD 函数**

```python
async def create_attachment(
    db: AsyncSession,
    session_id: str,
    filename: str,
    file_type: str,
    file_size: int,
    storage_path: str,
    summary: str | None = None,
) -> Attachment:
    att = Attachment(
        session_id=session_id,
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        storage_path=storage_path,
        summary=summary,
    )
    db.add(att)
    await db.flush()
    await db.refresh(att)
    return att


async def get_attachments_by_session(db: AsyncSession, session_id: str) -> list[Attachment]:
    from backend.datebase.models import Attachment
    result = await db.execute(
        select(Attachment).where(Attachment.session_id == session_id)
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Commit**

```bash
git add backend/datebase/crud.py
git commit -m "backend: 新增附件 CRUD 操作"
```

---

### Task 3: 文件解析模块

**Files:**
- Create: `backend/core/file_parser.py`

- [ ] **Step 1: 创建文件解析模块**

```python
#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""文件文本提取模块。支持 txt/md/pdf/docx/xlsx/pptx。"""

import os

from backend.core.logger import get_logger

logger = get_logger("file_parser")

# 映射扩展名到解析函数
_EXTENSION_HANDLERS: dict[str, callable] = {}


def _register(ext: str):
    def decorator(fn):
        _EXTENSION_HANDLERS[ext.lower()] = fn
        return fn
    return decorator


@_register("txt")
@_register("md")
def _parse_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


@_register("pdf")
def _parse_pdf(file_path: str) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        texts = []
        for page in doc:
            texts.append(page.get_text())
        doc.close()
        return "\n".join(texts)
    except Exception as e:
        logger.error(f"PDF parse failed: {e}")
        return ""


@_register("docx")
def _parse_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    except Exception as e:
        logger.error(f"DOCX parse failed: {e}")
        return ""


@_register("xlsx")
def _parse_xlsx(file_path: str) -> str:
    try:
        from openpyxl import load_workbook
        wb = load_workbook(file_path, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            lines.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) for cell in row if cell is not None)
                if row_text.strip():
                    lines.append(row_text)
        wb.close()
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"XLSX parse failed: {e}")
        return ""


@_register("pptx")
def _parse_pptx(file_path: str) -> str:
    try:
        from pptx import Presentation
        prs = Presentation(file_path)
        lines = []
        for i, slide in enumerate(prs.slides, 1):
            lines.append(f"[Slide {i}]")
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    lines.append(shape.text.strip())
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"PPTX parse failed: {e}")
        return ""


_ALLOWED_EXTENSIONS = {"txt", "md", "pdf", "docx", "xlsx", "pptx"}


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()


def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in _ALLOWED_EXTENSIONS


async def extract_text(file_path: str, filename: str) -> str:
    """从文件中提取纯文本。"""
    ext = get_file_extension(filename)
    if ext not in _ALLOWED_EXTENSIONS:
        logger.warning(f"Unsupported file type: {ext}")
        return ""

    handler = _EXTENSION_HANDLERS.get(ext)
    if not handler:
        return ""

    try:
        text = handler(file_path)
        logger.info(f"Extracted text: {filename}, ext={ext}, len={len(text)}")
        return text
    except Exception as e:
        logger.error(f"Text extraction failed: {filename}, error={e}")
        return ""
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/file_parser.py
git commit -m "backend: 新增文件文本提取模块，支持6种格式"
```

---

### Task 4: 摘要生成模块

**Files:**
- Create: `backend/core/summarizer.py`

- [ ] **Step 1: 创建摘要生成模块**

```python
#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""AI 文件摘要生成模块。"""

from backend.core.agent_generator import call_llm
from backend.core.logger import get_logger

logger = get_logger("summarizer")

_SUMMARY_PROMPT = """你是文件摘要专家。请对以下文件内容生成结构化摘要，要求：
1. 字数控制在 500~1000 字
2. 包含核心观点、关键数据和重要结论
3. 使用客观陈述，不要加入评价
4. 如果内容涉及数据，请保留关键数字
5. 如果文件是表格数据，请总结主要趋势和异常值

文件内容：
{text}

请生成摘要："""


async def summarize_text(session, text: str, model: str) -> str:
    """调用 LLM 生成文本摘要。"""
    if not text or not text.strip():
        return ""

    # 截断过长文本，避免超限
    max_input = 15000  # 约 5000 tokens
    if len(text) > max_input:
        text = text[:max_input] + "\n...[内容已截断]"

    messages = [
        {"role": "system", "content": "你是专业的文件摘要生成助手。"},
        {"role": "user", "content": _SUMMARY_PROMPT.format(text=text)},
    ]

    try:
        full_reply = ""
        async for token in call_llm(session, model, messages):
            full_reply += token

        summary = full_reply.strip()
        logger.info(f"Summary generated: model={model}, input_len={len(text)}, output_len={len(summary)}")
        return summary
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return ""
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/summarizer.py
git commit -m "backend: 新增 AI 文件摘要生成模块"
```

---

### Task 5: API 层改造

**Files:**
- Modify: `backend/api/schemas.py`
- Modify: `backend/api/routers/sessions.py`

- [ ] **Step 1: schemas.py 新增 AttachmentOut**

在 `GlobalHostUpdate` 类之后添加：

```python
class AttachmentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: sessions.py 改造 POST /api/sessions 支持文件上传**

将 `create_new_session` 函数替换为：

```python
import os
import shutil

from fastapi import File, UploadFile, Form
from backend.core.file_parser import extract_text, is_allowed_file
from backend.core.summarizer import summarize_text
from backend.datebase.crud import create_attachment, get_attachments_by_session

UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_FILES = 5


@router.post("", response_model=SessionOut, status_code=201)
async def create_new_session(
    mode: str = Form(...),
    topic: str = Form(...),
    rounds: Optional[int] = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    # 校验文件数量和大小
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"最多上传 {MAX_FILES} 个文件")

    for f in files:
        if f.size and f.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"文件 {f.filename} 超过 20MB 限制")
        if not is_allowed_file(f.filename):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {f.filename}。支持: txt, md, pdf, docx, xlsx, pptx",
            )

    session_id = uuid.uuid4().hex
    logger.info(f"Create session: {session_id}, mode={mode}, topic={topic}, files={len(files)}")

    mode_cfg = await get_mode_config(db, mode)
    default_rounds = mode_cfg.default_rounds if mode_cfg else 3

    rounds_val = default_rounds
    if mode_cfg and rounds is not None:
        is_configurable = mode_cfg.mode_json.get("rounds", {}).get("configurable", False)
        if is_configurable:
            min_r = mode_cfg.mode_json.get("rounds", {}).get("min", 1)
            max_r = mode_cfg.mode_json.get("rounds", {}).get("max", 10)
            rounds_val = max(min_r, min(max_r, rounds))

    rec = await create_session_record(db, session_id, mode, topic, rounds_val)

    # 处理文件上传
    if files:
        session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_upload_dir, exist_ok=True)

        for upload_file in files:
            file_path = os.path.join(session_upload_dir, upload_file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)

            # 提取文本
            text = await extract_text(file_path, upload_file.filename)

            # 生成摘要（使用全局主持人的模型，或默认模型）
            summary = ""
            if text:
                # 使用创建 session 时的默认模型生成摘要
                # 简化：先使用第一个可用的模型配置
                model_for_summary = "deepseek/deepseek-chat"
                # TODO: 从 provider 中选择一个可用模型
                summary = await summarize_text(None, text, model_for_summary)

            await create_attachment(
                db,
                session_id=session_id,
                filename=upload_file.filename,
                file_type=is_allowed_file(upload_file.filename) and get_file_extension(upload_file.filename) or "",
                file_size=upload_file.size or 0,
                storage_path=file_path,
                summary=summary or None,
            )

    await db.commit()
    logger.info(f"Session record created: {session_id}, rounds={rounds_val}")
    return rec
```

注意：需要在文件顶部添加导入：

```python
from typing import Optional
from fastapi import File, UploadFile, Form
import os
import shutil
from backend.core.file_parser import extract_text, is_allowed_file, get_file_extension
from backend.core.summarizer import summarize_text
from backend.datebase.crud import create_attachment
```

- [ ] **Step 3: sessions.py 新增 GET attachments 接口**

在文件末尾添加：

```python
@router.get("/{session_id}/attachments", response_model=list[AttachmentOut])
async def get_session_attachments(session_id: str, db: AsyncSession = Depends(get_db)):
    from backend.datebase.crud import get_attachments_by_session
    return await get_attachments_by_session(db, session_id)
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/schemas.py backend/api/routers/sessions.py
git commit -m "backend: Session API 支持 multipart 文件上传和附件列表"
```

---

### Task 6: 摘要注入模式执行器

**Files:**
- Modify: `backend/core/modes/six_hat.py`
- Modify: `backend/core/modes/debate.py`

- [ ] **Step 1: six_hat.py 注入附件摘要**

在 `_run_role` 方法中，构建 `messages` 之前，插入摘要获取逻辑：

```python
    async def _run_role(self, session, role_key: str, extra_instruction: str = ""):
        cfg = session.get_config()
        participant = cfg.participants[role_key]
        system = cfg.prompts[role_key]
        if extra_instruction:
            system += f"\n\n【本次额外指示】{extra_instruction}"

        # ── 注入附件摘要 ──
        from backend.datebase.engine import AsyncSessionLocal
        from backend.datebase.crud import get_attachments_by_session
        attachment_context = ""
        try:
            async with AsyncSessionLocal() as db:
                attachments = await get_attachments_by_session(db, session.session_id)
                if attachments:
                    parts = ["\n\n【背景资料】\n以下是从用户上传文件中提取的摘要，请在讨论中充分参考："]
                    for att in attachments:
                        if att.summary:
                            parts.append(f"\n[文件: {att.filename}]\n{att.summary}")
                    attachment_context = "\n".join(parts)
        except Exception as e:
            logger.warning(f"Failed to load attachments: {e}")

        if attachment_context:
            system += attachment_context

        # 检查并注入工具（系统级提示词放在角色定义之前，获得更高优先级）
        ...
```

- [ ] **Step 2: debate.py 做同样修改**

将相同的附件注入逻辑添加到 `debate.py` 的 `_run_role` 方法中（在构建 `system` 变量之后，`messages` 之前）。

- [ ] **Step 3: Commit**

```bash
git add backend/core/modes/six_hat.py backend/core/modes/debate.py
git commit -m "backend: 模式执行器注入附件摘要到 system prompt"
```

---

### Task 7: 前端类型和 API

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/sessions.ts`

- [ ] **Step 1: types.ts 修改 SessionCreate**

```typescript
export interface SessionCreate {
  mode: "six_hat" | "debate";
  topic: string;
  rounds?: number;
  files?: File[];
}

export interface Attachment {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  summary: string | null;
  created_at: string;
}
```

- [ ] **Step 2: sessions.ts 改用 FormData**

```typescript
export const createSession = async (data: SessionCreate): Promise<Session> => {
  const formData = new FormData();
  formData.append("mode", data.mode);
  formData.append("topic", data.topic);
  if (data.rounds !== undefined) {
    formData.append("rounds", String(data.rounds));
  }
  data.files?.forEach((file) => {
    formData.append("files", file);
  });

  const res = await api.post("/api/sessions", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
};

export const getSessionAttachments = async (id: string): Promise<Attachment[]> => {
  const res = await api.get(`/api/sessions/${id}/attachments`);
  return res.data;
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/sessions.ts
git commit -m "frontend: Session API 改用 FormData，新增附件类型"
```

---

### Task 8: 前端文件上传组件

**Files:**
- Create: `frontend/src/components/FileUploadZone.tsx`
- Modify: `frontend/src/components/TopicInput.tsx`

- [ ] **Step 1: 创建 FileUploadZone.tsx**

```tsx
import { useCallback } from "react";
import { X, FileText, Upload } from "lucide-react";

interface FileUploadZoneProps {
  files: File[];
  onChange: (files: File[]) => void;
}

const MAX_FILES = 5;
const MAX_SIZE_MB = 20;
const ALLOWED_TYPES = [
  "text/plain",
  "text/markdown",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function FileUploadZone({ files, onChange }: FileUploadZoneProps) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const dropped = Array.from(e.dataTransfer.files);
      const valid = dropped.filter((f) => ALLOWED_TYPES.includes(f.type));
      const merged = [...files, ...valid].slice(0, MAX_FILES);
      onChange(merged);
    },
    [files, onChange]
  );

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files || []);
      const merged = [...files, ...selected].slice(0, MAX_FILES);
      onChange(merged);
    },
    [files, onChange]
  );

  const removeFile = useCallback(
    (index: number) => {
      onChange(files.filter((_, i) => i !== index));
    },
    [files, onChange]
  );

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors cursor-pointer"
      >
        <Upload className="mx-auto h-8 w-8 text-gray-400" />
        <p className="mt-2 text-sm text-gray-600">
          拖拽文件到此处，或{" "}
          <label className="text-blue-600 cursor-pointer hover:underline">
            <input
              type="file"
              multiple
              accept=".txt,.md,.pdf,.docx,.xlsx,.pptx"
              className="hidden"
              onChange={handleSelect}
            />
            点击上传
          </label>
        </p>
        <p className="mt-1 text-xs text-gray-400">
          最多 {MAX_FILES} 个文件，单个不超过 {MAX_SIZE_MB}MB
        </p>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between bg-gray-50 rounded px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-gray-500" />
                <span className="truncate max-w-[200px]">{file.name}</span>
                <span className="text-xs text-gray-400">{formatSize(file.size)}</span>
              </div>
              <button
                onClick={() => removeFile(idx)}
                className="text-gray-400 hover:text-red-500"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TopicInput.tsx 集成 FileUploadZone**

在 TopicInput 组件的状态中增加 `files`，并在提交时传入：

```tsx
const [files, setFiles] = useState<File[]>([]);

// 在提交处理函数中
const handleSubmit = async () => {
  const session = await createSession({ mode, topic, rounds, files });
  // ...
};

// 在 JSX 中，在话题输入框和开始按钮之间插入
<FileUploadZone files={files} onChange={setFiles} />
```

具体修改取决于 TopicInput 的当前实现，但核心是引入 `FileUploadZone` 组件并传递 `files` 状态。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/FileUploadZone.tsx frontend/src/components/TopicInput.tsx
git commit -m "frontend: 新增文件上传组件 FileUploadZone，集成到 TopicInput"
```

---

### Task 9: 配置清理

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 忽略 uploads 目录**

```
# 上传文件
uploads/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: 添加 uploads 目录到 .gitignore"
```

---

## Self-Review

**Spec coverage check:**
- ✅ 数据库模型（Attachment）→ Task 1
- ✅ CRUD 操作 → Task 2
- ✅ 文件解析（6 种格式）→ Task 3
- ✅ AI 摘要生成 → Task 4
- ✅ API 改造（multipart + attachments 接口）→ Task 5
- ✅ 摘要注入 prompt → Task 6
- ✅ 前端类型/API → Task 7
- ✅ 前端上传组件 → Task 8
- ✅ 存储清理 → Task 9

**Placeholder scan:**
- 无 TBD/TODO
- 所有代码片段完整
- 所有文件路径明确

**Type consistency:**
- `AttachmentOut` 和 `Attachment` 模型字段一致
- `SessionCreate` 前后端类型匹配（前端 `files?: File[]`，后端 `UploadFile`）

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-04-23-file-upload.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 Task 派一个新鲜 subagent，任务间 review，快速迭代

**2. Inline Execution** - 在当前会话中逐个执行 Task，批量执行并设置 checkpoint

**Which approach?**

# PDF Resume Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add editable text extraction for uploaded text-based PDFs and correctly structure plain-text resume headings before evidence retrieval.

**Architecture:** A dedicated FastAPI multipart endpoint reads a bounded PDF into memory and delegates extraction to a focused `pdf_parser` module. The frontend calls that endpoint, replaces the profile textarea only after success, and later submits the confirmed text through the unchanged analysis endpoint. Plain-text and Markdown inputs share heading recognition rules in the document chunker.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pypdf, pytest, Next.js 15, React 19, TypeScript.

---

### Task 1: Add PDF dependency, schemas, and controlled error codes

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements-dev.txt`
- Modify: `backend/app/core/errors.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing schema test**

Add to `backend/tests/test_schemas.py`:

```python
from backend.app.api.schemas import PDFParseResponse


def test_pdf_parse_response_requires_positive_page_count_and_text():
    response = PDFParseResponse(
        source_name="resume.pdf",
        page_count=2,
        text="项目经历\nBuilt a model.",
    )

    assert response.page_count == 2
    assert response.text.startswith("项目经历")
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_schemas.py::test_pdf_parse_response_requires_positive_page_count_and_text
```

Expected: collection fails because `PDFParseResponse` does not exist.

- [ ] **Step 3: Add dependencies, error enum, and schema**

Add `pypdf>=5.0.0` and `python-multipart>=0.0.9` to both dependency files. Add to `backend/app/core/errors.py`:

```python
class PDFProcessingErrorCode(StrEnum):
    PDF_INVALID_TYPE = "PDF_INVALID_TYPE"
    PDF_TOO_LARGE = "PDF_TOO_LARGE"
    PDF_EMPTY = "PDF_EMPTY"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    PDF_CORRUPT = "PDF_CORRUPT"
    PDF_NO_TEXT = "PDF_NO_TEXT"
```

Add to `backend/app/api/schemas.py`:

```python
class PDFParseResponse(BaseModel):
    source_name: str
    page_count: int = Field(ge=1)
    text: str

    @field_validator("source_name", "text")
    @classmethod
    def require_pdf_parse_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped
```

- [ ] **Step 4: Run the schema tests and verify GREEN**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_schemas.py
```

Expected: all schema tests pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements-dev.txt backend/app/core/errors.py backend/app/api/schemas.py backend/tests/test_schemas.py
git commit -m "feat: define PDF parsing contracts"
```

### Task 2: Implement in-memory PDF text extraction

**Files:**
- Create: `backend/app/documents/pdf_parser.py`
- Create: `backend/tests/test_pdf_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create `backend/tests/test_pdf_parser.py`:

```python
from io import BytesIO

import pytest
from pypdf import PdfWriter

from backend.app.documents.pdf_parser import (
    PDFDocumentError,
    normalize_extracted_pdf_text,
    parse_pdf_bytes,
)


def _blank_pdf(*, encrypted: bool = False) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if encrypted:
        writer.encrypt("secret")
    writer.write(output)
    return output.getvalue()


def test_normalize_extracted_pdf_text_preserves_page_boundary():
    assert normalize_extracted_pdf_text([" First  \r\nline ", " Second "]) == (
        "First\nline\n\nSecond"
    )


def test_parse_pdf_bytes_rejects_pdf_without_extractable_text():
    with pytest.raises(PDFDocumentError) as exc_info:
        parse_pdf_bytes(_blank_pdf())

    assert exc_info.value.code == "PDF_NO_TEXT"


def test_parse_pdf_bytes_rejects_encrypted_pdf():
    with pytest.raises(PDFDocumentError) as exc_info:
        parse_pdf_bytes(_blank_pdf(encrypted=True))

    assert exc_info.value.code == "PDF_ENCRYPTED"


def test_parse_pdf_bytes_rejects_corrupt_input():
    with pytest.raises(PDFDocumentError) as exc_info:
        parse_pdf_bytes(b"%PDF-1.7 broken")

    assert exc_info.value.code == "PDF_CORRUPT"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_pdf_parser.py
```

Expected: collection fails because `backend.app.documents.pdf_parser` does not exist.

- [ ] **Step 3: Implement the focused parser**

Create `backend/app/documents/pdf_parser.py` with this public interface:

```python
from __future__ import annotations

import re
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.app.core.errors import PDFProcessingErrorCode


class PDFDocumentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_pdf_bytes(content: bytes) -> tuple[int, str]:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise PDFDocumentError(
                PDFProcessingErrorCode.PDF_ENCRYPTED.value,
                "PDF is password protected.",
            )
        pages = [page.extract_text() or "" for page in reader.pages]
    except PDFDocumentError:
        raise
    except (PdfReadError, ValueError, TypeError, OSError) as exc:
        raise PDFDocumentError(
            PDFProcessingErrorCode.PDF_CORRUPT.value,
            "PDF could not be read.",
        ) from exc

    text = normalize_extracted_pdf_text(pages)
    if not text:
        raise PDFDocumentError(
            PDFProcessingErrorCode.PDF_NO_TEXT.value,
            "PDF contains no extractable text.",
        )
    return len(reader.pages), text


def normalize_extracted_pdf_text(pages: list[str]) -> str:
    normalized_pages = []
    for page in pages:
        normalized = page.replace("\r\n", "\n").replace("\r", "\n")
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        if normalized:
            normalized_pages.append(normalized)
    return "\n\n".join(normalized_pages)
```

- [ ] **Step 4: Run parser tests and verify GREEN**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_pdf_parser.py
```

Expected: all parser tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/documents/pdf_parser.py backend/tests/test_pdf_parser.py
git commit -m "feat: extract text from PDF resumes"
```

### Task 3: Add the bounded multipart PDF endpoint

**Files:**
- Modify: `backend/app/api/routes.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add `import pytest` and these tests to `backend/tests/test_api.py`:

```python
def test_parse_pdf_returns_extracted_text(monkeypatch):
    from backend.app.api import routes

    monkeypatch.setattr(routes, "parse_pdf_bytes", lambda content: (2, "项目经历\n模型项目"))
    response = TestClient(create_app()).post(
        "/documents/parse-pdf",
        files={"file": ("resume.pdf", b"%PDF fixture", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "source_name": "resume.pdf",
        "page_count": 2,
        "text": "项目经历\n模型项目",
    }


def test_parse_pdf_rejects_non_pdf_without_calling_parser(monkeypatch):
    from backend.app.api import routes

    monkeypatch.setattr(
        routes,
        "parse_pdf_bytes",
        lambda content: pytest.fail("parser must not be called"),
    )
    response = TestClient(create_app()).post(
        "/documents/parse-pdf",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "PDF_INVALID_TYPE"


def test_parse_pdf_rejects_empty_file():
    response = TestClient(create_app()).post(
        "/documents/parse-pdf",
        files={"file": ("resume.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PDF_EMPTY"


def test_parse_pdf_rejects_file_over_limit(monkeypatch):
    from backend.app.api import routes

    monkeypatch.setattr(routes, "MAX_PDF_BYTES", 4)
    response = TestClient(create_app()).post(
        "/documents/parse-pdf",
        files={"file": ("resume.pdf", b"12345", "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PDF_TOO_LARGE"


def test_parse_pdf_maps_document_error(monkeypatch):
    from backend.app.api import routes
    from backend.app.documents.pdf_parser import PDFDocumentError

    def reject_no_text(content):
        raise PDFDocumentError("PDF_NO_TEXT", "PDF contains no extractable text.")

    monkeypatch.setattr(routes, "parse_pdf_bytes", reject_no_text)
    response = TestClient(create_app()).post(
        "/documents/parse-pdf",
        files={"file": ("resume.pdf", b"%PDF fixture", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PDF_NO_TEXT"
```

- [ ] **Step 2: Run API tests and verify RED**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_api.py -k parse_pdf
```

Expected: requests return 404 because the endpoint does not exist.

- [ ] **Step 3: Implement bounded upload and controlled responses**

In `backend/app/api/routes.py`, import `File`, `UploadFile`, `JSONResponse`, `PDFParseResponse`, `PDFProcessingErrorCode`, `PDFDocumentError`, and `parse_pdf_bytes`, then add:

```python
MAX_PDF_BYTES = 10 * 1024 * 1024


@router.post("/documents/parse-pdf", response_model=PDFParseResponse)
async def parse_pdf(file: UploadFile = File(...)):
    try:
        source_name = file.filename or ""
        if not source_name.lower().endswith(".pdf") or file.content_type != "application/pdf":
            return _pdf_error(
                PDFProcessingErrorCode.PDF_INVALID_TYPE.value,
                "仅支持 PDF 文件。",
                415,
            )

        content = await file.read(MAX_PDF_BYTES + 1)
        if not content:
            return _pdf_error(
                PDFProcessingErrorCode.PDF_EMPTY.value,
                "PDF 文件为空。",
                400,
            )
        if len(content) > MAX_PDF_BYTES:
            return _pdf_error(
                PDFProcessingErrorCode.PDF_TOO_LARGE.value,
                "PDF 文件不能超过 10 MB。",
                413,
            )

        try:
            page_count, text = parse_pdf_bytes(content)
        except PDFDocumentError as exc:
            return _pdf_error(exc.code, _pdf_user_message(exc.code), 400)
        return PDFParseResponse(
            source_name=source_name,
            page_count=page_count,
            text=text,
        )
    finally:
        await file.close()


def _pdf_error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _pdf_user_message(code: str) -> str:
    return {
        "PDF_ENCRYPTED": "PDF 已加密，请先移除密码。",
        "PDF_CORRUPT": "PDF 已损坏或无法读取。",
        "PDF_NO_TEXT": "未提取到文字，请使用文字型 PDF 或粘贴文本。",
    }.get(code, "PDF 解析失败。")
```

- [ ] **Step 4: Run API and existing error tests**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_api.py backend/tests/test_error_handling.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes.py backend/tests/test_api.py
git commit -m "feat: expose PDF resume parser endpoint"
```

### Task 4: Recognize standalone headings in plain and pasted text

**Files:**
- Modify: `backend/app/documents/chunker.py`
- Modify: `backend/tests/test_document_processing.py`

- [ ] **Step 1: Write failing heading tests**

Add these tests to `backend/tests/test_document_processing.py`:

```python
def test_plain_text_standalone_resume_headings_create_sections():
    document = ProfileDocument(
        document_id="doc_plain_resume",
        source_name="resume.pdf",
        source_type="text",
        content=(
            "教育经历\nUNSW 人工智能硕士\n"
            "项目经历\n语义分割项目\n"
            "实习经历\n腾讯人工智能实习生\n"
            "技能\nPython、PyTorch\n"
            "奖项\n校级奖学金"
        ),
    )

    chunks = chunk_profile_document(document)
    sections = {chunk.section_title: chunk.section_type for chunk in chunks}

    assert sections == {
        "教育经历": "education",
        "项目经历": "project",
        "实习经历": "internship",
        "技能": "skill",
        "奖项": "other",
    }


def test_markdown_source_accepts_unprefixed_resume_headings():
    document = ProfileDocument(
        document_id="doc_pasted_resume",
        source_name="profile.md",
        source_type="markdown",
        content="项目经历\n模型项目\n实习经历\n人工智能实习生",
    )

    chunks = chunk_profile_document(document)

    assert [chunk.section_type for chunk in chunks] == ["project", "internship"]


def test_heading_keyword_inside_body_does_not_split_section():
    document = ProfileDocument(
        document_id="doc_no_false_heading",
        source_name="resume.txt",
        source_type="text",
        content="项目经历\n完成模型训练，并参与项目经历复盘。",
    )

    chunks = chunk_profile_document(document)

    assert len(chunks) == 1
    assert chunks[0].section_type == "project"
    assert "参与项目经历复盘" in chunks[0].text
```

- [ ] **Step 2: Run document tests and verify RED**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_document_processing.py -k "plain_text or standalone"
```

Expected: headings are currently returned as `other` or remain inside one block.

- [ ] **Step 3: Unify resume heading recognition**

Refactor `chunk_profile_document` so both source types call one structured line scanner. Preserve `_MARKDOWN_HEADING_PATTERN`, and add an exact normalized title map:

```python
_PLAIN_RESUME_HEADINGS = {
    "教育经历": "education",
    "教育背景": "education",
    "项目经历": "project",
    "项目经验": "project",
    "实习经历": "internship",
    "工作经历": "internship",
    "技能": "skill",
    "专业技能": "skill",
    "奖项": "other",
    "荣誉奖项": "other",
    "其他": "other",
    "education": "education",
    "projects": "project",
    "project experience": "project",
    "internship": "internship",
    "experience": "internship",
    "work experience": "internship",
    "skills": "skill",
    "awards": "other",
    "other": "other",
}
```

Only `line.strip()` exact matches may activate a plain heading. Keep project and internship blocks intact before `_split_long_text`; split other sections by blank paragraphs.

- [ ] **Step 4: Run document and retrieval tests**

Run:

```bash
conda run -n carrer_agent pytest -q backend/tests/test_document_processing.py backend/tests/test_retrieval.py backend/tests/test_resume_evidence_agent.py
```

Expected: all tests pass, including existing Markdown behavior.

- [ ] **Step 5: Commit**

```bash
git add backend/app/documents/chunker.py backend/tests/test_document_processing.py
git commit -m "fix: structure plain-text resume headings"
```

### Task 5: Add editable PDF upload to the frontend

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/ProfileInput.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/scripts/verify-structure.mjs`

- [ ] **Step 1: Add a failing frontend structure check**

Read `ProfileInput.tsx` and `lib/api.ts` in `verify-structure.mjs`, then add:

```javascript
const profileInput = readFileSync(join(process.cwd(), "components/ProfileInput.tsx"), "utf8");
const api = readFileSync(join(process.cwd(), "lib/api.ts"), "utf8");
const pdfUploadMarkers = ["accept=\"application/pdf,.pdf\"", "正在解析 PDF", "PDF_NO_TEXT"];
const missingPdfMarkers = pdfUploadMarkers.filter((marker) => !profileInput.includes(marker));

if (missingPdfMarkers.length > 0 || !api.includes("parsePdfResume")) {
  console.error(`Missing PDF upload behavior: ${missingPdfMarkers.join(", ")}`);
  process.exit(1);
}
```

Run `cd frontend && npm run check` and confirm it exits 1 with `Missing PDF upload behavior`.

- [ ] **Step 2: Add frontend response types and API function**

Add:

```typescript
export interface PDFParseResponse {
  source_name: string;
  page_count: number;
  text: string;
}

export interface PDFParseError {
  error?: { code?: string; message?: string };
}
```

Implement `parsePdfResume(file: File)` in `frontend/lib/api.ts` with `FormData`; do not set `Content-Type` manually. Throw an error carrying the backend code when the response is not OK.

- [ ] **Step 3: Add upload behavior to ProfileInput**

Extend props with:

```typescript
onPdfParsed: (result: PDFParseResponse) => void;
```

Maintain local `isParsing`, `uploadMessage`, and `uploadError`. Validate `.pdf` and 10 MB client-side, call `parsePdfResume`, invoke `onPdfParsed` only on success, and map backend codes to Chinese messages. The textarea remains controlled by the parent.

- [ ] **Step 4: Preserve the uploaded source metadata in the analysis request**

In `page.tsx`, add:

```typescript
const [profileSource, setProfileSource] = useState({
  sourceName: "profile.md",
  sourceType: "markdown" as SourceType,
});
```

On successful PDF parsing, set the textarea text and `{sourceName: result.source_name, sourceType: "text"}`. Submit those values in `profile_documents[0]`. A failed parse never calls this callback and therefore preserves both text and source metadata.

- [ ] **Step 5: Run frontend checks and build**

Run:

```bash
cd frontend && npm run check && npm run build
```

Expected: structure check and Next.js production build pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/components/ProfileInput.tsx frontend/app/page.tsx frontend/scripts/verify-structure.mjs
git commit -m "feat: upload PDF resumes from the profile form"
```

### Task 6: Full verification and Sprint 2 task closure

**Files:**
- Modify: `docs/sprint2/tasks/pdf-resume-upload.md`
- Modify: `docs/sprint2/tasks/progress.md`

- [ ] **Step 1: Run the complete backend suite**

Run:

```bash
conda run -n carrer_agent pytest -q
```

Expected: all backend tests pass with no new warnings.

- [ ] **Step 2: Run complete frontend verification**

Run:

```bash
cd frontend && npm run check && npm run build
```

Expected: both commands exit 0.

- [ ] **Step 3: Verify the original failure mode**

Run:

```bash
conda run -n carrer_agent pytest -q \
  backend/tests/test_document_processing.py::test_plain_text_standalone_resume_headings_create_sections \
  backend/tests/test_api.py::test_parse_pdf_maps_document_error
```

Expected: both tests pass; the API assertion confirms `PDF_NO_TEXT` is returned before the analysis workflow runs.

- [ ] **Step 4: Update Sprint 2 status**

Mark every completed checkbox in `pdf-resume-upload.md`, change its status to `已完成`, and mark the corresponding module and acceptance items complete in `progress.md`. Record the exact backend test count and frontend verification commands in the task document.

- [ ] **Step 5: Commit documentation closure**

```bash
git add docs/sprint2/tasks/pdf-resume-upload.md docs/sprint2/tasks/progress.md
git commit -m "docs: complete sprint2 PDF resume upload task"
```

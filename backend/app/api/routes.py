from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from backend.app.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ModelListRequest,
    ModelListResponse,
    PDFParseResponse,
)
from backend.app.core.errors import PDFProcessingErrorCode
from backend.app.documents.pdf_parser import PDFDocumentError, parse_pdf_bytes
from backend.app.llm.model_catalog import ModelCatalogService
from backend.app.workflow import service


router = APIRouter()
MAX_PDF_BYTES = 10 * 1024 * 1024


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analysis", response_model=AnalysisResponse)
def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    return AnalysisResponse.model_validate(service.run_analysis(request))


@router.post("/models/list", response_model=ModelListResponse)
def list_models(request: ModelListRequest) -> ModelListResponse:
    try:
        return ModelCatalogService().list_models(request)
    except Exception:
        return ModelListResponse(
            models=[],
            warning="模型列表获取失败，请检查 API Key、Base URL 或手动输入模型名。",
        )


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
        PDFProcessingErrorCode.PDF_ENCRYPTED.value: "PDF 已加密，请先移除密码。",
        PDFProcessingErrorCode.PDF_CORRUPT.value: "PDF 已损坏或无法读取。",
        PDFProcessingErrorCode.PDF_NO_TEXT.value: (
            "未提取到文字，请使用文字型 PDF 或粘贴文本。"
        ),
    }.get(code, "PDF 解析失败。")

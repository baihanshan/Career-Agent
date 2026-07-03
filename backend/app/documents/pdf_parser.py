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

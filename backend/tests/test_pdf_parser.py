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

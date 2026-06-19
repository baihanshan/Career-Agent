import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


def valid_payload():
    return {
        "profile_documents": [
            {
                "source_name": "resume.md",
                "source_type": "markdown",
                "content": "Built a Python API for a course project.",
            }
        ],
        "job_description": "We need Python API experience.",
    }


def test_health_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_allows_local_frontend_cors_preflight():
    client = TestClient(create_app())

    response = client.options(
        "/analysis",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_analysis_rejects_empty_profile_documents():
    client = TestClient(create_app())
    payload = valid_payload()
    payload["profile_documents"] = []

    response = client.post("/analysis", json=payload)

    assert response.status_code == 422


def test_analysis_rejects_empty_job_description():
    client = TestClient(create_app())
    payload = valid_payload()
    payload["job_description"] = " "

    response = client.post("/analysis", json=payload)

    assert response.status_code == 422


def test_analysis_rejects_pdf_source_type_for_mvp():
    client = TestClient(create_app())
    payload = valid_payload()
    payload["profile_documents"][0]["source_name"] = "resume.pdf"
    payload["profile_documents"][0]["source_type"] = "pdf"

    response = client.post("/analysis", json=payload)

    assert response.status_code == 422


def test_analysis_calls_workflow_service(monkeypatch):
    from backend.app.workflow import service

    called = {}

    def fake_run_analysis(request):
        called["job_description"] = request.job_description
        return {
            "analysis_id": "analysis_test",
            "status": "completed",
            "result": {"mock": True},
        }

    monkeypatch.setattr(service, "run_analysis", fake_run_analysis)
    client = TestClient(create_app())

    response = client.post("/analysis", json=valid_payload())

    assert response.status_code == 200
    assert called["job_description"] == "We need Python API experience."
    assert response.json() == {
        "analysis_id": "analysis_test",
        "status": "completed",
        "result": {"mock": True},
        "error": None,
    }


def test_parse_pdf_returns_extracted_text(monkeypatch):
    from backend.app.api import routes

    monkeypatch.setattr(
        routes,
        "parse_pdf_bytes",
        lambda content: (2, "项目经历\n模型项目"),
    )
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

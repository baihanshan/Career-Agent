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


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3001"])
def test_allows_local_frontend_cors_preflight(origin):
    client = TestClient(create_app())

    response = client.options(
        "/analysis",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


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


def test_list_models_calls_model_catalog_service(monkeypatch):
    from backend.app.api import routes
    from backend.app.api.schemas import ModelListResponse, ModelOption

    called = {}

    class FakeCatalog:
        def list_models(self, request):
            called["request"] = request
            return ModelListResponse(models=[ModelOption(id="deepseek-chat")])

    monkeypatch.setattr(routes, "ModelCatalogService", FakeCatalog)
    client = TestClient(create_app())

    response = client.post(
        "/models/list",
        json={
            "provider": "deepseek",
            "api_key": "secret-key",
            "base_url": "https://api.deepseek.com",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "models": [{"id": "deepseek-chat", "owned_by": None}],
        "warning": None,
    }
    assert called["request"].provider == "deepseek"
    assert called["request"].api_key == "secret-key"


def test_list_models_returns_controlled_warning_without_echoing_api_key(monkeypatch):
    from backend.app.api import routes

    class FakeCatalog:
        def list_models(self, request):
            raise RuntimeError(f"provider rejected api key {request.api_key}")

    monkeypatch.setattr(routes, "ModelCatalogService", FakeCatalog)
    client = TestClient(create_app())

    response = client.post(
        "/models/list",
        json={
            "provider": "openai_compatible",
            "api_key": "secret-key",
            "base_url": "https://example.invalid/v1",
        },
    )

    serialized = response.text
    assert response.status_code == 200
    assert response.json() == {
        "models": [],
        "warning": "模型列表获取失败，请检查 API Key、Base URL 或手动输入模型名。",
    }
    assert "secret-key" not in serialized


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

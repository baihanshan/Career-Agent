import json

from fastapi.testclient import TestClient

from backend.app.api.schemas import AnalysisRequest
from backend.app.core.errors import AppError, ProcessingWarning
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import run_workflow
from backend.app.workflow.nodes import WorkflowServices


def test_app_error_and_processing_warning_models_are_serializable():
    error = AppError(code="VALIDATION_ERROR", message="输入内容不完整。")
    warning = ProcessingWarning(
        code="PROFILE_CONTENT_SHORT",
        message="个人材料较短，生成质量可能受限。",
        source="resume.md",
    )

    assert error.model_dump() == {
        "code": "VALIDATION_ERROR",
        "message": "输入内容不完整。",
        "details": None,
    }
    assert warning.model_dump() == {
        "code": "PROFILE_CONTENT_SHORT",
        "message": "个人材料较短，生成质量可能受限。",
        "source": "resume.md",
    }


def test_validation_error_returns_readable_message():
    from backend.app.main import create_app

    client = TestClient(create_app())

    response = client.post(
        "/analysis",
        json={"profile_documents": [], "job_description": " "},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "请检查输入内容" in response.json()["error"]["message"]


def test_vector_store_failure_returns_vector_store_error_code():
    response = run_workflow(
        request=_request(),
        services=WorkflowServices(
            retrieval_service=_FailingRetrievalService(),
            llm_service=LLMService(client=_StaticLLMClient()),
        ),
    )

    assert response.status == "failed"
    assert response.error == {
        "code": "VECTOR_STORE_ERROR",
        "message": "Profile materials could not be indexed. Please try again.",
        "details": None,
    }


def test_llm_parser_error_after_retry_returns_parse_error_code():
    response = run_workflow(
        request=_request(),
        services=WorkflowServices(
            retrieval_service=_retrieval_service(),
            llm_service=LLMService(client=_MalformedRequirementsLLMClient()),
        ),
    )

    assert response.status == "failed"
    assert response.error["code"] == "LLM_OUTPUT_PARSE_ERROR"
    assert response.error["message"] == "Job description could not be parsed into structured requirements."


def test_short_profile_material_generates_warning_without_blocking_workflow():
    request = AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="doc_short",
                source_name="short.md",
                source_type="markdown",
                content="Python API",
            )
        ],
        job_description="We need Python API experience.",
    )

    response = run_workflow(request=request, services=_services())

    assert response.status == "completed"
    assert response.result["processing_warnings"] == [
        {
            "code": "PROFILE_CONTENT_SHORT",
            "message": "Profile material is short; generated output may be less specific.",
            "source": "short.md",
        }
    ]


def test_weak_evidence_stays_in_evaluation_report_not_api_error():
    request = AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="doc_weak",
                source_name="weak.md",
                source_type="markdown",
                content="Built unrelated design workshops.",
            )
        ],
        job_description="We need Python API experience.",
    )

    response = run_workflow(request=request, services=_services())

    assert response.status == "completed"
    assert response.error is None
    assert response.result["evaluation_report"]["overall_status"] in {
        "pass_with_warnings",
        "fail",
    }


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="doc_resume",
                source_name="resume.md",
                source_type="markdown",
                content="## Projects\n\nBuilt Python API development with Python API services.",
            )
        ],
        job_description="We need Python API experience.",
    )


def _services() -> WorkflowServices:
    return WorkflowServices(
        retrieval_service=_retrieval_service(),
        llm_service=LLMService(client=_StaticLLMClient()),
    )


def _retrieval_service() -> RetrievalService:
    return RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )


class _FailingRetrievalService:
    def index_profile(self, chunks):
        raise RuntimeError("vector store unavailable")

    def retrieve_evidence(self, requirements, top_k):
        raise AssertionError("retrieve_evidence should not run after indexing failure")


class _MalformedRequirementsLLMClient:
    def generate(self, prompt_key, prompt, variables):
        if prompt_key == "extract_jd_requirements":
            return "{not json"
        raise AssertionError(f"Unexpected prompt key: {prompt_key}")


class _StaticLLMClient:
    def generate(self, prompt_key, prompt, variables):
        responses = {
            "extract_jd_requirements": [
                {
                    "requirement_id": "req_python",
                    "category": "hard_skill",
                    "text": "Python API development",
                    "importance": "high",
                    "keywords": ["Python", "API"],
                }
            ],
            "generate_application_assets": _assets_from_context(variables),
            "evaluate_claim_grounding": {
                "grounding_warnings": [],
                "coverage_gaps": [],
                "specificity_notes": ["Review weak evidence before using generated content."],
                "risk_summary": "Review warnings before using generated content.",
                "overall_status": "pass_with_warnings",
            },
        }
        return json.dumps(responses[prompt_key])


def _assets_from_context(variables):
    context = variables.get("context", {})
    evidence_ids = context.get("evidence_ids", [])
    first_evidence_id = evidence_ids[0] if evidence_ids else None
    bullet_evidence_ids = [first_evidence_id] if first_evidence_id else []
    return {
        "match_summary": "Generated summary based on evidence.",
        "resume_bullets": [
            {
                "text": "Built Python APIs backed by project evidence.",
                "target_requirement_ids": ["req_python"],
                "evidence_ids": bullet_evidence_ids,
                "risk_level": "low" if bullet_evidence_ids else "high",
            }
        ],
        "cover_letter": {
            "opening": "I am excited to apply.",
            "body": ["My background aligns with the role."],
            "closing": "Thank you for your consideration.",
            "evidence_ids": bullet_evidence_ids,
        },
        "interview_prep": [
            {
                "topic": "Evidence-backed discussion",
                "why_it_matters": "This connects background to role requirements.",
                "supporting_evidence_ids": bullet_evidence_ids,
                "prep_suggestion": "Prepare a concise walkthrough grounded in evidence.",
            }
        ],
    }

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.api.schemas import AnalysisRequest
from backend.app.core.errors import AppError, ProcessingWarning
from backend.app.core.errors import ReActErrorCode
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import run_workflow
from backend.app.workflow.nodes import WorkflowServices
from backend.app.workflow.resume_evidence_agent import ResumeEvidenceAgentError


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
                content="# 项目\nCareerPilot Python API",
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


def test_missing_resume_evidence_returns_user_friendly_retrieval_error():
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

    assert response.status == "failed"
    assert response.error["code"] == "REACT_QUALITY_GATE_FAILED"
    assert response.error["message"] == "Could not find usable resume evidence for this JD."


@pytest.mark.parametrize(
    "error_code",
    [
        ReActErrorCode.REACT_TOOL_CALL_ERROR.value,
        ReActErrorCode.REACT_OUTPUT_PARSE_ERROR.value,
        ReActErrorCode.REACT_QUALITY_GATE_FAILED.value,
        ReActErrorCode.REACT_EVIDENCE_VIOLATION.value,
    ],
)
def test_react_failures_preserve_stable_error_code_without_partial_result(error_code):
    services = _services()
    services.resume_evidence_agent = _FailingResumeEvidenceAgent(error_code)

    response = run_workflow(request=_request(), services=services)

    assert response.status == "failed"
    assert response.result is None
    assert response.error["code"] == error_code
    assert set(response.error) == {"code", "message"}


def test_react_output_parse_failure_reports_the_actual_failure_stage():
    services = _services()
    services.resume_evidence_agent = _FailingResumeEvidenceAgent(
        ReActErrorCode.REACT_OUTPUT_PARSE_ERROR.value
    )

    response = run_workflow(request=_request(), services=services)

    assert response.error == {
        "code": "REACT_OUTPUT_PARSE_ERROR",
        "message": "The model did not return valid structured output.",
    }


def test_unsupported_react_model_returns_stable_error(monkeypatch):
    from backend.app.llm.react_model import ReActModelUnavailableError
    from backend.app.workflow import service

    monkeypatch.setattr(
        service,
        "_default_services",
        lambda run_config: (_ for _ in ()).throw(
            ReActModelUnavailableError("Configured model cannot bind tools.")
        ),
    )

    response = service.run_analysis(_request())

    assert response["status"] == "failed"
    assert response["result"] is None
    assert response["error"] == {
        "code": "REACT_MODEL_UNAVAILABLE",
        "message": "The configured model cannot run tool-calling agents.",
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


class _FailingResumeEvidenceAgent:
    def __init__(self, code):
        self.code = code

    def run(self, state, retrieval_service):
        raise ResumeEvidenceAgentError(
            "Unsafe internal failure detail.",
            failed_tool="structured_tool",
            trace_summary="steps=1 tools=structured_tool statuses=error",
            code=self.code,
        )


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
                "text": f"Built Python APIs backed by project evidence {index}.",
                "target_requirement_ids": ["req_python"],
                "evidence_ids": bullet_evidence_ids,
                "risk_level": "low" if bullet_evidence_ids else "high",
            }
            for index in range(1, 4)
        ],
        "interview_prep": [
            {
                "topic": "Evidence-backed discussion",
                "why_it_matters": "This connects background to role requirements.",
                "supporting_evidence_ids": bullet_evidence_ids,
                "prep_suggestion": "Prepare a concise walkthrough grounded in evidence.",
            }
        ],
    }

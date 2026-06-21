import json
import logging

from fastapi.testclient import TestClient

from backend.app.api.schemas import AnalysisRequest
from backend.app.documents.models import ProfileDocument
from backend.app.main import create_app
from backend.app.workflow.graph import run_workflow
from backend.app.workflow.nodes import WorkflowServices
from backend.app.workflow.resume_evidence_agent import ResumeEvidenceAgentError
from backend.app.llm.client import LLMService
from backend.tests.test_workflow_integration import _request, _services


def test_cleanup_failure_logs_warning_without_overriding_success(caplog):
    services = _services()

    def failing_cleanup():
        raise RuntimeError("collection delete failed")

    services.retrieval_service.cleanup = failing_cleanup

    with caplog.at_level(logging.WARNING, logger="backend.app.workflow.graph"):
        response = run_workflow(request=_request(), services=services)

    assert response.status == "completed"
    assert "code=COLLECTION_CLEANUP_FAILED" in caplog.text
    assert "collection delete failed" in caplog.text


def test_agent_failure_response_has_no_partial_result_or_internal_details():
    response = run_workflow(request=_weak_request(), services=_services())
    serialized = json.dumps(response.model_dump(mode="json"))

    assert response.status == "failed"
    assert response.result is None
    assert set(response.error) == {"code", "message"}
    assert "Traceback" not in serialized
    assert "no usable evidence" not in serialized
    assert "SYSTEM_PROMPT_SECRET" not in serialized


def test_success_response_exposes_no_internal_reference_fields_or_values():
    response = run_workflow(request=_request(), services=_services())
    serialized = json.dumps(response.model_dump(mode="json"))

    assert response.status == "completed"
    for forbidden in (
        '"evidence_ids"',
        '"requirement_id"',
        '"chunk_id"',
        "req_python",
        "ev_",
        "chunk_",
    ):
        assert forbidden not in serialized


def test_agent_failure_log_contains_agent_tool_reason_and_trace_summary(caplog):
    with caplog.at_level(logging.ERROR, logger="backend.app.workflow.nodes"):
        response = run_workflow(request=_weak_request(), services=_services())

    assert response.status == "failed"
    assert "agent=resume_evidence_agent" in caplog.text
    assert "tool=quality_gate" in caplog.text
    assert "tools=search_resume_evidence" in caplog.text
    assert "reason=Resume Evidence Agent failed deterministic quality validation" in caplog.text
    assert "trace_summary=steps=3" in caplog.text
    assert "search_resume_evidence" in caplog.text


def test_validation_error_does_not_echo_api_key_or_internal_validation_details():
    client = TestClient(create_app())

    response = client.post(
        "/analysis",
        json={
            "profile_documents": [],
            "job_description": " ",
            "run_config": {
                "provider": "openai",
                "api_key": "super-secret-api-key",
            },
        },
    )
    payload = response.json()
    serialized = json.dumps(payload)

    assert response.status_code == 422
    assert set(payload["error"]) == {"code", "message"}
    assert "super-secret-api-key" not in serialized
    assert "errors" not in payload["error"]


def test_agent_log_redacts_api_key_prompt_hidden_reasoning_and_full_resume(caplog):
    request = _request(api_key="secret-agent-key")
    services = _services()
    services.resume_evidence_agent = _SensitiveFailingAgent(
        "secret-agent-key",
        request.profile_documents[0].content,
    )

    with caplog.at_level(logging.ERROR, logger="backend.app.workflow.nodes"):
        response = run_workflow(request=request, services=services)

    assert response.status == "failed"
    assert "secret-agent-key" not in caplog.text
    assert request.profile_documents[0].content not in caplog.text
    assert "SYSTEM_PROMPT_SECRET" not in caplog.text
    assert "hidden chain-of-thought" not in caplog.text


class _SensitiveFailingAgent:
    def __init__(self, api_key, resume):
        self.api_key = api_key
        self.resume = resume

    def run(self, state, retrieval_service):
        raise ResumeEvidenceAgentError(
            (
                f"{self.api_key} SYSTEM_PROMPT_SECRET hidden chain-of-thought "
                f"full resume: {self.resume}"
            ),
            failed_tool="sensitive_tool",
            trace_summary="steps=1 tools=sensitive_tool statuses=error",
            code="REACT_TOOL_CALL_ERROR",
        )


def _weak_request() -> AnalysisRequest:
    return AnalysisRequest(
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

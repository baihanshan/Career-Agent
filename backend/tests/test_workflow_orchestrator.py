import logging

import pytest

from backend.app.api.schemas import AnalysisRequest
from backend.app.core.errors import WorkflowErrorCode
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import WORKFLOW_NODE_ORDER, run_workflow
from backend.app.workflow.nodes import WorkflowServices
from backend.tests.test_error_handling import _StaticLLMClient
from backend.tests.test_workflow_integration import _request, _services


def test_sprint2_workflow_uses_fixed_agent_order():
    assert WORKFLOW_NODE_ORDER == [
        "parse_inputs",
        "index_profile",
        "jd_analyst",
        "resume_evidence_agent",
        "match_strategist",
        "resume_bullet_agent",
        "interview_prep_agent",
        "risk_auditor_agent",
        "finalize_response",
    ]


def test_successful_workflow_returns_all_sprint2_modules():
    response = run_workflow(request=_request(), services=_services())

    assert response.status == "completed"
    assert response.result["match_analysis"]
    assert "match_strategy" not in response.result
    assert len(response.result["generated_assets"]["resume_bullets"]) == 3
    assert response.result["generated_assets"]["interview_prep"]["jd_questions"]
    assert response.result["risk_report"] is not None
    assert {trace["agent_name"] for trace in response.result["agent_traces"]} == {
        "resume_evidence",
        "interview_prep",
        "risk_auditor",
    }
    assert "cover_letter" not in response.result["generated_assets"]


def test_workflow_error_codes_include_each_sprint2_agent():
    assert {
        WorkflowErrorCode.JD_ANALYST_ERROR.value,
        WorkflowErrorCode.RESUME_EVIDENCE_AGENT_ERROR.value,
        WorkflowErrorCode.MATCH_STRATEGIST_ERROR.value,
        WorkflowErrorCode.RESUME_BULLET_AGENT_ERROR.value,
        WorkflowErrorCode.INTERVIEW_PREP_AGENT_ERROR.value,
        WorkflowErrorCode.RISK_AUDITOR_AGENT_ERROR.value,
    } <= {item.value for item in WorkflowErrorCode}


def test_resume_evidence_agent_failure_stops_workflow_logs_reason_and_cleans_collection(
    caplog,
):
    services = WorkflowServices(
        retrieval_service=RetrievalService(
            embedding_client=FakeEmbeddingClient(),
            vector_store=InMemoryVectorStore(),
        ),
        llm_service=LLMService(client=_StaticLLMClient()),
    )
    request = AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="doc_weak",
                source_name="weak.md",
                source_type="markdown",
                content="Unrelated design workshop notes.",
            )
        ],
        job_description="We need Python API experience.",
    )

    with caplog.at_level(logging.ERROR, logger="backend.app.workflow.nodes"):
        response = run_workflow(request=request, services=services)

    assert response.status == "failed"
    assert response.error["code"] == "RESUME_EVIDENCE_AGENT_ERROR"
    assert response.error["message"] == "Could not find usable resume evidence for this JD."
    assert "resume_evidence_agent" in caplog.text
    assert "tool=quality_gate" in caplog.text
    assert "tools=search_resume_evidence" in caplog.text
    assert services.retrieval_service.vector_store.items == []


def test_cleanup_runs_when_graph_construction_fails(monkeypatch):
    retrieval_service = _CleanupTracker()
    services = WorkflowServices(
        retrieval_service=retrieval_service,
        llm_service=LLMService(client=_StaticLLMClient()),
    )

    monkeypatch.setattr(
        "backend.app.workflow.graph.build_analysis_graph",
        lambda services: (_ for _ in ()).throw(RuntimeError("graph build failed")),
    )

    with pytest.raises(RuntimeError, match="graph build failed"):
        run_workflow(request=_request(), services=services)

    assert retrieval_service.cleaned is True


class _CleanupTracker:
    def __init__(self):
        self.cleaned = False

    def cleanup(self):
        self.cleaned = True

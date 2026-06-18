import pytest

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.llm.client import LLMService
from backend.app.workflow.nodes import WorkflowServices, finalize_response, parse_inputs, retrieve_evidence
from backend.app.workflow.resume_evidence_agent import (
    RESUME_EVIDENCE_AGENT_PROMPT,
    ResumeEvidenceAgent,
    ResumeEvidenceAgentError,
    create_resume_evidence_react_agent,
)
from backend.tests.test_workflow_nodes import _request


def test_resume_evidence_agent_retries_project_search_after_skill_only_hit():
    service = _ScriptedRetrievalService(
        [
            [_evidence("ev_skill", "skill", 0.95)],
            [_evidence("ev_project", "project", 0.72)],
        ]
    )
    state = parse_inputs(_request()).model_copy(
        update={"jd_requirements": [_requirement()]}
    )

    next_state = ResumeEvidenceAgent().run(state, service)

    assert service.section_filters == [None, ["project", "internship"]]
    assert [item.evidence_id for item in next_state.retrieved_evidence] == [
        "ev_project",
        "ev_skill",
    ]
    assert next_state.agent_traces[0].agent_name == "resume_evidence"
    assert [step.tool_name for step in next_state.agent_traces[0].steps] == [
        "search_resume_evidence",
        "search_resume_evidence",
        "rerank_evidence",
    ]


def test_resume_evidence_agent_ranks_project_evidence_above_skill_evidence():
    service = _ScriptedRetrievalService(
        [[_evidence("ev_skill", "skill", 0.99), _evidence("ev_project", "project", 0.5)]]
    )
    state = parse_inputs(_request()).model_copy(
        update={"jd_requirements": [_requirement()]}
    )

    next_state = ResumeEvidenceAgent().run(state, service)

    assert [item.evidence_id for item in next_state.retrieved_evidence] == [
        "ev_project",
        "ev_skill",
    ]


def test_resume_evidence_agent_fails_after_three_empty_tool_steps():
    service = _ScriptedRetrievalService([[], [], []])
    state = parse_inputs(_request()).model_copy(
        update={"jd_requirements": [_requirement()]}
    )

    with pytest.raises(ResumeEvidenceAgentError) as exc_info:
        ResumeEvidenceAgent().run(state, service)

    assert service.call_count == 3
    assert "no usable evidence" in str(exc_info.value)


def test_retrieve_evidence_node_returns_friendly_error_when_agent_fails():
    services = WorkflowServices(
        retrieval_service=_ScriptedRetrievalService([[], [], []]),
        llm_service=LLMService(client=_UnusedLLMClient()),
    )
    state = parse_inputs(_request()).model_copy(
        update={"jd_requirements": [_requirement()]}
    )

    failed_state = retrieve_evidence(state, services)
    response = finalize_response(failed_state)

    assert response.status == "failed"
    assert response.error["code"] == "RESUME_EVIDENCE_AGENT_ERROR"
    assert response.error["message"] == "Could not find usable resume evidence for this JD."
    assert set(response.error) == {"code", "message"}


def test_resume_evidence_react_agent_uses_langgraph_create_react_agent(monkeypatch):
    calls = []

    def fake_create_react_agent(*, model, tools, prompt):
        calls.append({"model": model, "tools": tools, "prompt": prompt})
        return "compiled-agent"

    monkeypatch.setattr(
        "backend.app.workflow.resume_evidence_agent.create_react_agent",
        fake_create_react_agent,
    )

    agent = create_resume_evidence_react_agent(model="model", tools=["tool"])

    assert agent == "compiled-agent"
    assert calls[0]["tools"] == ["tool"]
    assert "project/internship" in calls[0]["prompt"]
    assert RESUME_EVIDENCE_AGENT_PROMPT == calls[0]["prompt"]


def _requirement() -> JDRequirement:
    return JDRequirement(
        requirement_id="req_python",
        category="hard_skill",
        text="Python API development",
        importance="high",
        keywords=["Python", "API"],
    )


def _evidence(evidence_id: str, section_type: str, score: float) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id="req_python",
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.md",
        section_label=section_type.title(),
        section_type=section_type,
        snippet=f"{section_type} evidence about Python API.",
        score=score,
    )


class _ScriptedRetrievalService:
    def __init__(self, responses: list[list[EvidenceItem]]) -> None:
        self.responses = responses
        self.call_count = 0
        self.section_filters = []

    def retrieve_evidence(self, requirements, top_k, section_filter=None):
        self.call_count += 1
        self.section_filters.append(section_filter)
        index = min(self.call_count - 1, len(self.responses) - 1)
        return self.responses[index]


class _UnusedLLMClient:
    def generate(self, prompt_key, prompt, variables):
        raise AssertionError("LLM should not be called in resume evidence tests")

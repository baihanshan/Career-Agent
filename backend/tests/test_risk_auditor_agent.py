import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import Field

from backend.app.api.schemas import (
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    InterviewPrep,
    JDRequirement,
    ResumeBullet,
)
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.workflow.domain_models import EvidenceSelection, ExperienceRecord
from backend.app.workflow.nodes import WorkflowServices, audit_risks, finalize_response
from backend.app.workflow.risk_auditor_agent import (
    RISK_AUDITOR_AGENT_PROMPT,
    RiskAuditorAgent,
    RiskAuditorAgentError,
    create_risk_auditor_react_agent,
)
from backend.app.workflow.state import AnalysisState


def test_multiple_python_projects_with_indirect_support_reject_missing_risk():
    state = _state(
        requirements=[_requirement("req_python", "扎实的 Python 编程基础")],
        evidence=[
            _evidence("ev_api", "req_python", "Built a Python API."),
            _evidence("ev_nlp", "req_python", "Built an NLP classifier in Python."),
        ],
        selections=[_selection("req_python", ["ev_api", "ev_nlp"], "strong", ["indirect"])],
    )
    result, model = _run_invalid_missing_then_empty(state, "req_python")

    assert result.internal_risk_report.risks == []
    assert _retry_contains(model, "RISK_CONTRADICTS_EVIDENCE")


@pytest.mark.parametrize(
    ("requirement_id", "requirement_text", "snippet"),
    [
        ("req_cv", "机器学习或计算机视觉经验", "DeepLabV3+ semantic segmentation project."),
        ("req_nlp", "自然语言处理经验", "Built an NLP classifier and RAG retrieval system."),
        ("req_multimodal", "多模态领域经验", "Evaluated image-to-text models in a multimodal team."),
    ],
)
def test_domain_experience_rejects_false_missing_risk(
    requirement_id,
    requirement_text,
    snippet,
):
    state = _state(
        requirements=[_requirement(requirement_id, requirement_text)],
        evidence=[_evidence("ev_domain", requirement_id, snippet)],
        selections=[_selection(requirement_id, ["ev_domain"], "strong", ["direct"])],
    )
    result, _ = _run_invalid_missing_then_empty(state, requirement_id)

    assert result.internal_risk_report.risks == []


def test_or_requirement_satisfied_by_one_branch_rejects_overall_missing_risk():
    requirement = _requirement(
        "req_domain",
        "掌握 NLP 或多模态至少一个领域",
    ).model_copy(
        update={
            "logical_operator": "OR",
            "alternatives": ["NLP", "多模态"],
        }
    )
    state = _state(
        requirements=[requirement],
        evidence=[_evidence("ev_nlp", "req_domain", "Built an NLP and RAG system.")],
        selections=[_selection("req_domain", ["ev_nlp"], "strong", ["direct"])],
    )
    result, model = _run_invalid_missing_then_empty(state, "req_domain")

    assert result.internal_risk_report.risks == []
    assert _retry_contains(model, "RISK_CONTRADICTS_EVIDENCE")


def test_strong_resume_evidence_not_selected_for_bullets_is_not_ability_gap():
    state = _state(
        requirements=[_requirement("req_python", "Python 编程能力")],
        evidence=[_evidence("ev_python", "req_python", "Built Python services.")],
        selections=[_selection("req_python", ["ev_python"], "strong", ["direct"])],
        bullet_requirement_ids=["req_other"],
    )
    result, model = _run_invalid_missing_then_empty(state, "req_python")

    assert result.internal_risk_report.risks == []
    assert any(
        step.tool_name == "get_resume_bullet_coverage"
        for step in result.agent_traces[-1].steps
    )
    assert _retry_contains(model, "RISK_CONTRADICTS_EVIDENCE")


def test_no_real_risk_allows_empty_list_without_manufacturing_three_items():
    model = _fake_model([_inspection_calls("req_python"), _final({"risks": []})])
    state = _state(
        selections=[_selection("req_python", ["ev_project"], "strong", ["direct"])],
    )

    result = RiskAuditorAgent(model=model).run(state)

    assert result.internal_risk_report.risks == []
    assert result.risk_report.risks == []
    assert len(model.invocations) == 2


def test_internal_evidence_ids_are_allowlisted_and_removed_from_public_risk():
    model = _fake_model(
        [_inspection_calls("req_python"), _final(_fixture("valid_evidence_risk"))]
    )
    state = _state(
        selections=[_selection("req_python", ["ev_project"], "weak", ["insufficient"])],
    )

    result = RiskAuditorAgent(model=model).run(state)
    response = finalize_response(result)
    rendered = json.dumps(response.result["risk_report"], ensure_ascii=False)

    assert result.internal_risk_report.risks[0].internal_supporting_evidence_ids == [
        "ev_project"
    ]
    assert "ev_project" not in rendered
    assert "req_python" not in rendered
    assert response.result["risk_report"]["risks"][0]["title"] == "工程规模证据仍不充分"


@pytest.mark.parametrize("invalid_fixture", ["unknown_evidence", "leaked_id"])
def test_unknown_evidence_or_visible_id_gets_feedback_retry(invalid_fixture):
    model = _fake_model(
        [
            _inspection_calls("req_python"),
            _final(_fixture(invalid_fixture)),
            _inspection_calls("req_python"),
            _final({"risks": []}),
        ]
    )
    state = _state(
        selections=[_selection("req_python", ["ev_project"], "strong", ["direct"])],
    )

    result = RiskAuditorAgent(model=model).run(state)

    assert result.internal_risk_report.risks == []
    retry_prompts = _retry_prompts(model)
    assert retry_prompts
    feedback = retry_prompts[0].split("Previous output failed validation.", 1)[1]
    assert "ev_unknown" not in feedback
    assert "req_python" not in feedback


def test_three_invalid_attempts_return_controlled_error():
    responses = []
    for _ in range(3):
        responses.extend(
            [_inspection_calls("req_python"), _final(_fixture("leaked_id"))]
        )
    model = _fake_model(responses)

    with pytest.raises(RiskAuditorAgentError, match="3 attempts") as exc_info:
        RiskAuditorAgent(model=model).run(_state())

    assert "req_python" not in str(exc_info.value)


def test_audit_risks_node_uses_runtime_react_model():
    model = _fake_model([_inspection_calls("req_python"), _final({"risks": []})])
    services = WorkflowServices(
        retrieval_service=object(),
        llm_service=LLMService(client=_UnusedLLMClient()),
        react_model=model,
    )
    state = _state(
        selections=[_selection("req_python", ["ev_project"], "strong", ["direct"])],
    )

    response = finalize_response(audit_risks(state, services))

    assert response.status == "completed"
    assert model.invocations


def test_factory_uses_langgraph_create_react_agent(monkeypatch):
    calls = []

    def fake_create_react_agent(*, model, tools, prompt, name):
        calls.append({"model": model, "tools": tools, "prompt": prompt, "name": name})
        return "compiled-agent"

    monkeypatch.setattr(
        "backend.app.workflow.risk_auditor_agent.create_react_agent",
        fake_create_react_agent,
    )

    agent = create_risk_auditor_react_agent(model="model", tools=["tool"])

    assert agent == "compiled-agent"
    assert calls[0]["tools"] == ["tool"]
    assert calls[0]["name"] == "risk_auditor"
    assert "resume coverage" in calls[0]["prompt"].lower()
    assert RISK_AUDITOR_AGENT_PROMPT == calls[0]["prompt"]


class _ToolCallingFakeModel(FakeMessagesListChatModel):
    invocations: list[list[object]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.invocations.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _run_invalid_missing_then_empty(state, requirement_id):
    model = _fake_model(
        [
            _inspection_calls(requirement_id),
            _final(_fixture("false_missing", requirement_id=requirement_id)),
            _inspection_calls(requirement_id),
            _final({"risks": []}),
        ]
    )
    return RiskAuditorAgent(model=model).run(state), model


def _inspection_calls(requirement_id):
    return AIMessage(
        content="",
        tool_calls=[
            _call("get_requirement", {"requirement_id": requirement_id}, "requirement"),
            _call(
                "get_requirement_evidence",
                {"requirement_id": requirement_id},
                "evidence",
            ),
            _call(
                "compare_capability_semantics",
                {"requirement_id": requirement_id},
                "semantics",
            ),
            _call("inspect_experience", {"experience_id": "exp_project"}, "experience"),
            _call("get_resume_bullet_coverage", {}, "bullet_coverage"),
            _call(
                "check_public_claim_grounding",
                {"claim": "Candidate public claim."},
                "grounding",
            ),
            _call(
                "classify_numeric_claim",
                {"claim": "Improved accuracy by 17%."},
                "numeric",
            ),
            _call("rank_candidate_risks", {"risks": [], "limit": 3}, "ranking"),
        ],
    )


def _call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def _fake_model(responses):
    return _ToolCallingFakeModel(responses=responses)


def _final(payload):
    return AIMessage(content=json.dumps(payload, ensure_ascii=False))


def _fixture(name, **replacements):
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "risk_auditor_react_calls.json").read_text(
            encoding="utf-8"
        )
    )[name]
    rendered = json.dumps(payload, ensure_ascii=False)
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return json.loads(rendered)


def _retry_prompts(model):
    return [
        message.content
        for invocation in model.invocations
        for message in invocation
        if getattr(message, "type", "") == "human" and "Previous output" in message.content
    ]


def _retry_contains(model, code):
    return any(code in prompt for prompt in _retry_prompts(model))


def _state(
    requirements=None,
    evidence=None,
    selections=None,
    bullet_requirement_ids=None,
):
    requirements = requirements or [_requirement("req_python", "Python API engineering")]
    evidence = evidence or [
        _evidence("ev_project", requirements[0].requirement_id, "Built a Python API.")
    ]
    selections = selections or [
        _selection(requirements[0].requirement_id, [evidence[0].evidence_id], "weak", ["insufficient"])
    ]
    bullet_requirement_ids = bullet_requirement_ids or [requirements[0].requirement_id]
    assets = GeneratedAssets(
        match_summary="Evidence-backed match summary.",
        resume_bullets=[
            ResumeBullet(
                text=f"Built an evidence-backed service component {index}.",
                target_requirement_ids=bullet_requirement_ids,
                evidence_ids=[evidence[0].evidence_id],
                risk_level="low",
            )
            for index in range(3)
        ],
        interview_prep=InterviewPrep(),
    )
    return AnalysisState(
        analysis_id="analysis_risk",
        profile_documents=[
            ProfileDocument(
                source_name="resume.pdf",
                source_type="text",
                content="Structured resume fixture for risk auditing.",
            )
        ],
        job_description="Applied AI role",
        jd_requirements=requirements,
        retrieved_evidence=evidence,
        evidence_selections=selections,
        allowed_evidence_ids={item.evidence_id for item in evidence},
        experience_records=[_experience()],
        generated_assets=assets,
        evaluation_report=EvaluationReport(
            grounding_warnings=[],
            coverage_gaps=[],
            specificity_notes=[],
            risk_summary="No deterministic grounding risk.",
            overall_status="pass",
        ),
    )


def _requirement(requirement_id, text):
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text=text,
        importance="high",
        keywords=text.split(),
        capability_tags=["applied_ai"],
        verification_mode="evidence_check",
    )


def _evidence(evidence_id, requirement_id, snippet):
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.pdf",
        section_type="project",
        snippet=snippet,
        score=0.9,
    )


def _selection(requirement_id, evidence_ids, level, support_types):
    return EvidenceSelection(
        requirement_id=requirement_id,
        selected_evidence_ids=evidence_ids,
        support_level=level,
        support_types=support_types,
        rationale="The evidence was semantically evaluated for this requirement.",
    )


def _experience():
    return ExperienceRecord(
        experience_id="exp_project",
        experience_type="project",
        name="CareerPilot",
        responsibilities=["Built an applied AI workflow."],
        technologies=["Python"],
        outcomes=["Delivered a working system."],
        raw_source_chunk_ids=["chunk_ev_project"],
        raw_text="Built an applied AI workflow in Python.",
    )


class _UnusedLLMClient:
    def generate(self, prompt_key, prompt, variables):
        raise AssertionError("One-shot LLMService must not generate risk audit output.")

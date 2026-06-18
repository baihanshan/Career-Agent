import pytest

from backend.app.api.schemas import (
    CoverageGap,
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    GroundingWarning,
    InterviewPrep,
    JDRequirement,
    ResumeBullet,
    RiskItem,
    RiskReport,
)
from backend.app.llm.client import LLMService
from backend.app.workflow.nodes import (
    WorkflowServices,
    audit_risks,
    finalize_response,
    parse_inputs,
)
from backend.app.workflow.risk_auditor_agent import (
    RISK_AUDITOR_AGENT_PROMPT,
    RiskAuditorAgent,
    RiskAuditorAgentError,
    create_risk_auditor_react_agent,
)
from backend.tests.test_workflow_nodes import _request


def test_risk_auditor_hides_internal_requirement_and_evidence_ids():
    state = _state(
        requirements=[_requirement("req_python", "Python API development", "high")],
        evidence=[_evidence("ev_project", "project")],
        report=_report(
            coverage_gaps=[
                CoverageGap(
                    requirement_id="req_python",
                    requirement_text="Python API development",
                    reason="req_python is not covered by ev_project.",
                    severity="high",
                )
            ]
        ),
    )

    next_state = RiskAuditorAgent().run(state)

    rendered = " ".join(
        str(value)
        for risk in next_state.risk_report.risks
        for value in risk.model_dump().values()
    )
    assert "req_python" not in rendered
    assert "ev_project" not in rendered
    assert "Python API development" in rendered


def test_risk_auditor_treats_skill_only_match_as_uncovered():
    state = _state(
        requirements=[_requirement("req_python", "Python API development", "high")],
        evidence=[_evidence("ev_skill", "skill")],
        report=_report(),
    )

    next_state = RiskAuditorAgent().run(state)

    assert next_state.risk_report.risks[0].risk_type == "JD 未覆盖"
    assert "项目或实习" in next_state.risk_report.risks[0].resume_current_state


def test_risk_auditor_deduplicates_repeated_generic_risks():
    duplicate = _risk("简历表述太泛", "项目描述过于笼统", "medium", "Python API")

    next_state = RiskAuditorAgent(
        risk_generator=lambda state: RiskReport(risks=[duplicate, duplicate])
    ).run(_state(report=_report(specificity_notes=["项目描述过于笼统"])))

    assert len(next_state.risk_report.risks) == 1


def test_risk_auditor_sorts_by_severity_then_jd_importance_and_limits_to_three():
    risks = [
        _risk("证据不足", "Low impact", "medium", "Optional tooling"),
        _risk("JD 未覆盖", "High impact", "medium", "Python API"),
        _risk("生成内容可能夸大", "Unsupported number", "high", "Metrics"),
        _risk("简历表述太泛", "Generic wording", "low", "Communication"),
    ]
    state = _state(
        requirements=[
            _requirement("req_python", "Python API", "high"),
            _requirement("req_optional", "Optional tooling", "low"),
        ],
        report=_report(coverage_gaps=[_gap()]),
    )

    next_state = RiskAuditorAgent(
        risk_generator=lambda state: RiskReport(risks=risks[:3])
    ).run(state)

    assert [item.title for item in next_state.risk_report.risks] == [
        "Unsupported number",
        "High impact",
        "Low impact",
    ]
    assert len(next_state.risk_report.risks) == 3


def test_risk_auditor_ranks_all_candidates_before_limiting_to_three():
    requirements = [
        _requirement(f"req_optional_{index}", f"Optional requirement {index}", "medium")
        for index in range(3)
    ]
    gaps = [
        CoverageGap(
            requirement_id=requirement.requirement_id,
            requirement_text=requirement.text,
            reason="Requirement is not covered.",
            severity="medium",
        )
        for requirement in requirements
    ]
    report = _report(coverage_gaps=gaps).model_copy(
        update={
            "grounding_warnings": [
                GroundingWarning(
                    asset_type="resume_bullet",
                    asset_id="resume_bullet:1",
                    claim="Improved throughput by 90%.",
                    reason="数字 90 没有出现在引用的证据中。",
                    severity="high",
                )
            ]
        }
    )

    next_state = RiskAuditorAgent().run(
        _state(requirements=requirements, report=report)
    )

    assert next_state.risk_report.risks[0].risk_type == "生成内容可能夸大"
    assert len(next_state.risk_report.risks) == 3


def test_risk_auditor_fails_after_three_invalid_attempts():
    attempts = []

    def invalid_generator(state):
        attempts.append(state.analysis_id)
        return RiskReport()

    with pytest.raises(RiskAuditorAgentError, match="3 attempts"):
        RiskAuditorAgent(risk_generator=invalid_generator).run(
            _state(report=_report(coverage_gaps=[_gap()]))
        )

    assert len(attempts) == 3


def test_audit_risks_node_returns_friendly_error_after_agent_failure():
    services = WorkflowServices(
        retrieval_service=object(),
        llm_service=LLMService(client=_UnusedLLMClient()),
        risk_auditor_agent=RiskAuditorAgent(
            risk_generator=lambda state: RiskReport()
        ),
    )
    failed_state = audit_risks(
        _state(report=_report(coverage_gaps=[_gap()])),
        services,
    )

    response = finalize_response(failed_state)

    assert response.status == "failed"
    assert response.error["code"] == "EVALUATION_ERROR"
    assert response.error["message"] == "Risk audit could not be completed safely."
    assert "3 attempts" in response.error["details"]["reason"]


def test_risk_auditor_react_agent_uses_only_allowed_tools(monkeypatch):
    calls = []

    def fake_create_react_agent(*, model, tools, prompt):
        calls.append({"model": model, "tools": tools, "prompt": prompt})
        return "compiled-agent"

    monkeypatch.setattr(
        "backend.app.workflow.risk_auditor_agent.create_react_agent",
        fake_create_react_agent,
    )
    tools = {
        "check_requirement_coverage": object(),
        "find_resume_vague_claims": object(),
        "check_generated_claim_grounding": object(),
        "rank_top_risks": object(),
    }

    agent = create_risk_auditor_react_agent(model="model", tools=tools)

    assert agent == "compiled-agent"
    assert set(calls[0]["tools"]) == set(tools.values())
    assert "project and internship" in calls[0]["prompt"].lower()
    assert "internal requirement ids" in calls[0]["prompt"].lower()
    assert RISK_AUDITOR_AGENT_PROMPT == calls[0]["prompt"]


def _state(requirements=None, evidence=None, report=None):
    requirements = requirements or [_requirement("req_python", "Python API", "high")]
    evidence = evidence or [_evidence("ev_project", "project")]
    assets = GeneratedAssets(
        match_summary="Evidence-backed match.",
        resume_bullets=[
            ResumeBullet(
                text=f"Built a FastAPI service with project evidence {index}.",
                target_requirement_ids=[requirements[0].requirement_id],
                evidence_ids=[evidence[0].evidence_id],
                risk_level="low",
            )
            for index in range(3)
        ],
        interview_prep=InterviewPrep(),
    )
    return parse_inputs(_request()).model_copy(
        update={
            "jd_requirements": requirements,
            "retrieved_evidence": evidence,
            "generated_assets": assets,
            "evaluation_report": report or _report(),
        }
    )


def _requirement(requirement_id: str, text: str, importance: str) -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text=text,
        importance=importance,
        keywords=text.split(),
    )


def _evidence(evidence_id: str, section_type: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id="req_python",
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.md",
        section_label=section_type.title(),
        section_type=section_type,
        snippet="Built a Python API for CareerPilot.",
        score=0.9,
    )


def _report(coverage_gaps=None, specificity_notes=None) -> EvaluationReport:
    return EvaluationReport(
        grounding_warnings=[],
        coverage_gaps=coverage_gaps or [],
        specificity_notes=specificity_notes or [],
        risk_summary="Review risks.",
        overall_status="pass_with_warnings" if coverage_gaps or specificity_notes else "pass",
    )


def _gap() -> CoverageGap:
    return CoverageGap(
        requirement_id="req_python",
        requirement_text="Python API",
        reason="High-priority requirement is uncovered.",
        severity="high",
    )


def _risk(risk_type: str, title: str, severity: str, requirement: str) -> RiskItem:
    return RiskItem(
        risk_type=risk_type,
        title=title,
        jd_requirement_summary=requirement,
        resume_current_state="Current resume evidence is incomplete.",
        risk_reason="The claim may not convince an interviewer.",
        recommendation="Add a concrete project example and verified outcome.",
        severity=severity,
    )


class _UnusedLLMClient:
    def generate(self, prompt_key, prompt, variables):
        raise AssertionError("LLM should not be called in risk auditor tests")

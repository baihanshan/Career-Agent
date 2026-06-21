import json

import pytest

from backend.app.api.schemas import (
    AgentToolResult,
    AgentTrace,
    EvaluationReport,
    GeneratedAssets,
    GroundingWarning,
    InterviewPrep,
    InterviewPrepQuestion,
    JDRequirement,
    MatchItem,
    ResumeBullet,
)
from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.workflow.domain_models import InternalRiskItem, InternalRiskReport
from backend.app.workflow.nodes import (
    WorkflowServices,
    finalize_response,
    public_output_gate,
)
from backend.app.workflow.public_output import (
    InternalIdLeakDetector,
    PublicOutputValidationError,
    project_public_result,
)
from backend.app.workflow.state import AnalysisState


@pytest.mark.parametrize(
    "polluted_text",
    [
        'Improved quality. (evidence_ids: ["req_3:evidence:2"])',
        "Supports req_python_api.",
        "See ev_project_1 for details.",
        "Copied from chunk_project_1.",
        "supporting_evidence_ids: []",
        "requirement_ids=[]",
    ],
)
def test_internal_id_detector_reports_public_text_field_path(polluted_text):
    leaks = InternalIdLeakDetector().find_leaks(
        {"generated_assets": {"resume_bullets": [{"text": polluted_text}]}}
    )

    assert leaks == ["generated_assets.resume_bullets.0.text"]


def test_internal_id_detector_allows_technology_dates_and_metrics():
    payload = {
        "text": (
            "使用 DeepLabV3+ 在 2024 年 2 月至 6 月完成实验，"
            "平均 IoU 提升 17%，Python 3 用于实验平台。"
        )
    }

    assert InternalIdLeakDetector().find_leaks(payload) == []


def test_public_projection_drops_internal_interview_bullet_and_risk_ids():
    state = _complete_state()

    result = project_public_result(state)
    serialized = result.model_dump(mode="json")
    serialized_text = json.dumps(serialized, ensure_ascii=False)

    bullet = serialized["generated_assets"]["resume_bullets"][0]
    question = serialized["generated_assets"]["interview_prep"]["jd_questions"][0]
    risk = serialized["risk_report"]["risks"][0]
    assert bullet == {"text": "Built a Python API and evaluated reliability.", "risk_level": "low"}
    assert question == {
        "question": "How would you design a reliable API?",
        "sample_answer": "I would define failure modes, metrics, and recovery paths.",
    }
    assert "internal_supporting_evidence_ids" not in risk
    assert "requirement_ids" not in risk
    assert "evidence_ids" not in serialized_text
    assert "requirement_id" not in serialized_text
    assert "chunk_id" not in serialized_text


def test_project_public_result_rejects_leak_with_structured_quality_issue():
    state = _complete_state()
    state.generated_assets.resume_bullets[0].text += ' (evidence_ids: ["ev_project"])'

    with pytest.raises(PublicOutputValidationError) as exc_info:
        project_public_result(state)

    issue = exc_info.value.issues[0]
    assert issue.code == "INTERNAL_ID_LEAK"
    assert issue.field_path == "generated_assets.resume_bullets.0.text"
    assert issue.severity == "high"
    assert "ev_project" not in issue.message


def test_finalize_response_serializes_only_public_projection():
    state = _complete_state()

    response = finalize_response(public_output_gate(state, _gate_services()))
    serialized = response.model_dump(mode="json")
    result = serialized["result"]

    assert response.status == "completed"
    assert "profile_chunks" not in result
    assert "match_strategy" not in result
    assert set(result["jd_requirements"][0]) == {
        "category",
        "text",
        "importance",
        "capability_tags",
        "verification_mode",
        "interviewability",
        "question_focus",
        "logical_operator",
        "alternatives",
    }
    assert set(result["match_analysis"][0]) == {
        "requirement_text",
        "match_level",
        "rationale",
        "gap_note",
    }
    assert "ev_project" not in json.dumps(result)
    assert "req_python" not in json.dumps(result)
    assert "chunk_project" not in json.dumps(result)


def test_finalize_response_returns_controlled_failure_instead_of_polluted_text():
    state = _complete_state()
    state.generated_assets.match_summary = "Matched req_python with ev_project."

    response = finalize_response(public_output_gate(state, _gate_services()))
    serialized = json.dumps(response.model_dump(mode="json"))

    assert response.status == "failed"
    assert response.result is None
    assert response.error == {
        "code": "INTERNAL_ID_LEAK",
        "message": "Generated output contained an internal reference and was not displayed.",
    }
    assert "req_python" not in serialized
    assert "ev_project" not in serialized


def _gate_services():
    return WorkflowServices(
        retrieval_service=object(),
        llm_service=LLMService(client=object()),
    )


def _complete_state():
    requirement = JDRequirement(
        requirement_id="req_python",
        category="hard_skill",
        text="Python API engineering",
        importance="high",
        keywords=["Python", "API"],
        capability_tags=["programming"],
        verification_mode="technical_question",
        interviewability=True,
        question_focus="API reliability and design trade-offs",
    )
    generated_assets = GeneratedAssets(
        match_summary="The resume contains relevant API engineering experience.",
        resume_bullets=[
            ResumeBullet(
                text="Built a Python API and evaluated reliability.",
                target_requirement_ids=["req_python"],
                evidence_ids=["ev_project"],
                risk_level="low",
            )
            for _ in range(3)
        ],
        interview_prep=InterviewPrep(
            jd_questions=[
                InterviewPrepQuestion(
                    question="How would you design a reliable API?",
                    sample_answer="I would define failure modes, metrics, and recovery paths.",
                    supporting_evidence_ids=["ev_project"],
                )
            ]
        ),
    )
    internal_risk_report = InternalRiskReport(
        risks=[
            InternalRiskItem(
                risk_type="evidence_strength",
                title="Production scale is unclear",
                jd_requirement_summary="Operate reliable production APIs.",
                resume_current_state="The resume describes implementation without traffic scale.",
                risk_reason="Scale and reliability evidence are limited.",
                recommendation="Add supported throughput or reliability evidence if available.",
                severity="medium",
                requirement_ids=["req_python"],
                internal_supporting_evidence_ids=["ev_project"],
            )
        ]
    )
    return AnalysisState(
        analysis_id="analysis_public",
        profile_documents=[
            ProfileDocument(
                source_name="resume.pdf",
                source_type="text",
                content="Private complete resume content.",
            )
        ],
        job_description="Build reliable APIs.",
        profile_chunks=[
            ProfileChunk(
                chunk_id="chunk_project",
                document_id="doc_private",
                source_name="resume.pdf",
                section_type="project",
                text="Private project evidence.",
            )
        ],
        jd_requirements=[requirement],
        match_analysis=[
            MatchItem(
                requirement_id="req_python",
                match_level="strong",
                rationale="The project demonstrates API engineering.",
                evidence_ids=["ev_project"],
            )
        ],
        generated_assets=generated_assets,
        evaluation_report=EvaluationReport(
            grounding_warnings=[
                GroundingWarning(
                    asset_type="resume_bullet",
                    asset_id="bullet_1",
                    claim="Built a reliable API.",
                    reason="Reliability metrics are not included.",
                    severity="medium",
                )
            ],
            coverage_gaps=[],
            specificity_notes=["Add supported reliability metrics if available."],
            risk_summary="One specificity issue was found.",
            overall_status="pass_with_warnings",
        ),
        agent_traces=[
            AgentTrace(
                agent_name="resume_evidence",
                steps=[
                    AgentToolResult(
                        tool_name="search_resume_evidence",
                        arguments_summary="section_type=project",
                        return_summary="Returned one relevant project.",
                        status="success",
                    )
                ],
                final_decision_summary="Use project evidence.",
            )
        ],
        internal_risk_report=internal_risk_report,
    )

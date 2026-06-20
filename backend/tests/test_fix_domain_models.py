import pytest
from pydantic import ValidationError

from backend.app.documents.models import ProfileDocument
from backend.app.workflow.domain_models import (
    EvidenceSelection,
    ExperienceRecord,
    InterviewAnswerPlan,
    InternalInterviewPrep,
    InternalInterviewQuestion,
    InternalRiskItem,
    InternalRiskReport,
    NumericClaim,
    QualityIssue,
)
from backend.app.workflow.state import WorkflowState


def test_experience_record_accepts_structured_project_and_internship_data():
    project = ExperienceRecord(
        experience_id="exp_project_1",
        experience_type="project",
        name="Semantic Segmentation",
        role_title="Project Lead",
        date_range="2024-02 to 2024-06",
        objective="Improve segmentation in natural environments.",
        responsibilities=["Built the experiment platform."],
        technologies=["Python", "PyTorch", "DeepLabV3+"],
        challenges=["Fuzzy object boundaries."],
        actions=["Added multi-scale feature fusion."],
        outcomes=["Improved mean IoU."],
        metrics=["17% mean IoU improvement"],
        raw_source_chunk_ids=["chunk_project_1"],
        raw_text="Project Lead Semantic Segmentation 2024-02 to 2024-06",
    )
    internship = ExperienceRecord(
        experience_id="exp_internship_1",
        experience_type="internship",
        name="Multimodal Model Evaluation",
        company_name="Tencent Hunyuan",
        role_title="AI Intern",
        responsibilities=["Designed an automated image-to-text evaluation flow."],
        technologies=["Python", "LLM"],
        raw_source_chunk_ids=["chunk_internship_1"],
        raw_text="AI Intern Tencent Hunyuan 2024-12 to 2025-01",
    )

    assert project.experience_type == "project"
    assert project.metrics == ["17% mean IoU improvement"]
    assert internship.experience_type == "internship"
    assert internship.company_name == "Tencent Hunyuan"


@pytest.mark.parametrize("support_level", ["strong", "partial"])
def test_supported_evidence_selection_requires_evidence(support_level):
    with pytest.raises(ValidationError, match="selected evidence"):
        EvidenceSelection(
            requirement_id="req_1",
            selected_evidence_ids=[],
            support_level=support_level,
            support_types=["direct"],
            rationale="The experience directly demonstrates the capability.",
        )


def test_missing_evidence_selection_cannot_claim_direct_support():
    with pytest.raises(ValidationError, match="direct support"):
        EvidenceSelection(
            requirement_id="req_1",
            selected_evidence_ids=["ev_1"],
            support_level="missing",
            support_types=["direct"],
            rationale="No sufficient evidence was found.",
        )


@pytest.mark.parametrize(
    "claim_type",
    [
        "performance_metric",
        "business_impact",
        "dataset_size",
        "count",
        "date",
        "duration",
        "ordinal",
        "model_or_version",
        "other",
    ],
)
def test_numeric_claim_accepts_only_documented_claim_types(claim_type):
    claim = NumericClaim(
        value="17%",
        normalized_value="0.17",
        claim_type=claim_type,
        context="Mean IoU improved by 17%.",
        evidence_ids=["ev_1"],
    )

    assert claim.claim_type == claim_type


def test_numeric_claim_rejects_unknown_claim_type():
    with pytest.raises(ValidationError):
        NumericClaim(
            value="17%",
            normalized_value="0.17",
            claim_type="percentage",
            context="Mean IoU improved by 17%.",
            evidence_ids=["ev_1"],
        )


@pytest.mark.parametrize(
    "missing_field",
    ["code", "field_path", "message", "retry_instruction", "severity"],
)
def test_quality_issue_requires_all_diagnostic_fields(missing_field):
    payload = {
        "code": "INTERNAL_ID_LEAK",
        "field_path": "interview.questions.0.question",
        "message": "The public question contains an internal ID.",
        "retry_instruction": "Rewrite the question without internal IDs.",
        "severity": "high",
    }
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        QualityIssue.model_validate(payload)


def test_internal_interview_and_risk_models_keep_ids_and_reject_blank_public_text():
    question = InternalInterviewQuestion(
        question="How would you evaluate a multimodal platform under data drift?",
        question_type="system_design",
        competencies_tested=["multimodal evaluation", "monitoring"],
        target_requirement_ids=["req_multimodal"],
        answer_plan=InterviewAnswerPlan(
            direct_answer="Separate quality, drift, and operational metrics.",
            selected_facts=["Evaluated multimodal model outputs."],
            reasoning_or_tradeoffs="Balance detection sensitivity and alert noise.",
            result="Validate against labeled drift scenarios.",
            reflection_or_transfer="Tune thresholds using observed failure modes.",
        ),
        sample_answer="I would separate model quality, drift, and operational metrics.",
        supporting_evidence_ids=["ev_internship_1"],
        experience_id="exp_internship_1",
    )
    prep = InternalInterviewPrep(jd_questions=[question])
    risk = InternalRiskItem(
        risk_type="evidence_strength",
        title="Production scale is not demonstrated",
        jd_requirement_summary="Operate multimodal systems at production scale.",
        resume_current_state="The resume describes model evaluation without traffic scale.",
        risk_reason="Operational scale and reliability evidence are absent.",
        recommendation="Add supported throughput or reliability evidence if available.",
        severity="medium",
        requirement_ids=["req_multimodal"],
        internal_supporting_evidence_ids=["ev_internship_1"],
    )
    report = InternalRiskReport(risks=[risk])

    assert prep.jd_questions[0].supporting_evidence_ids == ["ev_internship_1"]
    assert report.risks[0].requirement_ids == ["req_multimodal"]

    with pytest.raises(ValidationError):
        question.model_copy(update={"question": " "}, deep=True).__class__.model_validate(
            {**question.model_dump(), "question": " "}
        )
    with pytest.raises(ValidationError):
        InternalRiskItem.model_validate({**risk.model_dump(), "risk_reason": " "})


def test_workflow_state_domain_collections_have_independent_empty_defaults():
    def build_state(analysis_id):
        return WorkflowState(
            analysis_id=analysis_id,
            profile_documents=[
                ProfileDocument(
                    source_name="resume.txt",
                    source_type="text",
                    content="Python project",
                )
            ],
            job_description="Python role",
        )

    first = build_state("analysis_1")
    second = build_state("analysis_2")
    first.allowed_evidence_ids.add("ev_1")

    assert first.experience_records == []
    assert first.evidence_selections == []
    assert first.quality_issues == []
    assert second.allowed_evidence_ids == set()

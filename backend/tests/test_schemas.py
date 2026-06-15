import pytest
from pydantic import ValidationError

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.workflow.state import WorkflowState
from backend.app.api.schemas import (
    CoverLetterDraft,
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    GroundingWarning,
    InterviewPrepItem,
    JDRequirement,
    MatchItem,
    ResumeBullet,
)


def test_profile_document_rejects_empty_content():
    with pytest.raises(ValidationError):
        ProfileDocument(source_name="resume.md", source_type="markdown", content="  ")


def test_profile_document_rejects_pdf_for_mvp():
    with pytest.raises(ValidationError):
        ProfileDocument(source_name="resume.pdf", source_type="pdf", content="bytes as text")


def test_profile_chunk_requires_core_metadata():
    chunk = ProfileChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        source_name="resume.md",
        text="Built a search service.",
    )

    assert chunk.chunk_id == "chunk_1"
    assert chunk.document_id == "doc_1"
    assert chunk.source_name == "resume.md"
    assert chunk.text == "Built a search service."


def test_jd_requirement_rejects_invalid_importance():
    with pytest.raises(ValidationError):
        JDRequirement(
            requirement_id="req_1",
            category="hard_skill",
            text="Python experience",
            importance="critical",
            keywords=["python"],
        )


def test_evidence_item_score_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="ev_1",
            requirement_id="req_1",
            chunk_id="chunk_1",
            source_name="resume.md",
            snippet="Python project",
            score=1.2,
        )


def test_match_item_rejects_invalid_match_level():
    with pytest.raises(ValidationError):
        MatchItem(
            requirement_id="req_1",
            match_level="excellent",
            rationale="Strong Python project.",
            evidence_ids=["ev_1"],
        )


def test_generated_assets_resume_bullet_requires_evidence_ids_field():
    with pytest.raises(ValidationError):
        ResumeBullet.model_validate(
            {
                "text": "Built a retrieval prototype.",
                "target_requirement_ids": ["req_1"],
                "risk_level": "low",
            }
        )


def test_generated_assets_accepts_complete_application_payload():
    assets = GeneratedAssets(
        match_summary="Good fit for applied AI prototyping.",
        resume_bullets=[
            ResumeBullet(
                text="Built a retrieval prototype over project notes.",
                target_requirement_ids=["req_1"],
                evidence_ids=["ev_1"],
                risk_level="low",
            )
        ],
        cover_letter=CoverLetterDraft(
            opening="I am excited to apply.",
            body=["My project work aligns with the role."],
            closing="Thank you for your consideration.",
            evidence_ids=["ev_1"],
        ),
        interview_prep=[
            InterviewPrepItem(
                topic="Retrieval project",
                why_it_matters="The role asks for RAG experience.",
                supporting_evidence_ids=["ev_1"],
                prep_suggestion="Prepare a concise project walkthrough.",
            )
        ],
    )

    assert assets.resume_bullets[0].evidence_ids == ["ev_1"]


def test_evaluation_report_rejects_invalid_overall_status():
    with pytest.raises(ValidationError):
        EvaluationReport(
            grounding_warnings=[],
            coverage_gaps=[],
            specificity_notes=[],
            risk_summary="No major risks.",
            overall_status="maybe",
        )


def test_analysis_request_rejects_empty_profile_documents():
    with pytest.raises(ValidationError):
        AnalysisRequest(profile_documents=[], job_description="Build APIs")


def test_analysis_response_and_workflow_state_accept_core_shapes():
    requirement = JDRequirement(
        requirement_id="req_1",
        category="hard_skill",
        text="Python",
        importance="high",
        keywords=["python"],
    )
    warning = GroundingWarning(
        asset_type="resume_bullet",
        asset_id="bullet_1",
        claim="Built a production system",
        reason="No evidence mentions production.",
        severity="high",
    )
    report = EvaluationReport(
        grounding_warnings=[warning],
        coverage_gaps=[],
        specificity_notes=["Add a concrete project context."],
        risk_summary="One unsupported claim.",
        overall_status="pass_with_warnings",
    )

    state = WorkflowState(
        analysis_id="analysis_1",
        profile_documents=[
            ProfileDocument(source_name="resume.md", source_type="markdown", content="Python project")
        ],
        job_description="Python role",
        jd_requirements=[requirement],
        evaluation_report=report,
    )
    response = AnalysisResponse(analysis_id=state.analysis_id, status="completed", result={"ok": True})

    assert response.analysis_id == "analysis_1"
    assert state.jd_requirements[0].importance == "high"

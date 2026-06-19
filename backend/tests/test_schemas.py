import pytest
from pydantic import ValidationError

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.workflow.state import WorkflowState
from backend.app.api.schemas import (
    AgentTrace,
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    GroundingWarning,
    InterviewPrep,
    InterviewPrepQuestion,
    MatchStrategy,
    MatchStrategyItem,
    JDRequirement,
    MatchItem,
    PDFParseResponse,
    ResumeSection,
    ResumeSectionMetadata,
    ResumeBullet,
    RiskItem,
    RiskReport,
)


def test_pdf_parse_response_requires_positive_page_count_and_text():
    response = PDFParseResponse(
        source_name="resume.pdf",
        page_count=2,
        text="项目经历\nBuilt a model.",
    )

    assert response.page_count == 2
    assert response.text.startswith("项目经历")


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
                text=f"Built retrieval prototype {index} over project notes.",
                target_requirement_ids=["req_1"],
                evidence_ids=[f"ev_{index}"],
                risk_level="low",
            )
            for index in range(1, 4)
        ],
        interview_prep=InterviewPrep(
            jd_questions=[
                InterviewPrepQuestion(
                question="How did you build the retrieval project?",
                sample_answer="I built and evaluated a grounded retrieval workflow.",
                supporting_evidence_ids=["ev_1"],
                )
            ]
        ),
    )

    assert assets.resume_bullets[0].evidence_ids == ["ev_1"]
    assert "cover_letter" not in assets.model_dump()


def test_resume_section_accepts_known_section_type_and_metadata():
    section = ResumeSection(
        section_type="project",
        section_title="CareerPilot Agent",
        content="Built an evidence-grounded career agent.",
        metadata=ResumeSectionMetadata(
            project_name="CareerPilot Agent",
            technologies=["FastAPI", "LangGraph"],
        ),
    )

    assert section.section_type == "project"
    assert section.metadata.project_name == "CareerPilot Agent"


def test_resume_section_rejects_unknown_section_type():
    with pytest.raises(ValidationError):
        ResumeSection(
            section_type="publication",
            section_title="Paper",
            content="Published a paper.",
        )


def test_agent_trace_captures_tool_and_decision_shape():
    trace = AgentTrace(
        agent_name="resume_evidence",
        tool_name="search_resume_sections",
        arguments_summary="top_k=5 section_type=project",
        observation_summary="Found two relevant projects.",
        final_decision_summary="Use project evidence first.",
    )

    assert trace.agent_name == "resume_evidence"
    assert trace.final_decision_summary == "Use project evidence first."


def test_sprint2_assets_require_three_resume_bullets_and_no_cover_letter():
    bullets = [
        ResumeBullet(
            text=f"Project bullet {index}",
            target_requirement_ids=["req_1"],
            evidence_ids=[f"ev_{index}"],
            risk_level="low",
        )
        for index in range(3)
    ]
    assets = GeneratedAssets(
        match_summary="Strong project match.",
        resume_bullets=bullets,
        interview_prep={
            "jd_questions": [
                {
                    "question": "How have you built agent workflows?",
                    "sample_answer": "I built CareerPilot with LangGraph.",
                    "supporting_evidence_ids": ["ev_1"],
                }
            ],
            "resume_deep_dive_questions": [
                {
                    "question": "Walk through your retrieval project.",
                    "sample_answer": "I designed the indexing and ranking flow.",
                    "supporting_evidence_ids": ["ev_2"],
                }
            ],
        },
    )

    assert len(assets.resume_bullets) == 3

    with pytest.raises(ValidationError):
        GeneratedAssets(
            match_summary="Strong project match.",
            resume_bullets=bullets[:2],
            interview_prep=assets.interview_prep,
        )

    with pytest.raises(ValidationError):
        GeneratedAssets(
            match_summary="Strong project match.",
            resume_bullets=bullets,
            cover_letter={"opening": "Hello", "body": [], "closing": "Thanks", "evidence_ids": []},
            interview_prep=assets.interview_prep,
        )


def test_risk_report_allows_at_most_three_user_facing_risks():
    risks = [
        RiskItem(
            risk_type="JD 未覆盖",
            title=f"Risk {index}",
            jd_requirement_summary="Requires production RAG experience.",
            resume_current_state="Resume mentions a prototype only.",
            risk_reason="The current evidence may not prove production depth.",
            recommendation="Add deployment metrics or operational details.",
            severity="high",
        )
        for index in range(3)
    ]

    report = RiskReport(risks=risks)

    assert len(report.risks) == 3

    with pytest.raises(ValidationError):
        RiskReport(risks=risks + [risks[0]])


def test_workflow_state_accepts_sprint2_state_extensions():
    state = WorkflowState(
        analysis_id="analysis_1",
        profile_documents=[
            ProfileDocument(source_name="resume.md", source_type="markdown", content="Python project")
        ],
        job_description="Python role",
        structured_resume_sections=[
            ResumeSection(
                section_type="internship",
                section_title="AI Intern",
                content="Built retrieval evaluation tools.",
            )
        ],
        match_strategy=MatchStrategy(
            ranked_evidence=[
                MatchStrategyItem(
                    evidence_id="ev_1",
                    section_type="internship",
                    priority_score=0.9,
                    rationale="Internship evidence matches the high-priority requirement.",
                )
            ],
            summary="Prioritize internship evidence.",
        ),
        risk_report=RiskReport(risks=[]),
        agent_traces=[
            AgentTrace(
                agent_name="risk_auditor",
                tool_name="compare_requirements",
                arguments_summary="high priority requirements",
                observation_summary="One weakly covered requirement.",
                final_decision_summary="Create one risk item.",
            )
        ],
    )

    assert state.structured_resume_sections[0].section_type == "internship"
    assert state.match_strategy.ranked_evidence[0].evidence_id == "ev_1"
    assert state.agent_traces[0].agent_name == "risk_auditor"


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

from backend.app.api.schemas import (
    AgentToolResult,
    EvidenceItem,
    GeneratedAssets,
    InterviewPrepItem,
    JDRequirement,
    ResumeBullet,
    ResumeSection,
    ResumeSectionMetadata,
)
from backend.app.documents.models import ProfileDocument
from backend.app.workflow.agent_tools import (
    AGENT_TOOL_ALLOWLIST,
    MAX_REACT_AGENT_STEPS,
    TraceRecorder,
    build_agent_toolbox,
)
from backend.app.workflow.nodes import finalize_response
from backend.app.workflow.state import WorkflowState


def test_react_agent_tool_allowlists_and_step_limit_are_explicit():
    assert MAX_REACT_AGENT_STEPS == 3
    assert set(AGENT_TOOL_ALLOWLIST) == {
        "resume_evidence",
        "interview_prep",
        "risk_auditor",
    }
    assert AGENT_TOOL_ALLOWLIST["resume_evidence"] == {
        "search_resume_evidence",
        "get_resume_section",
        "rerank_evidence",
    }
    assert "rank_top_risks" in AGENT_TOOL_ALLOWLIST["risk_auditor"]
    assert set(build_agent_toolbox(_state_with_sensitive_details(), agent_name="resume_evidence")) == (
        AGENT_TOOL_ALLOWLIST["resume_evidence"]
    )


def test_agent_tools_return_summaries_without_full_hidden_prompt_text():
    state = _state_with_sensitive_details()
    toolbox = build_agent_toolbox(state)

    calls = [
        toolbox["search_resume_evidence"](
            query="Python API",
            section_filter=["project", "internship"],
            top_k=2,
        ),
        toolbox["get_resume_section"](section_type="project"),
        toolbox["rerank_evidence"](
            requirement=state.jd_requirements[0],
            evidence_items=state.retrieved_evidence,
        ),
        toolbox["get_high_priority_jd_requirements"](),
        toolbox["get_matched_project_and_internship_evidence"](),
        toolbox["draft_answer"](
            question="How did you build the API?",
            evidence=state.retrieved_evidence[0],
            jd_requirement=state.jd_requirements[0],
        ),
        toolbox["check_requirement_coverage"](requirement=state.jd_requirements[0]),
        toolbox["find_resume_vague_claims"](),
        toolbox["check_generated_claim_grounding"](claim="Built a production API."),
        toolbox["rank_top_risks"](
            risks=[
                {"title": "Low signal", "severity": "medium"},
                {"title": "Unsupported claim", "severity": "high"},
                {"title": "Minor wording", "severity": "low"},
                {"title": "Missing metric", "severity": "medium"},
            ],
            limit=3,
        ),
    ]

    assert all(isinstance(result, AgentToolResult) for result in calls)
    assert all(result.status == "success" for result in calls)
    assert all("SYSTEM_PROMPT_SECRET" not in result.return_summary for result in calls)
    assert all(len(result.return_summary) <= 320 for result in calls)


def test_trace_recorder_serializes_steps_to_frontend_response():
    state = _state_with_sensitive_details()
    recorder = TraceRecorder(agent_name="resume_evidence")
    recorder.record(
        AgentToolResult(
            tool_name="get_resume_section",
            arguments_summary="section_type=project",
            return_summary="1 project section found.",
            status="success",
        )
    )

    state = recorder.attach_to_state(state, final_decision_summary="Use project evidence first.")
    response = finalize_response(state)

    assert response.result is not None
    traces = response.result["agent_traces"]
    assert traces == [
        {
            "agent_name": "resume_evidence",
            "steps": [
                {
                    "tool_name": "get_resume_section",
                    "arguments_summary": "section_type=project",
                    "return_summary": "1 project section found.",
                    "status": "success",
                }
            ],
            "final_decision_summary": "Use project evidence first.",
        }
    ]


def _state_with_sensitive_details() -> WorkflowState:
    requirement = JDRequirement(
        requirement_id="req_python",
        category="hard_skill",
        text="Python API development",
        importance="high",
        keywords=["Python", "API"],
    )
    evidence = EvidenceItem(
        evidence_id="ev_project",
        requirement_id="req_python",
        chunk_id="chunk_project",
        source_name="resume.md",
        section_label="Projects",
        section_type="project",
        snippet="Built a Python API. SYSTEM_PROMPT_SECRET must never appear.",
        score=0.92,
    )
    return WorkflowState(
        analysis_id="analysis_trace",
        profile_documents=[
            ProfileDocument(
                source_name="resume.md",
                source_type="markdown",
                content="SYSTEM_PROMPT_SECRET",
            )
        ],
        job_description="Python API role",
        structured_resume_sections=[
            ResumeSection(
                section_type="project",
                section_title="CareerPilot",
                content="Built a Python API. SYSTEM_PROMPT_SECRET must never appear.",
                metadata=ResumeSectionMetadata(project_name="CareerPilot"),
            ),
            ResumeSection(
                section_type="skill",
                section_title="Skills",
                content="Python, FastAPI",
            ),
        ],
        jd_requirements=[requirement],
        retrieved_evidence=[evidence],
        generated_assets=GeneratedAssets(
            match_summary="Strong API match.",
            resume_bullets=[
                ResumeBullet(
                    text="Built a production API.",
                    target_requirement_ids=["req_python"],
                    evidence_ids=["ev_project"],
                    risk_level="low",
                )
            ],
            cover_letter={
                "opening": "Hello",
                "body": ["API background."],
                "closing": "Thanks",
                "evidence_ids": ["ev_project"],
            },
            interview_prep=[
                InterviewPrepItem(
                    topic="API project",
                    why_it_matters="Role asks for API development.",
                    supporting_evidence_ids=["ev_project"],
                    prep_suggestion="Discuss implementation tradeoffs.",
                )
            ],
        ),
    )

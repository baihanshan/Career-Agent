from langchain_core.tools import StructuredTool

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.documents.models import ProfileDocument
from backend.app.workflow.agent_tools import TraceRecorder
from backend.app.workflow.domain_models import ExperienceRecord
from backend.app.workflow.react_tools import (
    REACT_AGENT_TOOL_ALLOWLIST,
    StructuredToolResult,
    build_structured_react_tools,
)
from backend.app.workflow.state import WorkflowState


def test_search_resume_evidence_returns_structured_evidence_and_tracks_allowlist():
    state = _state()
    recorder = TraceRecorder("resume_evidence")
    tools = _tools_by_name(state, "resume_evidence", recorder)

    raw_result = tools["search_resume_evidence"].invoke(
        {"query": "Python API", "section_types": ["project"], "top_k": 5}
    )
    result = StructuredToolResult.model_validate(raw_result)

    assert result.status == "success"
    assert result.data["evidence"] == [
        state.retrieved_evidence[0].model_dump(mode="json")
    ]
    assert result.trace_summary == "Returned 1 evidence item(s)."
    assert state.allowed_evidence_ids == {"ev_project"}


def test_get_experience_returns_typed_record_and_unknown_id_is_controlled_error():
    state = _state()
    tools = _tools_by_name(state, "resume_evidence", TraceRecorder("resume_evidence"))

    found = StructuredToolResult.model_validate(
        tools["get_experience"].invoke({"experience_id": "exp_project"})
    )
    missing = StructuredToolResult.model_validate(
        tools["get_experience"].invoke({"experience_id": "exp_missing"})
    )

    assert found.data["experience"]["name"] == "Career Agent"
    assert found.data["experience"]["raw_source_chunk_ids"] == ["chunk_project"]
    assert missing.status == "error"
    assert missing.error.code == "REACT_TOOL_CALL_ERROR"
    assert "exp_missing" not in missing.trace_summary


def test_each_agent_receives_only_its_structured_tool_allowlist():
    state = _state()

    for agent_name, expected_names in REACT_AGENT_TOOL_ALLOWLIST.items():
        tools = build_structured_react_tools(
            state,
            agent_name,
            TraceRecorder(agent_name),
        )
        assert all(isinstance(tool, StructuredTool) for tool in tools)
        assert {tool.name for tool in tools} == expected_names

    assert "rank_candidate_risks" not in REACT_AGENT_TOOL_ALLOWLIST["resume_evidence"]
    assert "search_resume_evidence" not in REACT_AGENT_TOOL_ALLOWLIST["risk_auditor"]


def test_structured_tool_trace_redacts_secrets_prompt_reasoning_and_resume_text():
    state = _state()
    recorder = TraceRecorder("resume_evidence", attempt_number=2)
    tools = _tools_by_name(state, "resume_evidence", recorder)

    tools["search_resume_evidence"].invoke(
        {
            "query": (
                "api_key=sk-super-secret SYSTEM_PROMPT_SECRET hidden reasoning "
                + state.profile_documents[0].content
            ),
            "section_types": ["project"],
            "top_k": 5,
        }
    )

    assert len(recorder.steps) == 1
    step = recorder.steps[0]
    assert step.attempt_number == 2
    assert step.status == "success"
    combined = f"{step.arguments_summary} {step.return_summary}"
    assert "sk-super-secret" not in combined
    assert "SYSTEM_PROMPT_SECRET" not in combined
    assert "hidden reasoning" not in combined
    assert state.profile_documents[0].content not in combined
    assert len(step.arguments_summary) <= 320
    assert len(step.return_summary) <= 320


def _tools_by_name(state, agent_name, recorder):
    return {
        tool.name: tool
        for tool in build_structured_react_tools(state, agent_name, recorder)
    }


def _state():
    requirement = JDRequirement(
        requirement_id="req_python",
        category="hard_skill",
        text="Build Python APIs",
        importance="high",
        keywords=["Python", "API"],
        capability_tags=["programming"],
        verification_mode="technical_question",
        interviewability=True,
        question_focus="API design and reliability trade-offs",
    )
    evidence = EvidenceItem(
        evidence_id="ev_project",
        requirement_id="req_python",
        chunk_id="chunk_project",
        source_name="resume.pdf",
        section_type="project",
        snippet="Built a Python API for evidence-grounded career analysis.",
        score=0.94,
    )
    experience = ExperienceRecord(
        experience_id="exp_project",
        experience_type="project",
        name="Career Agent",
        role_title="Project Lead",
        responsibilities=["Designed the API workflow."],
        technologies=["Python", "FastAPI"],
        outcomes=["Built an evidence-grounded analysis flow."],
        raw_source_chunk_ids=["chunk_project"],
        raw_text="Project Lead Career Agent. Built a Python API.",
    )
    return WorkflowState(
        analysis_id="analysis_tools",
        profile_documents=[
            ProfileDocument(
                source_name="resume.pdf",
                source_type="text",
                content=(
                    "FULL PRIVATE RESUME CONTENT SYSTEM_PROMPT_SECRET "
                    "with many project details"
                ),
            )
        ],
        job_description="Build AI systems.",
        jd_requirements=[requirement],
        retrieved_evidence=[evidence],
        experience_records=[experience],
    )

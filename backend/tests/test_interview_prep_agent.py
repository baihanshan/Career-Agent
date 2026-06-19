import pytest

from backend.app.api.schemas import (
    EvidenceItem,
    GeneratedAssets,
    InterviewPrep,
    JDRequirement,
    ResumeBullet,
)
from backend.app.llm.client import LLMService
from backend.app.workflow.interview_prep_agent import (
    INTERVIEW_PREP_AGENT_PROMPT,
    InterviewPrepAgent,
    InterviewPrepAgentError,
    create_interview_prep_react_agent,
)
from backend.app.workflow.nodes import (
    WorkflowServices,
    finalize_response,
    generate_interview_prep,
    parse_inputs,
)
from backend.tests.test_workflow_nodes import _request


def test_interview_prep_uses_high_priority_jd_requirements_in_jd_questions():
    state = _state(
        requirements=[_requirement("req_python", "Python API development")],
        evidence=[_evidence("ev_project", "project", "CareerPilot API project")],
    )

    next_state = InterviewPrepAgent().run(state)

    question = next_state.generated_assets.interview_prep.jd_questions[0]
    assert "Python API development" in question.question
    assert question.sample_answer


def test_interview_prep_uses_project_and_internship_evidence_without_exposing_ids():
    state = _state(
        requirements=[_requirement("req_python", "Python API development")],
        evidence=[
            _evidence(
                "ev_project_secret",
                "project",
                "Built CareerPilot with FastAPI and reduced analysis latency by 30%.",
            ),
            _evidence(
                "ev_internship_secret",
                "internship",
                "At Acme, delivered an API monitoring dashboard for the platform team.",
            ),
        ],
    )

    next_state = InterviewPrepAgent().run(state)

    questions = next_state.generated_assets.interview_prep.resume_deep_dive_questions
    rendered = " ".join(
        f"{item.question} {item.sample_answer}" for item in questions
    )
    assert "CareerPilot" in rendered
    assert "Acme" in rendered
    assert "ev_project_secret" not in rendered
    assert "ev_internship_secret" not in rendered


def test_interview_prep_scales_question_counts_for_richer_inputs():
    state = _state(
        requirements=[
            _requirement(f"req_{index}", f"Requirement {index}")
            for index in range(4)
        ],
        evidence=[
            _evidence(f"ev_{index}", "project", f"Project experience {index}")
            for index in range(4)
        ],
    )

    next_state = InterviewPrepAgent().run(state)

    prep = next_state.generated_assets.interview_prep
    assert 3 <= len(prep.jd_questions) <= 4
    assert 3 <= len(prep.resume_deep_dive_questions) <= 4


def test_interview_prep_deduplicates_deep_dive_questions_for_same_chunk():
    first = _evidence("ev_project_python", "project", "CareerPilot project")
    duplicate_chunk = _evidence(
        "ev_project_api",
        "project",
        "CareerPilot project",
    ).model_copy(update={"chunk_id": first.chunk_id})
    state = _state(
        requirements=[_requirement("req_python", "Python API development")],
        evidence=[first, duplicate_chunk],
    )

    next_state = InterviewPrepAgent().run(state)

    questions = next_state.generated_assets.interview_prep.resume_deep_dive_questions
    assert len(questions) == 1
    assert questions[0].supporting_evidence_ids == ["ev_project_python"]


def test_interview_prep_fails_after_three_invalid_attempts():
    attempts = []

    def invalid_generator(state, requirements, evidence):
        attempts.append((requirements, evidence))
        return InterviewPrep()

    with pytest.raises(InterviewPrepAgentError, match="3 attempts"):
        InterviewPrepAgent(question_generator=invalid_generator).run(
            _state(
                requirements=[_requirement("req_python", "Python API development")],
                evidence=[_evidence("ev_project", "project", "CareerPilot project")],
            )
        )

    assert len(attempts) == 3


def test_interview_prep_fails_cleanly_when_project_and_internship_evidence_is_missing():
    with pytest.raises(InterviewPrepAgentError, match="3 attempts"):
        InterviewPrepAgent().run(
            _state(
                requirements=[_requirement("req_python", "Python API development")],
                evidence=[_evidence("ev_skill", "skill", "Python and FastAPI")],
            )
        )


def test_interview_prep_falls_back_to_medium_requirement_when_no_high_requirement_exists():
    requirement = _requirement("req_collaboration", "Cross-team collaboration").model_copy(
        update={"importance": "medium"}
    )

    next_state = InterviewPrepAgent().run(
        _state(
            requirements=[requirement],
            evidence=[_evidence("ev_internship", "internship", "Worked with Acme platform team")],
        )
    )

    assert "Cross-team collaboration" in (
        next_state.generated_assets.interview_prep.jd_questions[0].question
    )


def test_generate_interview_prep_node_returns_friendly_error_after_agent_failure():
    services = WorkflowServices(
        retrieval_service=object(),
        llm_service=LLMService(client=_UnusedLLMClient()),
        interview_prep_agent=InterviewPrepAgent(
            question_generator=lambda state, requirements, evidence: InterviewPrep()
        ),
    )
    state = _state(
        requirements=[_requirement("req_python", "Python API development")],
        evidence=[_evidence("ev_project", "project", "CareerPilot project")],
    )

    response = finalize_response(generate_interview_prep(state, services))

    assert response.status == "failed"
    assert response.error["code"] == "INTERVIEW_PREP_AGENT_ERROR"
    assert response.error["message"] == "Interview preparation could not be generated safely."
    assert set(response.error) == {"code", "message"}


def test_interview_prep_react_agent_uses_only_allowed_tools(monkeypatch):
    calls = []

    def fake_create_react_agent(*, model, tools, prompt):
        calls.append({"model": model, "tools": tools, "prompt": prompt})
        return "compiled-agent"

    monkeypatch.setattr(
        "backend.app.workflow.interview_prep_agent.create_react_agent",
        fake_create_react_agent,
    )
    tools = {
        "get_high_priority_jd_requirements": object(),
        "get_matched_project_and_internship_evidence": object(),
        "draft_answer": object(),
    }

    agent = create_interview_prep_react_agent(model="model", tools=tools)

    assert agent == "compiled-agent"
    assert set(calls[0]["tools"]) == set(tools.values())
    assert "complete sample answer" in calls[0]["prompt"].lower()
    assert "evidence ID" in calls[0]["prompt"]
    assert INTERVIEW_PREP_AGENT_PROMPT == calls[0]["prompt"]


def _state(requirements, evidence):
    assets = GeneratedAssets(
        match_summary="Strong evidence-backed match.",
        resume_bullets=[
            ResumeBullet(
                text=f"Evidence-backed bullet {index}",
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
        }
    )


def _requirement(requirement_id: str, text: str) -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text=text,
        importance="high",
        keywords=text.split(),
    )


def _evidence(evidence_id: str, section_type: str, snippet: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id="req_python",
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.md",
        section_label=section_type.title(),
        section_type=section_type,
        snippet=snippet,
        score=0.9,
    )


class _UnusedLLMClient:
    def generate(self, prompt_key, prompt, variables):
        raise AssertionError("LLM should not be called in interview prep tests")

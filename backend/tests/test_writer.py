import json
import pytest

from backend.app.api.schemas import EvidenceItem, JDRequirement, MatchItem
from backend.app.llm.client import FakeLLMClient, LLMService
from backend.app.llm.prompts import APPLICATION_GENERATION_PROMPT
from backend.app.workflow.writer import (
    WriterOutputError,
    build_writer_context,
    write_application,
)
from backend.app.workflow.domain_models import EvidenceSelection
from backend.app.workflow.public_output import project_public_result
from backend.app.workflow.state import AnalysisState
from backend.app.documents.models import ProfileDocument


def test_build_writer_context_contains_requirements_evidence_and_matches():
    context = build_writer_context(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
    )

    assert context["requirements"][0]["requirement_id"] == "req_python"
    assert context["evidence"][0]["evidence_id"] == "ev_python"
    assert context["match_analysis"][0]["match_level"] == "strong"
    assert context["evidence_ids"] == ["ev_python"]
    assert context["missing_requirement_ids"] == []


def test_write_application_returns_generated_assets_from_fake_llm():
    fake_client = FakeLLMClient(
        responses={"generate_application_assets": _assets_json(risk_level="low")}
    )
    service = LLMService(client=fake_client)

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        llm_service=service,
    )

    assert assets.match_summary == "Strong fit for Python API work."
    assert assets.resume_bullets[0].target_requirement_ids == ["req_python"]
    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert fake_client.calls[0]["prompt_key"] == "generate_application_assets"
    assert len(assets.resume_bullets) == 3


def test_missing_evidence_ids_trigger_structured_regeneration():
    client = _SequentialWriterClient(
        [
            _assets_json(evidence_ids=[], risk_level="low"),
            _assets_json(evidence_ids=["ev_python"], risk_level="low"),
        ]
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        evidence_selections=[_selection("ev_python")],
        allowed_evidence_ids={"ev_python"},
        llm_service=LLMService(client=client),
    )

    assert len(client.calls) == 2
    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert assets.resume_bullets[0].risk_level == "low"


def test_unknown_evidence_ids_trigger_structured_regeneration():
    client = _SequentialWriterClient(
        [
            _assets_json(
                evidence_ids=["made_up_evidence_id"],
                risk_level="low",
            ),
            _assets_json(evidence_ids=["ev_python"], risk_level="low"),
        ]
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        evidence_selections=[_selection("ev_python")],
        allowed_evidence_ids={"ev_python"},
        llm_service=LLMService(client=client),
    )

    assert len(client.calls) == 2
    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert assets.resume_bullets[0].risk_level == "low"


def test_missing_requirement_without_evidence_fails_safely():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": _assets_json(
                    target_requirement_ids=["req_missing"],
                    evidence_ids=[],
                    risk_level="low",
                    text="Can support distributed systems work.",
                )
            }
        )
    )

    with pytest.raises(WriterOutputError):
        write_application(
            requirements=[_requirement("req_missing")],
            evidence_items=[],
            match_items=[_match("req_missing", "missing", [])],
            llm_service=service,
        )

    assert len(service.client.calls) == 2


def test_write_application_does_not_return_cover_letter():
    service = LLMService(
        client=FakeLLMClient(
            responses={"generate_application_assets": _assets_json(risk_level="low")}
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        llm_service=service,
    )

    assert "cover_letter" not in assets.model_dump()


def test_skill_evidence_does_not_generate_standalone_resume_bullet():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": _assets_json(
                    evidence_ids=["ev_skill"],
                    text="Python, FastAPI, and LangGraph skills.",
                )
            }
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_skill", "req_python", section_type="skill")],
        match_items=[_match("req_python", "strong", ["ev_skill"])],
        llm_service=service,
    )

    assert all("skills." not in bullet.text for bullet in assets.resume_bullets)
    assert all(bullet.risk_level == "high" for bullet in assets.resume_bullets)


def test_internship_bullet_contains_company_project_outcome_and_tech_stack():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": _assets_json(
                    evidence_ids=["ev_internship"],
                    text="At Acme AI, built a retrieval dashboard with FastAPI and React, improving review efficiency by 30%.",
                )
            }
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[
            _evidence(
                "ev_internship",
                "req_python",
                section_type="internship",
                snippet="Company: Acme AI. Project: retrieval dashboard. Tech Stack: FastAPI, React. Result: improved review efficiency by 30%.",
            )
        ],
        match_items=[_match("req_python", "strong", ["ev_internship"])],
        llm_service=service,
    )

    bullet_text = assets.resume_bullets[0].text
    assert "Acme AI" in bullet_text
    assert "retrieval dashboard" in bullet_text
    assert "FastAPI" in bullet_text
    assert "30%" in bullet_text


def test_project_bullet_contains_project_name_contribution_tech_stack_and_result():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": _assets_json(
                    evidence_ids=["ev_project"],
                    text="Built CareerPilot Agent by designing the LangGraph workflow and FastAPI backend, improving JD-to-resume evidence matching.",
                )
            }
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[
            _evidence(
                "ev_project",
                "req_python",
                section_type="project",
                snippet="Project: CareerPilot Agent. Contribution: designed LangGraph workflow and FastAPI backend. Result: improved JD-to-resume evidence matching.",
            )
        ],
        match_items=[_match("req_python", "strong", ["ev_project"])],
        llm_service=service,
    )

    bullet_text = assets.resume_bullets[0].text
    assert "CareerPilot Agent" in bullet_text
    assert "design" in bullet_text
    assert "LangGraph" in bullet_text
    assert "improv" in bullet_text


def test_writer_normalizes_legacy_interview_output_for_agent_handoff():
    service = LLMService(
        client=FakeLLMClient(
            responses={"generate_application_assets": _assets_json(risk_level="low")}
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        llm_service=service,
    )

    prep_item = assets.interview_prep.jd_questions[0]
    assert prep_item.question == "Python API project"
    assert prep_item.sample_answer == "Prepare a concise project walkthrough."


def test_writer_prompt_contains_evidence_only_constraints():
    prompt = APPLICATION_GENERATION_PROMPT.lower()

    assert "evidence-only" in prompt
    assert "do not fabricate" in prompt
    assert "employers, dates, numbers, tools, outcomes" in prompt
    assert "exactly 3 resume_bullets" in prompt
    assert "skills only as supporting context" in prompt
    assert "project and internship evidence first" in prompt


@pytest.mark.parametrize(
    "polluted_text",
    [
        'Built a Python API. (evidence_ids: ["ev_python"])',
        "Built a Python API for req_python.",
        "Built a Python API. evidence_ids: []",
    ],
)
def test_writer_retries_when_bullet_text_contains_internal_ids(polluted_text):
    client = _SequentialWriterClient(
        [
            _assets_json(text=polluted_text),
            _assets_json(text="Built a Python API with evidence-grounded reliability checks."),
        ]
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        evidence_selections=[_selection("ev_python")],
        allowed_evidence_ids={"ev_python"},
        llm_service=LLMService(client=client),
    )

    assert len(client.calls) == 2
    assert "evidence_ids" not in assets.resume_bullets[0].text
    assert "req_python" not in assets.resume_bullets[0].text


def test_writer_fails_safely_when_regenerated_text_still_leaks_ids():
    client = _SequentialWriterClient(
        [_assets_json(text="Uses req_python."), _assets_json(text="Uses req_python.")]
    )

    with pytest.raises(WriterOutputError) as exc_info:
        write_application(
            requirements=[_requirement("req_python")],
            evidence_items=[_evidence("ev_python", "req_python")],
            match_items=[_match("req_python", "strong", ["ev_python"])],
            evidence_selections=[_selection("ev_python")],
            allowed_evidence_ids={"ev_python"},
            llm_service=LLMService(client=client),
        )

    assert len(client.calls) == 2
    assert "req_python" not in str(exc_info.value)


def test_internal_bullet_keeps_evidence_ids_but_public_projection_drops_them():
    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        evidence_selections=[_selection("ev_python")],
        allowed_evidence_ids={"ev_python"},
        llm_service=LLMService(
            client=FakeLLMClient(
                responses={"generate_application_assets": _assets_json()}
            )
        ),
    )
    state = AnalysisState(
        analysis_id="analysis_writer",
        profile_documents=[
            ProfileDocument(
                source_name="resume.txt",
                source_type="text",
                content="Built a Python API.",
            )
        ],
        job_description="Python API role",
        generated_assets=assets,
    )

    public = project_public_result(state).model_dump(mode="json")

    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert public["generated_assets"]["resume_bullets"][0] == {
        "text": "Built Python APIs backed by project evidence.",
        "risk_level": "low",
    }


def test_writer_rejects_evidence_outside_selection_allowlist():
    client = _SequentialWriterClient(
        [
            _assets_json(evidence_ids=["ev_unselected"]),
            _assets_json(evidence_ids=["ev_selected"]),
        ]
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[
            _evidence("ev_selected", "req_python"),
            _evidence("ev_unselected", "req_python"),
        ],
        match_items=[_match("req_python", "strong", ["ev_selected"])],
        evidence_selections=[_selection("ev_selected")],
        allowed_evidence_ids={"ev_selected", "ev_unselected"},
        llm_service=LLMService(client=client),
    )

    assert len(client.calls) == 2
    assert assets.resume_bullets[0].evidence_ids == ["ev_selected"]


def test_writer_rejects_selected_evidence_when_runtime_allowlist_is_empty():
    client = _SequentialWriterClient([_assets_json(), _assets_json()])

    with pytest.raises(WriterOutputError):
        write_application(
            requirements=[_requirement("req_python")],
            evidence_items=[_evidence("ev_python", "req_python")],
            match_items=[_match("req_python", "strong", ["ev_python"])],
            evidence_selections=[_selection("ev_python")],
            allowed_evidence_ids=set(),
            llm_service=LLMService(client=client),
        )

    assert len(client.calls) == 2


def test_contextual_skill_support_cannot_become_exaggerated_practice_claim():
    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_skill", "req_python", section_type="skill")],
        match_items=[_match("req_python", "partial", ["ev_skill"])],
        evidence_selections=[
            EvidenceSelection(
                requirement_id="req_python",
                selected_evidence_ids=["ev_skill"],
                support_level="partial",
                support_types=["contextual"],
                rationale="The skills section provides contextual support only.",
            )
        ],
        allowed_evidence_ids={"ev_skill"},
        llm_service=LLMService(
            client=FakeLLMClient(
                responses={
                    "generate_application_assets": _assets_json(
                        evidence_ids=["ev_skill"],
                        text="Led a production Python platform serving millions of users.",
                    )
                }
            )
        ),
    )

    assert all("millions" not in bullet.text for bullet in assets.resume_bullets)
    assert all(bullet.risk_level == "high" for bullet in assets.resume_bullets)


def _requirement(requirement_id: str) -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text="Build Python APIs",
        importance="high",
        keywords=["Python", "API"],
    )


def _evidence(
    evidence_id: str,
    requirement_id: str,
    section_type: str = "project",
    snippet: str = "Built Python FastAPI services.",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id="chunk_python",
        source_name="resume.md",
        section_label="Projects",
        section_type=section_type,
        snippet=snippet,
        score=0.91,
    )


def _match(requirement_id: str, match_level: str, evidence_ids: list[str]) -> MatchItem:
    return MatchItem(
        requirement_id=requirement_id,
        match_level=match_level,
        rationale="Evidence supports this requirement.",
        evidence_ids=evidence_ids,
        gap_note=None if evidence_ids else "No supporting evidence found.",
    )


def _assets_json(
    target_requirement_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    risk_level: str = "low",
    text: str = "Built Python APIs backed by project evidence.",
) -> str:
    target_requirement_ids = target_requirement_ids or ["req_python"]
    evidence_ids = ["ev_python"] if evidence_ids is None else evidence_ids
    return json.dumps(
        {
            "match_summary": "Strong fit for Python API work.",
            "resume_bullets": [
                {
                    "text": text,
                    "target_requirement_ids": target_requirement_ids,
                    "evidence_ids": evidence_ids,
                    "risk_level": risk_level,
                }
            ],
            "interview_prep": [
                {
                    "topic": "Python API project",
                    "why_it_matters": "The role asks for API development.",
                    "supporting_evidence_ids": evidence_ids,
                    "prep_suggestion": "Prepare a concise project walkthrough.",
                }
            ],
        }
    )


def _selection(evidence_id: str) -> EvidenceSelection:
    return EvidenceSelection(
        requirement_id="req_python",
        selected_evidence_ids=[evidence_id],
        support_level="strong",
        support_types=["direct"],
        rationale="The selected project directly supports the requirement.",
    )


class _SequentialWriterClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, prompt_key, prompt, variables):
        self.calls.append(
            {"prompt_key": prompt_key, "prompt": prompt, "variables": variables}
        )
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]

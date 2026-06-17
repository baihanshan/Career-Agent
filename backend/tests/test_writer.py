import json

from backend.app.api.schemas import EvidenceItem, JDRequirement, MatchItem
from backend.app.llm.client import FakeLLMClient, LLMService
from backend.app.llm.prompts import APPLICATION_GENERATION_PROMPT
from backend.app.workflow.writer import (
    build_writer_context,
    write_application,
)


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


def test_missing_evidence_ids_are_replaced_with_matching_evidence():
    service = LLMService(
        client=FakeLLMClient(
            responses={"generate_application_assets": _assets_json(evidence_ids=[], risk_level="low")}
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        llm_service=service,
    )

    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert assets.resume_bullets[0].risk_level == "low"


def test_unknown_evidence_ids_are_replaced_with_matching_evidence():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": _assets_json(
                    evidence_ids=["made_up_evidence_id"],
                    risk_level="low",
                )
            }
        )
    )

    assets = write_application(
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        match_items=[_match("req_python", "strong", ["ev_python"])],
        llm_service=service,
    )

    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert assets.resume_bullets[0].risk_level == "low"


def test_missing_requirement_bullet_is_downgraded_to_high_risk():
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

    assets = write_application(
        requirements=[_requirement("req_missing")],
        evidence_items=[],
        match_items=[_match("req_missing", "missing", [])],
        llm_service=service,
    )

    assert assets.resume_bullets[0].risk_level == "high"
    assert assets.resume_bullets[0].evidence_ids == []


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


def test_interview_prep_contains_topic_reason_and_suggestion():
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

    prep_item = assets.interview_prep[0]
    assert prep_item.topic == "Python API project"
    assert prep_item.why_it_matters
    assert prep_item.prep_suggestion


def test_writer_prompt_contains_evidence_only_constraints():
    prompt = APPLICATION_GENERATION_PROMPT.lower()

    assert "evidence-only" in prompt
    assert "do not fabricate" in prompt
    assert "employers, dates, numbers, tools, outcomes" in prompt
    assert "exactly 3 resume_bullets" in prompt
    assert "skills only as supporting context" in prompt
    assert "project and internship evidence first" in prompt


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

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


def test_cover_letter_contains_opening_body_and_closing():
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

    assert assets.cover_letter.opening
    assert assets.cover_letter.body == ["My Python API project aligns with the role."]
    assert assets.cover_letter.closing


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


def _requirement(requirement_id: str) -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text="Build Python APIs",
        importance="high",
        keywords=["Python", "API"],
    )


def _evidence(evidence_id: str, requirement_id: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id="chunk_python",
        source_name="resume.md",
        section_label="Projects",
        snippet="Built Python FastAPI services.",
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
            "cover_letter": {
                "opening": "I am excited about this backend role.",
                "body": ["My Python API project aligns with the role."],
                "closing": "Thank you for your consideration.",
                "evidence_ids": evidence_ids,
            },
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

import pytest

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.llm.client import FakeLLMClient, LLMService
from backend.app.llm.prompts import (
    APPLICATION_GENERATION_PROMPT,
    GROUNDING_EVALUATION_PROMPT,
    JD_REQUIREMENTS_PROMPT,
)
from backend.app.llm.structured_outputs import LLMOutputParseError


def test_fake_client_extracts_sample_jd_requirements():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "extract_jd_requirements": """
                [
                  {
                    "requirement_id": "req_python",
                    "category": "hard_skill",
                    "text": "Build Python APIs",
                    "importance": "high",
                    "keywords": ["Python", "API"]
                  }
                ]
                """
            }
        )
    )

    requirements = service.extract_jd_requirements("We need someone to build Python APIs.")

    assert requirements == [
        JDRequirement(
            requirement_id="req_python",
            category="hard_skill",
            text="Build Python APIs",
            importance="high",
            keywords=["Python", "API"],
        )
    ]


def test_malformed_requirements_json_raises_parse_error():
    service = LLMService(
        client=FakeLLMClient(responses={"extract_jd_requirements": "{not json"})
    )

    with pytest.raises(LLMOutputParseError):
        service.extract_jd_requirements("Bad output please.")


def test_application_assets_json_parses_to_generated_assets():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "generate_application_assets": """
                {
                  "match_summary": "Strong fit for API work.",
                  "resume_bullets": [
                    {
                      "text": "Built Python APIs backed by project evidence.",
                      "target_requirement_ids": ["req_python"],
                      "evidence_ids": ["ev_python"],
                      "risk_level": "low"
                    }
                  ],
                  "cover_letter": {
                    "opening": "I am excited about the API role.",
                    "body": ["My Python API project aligns with your backend needs."],
                    "closing": "Thank you for your consideration.",
                    "evidence_ids": ["ev_python"]
                  },
                  "interview_prep": [
                    {
                      "topic": "Python API project",
                      "why_it_matters": "The role asks for API development.",
                      "supporting_evidence_ids": ["ev_python"],
                      "prep_suggestion": "Prepare a concise project walkthrough."
                    }
                  ]
                }
                """
            }
        )
    )

    assets = service.generate_application_assets(
        context={
            "requirements": [_requirement()],
            "evidence": [_evidence()],
            "match_analysis": [],
        }
    )

    assert assets.resume_bullets[0].evidence_ids == ["ev_python"]
    assert assets.cover_letter.evidence_ids == ["ev_python"]


def test_grounding_evaluation_json_parses_to_evaluation_report():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "evaluate_claim_grounding": """
                {
                  "grounding_warnings": [
                    {
                      "asset_type": "resume_bullet",
                      "asset_id": "bullet_1",
                      "claim": "Scaled the service to one million users.",
                      "reason": "The evidence does not mention scale.",
                      "severity": "high"
                    }
                  ],
                  "coverage_gaps": [
                    {
                      "requirement_id": "req_python",
                      "reason": "Needs stronger production API evidence.",
                      "severity": "medium"
                    }
                  ],
                  "specificity_notes": ["Add project context."],
                  "risk_summary": "One unsupported scale claim.",
                  "overall_status": "pass_with_warnings"
                }
                """
            }
        )
    )

    report = service.evaluate_claim_grounding(
        claims=["Scaled the service to one million users."],
        evidence_items=[_evidence()],
    )

    assert report.grounding_warnings[0].severity == "high"
    assert report.coverage_gaps[0].requirement_id == "req_python"
    assert report.overall_status == "pass_with_warnings"


def test_prompts_explicitly_forbid_fabricating_experience():
    prompts = "\n".join(
        [JD_REQUIREMENTS_PROMPT, APPLICATION_GENERATION_PROMPT, GROUNDING_EVALUATION_PROMPT]
    ).lower()

    assert "do not fabricate" in prompts
    assert "evidence" in prompts


def _requirement() -> JDRequirement:
    return JDRequirement(
        requirement_id="req_python",
        category="hard_skill",
        text="Build Python APIs",
        importance="high",
        keywords=["Python", "API"],
    )


def _evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev_python",
        requirement_id="req_python",
        chunk_id="chunk_python",
        source_name="resume.md",
        section_label="Projects",
        snippet="Built Python FastAPI services.",
        score=0.91,
    )

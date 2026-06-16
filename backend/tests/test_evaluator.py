import json

from backend.app.api.schemas import (
    CoverLetterDraft,
    EvidenceItem,
    GeneratedAssets,
    InterviewPrepItem,
    JDRequirement,
    ResumeBullet,
)
from backend.app.evaluation.evaluator import evaluate_generated_assets
from backend.app.llm.client import FakeLLMClient, LLMService


def test_resume_bullet_without_evidence_id_produces_grounding_warning():
    assets = _assets(
        resume_bullets=[
            ResumeBullet(
                text="Built production-ready Python APIs.",
                target_requirement_ids=["req_python"],
                evidence_ids=[],
                risk_level="high",
            )
        ]
    )

    report = evaluate_generated_assets(
        assets=assets,
        requirements=[_requirement("req_python")],
        evidence_items=[],
    )

    assert report.grounding_warnings[0].asset_type == "resume_bullet"
    assert report.grounding_warnings[0].asset_id == "resume_bullet:1"
    assert report.grounding_warnings[0].severity == "high"


def test_number_not_present_in_evidence_produces_high_severity_warning():
    assets = _assets(
        resume_bullets=[
            ResumeBullet(
                text="Built Python APIs serving 1000 users.",
                target_requirement_ids=["req_python"],
                evidence_ids=["ev_python"],
                risk_level="low",
            )
        ]
    )

    report = evaluate_generated_assets(
        assets=assets,
        requirements=[_requirement("req_python")],
        evidence_items=[
            _evidence(
                "ev_python",
                "req_python",
                snippet="Built Python FastAPI services for a course project.",
            )
        ],
    )

    assert report.grounding_warnings[0].severity == "high"
    assert "1000" in report.grounding_warnings[0].claim


def test_uncovered_high_importance_requirement_produces_coverage_gap():
    report = evaluate_generated_assets(
        assets=_assets(resume_bullets=[]),
        requirements=[_requirement("req_python", importance="high")],
        evidence_items=[],
    )

    assert report.coverage_gaps[0].requirement_id == "req_python"
    assert report.coverage_gaps[0].severity == "high"


def test_generic_resume_bullet_produces_specificity_note():
    assets = _assets(
        resume_bullets=[
            ResumeBullet(
                text="Worked on AI.",
                target_requirement_ids=["req_python"],
                evidence_ids=["ev_python"],
                risk_level="low",
            )
        ]
    )

    report = evaluate_generated_assets(
        assets=assets,
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
    )

    assert report.specificity_notes == [
        "Resume bullet 1 is too generic; add concrete project context, action, or evidence."
    ]


def test_high_severity_warning_sets_overall_status_to_fail():
    assets = _assets(
        resume_bullets=[
            ResumeBullet(
                text="Built Python APIs serving 1000 users.",
                target_requirement_ids=["req_python"],
                evidence_ids=["ev_python"],
                risk_level="low",
            )
        ]
    )

    report = evaluate_generated_assets(
        assets=assets,
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
    )

    assert report.overall_status == "fail"
    assert report.risk_summary == "High-risk grounding issues found."


def test_fake_llm_semantic_grounding_warnings_are_included():
    service = LLMService(
        client=FakeLLMClient(
            responses={
                "evaluate_claim_grounding": json.dumps(
                    {
                        "grounding_warnings": [
                            {
                                "asset_type": "resume_bullet",
                                "asset_id": "semantic:1",
                                "claim": "Production-ready API.",
                                "reason": "Evidence does not support production readiness.",
                                "severity": "medium",
                            }
                        ],
                        "coverage_gaps": [],
                        "specificity_notes": [],
                        "risk_summary": "Semantic grounding warning.",
                        "overall_status": "pass_with_warnings",
                    }
                )
            }
        )
    )

    report = evaluate_generated_assets(
        assets=_assets(
            resume_bullets=[
                ResumeBullet(
                    text="Built production-ready Python APIs.",
                    target_requirement_ids=["req_python"],
                    evidence_ids=["ev_python"],
                    risk_level="low",
                )
            ]
        ),
        requirements=[_requirement("req_python")],
        evidence_items=[_evidence("ev_python", "req_python")],
        llm_service=service,
    )

    assert [warning.asset_id for warning in report.grounding_warnings] == ["semantic:1"]
    assert service.client.calls[0]["prompt_key"] == "evaluate_claim_grounding"


def _assets(resume_bullets: list[ResumeBullet]) -> GeneratedAssets:
    return GeneratedAssets(
        match_summary="Python API fit.",
        resume_bullets=resume_bullets,
        cover_letter=CoverLetterDraft(
            opening="I am excited to apply.",
            body=["My Python API work aligns with the role."],
            closing="Thank you for your consideration.",
            evidence_ids=["ev_python"],
        ),
        interview_prep=[
            InterviewPrepItem(
                topic="Python API project",
                why_it_matters="The role asks for API development.",
                supporting_evidence_ids=["ev_python"],
                prep_suggestion="Prepare a concise project walkthrough.",
            )
        ],
    )


def _requirement(requirement_id: str, importance: str = "high") -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text="Build Python APIs",
        importance=importance,
        keywords=["Python", "API"],
    )


def _evidence(
    evidence_id: str,
    requirement_id: str,
    snippet: str = "Built Python FastAPI services.",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id="chunk_python",
        source_name="resume.md",
        section_label="Projects",
        snippet=snippet,
        score=0.91,
    )

from __future__ import annotations

from typing import Any, Mapping

from backend.app.api.schemas import (
    EvidenceItem,
    GeneratedAssets,
    JDRequirement,
    MatchItem,
    ResumeBullet,
)
from backend.app.llm.client import LLMService


class WriterOutputError(ValueError):
    pass


def build_writer_context(
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
    match_items: list[MatchItem],
) -> dict[str, Any]:
    return {
        "requirements": [requirement.model_dump() for requirement in requirements],
        "evidence": [item.model_dump() for item in evidence_items],
        "match_analysis": [item.model_dump() for item in match_items],
        "evidence_ids": [item.evidence_id for item in evidence_items],
        "missing_requirement_ids": [
            item.requirement_id for item in match_items if item.match_level == "missing"
        ],
        "generation_rules": [
            "Use evidence-only claims for user experience.",
            "Every confident resume bullet must include evidence_ids.",
            "Do not fabricate employers, dates, numbers, tools, outcomes, or responsibilities.",
            "Missing requirements may only produce high-risk caveats or interview prep.",
        ],
    }


def write_application(
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
    match_items: list[MatchItem],
    llm_service: LLMService,
) -> GeneratedAssets:
    context = build_writer_context(
        requirements=requirements,
        evidence_items=evidence_items,
        match_items=match_items,
    )
    assets = llm_service.generate_application_assets(context=context)
    return _validate_and_downgrade_assets(assets, context)


def _validate_and_downgrade_assets(
    assets: GeneratedAssets,
    context: Mapping[str, Any],
) -> GeneratedAssets:
    evidence_ids = set(context["evidence_ids"])
    missing_requirement_ids = set(context["missing_requirement_ids"])
    resume_bullets = [
        _validate_and_downgrade_bullet(
            bullet=bullet,
            evidence_ids=evidence_ids,
            missing_requirement_ids=missing_requirement_ids,
        )
        for bullet in assets.resume_bullets
    ]
    return assets.model_copy(update={"resume_bullets": resume_bullets})


def _validate_and_downgrade_bullet(
    bullet: ResumeBullet,
    evidence_ids: set[str],
    missing_requirement_ids: set[str],
) -> ResumeBullet:
    unknown_evidence_ids = [item for item in bullet.evidence_ids if item not in evidence_ids]
    if unknown_evidence_ids:
        raise WriterOutputError(
            f"Resume bullet references unknown evidence ids: {', '.join(unknown_evidence_ids)}"
        )

    targets_missing_requirement = any(
        requirement_id in missing_requirement_ids
        for requirement_id in bullet.target_requirement_ids
    )
    if targets_missing_requirement:
        return bullet.model_copy(update={"risk_level": "high"})

    if not bullet.evidence_ids and bullet.risk_level != "high":
        raise WriterOutputError(
            "Resume bullets without evidence must be marked high risk."
        )

    return bullet

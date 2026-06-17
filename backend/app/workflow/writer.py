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
            "Generate exactly 3 resume bullets.",
            "Prioritize project and internship evidence before skill evidence.",
            "Use skill evidence only as supporting context, never as a standalone bullet.",
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
            context=context,
        )
        for bullet in assets.resume_bullets
    ]
    return assets.model_copy(update={"resume_bullets": resume_bullets})


def _validate_and_downgrade_bullet(
    bullet: ResumeBullet,
    evidence_ids: set[str],
    missing_requirement_ids: set[str],
    context: Mapping[str, Any],
) -> ResumeBullet:
    known_bullet_evidence_ids = [
        item for item in bullet.evidence_ids if item in evidence_ids
    ]
    if known_bullet_evidence_ids != bullet.evidence_ids:
        known_bullet_evidence_ids = known_bullet_evidence_ids or _fallback_evidence_ids(
            bullet.target_requirement_ids,
            context,
            evidence_ids,
        )
        bullet = bullet.model_copy(update={"evidence_ids": known_bullet_evidence_ids})

    targets_missing_requirement = any(
        requirement_id in missing_requirement_ids
        for requirement_id in bullet.target_requirement_ids
    )
    if targets_missing_requirement:
        return bullet.model_copy(update={"risk_level": "high"})

    if _uses_only_skill_evidence(bullet, context):
        return bullet.model_copy(
            update={
                "text": "需要补充项目或实习证据后，再将技能点转化为可展示的简历要点。",
                "risk_level": "high",
            }
        )

    if not bullet.evidence_ids and bullet.risk_level != "high":
        return bullet.model_copy(update={"risk_level": "high"})

    return bullet


def _uses_only_skill_evidence(bullet: ResumeBullet, context: Mapping[str, Any]) -> bool:
    if not bullet.evidence_ids:
        return False
    evidence_by_id = {
        item["evidence_id"]: item
        for item in context["evidence"]
        if item.get("evidence_id")
    }
    bullet_evidence = [
        evidence_by_id[evidence_id]
        for evidence_id in bullet.evidence_ids
        if evidence_id in evidence_by_id
    ]
    return bool(bullet_evidence) and all(
        item.get("section_type") == "skill" for item in bullet_evidence
    )


def _fallback_evidence_ids(
    requirement_ids: list[str],
    context: Mapping[str, Any],
    known_evidence_ids: set[str],
) -> list[str]:
    for match_item in context["match_analysis"]:
        if match_item["requirement_id"] in requirement_ids:
            return [
                evidence_id
                for evidence_id in match_item["evidence_ids"]
                if evidence_id in known_evidence_ids
            ]
    return []

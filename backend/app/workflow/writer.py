from __future__ import annotations

from typing import Any, Mapping

from backend.app.api.schemas import (
    EvidenceItem,
    GeneratedAssets,
    JDRequirement,
    MatchItem,
    ResumeBullet,
)
from backend.app.evaluation.quality_gate import (
    PublicOutputQualityGate,
    quality_issues_to_retry_message,
)
from backend.app.llm.client import LLMService
from backend.app.workflow.domain_models import EvidenceSelection, QualityIssue
from backend.app.workflow.public_output import InternalIdLeakDetector


class WriterOutputError(ValueError):
    def __init__(self, issues: list[QualityIssue]) -> None:
        super().__init__("Resume bullets failed deterministic safety validation.")
        self.issues = issues


def build_writer_context(
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
    match_items: list[MatchItem],
    evidence_selections: list[EvidenceSelection] | None = None,
    allowed_evidence_ids: set[str] | None = None,
) -> dict[str, Any]:
    selected_ids = {
        evidence_id
        for selection in evidence_selections or []
        for evidence_id in selection.selected_evidence_ids
    }
    source_ids = {item.evidence_id for item in evidence_items}
    runtime_allowlist = (
        source_ids if allowed_evidence_ids is None else set(allowed_evidence_ids)
    )
    effective_ids = (
        selected_ids & runtime_allowlist
        if evidence_selections is not None
        else runtime_allowlist
    )
    return {
        "requirements": [requirement.model_dump() for requirement in requirements],
        "evidence": [item.model_dump() for item in evidence_items],
        "evidence_selections": [
            item.model_dump(mode="json") for item in evidence_selections or []
        ],
        "match_analysis": [item.model_dump() for item in match_items],
        "evidence_ids": sorted(effective_ids),
        "missing_requirement_ids": [
            item.requirement_id for item in match_items if item.match_level == "missing"
        ],
        "generation_rules": [
            "Use evidence-only claims for user experience.",
            "Write all user-visible natural-language output in Simplified Chinese.",
            "Keep JSON keys, enum values, and internal IDs in the required schema form.",
            "Keep internal IDs only in structured JSON reference fields.",
            "Never put evidence, requirement, or chunk IDs in user-visible text.",
            "Do not fabricate employers, dates, numbers, tools, outcomes, or responsibilities.",
            "Missing requirements may only produce high-risk caveats or interview prep.",
            "Generate exactly 3 resume bullets.",
            "Prioritize project and internship evidence before skill evidence.",
            "Use contextual skill evidence only as context, never as a practice achievement.",
        ],
    }


def write_application(
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
    match_items: list[MatchItem],
    llm_service: LLMService,
    evidence_selections: list[EvidenceSelection] | None = None,
    allowed_evidence_ids: set[str] | None = None,
) -> GeneratedAssets:
    context = build_writer_context(
        requirements=requirements,
        evidence_items=evidence_items,
        match_items=match_items,
        evidence_selections=evidence_selections,
        allowed_evidence_ids=allowed_evidence_ids,
    )
    last_issues: list[QualityIssue] = []
    for attempt in range(2):
        assets = llm_service.generate_application_assets(context=context)
        assets = _downgrade_unsupported_assets(assets, context)
        last_issues = _validate_assets(assets, context)
        if not last_issues:
            return assets
        if attempt == 0:
            context = {
                **context,
                "quality_retry_feedback": quality_issues_to_retry_message(last_issues),
            }
    raise WriterOutputError(last_issues)


def _validate_assets(
    assets: GeneratedAssets,
    context: Mapping[str, Any],
) -> list[QualityIssue]:
    gate = PublicOutputQualityGate()
    issues = [
        QualityIssue(
            code="UNKNOWN_EVIDENCE_ID",
            field_path=f"resume_bullets.{index}.evidence_ids",
            message="A resume bullet has no traceable evidence reference.",
            retry_instruction=(
                "Reference at least one evidence ID returned by tools in the current "
                "Agent invocation."
            ),
            severity="high",
        )
        for index, bullet in enumerate(assets.resume_bullets)
        if not bullet.evidence_ids
    ]
    issues.extend(
        gate.validate_evidence_allowlist(
            {
                f"resume_bullets.{index}.evidence_ids": bullet.evidence_ids
                for index, bullet in enumerate(assets.resume_bullets)
            },
            set(context["evidence_ids"]),
        )
    )
    visible_payload = {
        "match_summary": assets.match_summary,
        "resume_bullets": [bullet.text for bullet in assets.resume_bullets],
        "interview_questions": [
            {
                "question": item.question,
                "sample_answer": item.sample_answer,
            }
            for item in [
                *assets.interview_prep.jd_questions,
                *assets.interview_prep.resume_deep_dive_questions,
            ]
        ],
    }
    issues.extend(
        QualityIssue(
            code="INTERNAL_ID_LEAK",
            field_path=path,
            message="A user-visible generated field contains an internal reference.",
            retry_instruction="Rewrite the field as natural language without internal IDs.",
            severity="high",
        )
        for path in InternalIdLeakDetector().find_leaks(visible_payload)
    )
    return sorted(issues, key=lambda item: (item.field_path, item.code))


def _downgrade_unsupported_assets(
    assets: GeneratedAssets,
    context: Mapping[str, Any],
) -> GeneratedAssets:
    missing_requirement_ids = set(context["missing_requirement_ids"])
    resume_bullets = [
        _downgrade_bullet(
            bullet=bullet,
            missing_requirement_ids=missing_requirement_ids,
            context=context,
        )
        for bullet in assets.resume_bullets
    ]
    return assets.model_copy(update={"resume_bullets": resume_bullets})


def _downgrade_bullet(
    bullet: ResumeBullet,
    missing_requirement_ids: set[str],
    context: Mapping[str, Any],
) -> ResumeBullet:
    if any(
        requirement_id in missing_requirement_ids
        for requirement_id in bullet.target_requirement_ids
    ):
        bullet = bullet.model_copy(update={"risk_level": "high"})

    if _uses_only_contextual_skill_evidence(bullet, context):
        return bullet.model_copy(
            update={
                "text": "该技能目前仅有技能列表佐证，需要补充项目或实习中的实际应用后再写入简历要点。",
                "risk_level": "high",
            }
        )

    if not bullet.evidence_ids and bullet.risk_level != "high":
        return bullet.model_copy(update={"risk_level": "high"})
    return bullet


def _uses_only_contextual_skill_evidence(
    bullet: ResumeBullet,
    context: Mapping[str, Any],
) -> bool:
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
    if not bullet_evidence or not all(
        item.get("section_type") == "skill" for item in bullet_evidence
    ):
        return False
    selection_by_evidence = {
        evidence_id: selection
        for selection in context.get("evidence_selections", [])
        for evidence_id in selection.get("selected_evidence_ids", [])
    }
    return all(
        not selection_by_evidence.get(item["evidence_id"])
        or "contextual"
        in selection_by_evidence[item["evidence_id"]].get("support_types", [])
        for item in bullet_evidence
    )

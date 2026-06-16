from __future__ import annotations

import re

from backend.app.api.schemas import (
    CoverageGap,
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    GroundingWarning,
    JDRequirement,
    ResumeBullet,
)
from backend.app.llm.client import LLMService


_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")


def evaluate_generated_assets(
    assets: GeneratedAssets,
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
    llm_service: LLMService | None = None,
) -> EvaluationReport:
    grounding_warnings = _check_resume_bullet_grounding(
        resume_bullets=assets.resume_bullets,
        evidence_items=evidence_items,
    )
    coverage_gaps = _check_coverage(
        resume_bullets=assets.resume_bullets,
        requirements=requirements,
    )
    specificity_notes = _check_specificity(assets.resume_bullets)

    if llm_service is not None:
        semantic_report = llm_service.evaluate_claim_grounding(
            claims=_claims_from_assets(assets),
            evidence_items=evidence_items,
        )
        grounding_warnings.extend(semantic_report.grounding_warnings)
        coverage_gaps.extend(semantic_report.coverage_gaps)
        specificity_notes.extend(semantic_report.specificity_notes)

    overall_status = _overall_status(
        grounding_warnings=grounding_warnings,
        coverage_gaps=coverage_gaps,
        specificity_notes=specificity_notes,
    )
    return EvaluationReport(
        grounding_warnings=grounding_warnings,
        coverage_gaps=coverage_gaps,
        specificity_notes=specificity_notes,
        risk_summary=_risk_summary(overall_status),
        overall_status=overall_status,
    )


def _check_resume_bullet_grounding(
    resume_bullets: list[ResumeBullet],
    evidence_items: list[EvidenceItem],
) -> list[GroundingWarning]:
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    warnings: list[GroundingWarning] = []
    for index, bullet in enumerate(resume_bullets, start=1):
        asset_id = f"resume_bullet:{index}"
        if not bullet.evidence_ids:
            warnings.append(
                GroundingWarning(
                    asset_type="resume_bullet",
                    asset_id=asset_id,
                    claim=bullet.text,
                    reason="Resume bullet does not cite any evidence ids.",
                    severity="high",
                )
            )
            continue

        unknown_ids = [item for item in bullet.evidence_ids if item not in evidence_by_id]
        if unknown_ids:
            warnings.append(
                GroundingWarning(
                    asset_type="resume_bullet",
                    asset_id=asset_id,
                    claim=bullet.text,
                    reason=f"Resume bullet cites unknown evidence ids: {', '.join(unknown_ids)}.",
                    severity="high",
                )
            )
            continue

        warnings.extend(
            _check_number_grounding(
                claim=bullet.text,
                asset_id=asset_id,
                evidence_items=[evidence_by_id[item] for item in bullet.evidence_ids],
            )
        )
    return warnings


def _check_number_grounding(
    claim: str,
    asset_id: str,
    evidence_items: list[EvidenceItem],
) -> list[GroundingWarning]:
    claim_numbers = _normalized_numbers(claim)
    if not claim_numbers:
        return []

    evidence_numbers: set[str] = set()
    for evidence_item in evidence_items:
        evidence_numbers.update(_normalized_numbers(evidence_item.snippet))

    unsupported_numbers = sorted(claim_numbers - evidence_numbers)
    return [
        GroundingWarning(
            asset_type="resume_bullet",
            asset_id=asset_id,
            claim=claim,
            reason=f"Number {number} does not appear in the cited evidence.",
            severity="high",
        )
        for number in unsupported_numbers
    ]


def _check_coverage(
    resume_bullets: list[ResumeBullet],
    requirements: list[JDRequirement],
) -> list[CoverageGap]:
    covered_requirement_ids = {
        requirement_id
        for bullet in resume_bullets
        for requirement_id in bullet.target_requirement_ids
    }
    return [
        CoverageGap(
            requirement_id=requirement.requirement_id,
            reason="High-importance requirement is not covered by generated resume bullets.",
            severity="high",
        )
        for requirement in requirements
        if requirement.importance == "high"
        and requirement.requirement_id not in covered_requirement_ids
    ]


def _check_specificity(resume_bullets: list[ResumeBullet]) -> list[str]:
    notes: list[str] = []
    for index, bullet in enumerate(resume_bullets, start=1):
        words = re.findall(r"[A-Za-z0-9]+", bullet.text)
        if len(words) < 6:
            notes.append(
                f"Resume bullet {index} is too generic; add concrete project context, action, or evidence."
            )
    return notes


def _claims_from_assets(assets: GeneratedAssets) -> list[str]:
    claims = [bullet.text for bullet in assets.resume_bullets]
    claims.extend(assets.cover_letter.body)
    claims.extend(item.prep_suggestion for item in assets.interview_prep)
    return claims


def _normalized_numbers(text: str) -> set[str]:
    return {
        match.group(0).replace(",", "").rstrip("%")
        for match in _NUMBER_PATTERN.finditer(text)
    }


def _overall_status(
    grounding_warnings: list[GroundingWarning],
    coverage_gaps: list[CoverageGap],
    specificity_notes: list[str],
) -> str:
    if any(warning.severity == "high" for warning in grounding_warnings):
        return "fail"
    if grounding_warnings or coverage_gaps or specificity_notes:
        return "pass_with_warnings"
    return "pass"


def _risk_summary(overall_status: str) -> str:
    if overall_status == "fail":
        return "High-risk grounding issues found."
    if overall_status == "pass_with_warnings":
        return "Review warnings before using generated content."
    return "No major grounding risks found."

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
        try:
            semantic_report = llm_service.evaluate_claim_grounding(
                claims=_claims_from_assets(assets),
                evidence_items=evidence_items,
            )
            grounding_warnings.extend(semantic_report.grounding_warnings)
            coverage_gaps.extend(
                _with_requirement_texts(
                    coverage_gaps=semantic_report.coverage_gaps,
                    requirements=requirements,
                )
            )
            specificity_notes.extend(semantic_report.specificity_notes)
        except Exception:
            specificity_notes.append(
                "语义证据评估未完成；已保留规则评估结果，请人工复核生成内容。"
            )

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
                    reason="该简历要点没有引用任何证据 id。",
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
                    reason=f"该简历要点引用了未知的证据 id：{', '.join(unknown_ids)}。",
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
            reason=f"数字 {number} 没有出现在引用的证据中。",
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
            requirement_text=requirement.text,
            reason="高优先级岗位要求没有被生成的简历要点覆盖。",
            severity="high",
        )
        for requirement in requirements
        if requirement.importance == "high"
        and requirement.requirement_id not in covered_requirement_ids
    ]


def _with_requirement_texts(
    coverage_gaps: list[CoverageGap],
    requirements: list[JDRequirement],
) -> list[CoverageGap]:
    text_by_id = {item.requirement_id: item.text for item in requirements}
    return [
        gap
        if gap.requirement_text
        else gap.model_copy(update={"requirement_text": text_by_id.get(gap.requirement_id)})
        for gap in coverage_gaps
    ]


def _check_specificity(resume_bullets: list[ResumeBullet]) -> list[str]:
    notes: list[str] = []
    for index, bullet in enumerate(resume_bullets, start=1):
        words = re.findall(r"[A-Za-z0-9]+", bullet.text)
        chinese_characters = re.findall(r"[\u4e00-\u9fff]", bullet.text)
        if len(words) < 6 and len(chinese_characters) < 18:
            notes.append(
                f"第 {index} 条简历要点过于笼统，建议补充具体项目背景、行动或证据。"
            )
    return notes


def _claims_from_assets(assets: GeneratedAssets) -> list[str]:
    claims = [bullet.text for bullet in assets.resume_bullets]
    questions = [
        *assets.interview_prep.jd_questions,
        *assets.interview_prep.resume_deep_dive_questions,
    ]
    claims.extend(item.sample_answer for item in questions)
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
        return "发现高风险证据支撑问题。"
    if overall_status == "pass_with_warnings":
        return "使用生成内容前，请先检查风险提示。"
    return "未发现明显的证据支撑风险。"

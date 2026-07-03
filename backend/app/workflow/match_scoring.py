from __future__ import annotations

from backend.app.api.schemas import (
    EvidenceItem,
    JDRequirement,
    MatchItem,
    MatchStrategy,
    MatchStrategyItem,
)


STRONG_SCORE_THRESHOLD = 0.75
PARTIAL_SCORE_THRESHOLD = 0.45


def score_requirement(
    requirement: JDRequirement,
    evidence_items: list[EvidenceItem],
) -> MatchItem:
    requirement_evidence = _evidence_for_requirement(requirement, evidence_items)
    if not requirement_evidence:
        return MatchItem(
            requirement_id=requirement.requirement_id,
            match_level="missing",
            rationale="No relevant evidence was found for this requirement.",
            evidence_ids=[],
            gap_note="No supporting evidence found.",
        )

    best_score = _priority_score(requirement_evidence[0])
    evidence_ids = [item.evidence_id for item in requirement_evidence]

    if best_score >= STRONG_SCORE_THRESHOLD:
        return MatchItem(
            requirement_id=requirement.requirement_id,
            match_level="strong",
            rationale="High-scoring evidence directly supports this requirement.",
            evidence_ids=evidence_ids,
            gap_note=None,
        )

    if best_score >= PARTIAL_SCORE_THRESHOLD:
        return MatchItem(
            requirement_id=requirement.requirement_id,
            match_level="partial",
            rationale="Evidence is relevant, but may not fully cover the requirement.",
            evidence_ids=evidence_ids,
            gap_note="Evidence is relevant but may not fully cover the requirement.",
        )

    return MatchItem(
        requirement_id=requirement.requirement_id,
        match_level="weak",
        rationale="Only weak or indirect evidence supports this requirement.",
        evidence_ids=evidence_ids,
        gap_note="Evidence is weak or indirect.",
    )


def score_matches(
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
) -> list[MatchItem]:
    return [score_requirement(requirement, evidence_items) for requirement in requirements]


def build_match_strategy(
    requirements: list[JDRequirement],
    evidence_items: list[EvidenceItem],
    match_items: list[MatchItem],
) -> MatchStrategy:
    covered_requirement_ids = [
        match.requirement_id
        for match in match_items
        if match.match_level in {"strong", "partial", "weak"}
    ]
    missing_requirement_ids = [
        requirement.requirement_id
        for requirement in requirements
        if requirement.requirement_id not in covered_requirement_ids
    ]
    ranked_evidence = [
        MatchStrategyItem(
            evidence_id=item.evidence_id,
            section_type=item.section_type,
            priority_score=_priority_score(item),
            rationale=_strategy_rationale(item),
            requirement_id=item.requirement_id,
        )
        for item in evidence_items
    ]
    ranked_evidence = sorted(
        ranked_evidence,
        key=lambda item: item.priority_score,
        reverse=True,
    )
    return MatchStrategy(
        ranked_evidence=ranked_evidence,
        covered_requirement_ids=covered_requirement_ids,
        missing_requirement_ids=missing_requirement_ids,
        summary=(
            f"{len(covered_requirement_ids)} requirement(s) covered; "
            f"{len(missing_requirement_ids)} missing."
        ),
    )


def _evidence_for_requirement(
    requirement: JDRequirement,
    evidence_items: list[EvidenceItem],
) -> list[EvidenceItem]:
    relevant_items = [
        item for item in evidence_items if item.requirement_id == requirement.requirement_id
    ]
    return sorted(relevant_items, key=_priority_score, reverse=True)


def _priority_score(evidence: EvidenceItem) -> float:
    section_adjustment = {
        "project": 0.15,
        "internship": 0.15,
        "skill": -0.15,
        "education": -0.05,
        "other": 0.0,
    }.get(evidence.section_type, 0.0)
    return max(0.0, min(1.0, round(evidence.score + section_adjustment, 6)))


def _strategy_rationale(evidence: EvidenceItem) -> str:
    if evidence.section_type in {"project", "internship"}:
        return "Project/internship evidence is prioritized for resume bullet generation."
    if evidence.section_type == "skill":
        return "Skill evidence is useful as support but lower priority than project/internship evidence."
    return "Evidence is ranked by JD match score with section priority adjustment."

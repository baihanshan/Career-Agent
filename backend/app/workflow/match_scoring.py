from __future__ import annotations

from backend.app.api.schemas import EvidenceItem, JDRequirement, MatchItem


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

    best_score = requirement_evidence[0].score
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


def _evidence_for_requirement(
    requirement: JDRequirement,
    evidence_items: list[EvidenceItem],
) -> list[EvidenceItem]:
    relevant_items = [
        item for item in evidence_items if item.requirement_id == requirement.requirement_id
    ]
    return sorted(relevant_items, key=lambda item: item.score, reverse=True)

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.workflow.match_scoring import score_matches, score_requirement


def test_requirement_without_evidence_is_missing():
    match = score_requirement(_requirement("req_python"), [])

    assert match.requirement_id == "req_python"
    assert match.match_level == "missing"
    assert match.evidence_ids == []
    assert match.gap_note == "No supporting evidence found."


def test_high_score_evidence_returns_strong_match():
    match = score_requirement(
        _requirement("req_python"),
        [_evidence("ev_python", "req_python", score=0.86)],
    )

    assert match.match_level == "strong"
    assert match.evidence_ids == ["ev_python"]
    assert match.gap_note is None


def test_medium_score_evidence_returns_partial_match():
    match = score_requirement(
        _requirement("req_python"),
        [_evidence("ev_python", "req_python", score=0.55)],
    )

    assert match.match_level == "partial"
    assert match.evidence_ids == ["ev_python"]
    assert match.gap_note == "Evidence is relevant but may not fully cover the requirement."


def test_low_score_evidence_returns_weak_match():
    match = score_requirement(
        _requirement("req_python"),
        [_evidence("ev_python", "req_python", score=0.24)],
    )

    assert match.match_level == "weak"
    assert match.evidence_ids == ["ev_python"]
    assert match.gap_note == "Evidence is weak or indirect."


def test_score_matches_returns_one_match_per_requirement():
    requirements = [_requirement("req_python"), _requirement("req_design")]
    evidence_items = [_evidence("ev_python", "req_python", score=0.91)]

    matches = score_matches(requirements, evidence_items)

    assert [match.requirement_id for match in matches] == ["req_python", "req_design"]
    assert [match.match_level for match in matches] == ["strong", "missing"]


def test_match_evidence_ids_are_filtered_to_current_requirement_evidence():
    match = score_requirement(
        _requirement("req_python"),
        [
            _evidence("ev_python", "req_python", score=0.9),
            _evidence("ev_design", "req_design", score=0.9),
        ],
    )

    assert match.evidence_ids == ["ev_python"]


def _requirement(requirement_id: str) -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text="Build Python APIs",
        importance="high",
        keywords=["Python", "API"],
    )


def _evidence(evidence_id: str, requirement_id: str, score: float) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.md",
        section_label="Projects",
        snippet="Built Python FastAPI services.",
        score=score,
    )

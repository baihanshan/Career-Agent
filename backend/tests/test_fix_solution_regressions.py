from __future__ import annotations

import json
from pathlib import Path

from backend.app.api.schemas import AgentToolResult, JDRequirement
from backend.app.evaluation.numeric_claims import (
    extract_numeric_claims,
    validate_numeric_claims,
)
from backend.app.evaluation.quality_gate import PublicOutputQualityGate
from backend.app.workflow.domain_models import InternalInterviewQuestion
from backend.app.workflow.public_output import InternalIdLeakDetector


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture() -> dict:
    return json.loads(
        (FIXTURE_DIR / "fix_react_tool_calls.json").read_text(encoding="utf-8")
    )


def _questions(payload: dict) -> list[InternalInterviewQuestion]:
    return [
        InternalInterviewQuestion.model_validate(item)
        for item in payload["interview_prep"]["questions"]
    ]


def test_quality_fixture_preserves_all_reported_resume_capabilities():
    profile = (FIXTURE_DIR / "fix_quality_profile.md").read_text(encoding="utf-8")
    jd = (FIXTURE_DIR / "fix_quality_jd.txt").read_text(encoding="utf-8")

    for fact in ["语义分割", "NLP", "RAG", "多模态", "Python", "17%"]:
        assert fact.casefold() in profile.casefold()
    assert "硕士或博士" in jd
    assert "Python/C++/Java" in jd


def test_qualification_is_document_checked_and_not_turned_into_a_question():
    payload = _fixture()
    requirements = [JDRequirement.model_validate(item) for item in payload["requirements"]]
    questions = _questions(payload)
    qualification_ids = {
        item.requirement_id for item in requirements if item.category == "qualification"
    }

    assert qualification_ids
    assert all(
        item.verification_mode == "document_check" and not item.interviewability
        for item in requirements
        if item.requirement_id in qualification_ids
    )
    assert all(
        qualification_ids.isdisjoint(question.target_requirement_ids)
        for question in questions
    )


def test_jd_questions_are_professional_scenarios_with_constraints_and_tradeoffs():
    questions = [
        item for item in _questions(_fixture()) if item.question_type == "jd"
    ]

    assert len(questions) >= 2
    for item in questions:
        assert any(marker in item.question for marker in ["场景", "平台", "系统"])
        assert any(marker in item.question for marker in ["约束", "延迟", "资源"])
        assert any(marker in item.question for marker in ["权衡", "取舍", "选择"])
        assert "如何满足" not in item.question


def test_project_question_and_answer_stay_below_copy_gate():
    payload = _fixture()
    profile = (FIXTURE_DIR / "fix_quality_profile.md").read_text(encoding="utf-8")
    deep_dive = [
        item for item in _questions(payload) if item.question_type == "resume_deep_dive"
    ]

    issues = PublicOutputQualityGate().validate_interview_questions(
        deep_dive,
        [profile],
    )
    assert deep_dive
    assert not {
        issue.code
        for issue in issues
        if issue.code in {"QUESTION_COPIES_SNIPPET", "ANSWER_COPIES_SNIPPET"}
    }


def test_capability_support_and_or_requirement_use_known_evidence():
    payload = _fixture()
    evidence_ids = {item["evidence_id"] for item in payload["evidence"]}
    support = payload["capability_support"]

    assert {"Python", "CV/ML", "NLP", "RAG", "多模态"} <= set(support)
    assert all(item["support_level"] in {"strong", "partial"} for item in support.values())
    assert all(
        set(item["evidence_ids"]) <= evidence_ids for item in support.values()
    )
    assert payload["or_requirement"]["support_level"] == "strong"
    assert payload["or_requirement"]["satisfied_alternatives"]


def test_number_4_dates_and_deeplab_version_do_not_create_metric_risks():
    text = "4. 2024 年使用 DeepLabV3+ 完成模型迭代。"
    claims = extract_numeric_claims(text)

    assert claims
    assert validate_numeric_claims(claims, []) == []


def test_public_text_has_zero_id_leaks_and_zero_unknown_evidence_references():
    payload = _fixture()
    evidence_ids = {item["evidence_id"] for item in payload["evidence"]}
    questions = _questions(payload)
    references = [
        evidence_id
        for item in questions
        for evidence_id in item.supporting_evidence_ids
    ]
    references.extend(
        evidence_id
        for item in payload["capability_support"].values()
        for evidence_id in item["evidence_ids"]
    )

    assert InternalIdLeakDetector().find_leaks(payload["public_text"]) == []
    assert set(references) <= evidence_ids
    assert "" not in references


def test_fake_react_fixture_covers_every_agent_with_structured_tool_calls():
    tool_calls = _fixture()["tool_calls"]

    assert set(tool_calls) == {"resume_evidence", "interview_prep", "risk_auditor"}
    for calls in tool_calls.values():
        assert calls
        assert all(AgentToolResult.model_validate(item) for item in calls)

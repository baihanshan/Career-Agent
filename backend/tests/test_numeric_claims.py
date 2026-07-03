import pytest

from backend.app.api.schemas import EvidenceItem
from backend.app.evaluation.numeric_claims import (
    extract_numeric_claims,
    validate_numeric_claims,
)
from backend.app.workflow.domain_models import NumericClaimType


@pytest.mark.parametrize(
    ("text", "value", "claim_type"),
    [
        ("平均 IoU 提升 17%。", "17%", NumericClaimType.PERFORMANCE_METRIC),
        ("测试集 AUC 达到 0.957。", "0.957", NumericClaimType.PERFORMANCE_METRIC),
        ("在 3,242 条语料上完成评估。", "3,242", NumericClaimType.DATASET_SIZE),
    ],
)
def test_meaningful_numeric_claims_require_grounding(text, value, claim_type):
    claims = extract_numeric_claims(text)

    claim = next(item for item in claims if item.value == value)
    assert claim.claim_type == claim_type
    assert validate_numeric_claims([claim], []) == [claim]


@pytest.mark.parametrize(
    ("text", "expected_type"),
    [
        ("实习时间为 2025 年 1 月。", NumericClaimType.DATE),
        ("第 4 条建议用于复盘。", NumericClaimType.ORDINAL),
        ("使用 DeepLabV3+ 完成分割。", NumericClaimType.MODEL_OR_VERSION),
        ("使用 Python 3 开发服务。", NumericClaimType.MODEL_OR_VERSION),
    ],
)
def test_dates_ordinals_and_versions_do_not_require_achievement_grounding(
    text,
    expected_type,
):
    claims = extract_numeric_claims(text)

    assert claims
    assert all(item.claim_type == expected_type for item in claims)
    assert validate_numeric_claims(claims, []) == []


def test_duration_is_distinguished_from_calendar_date():
    claims = extract_numeric_claims("项目历时 6 个月完成。")

    assert claims[0].claim_type == NumericClaimType.DURATION
    assert validate_numeric_claims(claims, []) == []


def test_percentage_and_decimal_fraction_are_semantically_equivalent():
    claims = extract_numeric_claims(
        "平均 IoU 提升 17%。",
        evidence_ids=["ev_metric"],
    )
    evidence = [
        _evidence(
            "ev_metric",
            "实验结果显示平均 IoU 相对基线提升 0.17。",
        )
    ]

    unsupported = validate_numeric_claims(claims, evidence)

    assert claims[0].normalized_value == "0.17"
    assert unsupported == []


def test_unsupported_claim_retains_complete_sentence_context():
    text = "在独立测试集上，模型平均 IoU 提升 17%，同时保持推理延迟稳定。"

    claim = extract_numeric_claims(text)[0]

    assert claim.context == text
    assert claim.value == "17%"


def _evidence(evidence_id: str, snippet: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id="req_metric",
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.pdf",
        section_type="project",
        snippet=snippet,
        score=0.9,
    )

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from backend.app.api.schemas import EvidenceItem
from backend.app.workflow.domain_models import NumericClaim, NumericClaimType


_NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
_SENTENCE_BOUNDARIES = "。！？!?\n；;"
_STRICT_CLAIM_TYPES = {
    NumericClaimType.PERFORMANCE_METRIC,
    NumericClaimType.BUSINESS_IMPACT,
    NumericClaimType.DATASET_SIZE,
    NumericClaimType.COUNT,
}
_METRIC_MARKERS = re.compile(
    r"(?i)(?:auc(?:-roc)?|f1(?:-score)?|iou|accuracy|precision|recall|latency|"
    r"准确率|精度|召回率|损失|延迟|吞吐|提升|提高|降低|下降)"
)
_BUSINESS_MARKERS = re.compile(
    r"(?i)(?:revenue|conversion|users?|customers?|efficiency|cost|sales|"
    r"营收|转化|用户|客户|效率|成本|销量|业务)"
)
_DATASET_UNITS = (
    r"(?:条|个)?\s*(?:语料|样本|数据|records?|samples?|examples?|images?|tokens?)"
)
_COUNT_UNITS = (
    r"(?:个|类|项|名|次|套|种|部门|工具|智能体|classes?|departments?|tools?|agents?)"
)


def extract_numeric_claims(
    text: str,
    evidence_ids: list[str] | None = None,
) -> list[NumericClaim]:
    claims: list[NumericClaim] = []
    for match in _NUMBER_PATTERN.finditer(text):
        value = match.group(0)
        context = _sentence_context(text, match.start(), match.end())
        local_context = text[max(0, match.start() - 28) : match.end() + 28]
        claim_type = classify_numeric_claim(value, local_context)
        claims.append(
            NumericClaim(
                value=value,
                normalized_value=_normalize_numeric_value(value),
                claim_type=claim_type,
                context=context,
                evidence_ids=list(evidence_ids or []),
            )
        )
    return claims


def classify_numeric_claim(value: str, context: str) -> NumericClaimType:
    escaped = re.escape(value)
    if re.search(rf"第\s*{escaped}\s*(?:条|项|次|名|章|节|轮|个)", context):
        return NumericClaimType.ORDINAL
    if re.search(rf"(?:^|[\s；;。]){escaped}[.)、]\s*", context):
        return NumericClaimType.ORDINAL
    if re.search(rf"{escaped}\s*(?:年|月|日|号)", context) or re.search(
        rf"(?:年|月)\s*{escaped}\s*(?:月|日|号)?",
        context,
    ):
        return NumericClaimType.DATE
    if re.search(
        rf"{escaped}\s*(?:个月|月|天|周|年|hours?|days?|weeks?|months?|years?)",
        context,
        re.IGNORECASE,
    ) and re.search(r"(?:持续|历时|耗时|duration|for\s+)", context, re.IGNORECASE):
        return NumericClaimType.DURATION
    if re.search(
        rf"(?i)(?:deeplabv|python\s+|gpt-|bert-|version\s*|版本\s*|v){escaped}\+?",
        context,
    ):
        return NumericClaimType.MODEL_OR_VERSION
    if re.search(rf"{escaped}\s*{_DATASET_UNITS}", context, re.IGNORECASE):
        return NumericClaimType.DATASET_SIZE
    if _BUSINESS_MARKERS.search(context) and (
        value.endswith("%")
        or re.search(rf"{escaped}\s*(?:人|次|家|users?|customers?)", context, re.I)
    ):
        return NumericClaimType.BUSINESS_IMPACT
    if value.endswith("%") or _METRIC_MARKERS.search(context):
        return NumericClaimType.PERFORMANCE_METRIC
    if re.search(rf"{escaped}\s*{_COUNT_UNITS}", context, re.IGNORECASE):
        return NumericClaimType.COUNT
    return NumericClaimType.OTHER


def validate_numeric_claims(
    claims: list[NumericClaim],
    evidence_items: list[EvidenceItem],
) -> list[NumericClaim]:
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    unsupported: list[NumericClaim] = []
    for claim in claims:
        if claim.claim_type not in _STRICT_CLAIM_TYPES:
            continue
        relevant_evidence = (
            [
                evidence_by_id[evidence_id]
                for evidence_id in claim.evidence_ids
                if evidence_id in evidence_by_id
            ]
            if claim.evidence_ids
            else evidence_items
        )
        evidence_claims = [
            evidence_claim
            for item in relevant_evidence
            for evidence_claim in extract_numeric_claims(
                item.snippet,
                evidence_ids=[item.evidence_id],
            )
        ]
        if not any(_claims_match(claim, evidence_claim) for evidence_claim in evidence_claims):
            unsupported.append(claim)
    return unsupported


def _claims_match(left: NumericClaim, right: NumericClaim) -> bool:
    if left.normalized_value != right.normalized_value:
        return False
    return _claim_family(left.claim_type) == _claim_family(right.claim_type)


def _claim_family(claim_type: NumericClaimType) -> str:
    if claim_type in {
        NumericClaimType.PERFORMANCE_METRIC,
        NumericClaimType.BUSINESS_IMPACT,
    }:
        return "impact"
    if claim_type in {NumericClaimType.DATASET_SIZE, NumericClaimType.COUNT}:
        return "count"
    return claim_type.value


def _normalize_numeric_value(value: str) -> str:
    raw = value.replace(",", "")
    is_percentage = raw.endswith("%")
    if is_percentage:
        raw = raw[:-1]
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return raw
    if is_percentage:
        number /= Decimal("100")
    rendered = format(number.normalize(), "f")
    return "0" if rendered in {"-0", ""} else rendered


def _sentence_context(text: str, start: int, end: int) -> str:
    left = max((text.rfind(marker, 0, start) for marker in _SENTENCE_BOUNDARIES), default=-1)
    right_candidates = [
        position
        for marker in _SENTENCE_BOUNDARIES
        if (position := text.find(marker, end)) >= 0
    ]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return text[left + 1 : right].strip()

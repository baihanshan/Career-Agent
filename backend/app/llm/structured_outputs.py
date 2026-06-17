from __future__ import annotations

import json
import re
from typing import Any, Mapping
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from backend.app.api.schemas import EvaluationReport, GeneratedAssets, JDRequirement


ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMOutputParseError(ValueError):
    pass


def parse_model(raw_output: str, model_type: type[ModelT]) -> ModelT:
    normalized_output = _normalize_json_output(raw_output)
    try:
        return model_type.model_validate_json(normalized_output)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMOutputParseError(str(exc)) from exc


def parse_model_list(raw_output: str, model_type: type[ModelT]) -> list[ModelT]:
    normalized_output = _normalize_json_output(raw_output)
    try:
        payload = json.loads(normalized_output)
        if isinstance(payload, dict):
            payload = _extract_list_from_object(payload)
        return TypeAdapter(list[model_type]).validate_python(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMOutputParseError(str(exc)) from exc


def parse_jd_requirements(raw_output: str) -> list[JDRequirement]:
    normalized_output = _normalize_json_output(raw_output)
    try:
        payload = json.loads(normalized_output)
        if isinstance(payload, dict):
            payload = _extract_list_from_object(payload)
        if not isinstance(payload, list):
            raise ValueError("JD requirements output must be a list or wrapped list.")
        return [
            JDRequirement.model_validate(_normalize_jd_requirement(item, index))
            for index, item in enumerate(payload, start=1)
        ]
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise LLMOutputParseError(str(exc)) from exc


def parse_generated_assets(
    raw_output: str,
    context: Mapping[str, Any],
) -> GeneratedAssets:
    normalized_output = _normalize_json_output(raw_output)
    try:
        payload = json.loads(normalized_output)
        if isinstance(payload, dict):
            payload = _extract_object_from_wrappers(
                payload,
                ("generated_assets", "application_assets", "assets", "result"),
            )
        if not isinstance(payload, dict):
            raise ValueError("Generated assets output must be a JSON object.")
        return GeneratedAssets.model_validate(
            _normalize_generated_assets(payload, context)
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise LLMOutputParseError(str(exc)) from exc


def parse_evaluation_report(raw_output: str) -> EvaluationReport:
    normalized_output = _normalize_json_output(raw_output)
    try:
        payload = json.loads(normalized_output)
        if isinstance(payload, dict):
            payload = _extract_object_from_wrappers(
                payload,
                ("evaluation_report", "report", "result"),
            )
        if not isinstance(payload, dict):
            raise ValueError("Evaluation report output must be a JSON object.")
        return EvaluationReport.model_validate(_normalize_evaluation_report(payload))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise LLMOutputParseError(str(exc)) from exc


def _normalize_json_output(raw_output: str) -> str:
    stripped = raw_output.strip()
    if stripped.startswith(("{", "[")):
        return stripped
    fenced_match = re.search(
        r"```(?:json)?\s*(?P<body>.*?)\s*```",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced_match:
        return fenced_match.group("body").strip()
    extracted_json = _extract_balanced_json(stripped)
    if extracted_json is not None:
        return extracted_json
    return stripped


def _extract_list_from_object(payload: dict[str, Any]) -> Any:
    for key in ("requirements", "items", "data", "results", "job_requirements"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested_value = _extract_list_from_object(value)
            if isinstance(nested_value, list):
                return nested_value
    for value in payload.values():
        if isinstance(value, dict):
            nested_value = _extract_list_from_object(value)
            if isinstance(nested_value, list):
                return nested_value
    return payload


def _extract_object_from_wrappers(
    payload: dict[str, Any],
    wrapper_keys: tuple[str, ...],
) -> dict[str, Any]:
    for key in wrapper_keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _normalize_jd_requirement(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, str):
        return {
            "requirement_id": f"req_{index}",
            "category": "responsibility",
            "text": item,
            "importance": "medium",
            "keywords": [],
        }
    if not isinstance(item, dict):
        raise ValueError(f"Requirement {index} must be an object or string.")

    text = _first_text_value(
        item,
        (
            "text",
            "requirement_text",
            "requirement",
            "description",
            "name",
            "title",
            "content",
            "summary",
        ),
    )
    if not text:
        raise ValueError(f"Requirement {index} is missing requirement text.")

    requirement_id = _first_text_value(
        item,
        ("requirement_id", "id", "key", "requirementId"),
    ) or f"req_{index}"

    return {
        "requirement_id": _safe_requirement_id(requirement_id, index),
        "category": _normalize_category(
            _first_text_value(item, ("category", "type", "kind")) or ""
        ),
        "text": text,
        "importance": _normalize_importance(
            _first_text_value(item, ("importance", "priority", "level", "required")) or ""
        ),
        "keywords": _normalize_keywords(item.get("keywords") or item.get("skills") or []),
    }


def _first_text_value(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_requirement_id(value: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_:-]+", "_", value.strip()).strip("_")
    return normalized or f"req_{index}"


def _normalize_category(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    category_map = {
        "technical": "hard_skill",
        "technical_skill": "hard_skill",
        "skill": "hard_skill",
        "skills": "hard_skill",
        "hard": "hard_skill",
        "must_have": "hard_skill",
        "communication": "soft_skill",
        "interpersonal": "soft_skill",
        "soft": "soft_skill",
        "education": "qualification",
        "degree": "qualification",
        "certification": "qualification",
        "preferred": "nice_to_have",
        "bonus": "nice_to_have",
        "plus": "nice_to_have",
    }
    if normalized in {
        "responsibility",
        "hard_skill",
        "soft_skill",
        "qualification",
        "nice_to_have",
    }:
        return normalized
    return category_map.get(normalized, "responsibility")


def _normalize_importance(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {
        "high",
        "required",
        "mandatory",
        "must",
        "must_have",
        "critical",
        "essential",
        "core",
    }:
        return "high"
    if normalized in {"low", "optional", "nice_to_have", "preferred", "bonus"}:
        return "low"
    return "medium"


def _normalize_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;，；]", value) if item.strip()]
    return []


def _normalize_generated_assets(
    payload: dict[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    resume_bullets = payload.get("resume_bullets") or payload.get("bullets") or []
    cover_letter = payload.get("cover_letter") or payload.get("letter") or {}
    interview_prep = (
        payload.get("interview_prep")
        or payload.get("interview_questions")
        or payload.get("interview_tips")
        or []
    )
    match_summary = (
        _string_value(payload.get("match_summary"))
        or _string_value(payload.get("summary"))
        or "根据已检索到的个人材料证据，候选人与目标岗位存在可解释的匹配点。"
    )

    return {
        "match_summary": match_summary,
        "resume_bullets": [
            _normalize_resume_bullet(item, index, context)
            for index, item in enumerate(_list_value(resume_bullets), start=1)
        ],
        "cover_letter": _normalize_cover_letter(cover_letter, context),
        "interview_prep": [
            _normalize_interview_prep_item(item, index, context)
            for index, item in enumerate(_list_value(interview_prep), start=1)
        ],
    }


def _normalize_resume_bullet(
    item: Any,
    index: int,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(item, str):
        text = item
        raw_targets: Any = []
        raw_evidence_ids: Any = []
        raw_risk_level: Any = ""
    elif isinstance(item, dict):
        text = (
            _string_value(item.get("text"))
            or _string_value(item.get("bullet"))
            or _string_value(item.get("content"))
            or _string_value(item.get("description"))
            or f"生成的简历要点 {index}"
        )
        raw_targets = (
            item.get("target_requirement_ids")
            or item.get("target_requirement_id")
            or item.get("requirement_ids")
            or item.get("requirement_id")
            or item.get("requirements")
            or []
        )
        raw_evidence_ids = (
            item.get("evidence_ids")
            or item.get("evidence_id")
            or item.get("supporting_evidence_ids")
            or item.get("citations")
            or []
        )
        raw_risk_level = item.get("risk_level") or item.get("risk") or ""
    else:
        raise ValueError(f"Resume bullet {index} must be an object or string.")

    target_requirement_ids = _known_requirement_ids(
        raw_targets,
        context,
    ) or _default_requirement_ids(context)
    evidence_ids = _known_evidence_ids(raw_evidence_ids, context)
    if not evidence_ids:
        evidence_ids = _fallback_evidence_ids(target_requirement_ids, context)

    return {
        "text": text,
        "target_requirement_ids": target_requirement_ids,
        "evidence_ids": evidence_ids,
        "risk_level": _normalize_risk_level(raw_risk_level, evidence_ids),
    }


def _normalize_cover_letter(item: Any, context: Mapping[str, Any]) -> dict[str, Any]:
    fallback_evidence_ids = _fallback_evidence_ids(_default_requirement_ids(context), context)
    if isinstance(item, str):
        return {
            "opening": "您好，我很高兴申请这个岗位。",
            "body": [item],
            "closing": "感谢您的时间与考虑，期待进一步交流。",
            "evidence_ids": fallback_evidence_ids,
        }
    if not isinstance(item, dict):
        item = {}
    body = item.get("body") or item.get("paragraphs") or item.get("content") or []
    return {
        "opening": _string_value(item.get("opening")) or "您好，我很高兴申请这个岗位。",
        "body": _list_value(body) or ["根据已引用的个人材料证据，我的经历与该岗位要求具有相关性。"],
        "closing": _string_value(item.get("closing")) or "感谢您的时间与考虑，期待进一步交流。",
        "evidence_ids": _known_evidence_ids(item.get("evidence_ids") or [], context)
        or fallback_evidence_ids,
    }


def _normalize_interview_prep_item(
    item: Any,
    index: int,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    fallback_requirement_ids = _default_requirement_ids(context)
    fallback_evidence_ids = _fallback_evidence_ids(fallback_requirement_ids, context)
    if isinstance(item, str):
        return {
            "topic": f"面试准备 {index}",
            "why_it_matters": "这个话题可以把个人经历和目标岗位要求直接连接起来。",
            "supporting_evidence_ids": fallback_evidence_ids,
            "prep_suggestion": item,
        }
    if not isinstance(item, dict):
        item = {}
    return {
        "topic": _string_value(item.get("topic"))
        or _string_value(item.get("question"))
        or f"面试准备 {index}",
        "why_it_matters": _string_value(item.get("why_it_matters"))
        or _string_value(item.get("reason"))
        or "这个话题可以把个人经历和目标岗位要求直接连接起来。",
        "supporting_evidence_ids": _known_evidence_ids(
            item.get("supporting_evidence_ids") or item.get("evidence_ids") or [],
            context,
        )
        or fallback_evidence_ids,
        "prep_suggestion": _string_value(item.get("prep_suggestion"))
        or _string_value(item.get("suggestion"))
        or _string_value(item.get("answer"))
        or "准备一段简洁的项目 walkthrough，并明确说明能力点对应的材料证据。",
    }


def _string_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _known_requirement_ids(value: Any, context: Mapping[str, Any]) -> list[str]:
    known_ids = {
        _get_value(item, "requirement_id")
        for item in context.get("requirements", [])
        if _get_value(item, "requirement_id")
    }
    return [item for item in _string_list(value) if item in known_ids]


def _default_requirement_ids(context: Mapping[str, Any]) -> list[str]:
    for item in context.get("match_analysis", []):
        if _get_value(item, "match_level") != "missing":
            requirement_id = _get_value(item, "requirement_id")
            if isinstance(requirement_id, str) and requirement_id:
                return [requirement_id]
    for item in context.get("requirements", []):
        requirement_id = _get_value(item, "requirement_id")
        if isinstance(requirement_id, str) and requirement_id:
            return [requirement_id]
    return []


def _known_evidence_ids(value: Any, context: Mapping[str, Any]) -> list[str]:
    known_ids = set(context.get("evidence_ids", []))
    if not known_ids:
        known_ids = {
            _get_value(item, "evidence_id")
            for item in context.get("evidence", [])
            if _get_value(item, "evidence_id")
        }
    return [item for item in _string_list(value) if item in known_ids]


def _fallback_evidence_ids(
    requirement_ids: list[str],
    context: Mapping[str, Any],
) -> list[str]:
    for match_item in context.get("match_analysis", []):
        if _get_value(match_item, "requirement_id") not in requirement_ids:
            continue
        return _known_evidence_ids(_get_value(match_item, "evidence_ids") or [], context)
    return []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_risk_level(value: Any, evidence_ids: list[str]) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    return "low" if evidence_ids else "high"


def _normalize_evaluation_report(payload: dict[str, Any]) -> dict[str, Any]:
    grounding_warnings = (
        payload.get("grounding_warnings")
        or payload.get("warnings")
        or payload.get("issues")
        or []
    )
    coverage_gaps = (
        payload.get("coverage_gaps")
        or payload.get("gaps")
        or payload.get("missing_requirements")
        or []
    )
    specificity_notes = payload.get("specificity_notes") or payload.get("notes") or []
    return {
        "grounding_warnings": [
            _normalize_grounding_warning(item, index)
            for index, item in enumerate(_list_value(grounding_warnings), start=1)
        ],
        "coverage_gaps": [
            _normalize_coverage_gap(item, index)
            for index, item in enumerate(_list_value(coverage_gaps), start=1)
        ],
        "specificity_notes": [str(item) for item in _list_value(specificity_notes)],
        "risk_summary": _string_value(payload.get("risk_summary"))
        or _string_value(payload.get("summary"))
        or "模型语义评估完成。",
        "overall_status": _normalize_overall_status(
            payload.get("overall_status") or payload.get("status")
        ),
    }


def _normalize_grounding_warning(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, str):
        return {
            "asset_type": "resume_bullet",
            "asset_id": f"semantic:{index}",
            "claim": item,
            "reason": item,
            "severity": "medium",
        }
    if not isinstance(item, dict):
        item = {}
    return {
        "asset_type": _normalize_asset_type(item.get("asset_type") or item.get("type")),
        "asset_id": _string_value(item.get("asset_id"))
        or _string_value(item.get("id"))
        or f"semantic:{index}",
        "claim": _string_value(item.get("claim"))
        or _string_value(item.get("text"))
        or _string_value(item.get("content"))
        or "模型指出存在证据支撑风险。",
        "reason": _string_value(item.get("reason"))
        or _string_value(item.get("message"))
        or _string_value(item.get("explanation"))
        or "模型指出该内容需要人工复核。",
        "severity": _normalize_severity(item.get("severity") or item.get("level")),
    }


def _normalize_coverage_gap(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, str):
        return {
            "requirement_id": f"req_{index}",
            "reason": item,
            "severity": "medium",
        }
    if not isinstance(item, dict):
        item = {}
    return {
        "requirement_id": _string_value(item.get("requirement_id"))
        or _string_value(item.get("id"))
        or f"req_{index}",
        "reason": _string_value(item.get("reason"))
        or _string_value(item.get("message"))
        or "模型指出该岗位要求覆盖不足。",
        "severity": _normalize_severity(item.get("severity") or item.get("level")),
    }


def _normalize_asset_type(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"resume", "bullet", "resume_bullets"}:
        return "resume_bullet"
    if normalized in {"letter", "cover"}:
        return "cover_letter"
    if normalized in {"summary"}:
        return "match_summary"
    if normalized in {"interview", "interview_question", "interview_questions"}:
        return "interview_prep"
    if normalized in {"resume_bullet", "cover_letter", "match_summary", "interview_prep"}:
        return normalized
    return "resume_bullet"


def _normalize_severity(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"high", "error", "critical", "fail", "failed"}:
        return "high"
    if normalized in {"low", "info", "minor", "pass"}:
        return "low"
    return "medium"


def _normalize_overall_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"fail", "failed", "error", "high_risk"}:
        return "fail"
    if normalized in {"pass", "passed", "ok", "success"}:
        return "pass"
    return "pass_with_warnings"


def _get_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _extract_balanced_json(text: str) -> str | None:
    starts = [
        (start, opener, closer)
        for opener, closer in (("[", "]"), ("{", "}"))
        if (start := text.find(opener)) != -1
    ]
    for start, opener, closer in sorted(starts):
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if character == opener:
                depth += 1
            elif character == closer:
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None

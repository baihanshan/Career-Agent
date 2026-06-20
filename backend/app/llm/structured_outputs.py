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
        normalized = {
            "requirement_id": f"req_{index}",
            "category": "responsibility",
            "text": item,
            "importance": "medium",
            "keywords": [],
        }
        normalized.update(_normalize_requirement_semantics({}, item, "responsibility", []))
        return normalized
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

    category = _normalize_category(
        _first_text_value(item, ("category", "type", "kind")) or ""
    )
    keywords = _normalize_keywords(item.get("keywords") or item.get("skills") or [])
    normalized = {
        "requirement_id": _safe_requirement_id(requirement_id, index),
        "category": category,
        "text": text,
        "importance": _normalize_importance(
            _first_text_value(item, ("importance", "priority", "level", "required")) or ""
        ),
        "keywords": keywords,
    }
    normalized.update(_normalize_requirement_semantics(item, text, category, keywords))
    return normalized


def _normalize_requirement_semantics(
    item: dict[str, Any],
    text: str,
    category: str,
    keywords: list[str],
) -> dict[str, Any]:
    capability_tags = _normalize_string_list(
        item.get("capability_tags") or item.get("capabilities") or []
    )
    capability_tags = _dedupe(
        capability_tags + _infer_capability_tags(" ".join([text, *keywords]))
    )

    requested_mode = _first_text_value(
        item,
        ("verification_mode", "verificationMode", "assessment_mode"),
    )
    verification_mode = _normalize_verification_mode(
        requested_mode,
        text=text,
        category=category,
        capability_tags=capability_tags,
    )
    default_interviewability = verification_mode in {
        "technical_question",
        "system_design",
        "behavioral_question",
    }
    interviewability = _normalize_boolean(
        item.get("interviewability", item.get("interviewable")),
        default=default_interviewability,
    )
    if verification_mode == "document_check":
        interviewability = False

    logical_operator = _normalize_logical_operator(
        item.get("logical_operator") or item.get("operator"), text
    )
    alternatives = _normalize_string_list(
        item.get("alternatives") or item.get("branches") or []
    )
    if logical_operator == "OR" and len(alternatives) < 2:
        alternatives = _extract_or_alternatives(text)

    question_focus = _first_text_value(
        item,
        ("question_focus", "questionFocus", "interview_focus"),
    )
    if interviewability and not question_focus:
        question_focus = _default_question_focus(verification_mode, capability_tags)
    if not interviewability:
        question_focus = None

    return {
        "capability_tags": capability_tags,
        "verification_mode": verification_mode,
        "interviewability": interviewability,
        "question_focus": question_focus,
        "logical_operator": logical_operator,
        "alternatives": alternatives,
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


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return _dedupe(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        return _dedupe(
            item.strip()
            for item in re.split(r"[,;，；]", value)
            if item.strip()
        )
    return []


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(values))


def _infer_capability_tags(text: str) -> list[str]:
    lowered = text.casefold()
    rules = (
        ("programming", ("python", "c++", "java", "编程")),
        ("algorithms", ("algorithm", "data structure", "算法", "数据结构")),
        ("machine_learning", ("machine learning", "机器学习", "深度学习")),
        ("nlp", ("nlp", "natural language", "自然语言")),
        ("multimodal", ("multimodal", "多模态")),
        ("platform", ("platform", "平台")),
        ("evaluation", ("evaluation", "evaluate", "评估")),
        ("system_design", ("architecture", "system design", "架构", "系统设计")),
        ("communication", ("communication", "沟通", "协作")),
        ("leadership", ("leadership", "lead team", "领导", "带领团队")),
    )
    return [tag for tag, terms in rules if any(term in lowered for term in terms)]


def _normalize_verification_mode(
    value: str | None,
    *,
    text: str,
    category: str,
    capability_tags: list[str],
) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "document": "document_check",
        "qualification": "document_check",
        "evidence": "evidence_check",
        "technical": "technical_question",
        "technical_interview": "technical_question",
        "design": "system_design",
        "architecture": "system_design",
        "behavioral": "behavioral_question",
        "behavioural": "behavioral_question",
    }
    normalized = aliases.get(normalized, normalized)
    known_modes = {
        "document_check",
        "evidence_check",
        "technical_question",
        "system_design",
        "behavioral_question",
    }

    if category == "qualification" or _is_static_qualification(text):
        return "document_check"
    if normalized in known_modes:
        return normalized
    if "platform" in capability_tags or "system_design" in capability_tags:
        return "system_design"
    if category == "hard_skill":
        return "technical_question"
    if category == "soft_skill":
        return "behavioral_question"
    return "evidence_check"


def _is_static_qualification(text: str) -> bool:
    lowered = text.casefold()
    return any(
        term in lowered
        for term in (
            "degree",
            "bachelor",
            "master",
            "phd",
            "doctorate",
            "学历",
            "本科",
            "硕士",
            "博士",
            "毕业时间",
        )
    )


def _normalize_boolean(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return default


def _normalize_logical_operator(value: Any, text: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"OR", "ANY", "ONE_OF", "EITHER"}:
        return "OR"
    if normalized in {"AND", "ALL", "ALL_OF"}:
        return "AND"
    lowered = text.casefold()
    if any(
        marker in lowered
        for marker in ("至少一个", "任一", "任选", "at least one", "either")
    ):
        return "OR"
    return "AND"


def _extract_or_alternatives(text: str) -> list[str]:
    prefix = re.split(
        r"至少一个|任一|任选|at least one|either",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    clause = re.split(r"[，,；;]", prefix)[-1]
    clause = re.sub(
        r"^(?:了解|熟悉|掌握|具备|experience (?:with|in))\s*",
        "",
        clause.strip(),
        flags=re.IGNORECASE,
    )
    parts = [
        re.sub(r"(?:等)?(?:相关)?领域$", "", part.strip()).strip()
        for part in re.split(r"[/、]|\s+or\s+|或", clause, flags=re.IGNORECASE)
    ]
    return _dedupe(part for part in parts if part)


def _default_question_focus(
    verification_mode: str,
    capability_tags: list[str],
) -> str:
    if verification_mode == "system_design":
        if "multimodal" in capability_tags:
            return "multimodal platform design, data/model choices, evaluation, and engineering trade-offs"
        return "system architecture, constraints, design choices, validation, and trade-offs"
    if verification_mode == "technical_question":
        if {"programming", "algorithms"}.issubset(capability_tags):
            return "applied programming and algorithm choices under complexity and reliability constraints"
        return "applied technical decisions, alternatives, validation, and engineering trade-offs"
    return "specific decisions, collaboration, outcomes, and reflection from a real experience"


def _normalize_generated_assets(
    payload: dict[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    resume_bullets = payload.get("resume_bullets") or payload.get("bullets") or []
    raw_interview_prep = (
        payload.get("interview_prep")
        or payload.get("interview_questions")
        or payload.get("interview_tips")
        or {}
    )
    match_summary = (
        _string_value(payload.get("match_summary"))
        or _string_value(payload.get("summary"))
        or "根据已检索到的个人材料证据，候选人与目标岗位存在可解释的匹配点。"
    )
    normalized_bullets = [
        _normalize_resume_bullet(item, index, context)
        for index, item in enumerate(_list_value(resume_bullets), start=1)
    ]

    return {
        "match_summary": match_summary,
        "resume_bullets": _exactly_three_resume_bullets(normalized_bullets, context),
        "interview_prep": _normalize_interview_prep(raw_interview_prep, context),
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


def _exactly_three_resume_bullets(
    bullets: list[dict[str, Any]],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    normalized = list(bullets[:3])
    while len(normalized) < 3:
        normalized.append(_fallback_resume_bullet(len(normalized) + 1, context))
    return normalized


def _fallback_resume_bullet(index: int, context: Mapping[str, Any]) -> dict[str, Any]:
    evidence = _preferred_evidence(context)
    requirement_ids = _default_requirement_ids(context)
    evidence_ids = [_get_value(evidence, "evidence_id")] if evidence else []
    evidence_ids = [item for item in evidence_ids if isinstance(item, str)]
    if evidence:
        section_type = _get_value(evidence, "section_type") or "other"
        snippet = _string_value(_get_value(evidence, "snippet")) or _string_value(
            _get_value(evidence, "text")
        )
        text = (
            f"基于{section_type}证据补充第 {index} 条简历要点："
            f"{snippet or '请补充项目或实习中的具体贡献、技术栈和结果。'}"
        )
    else:
        text = f"第 {index} 条简历要点需要补充可追溯的项目或实习证据。"
    return {
        "text": text,
        "target_requirement_ids": requirement_ids,
        "evidence_ids": evidence_ids,
        "risk_level": "low" if evidence_ids else "high",
    }


def _preferred_evidence(context: Mapping[str, Any]) -> dict[str, Any] | None:
    evidence_items = [
        item for item in context.get("evidence", []) if isinstance(item, dict)
    ]
    if not evidence_items:
        return None
    return sorted(
        evidence_items,
        key=lambda item: (
            {"project": 2, "internship": 2, "skill": 0}.get(
                _get_value(item, "section_type"),
                1,
            ),
            float(_get_value(item, "score") or 0),
        ),
        reverse=True,
    )[0]


def _normalize_interview_prep(
    value: Any,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(value, dict) and (
        "jd_questions" in value or "resume_deep_dive_questions" in value
    ):
        jd_questions = value.get("jd_questions") or []
        resume_questions = value.get("resume_deep_dive_questions") or []
    else:
        jd_questions = _list_value(value)
        resume_questions = []
    return {
        "jd_questions": [
            _normalize_interview_question(item, index, context)
            for index, item in enumerate(_list_value(jd_questions), start=1)
        ],
        "resume_deep_dive_questions": [
            _normalize_interview_question(item, index, context)
            for index, item in enumerate(_list_value(resume_questions), start=1)
        ],
    }


def _normalize_interview_question(
    item: Any,
    index: int,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    fallback_requirement_ids = _default_requirement_ids(context)
    fallback_evidence_ids = _fallback_evidence_ids(fallback_requirement_ids, context)
    if isinstance(item, str):
        return {
            "question": f"面试问题 {index}",
            "sample_answer": item,
            "supporting_evidence_ids": fallback_evidence_ids,
        }
    if not isinstance(item, dict):
        item = {}
    return {
        "question": _string_value(item.get("question"))
        or _string_value(item.get("topic"))
        or f"面试问题 {index}",
        "sample_answer": _string_value(item.get("sample_answer"))
        or _string_value(item.get("answer"))
        or _string_value(item.get("prep_suggestion"))
        or _string_value(item.get("suggestion"))
        or "请结合相关经历说明具体职责、技术决策、结果和复盘。",
        "supporting_evidence_ids": _known_evidence_ids(
            item.get("supporting_evidence_ids") or item.get("evidence_ids") or [],
            context,
        )
        or fallback_evidence_ids,
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
        return "resume_bullet"
    if normalized in {"summary"}:
        return "match_summary"
    if normalized in {"interview", "interview_question", "interview_questions"}:
        return "interview_prep"
    if normalized in {"resume_bullet", "match_summary", "interview_prep"}:
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

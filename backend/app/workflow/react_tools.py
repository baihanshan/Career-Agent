from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, model_validator

from backend.app.api.schemas import ResumeSectionType
from backend.app.workflow.agent_tools import TraceRecorder
from backend.app.workflow.state import WorkflowState


REACT_AGENT_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "resume_evidence": {
        "search_resume_evidence",
        "get_experience",
        "get_resume_section",
        "compare_requirement_to_evidence",
        "rerank_evidence",
    },
    "interview_prep": {
        "get_interviewable_requirements",
        "get_requirement_evidence",
        "get_experience",
    },
    "risk_auditor": {
        "get_requirement",
        "get_requirement_evidence",
        "inspect_experience",
        "compare_capability_semantics",
        "check_public_claim_grounding",
        "classify_numeric_claim",
        "get_resume_bullet_coverage",
        "rank_candidate_risks",
    },
}


class StructuredToolError(BaseModel):
    code: str
    message: str


class StructuredToolResult(BaseModel):
    status: Literal["success", "error"]
    data: dict[str, Any] = Field(default_factory=dict)
    trace_summary: str
    error: StructuredToolError | None = None

    @model_validator(mode="after")
    def validate_error_shape(self) -> "StructuredToolResult":
        if self.status == "error" and self.error is None:
            raise ValueError("Error tool results require an error payload.")
        if self.status == "success" and self.error is not None:
            raise ValueError("Successful tool results cannot contain an error payload.")
        return self


class SearchResumeEvidenceArgs(BaseModel):
    query: str
    section_types: list[ResumeSectionType] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class GetExperienceArgs(BaseModel):
    experience_id: str


class GetResumeSectionArgs(BaseModel):
    section_type: ResumeSectionType


class RequirementEvidenceArgs(BaseModel):
    requirement_id: str
    evidence_ids: list[str] = Field(default_factory=list)


class RequirementIdArgs(BaseModel):
    requirement_id: str


class EmptyArgs(BaseModel):
    pass


class ClaimArgs(BaseModel):
    claim: str


class RiskRankingArgs(BaseModel):
    risks: list[dict[str, Any]]
    limit: int = Field(default=3, ge=1, le=3)


def build_structured_react_tools(
    state: WorkflowState,
    agent_name: str,
    recorder: TraceRecorder,
) -> list[StructuredTool]:
    if agent_name not in REACT_AGENT_TOOL_ALLOWLIST:
        raise ValueError(f"Unknown ReAct agent: {agent_name}")

    registry = _tool_registry(state, recorder)
    allowed = REACT_AGENT_TOOL_ALLOWLIST[agent_name]
    return [registry[name] for name in sorted(allowed)]


def _tool_registry(
    state: WorkflowState,
    recorder: TraceRecorder,
) -> dict[str, StructuredTool]:
    return {
        "search_resume_evidence": _structured_tool(
            state,
            recorder,
            "search_resume_evidence",
            "Search typed resume evidence by section and return evidence records.",
            SearchResumeEvidenceArgs,
            lambda query, section_types, top_k: _search_resume_evidence(
                state, section_types, top_k
            ),
        ),
        "get_experience": _structured_tool(
            state,
            recorder,
            "get_experience",
            "Get one structured project or internship by experience ID.",
            GetExperienceArgs,
            lambda experience_id: _get_experience(state, experience_id),
        ),
        "inspect_experience": _structured_tool(
            state,
            recorder,
            "inspect_experience",
            "Inspect one structured experience for risk analysis.",
            GetExperienceArgs,
            lambda experience_id: _get_experience(state, experience_id),
        ),
        "get_resume_section": _structured_tool(
            state,
            recorder,
            "get_resume_section",
            "Get structured resume sections of one type.",
            GetResumeSectionArgs,
            lambda section_type: _get_resume_section(state, section_type),
        ),
        "compare_requirement_to_evidence": _structured_tool(
            state,
            recorder,
            "compare_requirement_to_evidence",
            "Return one requirement with selected evidence for semantic comparison.",
            RequirementEvidenceArgs,
            lambda requirement_id, evidence_ids: _requirement_evidence(
                state, requirement_id, evidence_ids
            ),
        ),
        "rerank_evidence": _structured_tool(
            state,
            recorder,
            "rerank_evidence",
            "Rank selected evidence by source type and retrieval score.",
            RequirementEvidenceArgs,
            lambda requirement_id, evidence_ids: _rerank_evidence(
                state, requirement_id, evidence_ids
            ),
        ),
        "get_interviewable_requirements": _structured_tool(
            state,
            recorder,
            "get_interviewable_requirements",
            "Return requirements eligible for professional interview questions.",
            EmptyArgs,
            lambda: _interviewable_requirements(state),
        ),
        "get_requirement": _structured_tool(
            state,
            recorder,
            "get_requirement",
            "Get one typed JD requirement.",
            RequirementIdArgs,
            lambda requirement_id: _get_requirement(state, requirement_id),
        ),
        "get_requirement_evidence": _structured_tool(
            state,
            recorder,
            "get_requirement_evidence",
            "Return all known evidence for one JD requirement.",
            RequirementIdArgs,
            lambda requirement_id: _requirement_evidence(state, requirement_id, []),
        ),
        "compare_capability_semantics": _structured_tool(
            state,
            recorder,
            "compare_capability_semantics",
            "Return capability tags and evidence for semantic coverage reasoning.",
            RequirementIdArgs,
            lambda requirement_id: _capability_semantics(state, requirement_id),
        ),
        "check_public_claim_grounding": _structured_tool(
            state,
            recorder,
            "check_public_claim_grounding",
            "Find possible evidence support for one public claim.",
            ClaimArgs,
            lambda claim: _claim_grounding(state, claim),
        ),
        "classify_numeric_claim": _structured_tool(
            state,
            recorder,
            "classify_numeric_claim",
            "Classify the semantic type of a numeric claim candidate.",
            ClaimArgs,
            lambda claim: _classify_numeric_claim(claim),
        ),
        "get_resume_bullet_coverage": _structured_tool(
            state,
            recorder,
            "get_resume_bullet_coverage",
            "Return requirement IDs selected by generated resume bullets.",
            EmptyArgs,
            lambda: _resume_bullet_coverage(state),
        ),
        "rank_candidate_risks": _structured_tool(
            state,
            recorder,
            "rank_candidate_risks",
            "Rank candidate risks by severity without manufacturing new risks.",
            RiskRankingArgs,
            lambda risks, limit: _rank_candidate_risks(risks, limit),
        ),
    }


def _structured_tool(
    state: WorkflowState,
    recorder: TraceRecorder,
    name: str,
    description: str,
    args_schema: type[BaseModel],
    handler: Callable[..., StructuredToolResult],
) -> StructuredTool:
    def invoke(**kwargs: Any) -> dict[str, Any]:
        try:
            result = handler(**kwargs)
        except Exception:
            result = _error("The tool could not complete the requested operation.")
        recorder.record_tool_call(
            tool_name=name,
            arguments_summary=_arguments_summary(kwargs, state),
            return_summary=result.trace_summary,
            status=result.status,
        )
        return result.model_dump(mode="json")

    return StructuredTool.from_function(
        func=invoke,
        name=name,
        description=description,
        args_schema=args_schema,
    )


def _search_resume_evidence(
    state: WorkflowState,
    section_types: list[ResumeSectionType],
    top_k: int,
) -> StructuredToolResult:
    evidence = [
        item
        for item in state.retrieved_evidence
        if not section_types or item.section_type in section_types
    ][:top_k]
    state.allowed_evidence_ids.update(item.evidence_id for item in evidence)
    return _success(
        {"evidence": [item.model_dump(mode="json") for item in evidence]},
        f"Returned {len(evidence)} evidence item(s).",
    )


def _get_experience(
    state: WorkflowState,
    experience_id: str,
) -> StructuredToolResult:
    experience = next(
        (item for item in state.experience_records if item.experience_id == experience_id),
        None,
    )
    if experience is None:
        return _error("The requested experience was not found.")
    return _success(
        {"experience": experience.model_dump(mode="json")},
        "Returned one structured experience.",
    )


def _get_resume_section(
    state: WorkflowState,
    section_type: ResumeSectionType,
) -> StructuredToolResult:
    sections = [
        item.model_dump(mode="json")
        for item in state.structured_resume_sections
        if item.section_type == section_type
    ]
    return _success(
        {"sections": sections},
        f"Returned {len(sections)} {section_type} section(s).",
    )


def _get_requirement(
    state: WorkflowState,
    requirement_id: str,
) -> StructuredToolResult:
    requirement = next(
        (item for item in state.jd_requirements if item.requirement_id == requirement_id),
        None,
    )
    if requirement is None:
        return _error("The requested requirement was not found.")
    return _success(
        {"requirement": requirement.model_dump(mode="json")},
        "Returned one JD requirement.",
    )


def _requirement_evidence(
    state: WorkflowState,
    requirement_id: str,
    evidence_ids: list[str],
) -> StructuredToolResult:
    requirement = next(
        (item for item in state.jd_requirements if item.requirement_id == requirement_id),
        None,
    )
    if requirement is None:
        return _error("The requested requirement was not found.")
    evidence = [
        item
        for item in state.retrieved_evidence
        if item.requirement_id == requirement_id
        and (not evidence_ids or item.evidence_id in evidence_ids)
    ]
    state.allowed_evidence_ids.update(item.evidence_id for item in evidence)
    return _success(
        {
            "requirement": requirement.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        },
        f"Returned {len(evidence)} evidence item(s) for one requirement.",
    )


def _rerank_evidence(
    state: WorkflowState,
    requirement_id: str,
    evidence_ids: list[str],
) -> StructuredToolResult:
    result = _requirement_evidence(state, requirement_id, evidence_ids)
    if result.status == "error":
        return result
    preferred = {"project": 2, "internship": 2, "skill": 1, "education": 0, "other": 0}
    ranked = sorted(
        result.data["evidence"],
        key=lambda item: (preferred.get(item["section_type"], 0), item["score"]),
        reverse=True,
    )
    result.data["evidence"] = ranked
    result.trace_summary = f"Ranked {len(ranked)} evidence item(s)."
    return result


def _interviewable_requirements(state: WorkflowState) -> StructuredToolResult:
    requirements = [
        item.model_dump(mode="json")
        for item in state.jd_requirements
        if item.interviewability
    ]
    return _success(
        {"requirements": requirements},
        f"Returned {len(requirements)} interviewable requirement(s).",
    )


def _capability_semantics(
    state: WorkflowState,
    requirement_id: str,
) -> StructuredToolResult:
    result = _requirement_evidence(state, requirement_id, [])
    if result.status == "success":
        result.trace_summary = "Returned capability tags and supporting evidence."
    return result


def _claim_grounding(state: WorkflowState, claim: str) -> StructuredToolResult:
    terms = {item.casefold() for item in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", claim)}
    evidence = [
        item
        for item in state.retrieved_evidence
        if terms & {term.casefold() for term in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", item.snippet)}
    ]
    state.allowed_evidence_ids.update(item.evidence_id for item in evidence)
    return _success(
        {"evidence": [item.model_dump(mode="json") for item in evidence]},
        f"Found {len(evidence)} possible supporting evidence item(s).",
    )


def _classify_numeric_claim(claim: str) -> StructuredToolResult:
    lowered = claim.casefold()
    if re.search(r"\d{4}[年./-]", claim):
        claim_type = "date"
    elif re.search(r"\b(?:v?\d+(?:\.\d+)+)\b", claim) or "version" in lowered:
        claim_type = "model_or_version"
    elif "%" in claim or any(term in lowered for term in ("accuracy", "auc", "f1", "iou")):
        claim_type = "performance_metric"
    else:
        claim_type = "other"
    return _success(
        {"claim": claim, "claim_type": claim_type},
        f"Classified one numeric claim as {claim_type}.",
    )


def _resume_bullet_coverage(state: WorkflowState) -> StructuredToolResult:
    requirement_ids: list[str] = []
    if state.generated_assets is not None:
        requirement_ids = list(
            dict.fromkeys(
                requirement_id
                for bullet in state.generated_assets.resume_bullets
                for requirement_id in bullet.target_requirement_ids
            )
        )
    return _success(
        {"requirement_ids": requirement_ids},
        f"Returned coverage for {len(requirement_ids)} requirement(s).",
    )


def _rank_candidate_risks(
    risks: list[dict[str, Any]],
    limit: int,
) -> StructuredToolResult:
    severity = {"high": 3, "medium": 2, "low": 1}
    ranked = sorted(
        risks,
        key=lambda item: severity.get(str(item.get("severity", "")).casefold(), 0),
        reverse=True,
    )[:limit]
    return _success({"risks": ranked}, f"Ranked {len(ranked)} candidate risk(s).")


def _arguments_summary(arguments: dict[str, Any], state: WorkflowState) -> str:
    parts: list[str] = []
    for key, value in arguments.items():
        if key in {"query", "claim"}:
            rendered = _redact(str(value), state)
            parts.append(f"{key}={rendered[:80]}")
        elif isinstance(value, list):
            parts.append(f"{key}_count={len(value)}")
        else:
            parts.append(f"{key}={_redact(str(value), state)[:80]}")
    return " ".join(parts) or "no arguments"


def _redact(value: str, state: WorkflowState) -> str:
    sanitized = value
    for document in state.profile_documents:
        if document.content:
            sanitized = sanitized.replace(document.content, "[resume redacted]")
    sanitized = sanitized.replace("SYSTEM_PROMPT_SECRET", "[redacted]")
    sanitized = re.sub(
        r"(?i)(?:api[_-]?key\s*[=:]\s*|bearer\s+|sk-)[^\s,;]+",
        "[redacted]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)hidden\s+(?:chain[- ]of[- ]thought|reasoning)",
        "[redacted]",
        sanitized,
    )
    return " ".join(sanitized.split())


def _success(data: dict[str, Any], summary: str) -> StructuredToolResult:
    return StructuredToolResult(status="success", data=data, trace_summary=summary)


def _error(message: str) -> StructuredToolResult:
    return StructuredToolResult(
        status="error",
        data={},
        trace_summary="The tool returned a controlled error.",
        error=StructuredToolError(code="REACT_TOOL_CALL_ERROR", message=message),
    )

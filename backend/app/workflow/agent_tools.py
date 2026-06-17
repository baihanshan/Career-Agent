from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.api.schemas import (
    AgentToolResult,
    AgentTrace,
    EvidenceItem,
    JDRequirement,
    ResumeSectionType,
)
from backend.app.workflow.state import WorkflowState


MAX_REACT_AGENT_STEPS = 3

AGENT_TOOL_ALLOWLIST = {
    "resume_evidence": {
        "search_resume_evidence",
        "get_resume_section",
        "rerank_evidence",
    },
    "interview_prep": {
        "get_high_priority_jd_requirements",
        "get_matched_project_and_internship_evidence",
        "draft_answer",
    },
    "risk_auditor": {
        "check_requirement_coverage",
        "find_resume_vague_claims",
        "check_generated_claim_grounding",
        "rank_top_risks",
    },
}


class TraceRecorder:
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.steps: list[AgentToolResult] = []

    def record(self, result: AgentToolResult) -> None:
        self.steps.append(result)

    def attach_to_state(
        self,
        state: WorkflowState,
        final_decision_summary: str,
    ) -> WorkflowState:
        trace = AgentTrace(
            agent_name=self.agent_name,
            steps=self.steps,
            final_decision_summary=_summary(final_decision_summary),
        )
        return state.model_copy(update={"agent_traces": [*state.agent_traces, trace]})


def build_agent_toolbox(
    state: WorkflowState,
    agent_name: str | None = None,
) -> dict[str, Callable[..., AgentToolResult]]:
    tools = {
        "search_resume_evidence": lambda query, section_filter=None, top_k=5: _tool_result(
            "search_resume_evidence",
            f"query={_summary(query, 80)} section_filter={section_filter or []} top_k={top_k}",
            _search_resume_evidence(state, section_filter=section_filter, top_k=top_k),
        ),
        "get_resume_section": lambda section_type: _tool_result(
            "get_resume_section",
            f"section_type={section_type}",
            _get_resume_section(state, section_type=section_type),
        ),
        "rerank_evidence": lambda requirement, evidence_items: _tool_result(
            "rerank_evidence",
            f"requirement={_requirement_label(requirement)} evidence_count={len(evidence_items)}",
            _rerank_evidence(requirement=requirement, evidence_items=evidence_items),
        ),
        "get_high_priority_jd_requirements": lambda: _tool_result(
            "get_high_priority_jd_requirements",
            "importance=high",
            _get_high_priority_jd_requirements(state),
        ),
        "get_matched_project_and_internship_evidence": lambda: _tool_result(
            "get_matched_project_and_internship_evidence",
            "section_type in project,internship",
            _get_matched_project_and_internship_evidence(state),
        ),
        "draft_answer": lambda question, evidence, jd_requirement: _tool_result(
            "draft_answer",
            f"question={_summary(question, 80)} evidence={_evidence_label(evidence)}",
            _draft_answer(question=question, evidence=evidence, jd_requirement=jd_requirement),
        ),
        "check_requirement_coverage": lambda requirement: _tool_result(
            "check_requirement_coverage",
            f"requirement={_requirement_label(requirement)}",
            _check_requirement_coverage(state, requirement=requirement),
        ),
        "find_resume_vague_claims": lambda: _tool_result(
            "find_resume_vague_claims",
            "source=generated_resume_bullets",
            _find_resume_vague_claims(state),
        ),
        "check_generated_claim_grounding": lambda claim: _tool_result(
            "check_generated_claim_grounding",
            f"claim={_summary(claim, 80)}",
            _check_generated_claim_grounding(state, claim=claim),
        ),
        "rank_top_risks": lambda risks, limit=3: _tool_result(
            "rank_top_risks",
            f"risk_count={len(risks)} limit={limit}",
            _rank_top_risks(risks=risks, limit=limit),
        ),
    }
    if agent_name is None:
        return tools
    allowed_tools = AGENT_TOOL_ALLOWLIST[agent_name]
    return {name: tool for name, tool in tools.items() if name in allowed_tools}


def _search_resume_evidence(
    state: WorkflowState,
    section_filter: list[ResumeSectionType] | None,
    top_k: int,
) -> str:
    evidence = [
        item
        for item in state.retrieved_evidence
        if not section_filter or item.section_type in section_filter
    ][:top_k]
    labels = [_evidence_label(item) for item in evidence]
    return f"{len(evidence)} evidence item(s): {', '.join(labels) or 'none'}."


def _get_resume_section(state: WorkflowState, section_type: ResumeSectionType) -> str:
    sections = [
        section
        for section in state.structured_resume_sections
        if section.section_type == section_type
    ]
    titles = [_summary(section.section_title, 48) for section in sections]
    return f"{len(sections)} {section_type} section(s): {', '.join(titles) or 'none'}."


def _rerank_evidence(requirement: JDRequirement, evidence_items: list[EvidenceItem]) -> str:
    preferred = {"project": 2, "internship": 2, "skill": 1, "education": 0, "other": 0}
    ranked = sorted(
        evidence_items,
        key=lambda item: (preferred.get(item.section_type, 0), item.score),
        reverse=True,
    )
    labels = [_evidence_label(item) for item in ranked[:3]]
    return f"Top evidence for {_requirement_label(requirement)}: {', '.join(labels) or 'none'}."


def _get_high_priority_jd_requirements(state: WorkflowState) -> str:
    requirements = [item for item in state.jd_requirements if item.importance == "high"]
    labels = [_requirement_label(item) for item in requirements]
    return f"{len(requirements)} high-priority requirement(s): {', '.join(labels) or 'none'}."


def _get_matched_project_and_internship_evidence(state: WorkflowState) -> str:
    evidence = [
        item
        for item in state.retrieved_evidence
        if item.section_type in {"project", "internship"}
    ]
    labels = [_evidence_label(item) for item in evidence[:5]]
    return f"{len(evidence)} project/internship evidence item(s): {', '.join(labels) or 'none'}."


def _draft_answer(question: str, evidence: EvidenceItem, jd_requirement: JDRequirement) -> str:
    return (
        f"Draft answer outline for '{_summary(question, 60)}': connect "
        f"{_requirement_label(jd_requirement)} with {_evidence_label(evidence)}."
    )


def _check_requirement_coverage(state: WorkflowState, requirement: JDRequirement) -> str:
    matching = [
        item
        for item in state.retrieved_evidence
        if item.requirement_id == requirement.requirement_id
    ]
    status = "covered" if matching else "not covered"
    return f"{_requirement_label(requirement)} is {status} by {len(matching)} evidence item(s)."


def _find_resume_vague_claims(state: WorkflowState) -> str:
    if state.generated_assets is None:
        return "No generated assets available."
    vague_terms = {"production", "large-scale", "advanced", "significant", "robust"}
    claims = [
        bullet.text
        for bullet in state.generated_assets.resume_bullets
        if any(term in bullet.text.lower() for term in vague_terms)
    ]
    return f"{len(claims)} potentially vague claim(s): {_summary('; '.join(claims) or 'none')}."


def _check_generated_claim_grounding(state: WorkflowState, claim: str) -> str:
    claim_terms = {term.lower() for term in claim.split() if len(term) > 3}
    matching = [
        item
        for item in state.retrieved_evidence
        if claim_terms & {term.lower().strip(".,;:") for term in item.snippet.split()}
    ]
    status = "has possible support" if matching else "has no direct support"
    return f"Claim '{_summary(claim, 60)}' {status} from {len(matching)} evidence item(s)."


def _rank_top_risks(risks: list[dict[str, Any]], limit: int = 3) -> str:
    severity_rank = {"high": 3, "medium": 2, "low": 1}
    ranked = sorted(
        risks,
        key=lambda risk: severity_rank.get(str(risk.get("severity", "")).lower(), 0),
        reverse=True,
    )[:limit]
    labels = [
        f"{_summary(str(risk.get('title', 'untitled')), 48)}:{risk.get('severity', 'unknown')}"
        for risk in ranked
    ]
    return f"Top {len(ranked)} risk(s): {', '.join(labels) or 'none'}."


def _tool_result(tool_name: str, arguments_summary: str, return_summary: str) -> AgentToolResult:
    return AgentToolResult(
        tool_name=tool_name,
        arguments_summary=_summary(arguments_summary),
        return_summary=_summary(return_summary),
        status="success",
    )


def _requirement_label(requirement: JDRequirement) -> str:
    return f"{requirement.requirement_id}:{_summary(requirement.text, 60)}"


def _evidence_label(evidence: EvidenceItem) -> str:
    return f"{evidence.evidence_id}:{evidence.section_type}:score={round(evidence.score, 3)}"


def _summary(value: str, limit: int = 320) -> str:
    sanitized = value.replace("SYSTEM_PROMPT_SECRET", "[redacted]")
    sanitized = " ".join(sanitized.split())
    if len(sanitized) <= limit:
        return sanitized
    return f"{sanitized[: limit - 3]}..."

from __future__ import annotations

from backend.app.api.schemas import AgentToolResult, EvidenceItem
from backend.app.core.errors import AgentExecutionError
from backend.app.workflow.agent_tools import MAX_REACT_AGENT_STEPS, TraceRecorder
from backend.app.workflow.state import AnalysisState

try:
    from langgraph.prebuilt import create_react_agent
except ImportError:  # pragma: no cover - dependency is present in normal installs
    create_react_agent = None


RESUME_EVIDENCE_AGENT_PROMPT = """
You are the Resume Evidence Agent.
Use only the allowed tools: search_resume_evidence, get_resume_section, rerank_evidence.
Prioritize project/internship evidence for resume bullets and downstream generation.
Skill evidence is auxiliary. If the first result set only contains skill evidence, continue searching project/internship sections.
Stop after at most 3 tool steps. If no usable evidence is found, fail rather than returning weak evidence.
Return structured evidence items only; do not expose hidden reasoning.
""".strip()


class ResumeEvidenceAgentError(AgentExecutionError):
    pass


class ResumeEvidenceAgent:
    def __init__(self, max_steps: int = MAX_REACT_AGENT_STEPS) -> None:
        self.max_steps = max_steps

    def run(self, state: AnalysisState, retrieval_service) -> AnalysisState:
        recorder = TraceRecorder(agent_name="resume_evidence")
        evidence: list[EvidenceItem] = []
        usable_evidence_seen = False

        for step_number in range(1, self.max_steps + 1):
            section_filter = _section_filter_for_step(
                step_number=step_number,
                evidence=evidence,
                usable_evidence_seen=usable_evidence_seen,
            )
            retrieved = retrieval_service.retrieve_evidence(
                requirements=state.jd_requirements,
                top_k=state.run_config.top_k,
                section_filter=section_filter,
            )
            recorder.record(
                AgentToolResult(
                    tool_name="search_resume_evidence",
                    arguments_summary=(
                        f"step={step_number} section_filter={section_filter or []} "
                        f"top_k={state.run_config.top_k}"
                    ),
                    return_summary=_evidence_summary(retrieved),
                    status="success",
                )
            )

            evidence = _merge_evidence(evidence, retrieved)
            usable_evidence_seen = _has_usable_evidence(evidence)
            if usable_evidence_seen:
                break

        if not evidence or not usable_evidence_seen:
            raise ResumeEvidenceAgentError(
                "Resume Evidence Agent found no usable evidence in 3 tool steps.",
                failed_tool="search_resume_evidence",
                trace_summary=recorder.summary(),
            )

        ranked = _rank_evidence(evidence)
        recorder.record(
            AgentToolResult(
                tool_name="rerank_evidence",
                arguments_summary=f"evidence_count={len(evidence)}",
                return_summary=_evidence_summary(ranked),
                status="success",
            )
        )
        return recorder.attach_to_state(
            state.model_copy(update={"retrieved_evidence": ranked}),
            final_decision_summary="Prioritized project/internship evidence for downstream generation.",
        )


def create_resume_evidence_react_agent(model, tools):
    if create_react_agent is None:
        raise RuntimeError("langgraph.prebuilt.create_react_agent is unavailable.")
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=RESUME_EVIDENCE_AGENT_PROMPT,
    )


def _section_filter_for_step(
    step_number: int,
    evidence: list[EvidenceItem],
    usable_evidence_seen: bool,
) -> list[str] | None:
    if step_number == 1:
        return None
    if evidence and not usable_evidence_seen:
        return ["project", "internship"]
    return None


def _merge_evidence(
    existing: list[EvidenceItem],
    new_items: list[EvidenceItem],
) -> list[EvidenceItem]:
    by_id = {item.evidence_id: item for item in existing}
    for item in new_items:
        by_id.setdefault(item.evidence_id, item)
    return list(by_id.values())


def _rank_evidence(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    section_priority = {"project": 3, "internship": 3, "skill": 1, "education": 0, "other": 0}
    return sorted(
        evidence,
        key=lambda item: (section_priority.get(item.section_type, 0), item.score),
        reverse=True,
    )


def _has_usable_evidence(evidence: list[EvidenceItem]) -> bool:
    return any(item.section_type != "skill" for item in evidence)


def _evidence_summary(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "0 evidence items."
    labels = [
        f"{item.evidence_id}:{item.section_type}:score={round(item.score, 3)}"
        for item in evidence[:5]
    ]
    return f"{len(evidence)} evidence item(s): {', '.join(labels)}."

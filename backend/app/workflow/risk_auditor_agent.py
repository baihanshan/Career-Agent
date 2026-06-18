from __future__ import annotations

import re
from collections.abc import Callable

from backend.app.api.schemas import RiskItem, RiskReport
from backend.app.core.errors import AgentExecutionError
from backend.app.workflow.agent_tools import (
    MAX_REACT_AGENT_STEPS,
    TraceRecorder,
    build_agent_toolbox,
)
from backend.app.workflow.state import AnalysisState

try:
    from langgraph.prebuilt import create_react_agent
except ImportError:  # pragma: no cover - dependency is present in normal installs
    create_react_agent = None


RISK_AUDITOR_AGENT_PROMPT = """
You are the Risk Auditor Agent.
Use only check_requirement_coverage, find_resume_vague_claims,
check_generated_claim_grounding, and rank_top_risks. Finish within at most 3 ReAct rounds.
Prioritize project and internship evidence; a skill list alone does not cover a JD requirement.
Return at most 3 concrete risks ordered by severity and job-search impact.
Each risk must include its title, user-readable JD requirement, current resume state,
specific reason, and actionable recommendation. Never expose internal requirement IDs or
evidence IDs. Supported risk types are JD 未覆盖, 简历表述太泛, 证据不足, and 生成内容可能夸大.
""".strip()


RiskGenerator = Callable[[AnalysisState], RiskReport]
_INTERNAL_ID_PATTERN = re.compile(r"\b(?:req|ev|chunk)_[A-Za-z0-9_:.-]+\b", re.IGNORECASE)
_SEVERITY_SCORE = {"high": 3, "medium": 2, "low": 1}
_IMPORTANCE_SCORE = {"high": 3, "medium": 2, "low": 1}


class RiskAuditorAgentError(AgentExecutionError):
    pass


class RiskAuditorAgent:
    def __init__(
        self,
        max_steps: int = MAX_REACT_AGENT_STEPS,
        risk_generator: RiskGenerator | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.risk_generator = risk_generator or _generate_risks

    def run(self, state: AnalysisState) -> AnalysisState:
        if state.generated_assets is None or state.evaluation_report is None:
            raise RiskAuditorAgentError(
                "Generated assets and evaluation report are required before risk audit.",
                failed_tool="precondition_check",
                trace_summary="steps=0 tools=none statuses=none",
            )

        recorder = TraceRecorder(agent_name="risk_auditor")
        toolbox = build_agent_toolbox(state, agent_name="risk_auditor")
        has_signals = bool(_candidate_risks(state))

        for _attempt in range(1, self.max_steps + 1):
            for requirement in state.jd_requirements:
                recorder.record(toolbox["check_requirement_coverage"](requirement=requirement))
            recorder.record(toolbox["find_resume_vague_claims"]())
            for bullet in state.generated_assets.resume_bullets:
                recorder.record(toolbox["check_generated_claim_grounding"](claim=bullet.text))

            generated = self.risk_generator(state)
            normalized = _normalize_report(generated, state)
            recorder.record(
                toolbox["rank_top_risks"](
                    risks=[risk.model_dump() for risk in normalized.risks],
                    limit=3,
                )
            )
            if _is_qualified(normalized, state, has_signals):
                return recorder.attach_to_state(
                    state.model_copy(update={"risk_report": normalized}),
                    final_decision_summary=(
                        f"Selected {len(normalized.risks)} concrete risk(s) by severity and "
                        "job-search impact."
                    ),
                )

        raise RiskAuditorAgentError(
            f"Risk Auditor Agent produced no qualified output after {self.max_steps} attempts.",
            failed_tool="rank_top_risks",
            trace_summary=recorder.summary(),
        )


def create_risk_auditor_react_agent(model, tools):
    if create_react_agent is None:
        raise RuntimeError("langgraph.prebuilt.create_react_agent is unavailable.")
    allowed_names = {
        "check_requirement_coverage",
        "find_resume_vague_claims",
        "check_generated_claim_grounding",
        "rank_top_risks",
    }
    if isinstance(tools, dict):
        selected_tools = [tool for name, tool in tools.items() if name in allowed_names]
    else:
        selected_tools = list(tools)
    return create_react_agent(
        model=model,
        tools=selected_tools,
        prompt=RISK_AUDITOR_AGENT_PROMPT,
    )


def _generate_risks(state: AnalysisState) -> RiskReport:
    return _normalize_risks(_candidate_risks(state), state)


def _candidate_risks(state: AnalysisState) -> list[RiskItem]:
    report = state.evaluation_report
    if report is None:
        return []

    risks: list[RiskItem] = []
    requirement_by_id = {item.requirement_id: item for item in state.jd_requirements}
    project_internship_requirement_ids = {
        item.requirement_id
        for item in state.retrieved_evidence
        if item.section_type in {"project", "internship"}
    }
    gap_ids = {gap.requirement_id for gap in report.coverage_gaps}
    for requirement in state.jd_requirements:
        if (
            requirement.importance == "high"
            and requirement.requirement_id not in project_internship_requirement_ids
        ):
            gap_ids.add(requirement.requirement_id)

    for requirement_id in gap_ids:
        requirement = requirement_by_id.get(requirement_id)
        requirement_text = requirement.text if requirement else "关键岗位要求"
        risks.append(
            RiskItem(
                risk_type="JD 未覆盖",
                title="关键岗位要求缺少项目或实习支撑",
                jd_requirement_summary=requirement_text,
                resume_current_state="当前项目或实习经历中未找到直接支撑该要求的具体内容。",
                risk_reason="仅列出技能或完全缺少相关经历，难以证明具备岗位要求的实践能力。",
                recommendation="补充一个真实项目或实习案例，说明个人职责、技术方案和可验证结果。",
                severity="high" if requirement and requirement.importance == "high" else "medium",
            )
        )

    for warning in report.grounding_warnings:
        exaggerated = bool(re.search(r"数字|夸大|unsupported|number", warning.reason, re.I))
        risks.append(
            RiskItem(
                risk_type="生成内容可能夸大" if exaggerated else "证据不足",
                title="生成内容包含缺少证据支撑的表述",
                jd_requirement_summary=_requirement_summary_for_claim(state, warning.claim),
                resume_current_state=warning.claim,
                risk_reason=warning.reason,
                recommendation="删除无法核实的内容，或补充能直接证明该职责、技术或结果的材料。",
                severity=warning.severity,
            )
        )

    if report.specificity_notes:
        risks.append(
            RiskItem(
                risk_type="简历表述太泛",
                title="项目或实习描述缺少具体行动与结果",
                jd_requirement_summary=_top_requirement_text(state),
                resume_current_state="；".join(report.specificity_notes),
                risk_reason="泛化描述无法让招聘方判断候选人的个人贡献和实际能力。",
                recommendation="补充项目目标、个人职责、关键技术决策以及有证据支撑的结果。",
                severity="medium",
            )
        )
    return risks


def _normalize_report(report: RiskReport, state: AnalysisState) -> RiskReport:
    return _normalize_risks(report.risks, state)


def _normalize_risks(risks: list[RiskItem], state: AnalysisState) -> RiskReport:
    unique: dict[tuple[str, str, str], RiskItem] = {}
    for risk in risks:
        sanitized = _sanitize_risk(risk, state)
        key = (
            sanitized.risk_type,
            sanitized.title.casefold(),
            sanitized.jd_requirement_summary.casefold(),
        )
        existing = unique.get(key)
        if existing is None or _SEVERITY_SCORE[sanitized.severity] > _SEVERITY_SCORE[
            existing.severity
        ]:
            unique[key] = sanitized

    importance_by_text = {
        item.text.casefold(): _IMPORTANCE_SCORE[item.importance]
        for item in state.jd_requirements
    }
    ranked = sorted(
        unique.values(),
        key=lambda risk: (
            _SEVERITY_SCORE[risk.severity],
            importance_by_text.get(risk.jd_requirement_summary.casefold(), 0),
        ),
        reverse=True,
    )[:3]
    return RiskReport(risks=ranked)


def _sanitize_risk(risk: RiskItem, state: AnalysisState) -> RiskItem:
    hidden_ids = {
        *(item.requirement_id for item in state.jd_requirements),
        *(item.evidence_id for item in state.retrieved_evidence),
        *(item.chunk_id for item in state.retrieved_evidence),
    }

    def clean(value: str) -> str:
        cleaned = value
        for hidden_id in hidden_ids:
            cleaned = cleaned.replace(hidden_id, "")
        cleaned = _INTERNAL_ID_PATTERN.sub("", cleaned)
        return " ".join(cleaned.split()).strip(" ,，。:：;；-") or "未提供可展示信息"

    return risk.model_copy(
        update={
            "title": clean(risk.title),
            "jd_requirement_summary": clean(risk.jd_requirement_summary),
            "resume_current_state": clean(risk.resume_current_state),
            "risk_reason": clean(risk.risk_reason),
            "recommendation": clean(risk.recommendation),
        }
    )


def _is_qualified(report: RiskReport, state: AnalysisState, has_signals: bool) -> bool:
    if has_signals and not report.risks:
        return False
    hidden_ids = {
        *(item.requirement_id for item in state.jd_requirements),
        *(item.evidence_id for item in state.retrieved_evidence),
    }
    for risk in report.risks:
        visible = " ".join(str(value) for value in risk.model_dump().values())
        if any(hidden_id in visible for hidden_id in hidden_ids):
            return False
    return True


def _requirement_summary_for_claim(state: AnalysisState, claim: str) -> str:
    claim_lower = claim.casefold()
    matching = [
        requirement
        for requirement in state.jd_requirements
        if any(keyword.casefold() in claim_lower for keyword in requirement.keywords)
    ]
    return matching[0].text if matching else _top_requirement_text(state)


def _top_requirement_text(state: AnalysisState) -> str:
    ranked = sorted(
        state.jd_requirements,
        key=lambda item: _IMPORTANCE_SCORE[item.importance],
        reverse=True,
    )
    return ranked[0].text if ranked else "目标岗位的核心要求"

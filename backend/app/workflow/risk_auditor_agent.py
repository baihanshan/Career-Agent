from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from backend.app.api.schemas import RiskItem, RiskReport
from backend.app.core.errors import AgentExecutionError, ReActErrorCode
from backend.app.llm.react_model import react_response_format
from backend.app.evaluation.quality_gate import (
    PublicOutputQualityGate,
    quality_issues_to_retry_message,
)
from backend.app.workflow.agent_tools import MAX_REACT_AGENT_STEPS, TraceRecorder
from backend.app.workflow.domain_models import (
    InternalRiskItem,
    InternalRiskReport,
    QualityIssue,
)
from backend.app.workflow.json_outputs import parse_json_payload_from_text
from backend.app.workflow.public_output import InternalIdLeakDetector
from backend.app.workflow.react_tools import build_structured_react_tools
from backend.app.workflow.state import AnalysisState

try:
    from langchain.agents import create_agent
except ImportError:  # pragma: no cover - dependency is present in normal installs
    create_agent = None


RISK_AUDITOR_AGENT_PROMPT = """
You are the Risk Auditor ReAct Agent. Distinguish three independent concepts:
resume coverage (whether the full resume contains relevant evidence), evidence strength
(whether that evidence proves the requirement), and bullet coverage (whether one of three
generated bullets selected the requirement). Missing bullet coverage alone is never an
ability gap.

Before proposing risks, classify the role type from the JD and requirement catalog. Use
the risk_audit_policy payload to decide which screening dimensions are truly core for
that role type. Do not mechanically audit every JD sentence. Think like a real recruiter,
business interviewer, or technical interviewer: focus on the gaps most likely to affect
screening, interview depth, or hiring confidence.

For technical R&D roles, prioritize core technical direction, missing required technology
experience, project depth, engineering implementation, algorithm/model/system/architecture
ability, data processing, performance optimization, deployment, stability, scale, and
quantified outcomes. For product or project management roles, prioritize requirement
analysis, user/business scenario understanding, product or project ownership, delivery
from 0 to 1 or 1 to N, cross-functional coordination, data/competitive/user-feedback
analysis, growth/conversion/business metrics, personal contribution, and business impact.

Generic soft skills such as learning ability, adaptability, communication, teamwork,
passion, pressure tolerance, responsibility, independent thinking, and retrospection are
low-priority by default. Only output a soft-skill risk when it is a true core screening
criterion for this role, is not already indirectly shown by projects, internships, team
delivery, or outcomes, and would realistically affect resume screening or interviews.

Use the structured requirement, evidence, experience, capability-semantic, numeric,
public-claim-grounding, bullet-coverage, and risk-ranking tools before returning output.
Treat strong direct or indirect support as covered. Multiple projects may jointly prove a
foundational capability. For OR requirements, one reliably supported alternative satisfies
the whole requirement. Education and skill evidence may provide contextual support, while
project and internship facts establish applied support.

Return no risk when the evidence does not justify one; never manufacture three items.
Every risk must explain a real gap and an actionable recommendation. Internal requirement
and evidence IDs belong only in requirement_ids and internal_supporting_evidence_ids and
must never appear in user-visible text.

Return only JSON with a top-level risks list. Each risk contains risk_type, title,
jd_requirement_summary, resume_current_state, risk_reason, recommendation, severity,
risk_dimension, risk_priority, requirement_ids, and internal_supporting_evidence_ids.
Use risk_priority from 0 to 100, where core role risks should be much higher than generic
soft-skill concerns. Do not return markdown or hidden reasoning.
JSON example:
{"risks":[{"risk_type":"证据不足","title":"核心要求缺少足够项目细节","jd_requirement_summary":"JD asks for applied machine learning experience.","resume_current_state":"The resume mentions related work but lacks method and evaluation details.","risk_reason":"The current evidence is relevant but not strong enough to prove the requirement.","recommendation":"Add model choice, dataset, evaluation metric, and your personal contribution.","severity":"medium","risk_dimension":"project_depth","risk_priority":80,"requirement_ids":["req_example"],"internal_supporting_evidence_ids":["ev_example"]}]}
""".strip()


_SEVERITY_SCORE = {"high": 3, "medium": 2, "low": 1}
_RISK_DIMENSION_SCORE = {
    "core_technical_direction": 100,
    "missing_required_technology": 95,
    "algorithm_model_system_architecture": 90,
    "project_depth": 85,
    "engineering_implementation": 80,
    "data_modeling": 75,
    "scale_distributed_deployment_stability": 70,
    "quantified_outcomes": 65,
    "requirement_analysis": 100,
    "business_user_scenario_understanding": 95,
    "product_project_ownership": 90,
    "zero_to_one_or_scale_delivery": 85,
    "cross_functional_delivery": 75,
    "business_outcome_metrics": 70,
    "personal_contribution_clarity": 65,
    "generic_soft_skill": 10,
}

_RISK_AUDIT_POLICY = {
    "required_first_step": "classify_role_type",
    "role_type_options": [
        "technical_r_and_d",
        "product_project_management",
        "business_analysis_or_solution",
        "other",
    ],
    "role_priority_dimensions": {
        "technical_r_and_d": [
            "core_technical_direction",
            "missing_required_technology",
            "algorithm_model_system_architecture",
            "project_depth",
            "engineering_implementation",
            "data_modeling",
            "scale_distributed_deployment_stability",
            "quantified_outcomes",
            "generic_soft_skill",
        ],
        "product_project_management": [
            "requirement_analysis",
            "business_user_scenario_understanding",
            "product_project_ownership",
            "zero_to_one_or_scale_delivery",
            "cross_functional_delivery",
            "business_outcome_metrics",
            "personal_contribution_clarity",
            "generic_soft_skill",
        ],
    },
    "soft_skill_rule": {
        "default_priority": "low",
        "soft_skill_examples": [
            "learning_ability",
            "adaptability",
            "communication",
            "teamwork",
            "passion",
            "pressure_tolerance",
            "responsibility",
            "independent_thinking",
            "retrospection",
        ],
        "only_surface_when": [
            "the role treats it as a core screening criterion",
            "projects, internships, team delivery, or outcomes do not indirectly prove it",
            "the gap would realistically affect resume screening or interviews",
        ],
    },
}


class RiskAuditorAgentError(AgentExecutionError):
    def __init__(
        self,
        message: str,
        *,
        failed_tool: str,
        trace_summary: str,
        code: str = ReActErrorCode.REACT_QUALITY_GATE_FAILED.value,
    ) -> None:
        super().__init__(
            message,
            failed_tool=failed_tool,
            trace_summary=trace_summary,
        )
        self.code = code


class RiskAuditorAgent:
    def __init__(
        self,
        model: Any | None = None,
        *,
        max_steps: int = MAX_REACT_AGENT_STEPS,
        max_attempts: int = 3,
    ) -> None:
        self.model = model or _DeterministicRiskAuditorChatModel()
        self.max_steps = max_steps
        self.max_attempts = max_attempts
        self.quality_gate = PublicOutputQualityGate()

    def run(self, state: AnalysisState) -> AnalysisState:
        if state.generated_assets is None or state.evaluation_report is None:
            raise RiskAuditorAgentError(
                "Generated assets and evaluation report are required before risk audit.",
                failed_tool="precondition_check",
                trace_summary="steps=0 tools=none statuses=none",
            )

        all_steps = []
        retry_feedback = ""
        last_issues: list[QualityIssue] = []

        for attempt_number in range(1, self.max_attempts + 1):
            tool_state = state.model_copy(deep=True)
            tool_state.allowed_evidence_ids = set()
            recorder = TraceRecorder(
                agent_name="risk_auditor",
                attempt_number=attempt_number,
            )
            tools = build_structured_react_tools(
                tool_state,
                "risk_auditor",
                recorder,
            )
            agent = create_risk_auditor_react_agent(self.model, tools)
            try:
                result = agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": _invocation_prompt(tool_state, retry_feedback),
                            }
                        ]
                    },
                    config={"recursion_limit": self.max_steps * 3 + 8},
                )
                report = _parse_final_report(result)
            except Exception as exc:
                all_steps.extend(recorder.steps)
                last_issues = [
                    _quality_issue(
                        "REACT_OUTPUT_PARSE_ERROR",
                        "risk_report",
                        "Return valid JSON matching the internal risk report schema.",
                    )
                ]
                retry_feedback = quality_issues_to_retry_message(last_issues)
                if attempt_number == self.max_attempts:
                    raise RiskAuditorAgentError(
                        "Risk Auditor Agent could not produce valid structured output.",
                        failed_tool="structured_output",
                        trace_summary=_trace_summary(all_steps),
                        code=ReActErrorCode.REACT_OUTPUT_PARSE_ERROR.value,
                    ) from exc
                continue

            all_steps.extend(recorder.steps)
            _normalize_internal_supporting_evidence_ids(tool_state, report)
            last_issues = _validate_report(
                state=tool_state,
                report=report,
                tool_names=[step.tool_name for step in recorder.steps],
                quality_gate=self.quality_gate,
            )
            if not last_issues:
                normalized = _normalize_report(report, tool_state)
                public_report = _to_public_report(normalized)
                final_recorder = TraceRecorder(agent_name="risk_auditor")
                final_recorder.steps = all_steps
                updated = state.model_copy(
                    update={
                        "internal_risk_report": normalized,
                        "risk_report": public_report,
                    }
                )
                return final_recorder.attach_to_state(
                    updated,
                    final_decision_summary=(
                        f"Validated and ranked {len(normalized.risks)} evidence-consistent risk(s)."
                    ),
                )

            retry_feedback = quality_issues_to_retry_message(last_issues)

        if any(step.status == "error" for step in all_steps):
            error_code = ReActErrorCode.REACT_TOOL_CALL_ERROR.value
        elif any(issue.code == "UNKNOWN_EVIDENCE_ID" for issue in last_issues):
            error_code = ReActErrorCode.REACT_EVIDENCE_VIOLATION.value
        else:
            error_code = ReActErrorCode.REACT_QUALITY_GATE_FAILED.value
        raise RiskAuditorAgentError(
            "Risk Auditor Agent failed deterministic quality validation after 3 attempts.",
            failed_tool="quality_gate",
            trace_summary=_trace_summary(all_steps),
            code=error_code,
        )


def create_risk_auditor_react_agent(model, tools):
    if create_agent is None:
        raise RuntimeError("langchain.agents.create_agent is unavailable.")
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=RISK_AUDITOR_AGENT_PROMPT,
        response_format=react_response_format(model, InternalRiskReport),
        name="risk_auditor",
    )


def _invocation_prompt(state: AnalysisState, retry_feedback: str) -> str:
    payload = {
        "risk_audit_policy": _RISK_AUDIT_POLICY,
        "job_description_excerpt": state.job_description[:1200],
        "requirement_catalog": [
            {
                "requirement_id": item.requirement_id,
                "category": item.category,
                "text": item.text,
                "importance": item.importance,
                "capability_tags": item.capability_tags,
                "verification_mode": item.verification_mode,
                "interviewability": item.interviewability,
                "logical_operator": item.logical_operator,
                "alternatives": item.alternatives,
            }
            for item in state.jd_requirements
        ],
        "experience_catalog": [
            {
                "experience_id": item.experience_id,
                "experience_type": item.experience_type,
                "name": item.name,
            }
            for item in state.experience_records
        ],
        "grounding_warnings": [
            {
                "claim": item.claim,
                "reason": item.reason,
                "severity": item.severity,
            }
            for item in state.evaluation_report.grounding_warnings
        ],
        "specificity_notes": state.evaluation_report.specificity_notes,
    }
    prompt = (
        "Inspect the internal catalog with tools and return an evidence-consistent risk report:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    if retry_feedback:
        prompt += "\n\nPrevious output failed validation.\n" + retry_feedback
    return prompt


def _parse_final_report(result: dict[str, Any]) -> InternalRiskReport:
    structured = result.get("structured_response")
    if structured is not None:
        return InternalRiskReport.model_validate(_coerce_risk_report_payload(structured))
    messages = result.get("messages") or []
    content = next(
        (
            message.content
            for message in reversed(messages)
            if getattr(message, "type", "") == "ai"
            and getattr(message, "content", "")
        ),
        "",
    )
    if not isinstance(content, str):
        raise ValueError("Final Agent message must contain JSON text.")
    payload = parse_json_payload_from_text(content)
    return InternalRiskReport.model_validate(_coerce_risk_report_payload(payload))


def _coerce_risk_report_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, InternalRiskReport):
        return payload.model_dump(mode="json")
    if isinstance(payload, list):
        return {"risks": [_coerce_risk_item(item) for item in payload]}
    if not isinstance(payload, dict):
        return payload

    risks = _extract_risks(payload)
    if risks is None:
        return payload
    return {"risks": [_coerce_risk_item(item) for item in risks]}


def _extract_risks(payload: dict[str, Any]) -> Any:
    if "risks" in payload:
        return payload["risks"]
    for key in ("risk_report", "report", "result", "output"):
        value = payload.get(key)
        if isinstance(value, dict) and "risks" in value:
            return value["risks"]
    return None


def _coerce_risk_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    coerced = dict(item)
    coerced["severity"] = _coerce_severity(coerced.get("severity", "medium"))
    coerced["risk_priority"] = _coerce_risk_priority(
        coerced.get("risk_priority", coerced.get("priority", 0))
    )
    for key in ("requirement_ids", "internal_supporting_evidence_ids"):
        coerced[key] = _coerce_string_list(coerced.get(key, []))
    return coerced


def _coerce_severity(value: Any) -> str:
    normalized = str(value).strip().casefold()
    mapping = {
        "高": "high",
        "高风险": "high",
        "high": "high",
        "中": "medium",
        "中风险": "medium",
        "medium": "medium",
        "med": "medium",
        "低": "low",
        "低风险": "low",
        "low": "low",
    }
    return mapping.get(normalized, "medium")


def _coerce_risk_priority(value: Any) -> int:
    if isinstance(value, int):
        return max(0, min(value, 100))
    try:
        return max(0, min(int(str(value).strip()), 100))
    except ValueError:
        mapping = {
            "critical": 95,
            "核心": 90,
            "high": 80,
            "高": 80,
            "medium": 50,
            "中": 50,
            "low": 20,
            "低": 20,
        }
        return mapping.get(str(value).strip().casefold(), 0)


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _normalize_internal_supporting_evidence_ids(
    state: AnalysisState,
    report: InternalRiskReport,
) -> None:
    evidence_by_requirement: dict[str, list[str]] = {}
    for item in state.retrieved_evidence:
        if item.evidence_id not in state.allowed_evidence_ids:
            continue
        evidence_by_requirement.setdefault(item.requirement_id, []).append(item.evidence_id)

    for risk in report.risks:
        valid_ids = [
            evidence_id
            for evidence_id in dict.fromkeys(risk.internal_supporting_evidence_ids)
            if evidence_id in state.allowed_evidence_ids
        ]
        if not valid_ids:
            candidates: list[str] = []
            for requirement_id in risk.requirement_ids:
                candidates.extend(evidence_by_requirement.get(requirement_id, []))
            valid_ids = list(dict.fromkeys(candidates))[:3]
        risk.internal_supporting_evidence_ids = valid_ids


def _validate_report(
    *,
    state: AnalysisState,
    report: InternalRiskReport,
    tool_names: list[str],
    quality_gate: PublicOutputQualityGate,
) -> list[QualityIssue]:
    issues = quality_gate.validate_evidence_allowlist(
        {
            f"risk_report.risks.{index}.internal_supporting_evidence_ids": (
                item.internal_supporting_evidence_ids
            )
            for index, item in enumerate(report.risks)
        },
        state.allowed_evidence_ids,
    )
    issues.extend(
        quality_gate.validate_risk_consistency(
            report,
            state.evidence_selections,
        )
    )

    requirement_ids = {item.requirement_id for item in state.jd_requirements}
    for index, risk in enumerate(report.risks):
        if not risk.requirement_ids:
            issues.append(
                _quality_issue(
                    "MISSING_REQUIREMENT_REFERENCE",
                    f"risk_report.risks.{index}.requirement_ids",
                    "Reference at least one requirement from the current analysis.",
                )
            )
        elif not set(risk.requirement_ids).issubset(requirement_ids):
            issues.append(
                _quality_issue(
                    "INVALID_REQUIREMENT_REFERENCE",
                    f"risk_report.risks.{index}.requirement_ids",
                    "Use only requirement IDs from the current analysis.",
                )
            )

    visible_payload = {
        "risks": [
            {
                "risk_type": item.risk_type,
                "title": item.title,
                "jd_requirement_summary": item.jd_requirement_summary,
                "resume_current_state": item.resume_current_state,
                "risk_reason": item.risk_reason,
                "recommendation": item.recommendation,
            }
            for item in report.risks
        ]
    }
    issues.extend(
        _quality_issue(
            "INTERNAL_ID_LEAK",
            path,
            "Rewrite the visible risk field without internal IDs.",
        )
        for path in InternalIdLeakDetector().find_leaks(visible_payload)
    )
    issues.extend(_duplicate_risk_issues(report))
    issues.extend(_required_tool_issues(state, report, tool_names))
    return sorted(issues, key=lambda issue: (issue.field_path, issue.code))


def _duplicate_risk_issues(report: InternalRiskReport) -> list[QualityIssue]:
    seen = set()
    issues = []
    for index, risk in enumerate(report.risks):
        key = (
            tuple(sorted(risk.requirement_ids)),
            risk.risk_type.casefold(),
            _normalize_text(risk.title),
        )
        if key in seen:
            issues.append(
                _quality_issue(
                    "DUPLICATE_RISK",
                    f"risk_report.risks.{index}",
                    "Remove the duplicate risk or narrow it to a distinct evidence gap.",
                )
            )
        seen.add(key)
    return issues


def _required_tool_issues(
    state: AnalysisState,
    report: InternalRiskReport,
    tool_names: list[str],
) -> list[QualityIssue]:
    required = {
        "get_resume_bullet_coverage",
        "rank_candidate_risks",
    }
    if state.jd_requirements:
        required.update(
            {
                "get_requirement",
                "get_requirement_evidence",
                "compare_capability_semantics",
            }
        )
    if state.experience_records:
        required.add("inspect_experience")
    if state.evaluation_report and state.evaluation_report.grounding_warnings:
        required.update({"check_public_claim_grounding", "classify_numeric_claim"})
    missing = sorted(required - set(tool_names))
    return [
        _quality_issue(
            "MISSING_REQUIRED_TOOL_CALL",
            "risk_report",
            f"Call {tool_name} before finalizing the risk report.",
        )
        for tool_name in missing
    ]


def _normalize_report(
    report: InternalRiskReport,
    state: AnalysisState,
) -> InternalRiskReport:
    importance = {
        item.requirement_id: {"high": 3, "medium": 2, "low": 1}[item.importance]
        for item in state.jd_requirements
    }
    ranked = sorted(
        report.risks,
        key=lambda risk: (
            _SEVERITY_SCORE[risk.severity],
            risk.risk_priority,
            _RISK_DIMENSION_SCORE.get((risk.risk_dimension or "").casefold(), 0),
            max((importance.get(item, 0) for item in risk.requirement_ids), default=0),
        ),
        reverse=True,
    )[:3]
    return InternalRiskReport(risks=ranked)


def _to_public_report(report: InternalRiskReport) -> RiskReport:
    return RiskReport(
        risks=[
            RiskItem(
                risk_type=item.risk_type,
                title=item.title,
                jd_requirement_summary=item.jd_requirement_summary,
                resume_current_state=item.resume_current_state,
                risk_reason=item.risk_reason,
                recommendation=item.recommendation,
                severity=item.severity,
            )
            for item in report.risks
        ]
    )


def _quality_issue(code: str, field_path: str, instruction: str) -> QualityIssue:
    return QualityIssue(
        code=code,
        field_path=field_path,
        message="Risk audit failed deterministic validation.",
        retry_instruction=instruction,
        severity="high",
    )


def _normalize_text(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _trace_summary(steps) -> str:
    tools = ",".join(step.tool_name for step in steps) or "none"
    statuses = ",".join(step.status for step in steps) or "none"
    return f"steps={len(steps)} tools={tools} statuses={statuses}"


class _DeterministicRiskAuditorChatModel(BaseChatModel):
    """Tool-calling local model; configured providers use ReActModelFactory."""

    @property
    def _llm_type(self) -> str:
        return "deterministic-risk-auditor-tool-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        catalog = _catalog_from_messages(messages)
        payloads = _tool_payloads(messages)
        if not payloads:
            message = AIMessage(content="", tool_calls=_inspection_tool_calls(catalog))
        elif not any("risks" in payload.get("data", {}) for payload in payloads):
            candidates = _deterministic_candidate_risks(catalog, payloads)
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "rank_candidate_risks",
                        "args": {"risks": candidates, "limit": 3},
                        "id": "rank_candidate_risks",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            risks = next(
                payload.get("data", {}).get("risks", [])
                for payload in reversed(payloads)
                if "risks" in payload.get("data", {})
            )
            message = AIMessage(content=json.dumps({"risks": risks}, ensure_ascii=False))
        return ChatResult(generations=[ChatGeneration(message=message)])


def _inspection_tool_calls(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for index, item in enumerate(catalog.get("requirement_catalog", []), start=1):
        requirement_id = item["requirement_id"]
        calls.extend(
            [
                _tool_call("get_requirement", {"requirement_id": requirement_id}, f"req_{index}"),
                _tool_call(
                    "get_requirement_evidence",
                    {"requirement_id": requirement_id},
                    f"evidence_{index}",
                ),
                _tool_call(
                    "compare_capability_semantics",
                    {"requirement_id": requirement_id},
                    f"semantics_{index}",
                ),
            ]
        )
    for index, item in enumerate(catalog.get("experience_catalog", []), start=1):
        calls.append(
            _tool_call(
                "inspect_experience",
                {"experience_id": item["experience_id"]},
                f"experience_{index}",
            )
        )
    calls.append(_tool_call("get_resume_bullet_coverage", {}, "bullet_coverage"))
    for index, warning in enumerate(catalog.get("grounding_warnings", []), start=1):
        calls.extend(
            [
                _tool_call(
                    "check_public_claim_grounding",
                    {"claim": warning["claim"]},
                    f"claim_{index}",
                ),
                _tool_call(
                    "classify_numeric_claim",
                    {"claim": warning["claim"]},
                    f"numeric_{index}",
                ),
            ]
        )
    return calls


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def _deterministic_candidate_risks(
    catalog: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirements = {
        item["requirement_id"]: item
        for payload in payloads
        for item in [payload.get("data", {}).get("requirement")]
        if item
    }
    selections = {
        item["requirement_id"]: item
        for payload in payloads
        for item in [payload.get("data", {}).get("evidence_selection")]
        if item
    }
    risks = []
    for requirement_id, requirement in requirements.items():
        selection = selections.get(requirement_id)
        if selection and selection.get("support_level") in {"strong", "partial"}:
            continue
        evidence_ids = selection.get("selected_evidence_ids", []) if selection else []
        if evidence_ids:
            risks.append(
                {
                    "risk_type": "evidence_strength",
                    "title": "现有经历的证明力度有限",
                    "jd_requirement_summary": requirement.get("text", "岗位核心要求"),
                    "resume_current_state": "简历包含相关内容，但职责深度或结果证据仍不充分。",
                    "risk_reason": "现有材料只能形成较弱支持，尚不足以证明岗位要求的实践深度。",
                    "recommendation": "补充真实职责、关键决策和可核实结果，以增强证据强度。",
                    "severity": "medium",
                    "requirement_ids": [requirement_id],
                    "internal_supporting_evidence_ids": evidence_ids,
                }
            )
        else:
            risks.append(
                {
                    "risk_type": "resume_coverage",
                    "title": "完整简历尚未覆盖该核心能力",
                    "jd_requirement_summary": requirement.get("text", "岗位核心要求"),
                    "resume_current_state": "完整简历中未找到能够支持该要求的相关经历。",
                    "risk_reason": "当前材料没有形成可验证的直接或间接能力证据。",
                    "recommendation": "如有真实经历，请补充对应项目职责、技术方案和结果。",
                    "severity": "high",
                    "requirement_ids": [requirement_id],
                    "internal_supporting_evidence_ids": [],
                }
            )

    first_requirement_id = next(iter(requirements), None)
    first_requirement = requirements.get(first_requirement_id or "", {})
    for warning in catalog.get("grounding_warnings", []):
        if first_requirement_id is None:
            continue
        risks.append(
            {
                "risk_type": "unsupported_generated_claim",
                "title": "生成内容包含未充分支撑的声明",
                "jd_requirement_summary": first_requirement.get("text", "岗位核心要求"),
                "resume_current_state": warning["claim"],
                "risk_reason": warning["reason"],
                "recommendation": "删除无法核实的表述，或补充能够直接支持该声明的材料。",
                "severity": warning["severity"],
                "requirement_ids": [first_requirement_id],
                "internal_supporting_evidence_ids": [],
            }
        )
    if catalog.get("specificity_notes") and first_requirement_id is not None:
        risks.append(
            {
                "risk_type": "resume_specificity",
                "title": "简历描述仍缺少具体行动或结果",
                "jd_requirement_summary": first_requirement.get("text", "岗位核心要求"),
                "resume_current_state": "；".join(catalog["specificity_notes"]),
                "risk_reason": "泛化描述不足以说明个人贡献和实际能力。",
                "recommendation": "补充项目目标、个人职责、关键决策和有证据支撑的结果。",
                "severity": "medium",
                "requirement_ids": [first_requirement_id],
                "internal_supporting_evidence_ids": [],
            }
        )
    return risks


def _catalog_from_messages(messages: list[BaseMessage]) -> dict[str, Any]:
    content = next(
        (
            str(message.content)
            for message in messages
            if getattr(message, "type", "") == "human"
        ),
        "{}",
    )
    start = content.find("{")
    if start < 0:
        return {}
    try:
        payload, _ = json.JSONDecoder().raw_decode(content[start:])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_payloads(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    payloads = []
    for message in messages:
        if getattr(message, "type", "") != "tool":
            continue
        try:
            payload = (
                json.loads(message.content)
                if isinstance(message.content, str)
                else message.content
            )
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads

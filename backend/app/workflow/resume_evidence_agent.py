from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

from backend.app.core.errors import AgentExecutionError, ReActErrorCode
from backend.app.llm.react_model import react_response_format
from backend.app.evaluation.quality_gate import (
    PublicOutputQualityGate,
    quality_issues_to_retry_message,
)
from backend.app.workflow.agent_tools import MAX_REACT_AGENT_STEPS, TraceRecorder
from backend.app.workflow.domain_models import EvidenceSelection, QualityIssue
from backend.app.workflow.json_outputs import parse_json_payload_from_text
from backend.app.workflow.react_tools import build_structured_react_tools
from backend.app.workflow.state import AnalysisState

try:
    from langchain.agents import create_agent
except ImportError:  # pragma: no cover - dependency is present in normal installs
    create_agent = None


logger = logging.getLogger(__name__)


RESUME_EVIDENCE_AGENT_PROMPT = """
You are the Resume Evidence ReAct Agent.
Use the available structured tools to find the smallest semantically relevant evidence set
for every JD requirement. You must call search_resume_evidence before selecting evidence.
When a result is only lexical, contextual, education, skill, or otherwise insufficient,
continue with get_experience, get_resume_section, compare_requirement_to_evidence, or
rerank_evidence as appropriate. Do not conclude support from section type or score alone.
Multiple projects may jointly provide indirect support for a foundational capability.
An internship whose actual work matches the requested domain may provide direct support.
Use only evidence IDs returned by tools in the current invocation. Never invent IDs.
For each requirement, stop calling tools once you have enough evidence to decide
strong, partial, or missing support. Do not keep searching for perfect evidence.
Return only JSON with a top-level "selections" list matching EvidenceSelection fields:
requirement_id, selected_evidence_ids, support_level, support_types, rationale,
and uncovered_aspects. Do not include hidden reasoning or markdown fences.
JSON example:
{"selections":[{"requirement_id":"req_example","selected_evidence_ids":["ev_example"],"support_level":"strong","support_types":["direct"],"rationale":"The evidence directly supports the requirement.","uncovered_aspects":[]}]}
""".strip()


class _EvidenceSelectionOutput(BaseModel):
    selections: list[EvidenceSelection] = Field(default_factory=list)


class ResumeEvidenceAgentError(AgentExecutionError):
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


class ResumeEvidenceAgent:
    def __init__(
        self,
        model: Any | None = None,
        *,
        max_steps: int = MAX_REACT_AGENT_STEPS,
        max_attempts: int = 3,
    ) -> None:
        self.model = model or _DeterministicResumeEvidenceChatModel()
        self.max_steps = max_steps
        self.max_attempts = max_attempts
        self.quality_gate = PublicOutputQualityGate()

    def run(self, state: AnalysisState, retrieval_service) -> AnalysisState:
        tool_state = state.model_copy(deep=True)
        all_steps = []
        retry_feedback = ""
        last_issues: list[QualityIssue] = []

        for attempt_number in range(1, self.max_attempts + 1):
            recorder = TraceRecorder(
                agent_name="resume_evidence",
                attempt_number=attempt_number,
            )
            tools = build_structured_react_tools(
                tool_state,
                "resume_evidence",
                recorder,
                retrieval_service=retrieval_service,
            )
            agent = create_resume_evidence_react_agent(self.model, tools)
            result: dict[str, Any] | None = None
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
                    config={
                        "recursion_limit": _recursion_limit(
                            self.max_steps,
                            len(tool_state.jd_requirements),
                        )
                    },
                )
                selections = _parse_final_selections(result)
            except GraphRecursionError as exc:
                _log_structured_output_parse_failure(
                    exc,
                    result,
                    tool_state,
                    attempt_number,
                )
                all_steps.extend(recorder.steps)
                last_issues = [
                    _quality_issue(
                        "REACT_RECURSION_LIMIT_ERROR",
                        "evidence_selections",
                        "Stop calling tools and return final JSON using evidence already returned.",
                    )
                ]
                retry_feedback = quality_issues_to_retry_message(last_issues)
                if attempt_number == self.max_attempts:
                    raise ResumeEvidenceAgentError(
                        "Resume Evidence Agent exceeded the tool recursion limit before producing final output.",
                        failed_tool="recursion_limit",
                        trace_summary=_trace_summary(all_steps),
                        code=ReActErrorCode.REACT_RECURSION_LIMIT_ERROR.value,
                    ) from exc
                continue
            except Exception as exc:
                _log_structured_output_parse_failure(
                    exc,
                    result,
                    tool_state,
                    attempt_number,
                )
                all_steps.extend(recorder.steps)
                last_issues = [
                    _quality_issue(
                        "REACT_OUTPUT_PARSE_ERROR",
                        "evidence_selections",
                        "Return valid JSON matching the EvidenceSelection list schema.",
                    )
                ]
                retry_feedback = quality_issues_to_retry_message(last_issues)
                if attempt_number == self.max_attempts:
                    raise ResumeEvidenceAgentError(
                        "Resume Evidence Agent could not produce valid structured output.",
                        failed_tool="structured_output",
                        trace_summary=_trace_summary(all_steps),
                        code=ReActErrorCode.REACT_OUTPUT_PARSE_ERROR.value,
                    ) from exc
                continue

            all_steps.extend(recorder.steps)
            last_issues = _validate_selections(tool_state, selections, self.quality_gate)
            if not last_issues:
                selected_ids = [
                    evidence_id
                    for selection in selections
                    for evidence_id in selection.selected_evidence_ids
                ]
                evidence_by_id = {
                    item.evidence_id: item for item in tool_state.retrieved_evidence
                }
                selected_evidence = [
                    evidence_by_id[evidence_id]
                    for evidence_id in dict.fromkeys(selected_ids)
                    if evidence_id in evidence_by_id
                ]
                final_recorder = TraceRecorder(agent_name="resume_evidence")
                final_recorder.steps = all_steps
                updated = state.model_copy(
                    update={
                        "retrieved_evidence": selected_evidence,
                        "evidence_selections": selections,
                        "allowed_evidence_ids": set(tool_state.allowed_evidence_ids),
                    }
                )
                return final_recorder.attach_to_state(
                    updated,
                    final_decision_summary=(
                        f"Validated evidence selections for {len(selections)} requirement(s)."
                    ),
                )

            retry_feedback = quality_issues_to_retry_message(last_issues)

        if any(step.status == "error" for step in all_steps):
            error_code = ReActErrorCode.REACT_TOOL_CALL_ERROR.value
        elif any(issue.code == "UNKNOWN_EVIDENCE_ID" for issue in last_issues):
            error_code = ReActErrorCode.REACT_EVIDENCE_VIOLATION.value
        else:
            error_code = ReActErrorCode.REACT_QUALITY_GATE_FAILED.value
        raise ResumeEvidenceAgentError(
            "Resume Evidence Agent failed deterministic quality validation after 3 attempts.",
            failed_tool="quality_gate",
            trace_summary=_trace_summary(all_steps),
            code=error_code,
        )


def create_resume_evidence_react_agent(model, tools):
    if create_agent is None:
        raise RuntimeError("langchain.agents.create_agent is unavailable.")
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=RESUME_EVIDENCE_AGENT_PROMPT,
        response_format=react_response_format(model, _EvidenceSelectionOutput),
        name="resume_evidence",
    )


def _invocation_prompt(state: AnalysisState, retry_feedback: str) -> str:
    requirements = [item.model_dump(mode="json") for item in state.jd_requirements]
    prompt = (
        "Analyze these JD requirements and return one EvidenceSelection for each:\n"
        + json.dumps(requirements, ensure_ascii=False)
    )
    if retry_feedback:
        prompt += "\n\nPrevious output failed validation.\n" + retry_feedback
    return prompt


def _recursion_limit(max_steps: int, requirement_count: int) -> int:
    return max(max_steps * 2 + 4, requirement_count * 4 + 12, 30)


def _parse_final_selections(result: dict[str, Any]) -> list[EvidenceSelection]:
    structured = result.get("structured_response")
    if structured is not None:
        return _EvidenceSelectionOutput.model_validate(structured).selections
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
    if isinstance(payload, list):
        payload = {"selections": payload}
    return _EvidenceSelectionOutput.model_validate(payload).selections


def _log_structured_output_parse_failure(
    exc: Exception,
    result: dict[str, Any] | None,
    state: AnalysisState,
    attempt_number: int,
) -> None:
    logger.warning(
        "event=resume_evidence_structured_output_parse_failed "
        "attempt=%s exception=%s reason=%s final_ai_message=%s",
        attempt_number,
        exc.__class__.__name__,
        _safe_debug_text(str(exc), state),
        _safe_debug_text(_extract_final_ai_content(result), state, limit=1000),
    )


def _extract_final_ai_content(result: dict[str, Any] | None) -> str:
    if not result:
        return "[no agent result]"
    messages = result.get("messages") or []
    for message in reversed(messages):
        if getattr(message, "type", "") != "ai":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content or "[empty ai message]"
        try:
            return json.dumps(content, ensure_ascii=False)
        except TypeError:
            return str(content)
    return "[no ai message]"


def _safe_debug_text(
    value: str,
    state: AnalysisState,
    *,
    limit: int = 480,
) -> str:
    sanitized = value.replace("SYSTEM_PROMPT_SECRET", "[redacted]")
    if state.run_config.api_key:
        sanitized = sanitized.replace(state.run_config.api_key, "[redacted]")
    for document in state.profile_documents:
        if document.content:
            sanitized = sanitized.replace(document.content, "[resume redacted]")
    sanitized = re.sub(
        r"(?i)hidden\s+(?:chain[- ]of[- ]thought|reasoning)",
        "[reasoning redacted]",
        sanitized,
    )
    sanitized = " ".join(sanitized.split())
    return sanitized[:limit]


def _validate_selections(
    state: AnalysisState,
    selections: list[EvidenceSelection],
    quality_gate: PublicOutputQualityGate,
) -> list[QualityIssue]:
    issues = quality_gate.validate_evidence_allowlist(
        {
            f"evidence_selections.{index}.selected_evidence_ids": item.selected_evidence_ids
            for index, item in enumerate(selections)
        },
        state.allowed_evidence_ids,
    )
    expected_ids = {item.requirement_id for item in state.jd_requirements}
    actual_ids = {item.requirement_id for item in selections}
    for requirement_id in sorted(expected_ids - actual_ids):
        issues.append(
            _quality_issue(
                "MISSING_EVIDENCE_SELECTION",
                "evidence_selections",
                "Return exactly one selection for every provided JD requirement.",
            )
        )
    if actual_ids - expected_ids or len(actual_ids) != len(selections):
        issues.append(
            _quality_issue(
                "INVALID_REQUIREMENT_REFERENCE",
                "evidence_selections",
                "Use each provided requirement ID exactly once.",
            )
        )
    if selections and not any(item.selected_evidence_ids for item in selections):
        issues.append(
            _quality_issue(
                "NO_USABLE_EVIDENCE",
                "evidence_selections",
                "Search additional project, internship, skill, or education evidence before concluding.",
            )
        )

    evidence_by_id = {item.evidence_id: item for item in state.retrieved_evidence}
    for index, selection in enumerate(selections):
        chunk_ids = [
            evidence_by_id[evidence_id].chunk_id
            for evidence_id in selection.selected_evidence_ids
            if evidence_id in evidence_by_id
        ]
        if len(chunk_ids) != len(set(chunk_ids)):
            issues.append(
                _quality_issue(
                    "DUPLICATE_EVIDENCE_CHUNK",
                    f"evidence_selections.{index}.selected_evidence_ids",
                    "Remove duplicate references to the same resume chunk.",
                )
            )
    return sorted(issues, key=lambda issue: (issue.field_path, issue.code))


def _quality_issue(code: str, field_path: str, instruction: str) -> QualityIssue:
    return QualityIssue(
        code=code,
        field_path=field_path,
        message="Resume evidence output failed deterministic validation.",
        retry_instruction=instruction,
        severity="high",
    )


def _trace_summary(steps) -> str:
    tools = ",".join(step.tool_name for step in steps) or "none"
    statuses = ",".join(step.status for step in steps) or "none"
    return f"steps={len(steps)} tools={tools} statuses={statuses}"


class _DeterministicResumeEvidenceChatModel(BaseChatModel):
    """Tool-calling test/local model; real providers use ReActModelFactory."""

    @property
    def _llm_type(self) -> str:
        return "deterministic-resume-evidence-tool-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        requirements = _requirements_from_messages(messages)
        tool_payloads = _tool_payloads(messages)
        if not tool_payloads:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_resume_evidence",
                        "args": {
                            "query": item.get("text", ""),
                            "requirement_id": item.get("requirement_id"),
                            "top_k": 5,
                        },
                        "id": f"search_{index}",
                        "type": "tool_call",
                    }
                    for index, item in enumerate(requirements, start=1)
                ],
            )
        else:
            evidence = [
                item
                for payload in tool_payloads
                for item in payload.get("data", {}).get("evidence", [])
            ]
            selections = []
            for requirement in requirements:
                requirement_id = requirement.get("requirement_id", "")
                matching = [
                    item
                    for item in evidence
                    if item.get("requirement_id") == requirement_id
                ]
                experience_evidence = [
                    item
                    for item in matching
                    if item.get("section_type") in {"project", "internship"}
                ]
                if experience_evidence:
                    selected = experience_evidence
                    level = "strong"
                    support_types = ["direct"]
                elif matching:
                    selected = matching
                    level = "partial"
                    support_types = ["contextual"]
                else:
                    selected = []
                    level = "missing"
                    support_types = ["insufficient"]
                selections.append(
                    {
                        "requirement_id": requirement_id,
                        "selected_evidence_ids": [
                            item.get("evidence_id") for item in selected
                        ],
                        "support_level": level,
                        "support_types": support_types,
                        "rationale": (
                            "Deterministic local mode selected evidence returned by the search tool."
                        ),
                        "uncovered_aspects": (
                            [] if selected else ["No usable evidence was returned."]
                        ),
                    }
                )
            message = AIMessage(
                content=json.dumps({"selections": selections}, ensure_ascii=False)
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


def _requirements_from_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    human_content = next(
        (
            str(message.content)
            for message in messages
            if getattr(message, "type", "") == "human"
        ),
        "[]",
    )
    start = human_content.find("[")
    if start < 0:
        return []
    try:
        requirements, _ = json.JSONDecoder().raw_decode(human_content[start:])
    except json.JSONDecodeError:
        return []
    return requirements if isinstance(requirements, list) else []


def _tool_payloads(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for message in messages:
        if getattr(message, "type", "") != "tool":
            continue
        content = message.content
        try:
            payload = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads

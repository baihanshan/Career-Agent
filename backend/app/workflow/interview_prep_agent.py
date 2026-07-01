from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from backend.app.api.schemas import InterviewPrep, InterviewPrepQuestion
from backend.app.core.errors import AgentExecutionError, ReActErrorCode
from backend.app.llm.react_model import react_response_format
from backend.app.evaluation.quality_gate import (
    PublicOutputQualityGate,
    quality_issues_to_retry_message,
)
from backend.app.workflow.agent_tools import MAX_REACT_AGENT_STEPS, TraceRecorder
from backend.app.workflow.domain_models import (
    InternalInterviewPrep,
    InternalInterviewQuestion,
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


logger = logging.getLogger(__name__)


INTERVIEW_PREP_AGENT_PROMPT = """
You are the Interview Prep ReAct Agent. Use the structured tools before drafting output.
Call get_interviewable_requirements to select JD topics. Never turn document_check,
qualification, degree, date, or other resume-verifiable facts into interview questions.
Call get_requirement_evidence for evidence-grounded answer facts and get_experience before
writing a resume deep-dive question about that experience.
All user-visible natural-language fields must be written in Simplified Chinese, including
question, answer_plan text fields, sample_answer, and resume deep-dive questions. Keep JSON
keys, enum-like values, IDs, and structured internal fields in the existing schema form.
Do not translate, rename, omit, or add JSON fields. The output must use exactly these schema
keys: jd_questions, resume_deep_dive_questions, question, question_type,
competencies_tested, target_requirement_ids, answer_plan, direct_answer, selected_facts,
reasoning_or_tradeoffs, result, reflection_or_transfer, sample_answer,
supporting_evidence_ids, and experience_id.

JD questions must be realistic professional technical, system-design, or behavioral scenarios.
Include a concrete goal, input/output, constraint, failure mode, or trade-off as appropriate.
Never ask how the candidate "meets" or "satisfies" a JD requirement.
Resume questions may identify an experience only by project name, company and role, or one
short summary. Never paste the full resume snippet. Questions for the same experience must
test different competencies and focus areas.

Create an answer_plan before every natural sample_answer. A plan contains direct_answer,
selected_facts, reasoning_or_tradeoffs, result, and reflection_or_transfer. Reorganize facts
to answer the question directly; do not copy a resume paragraph and append a generic summary.
Use only requirement, evidence, and experience IDs returned or supplied for the current
invocation, and keep every ID exclusively in structured internal fields. Never show IDs in
question or answer text.

Return only JSON with jd_questions and resume_deep_dive_questions. Every item must contain:
question, question_type, competencies_tested, target_requirement_ids, answer_plan,
sample_answer, supporting_evidence_ids, and optional experience_id. Do not return markdown,
hidden reasoning, or chain-of-thought.
JSON example:
{"jd_questions":[{"question":"如果系统需要在高并发约束下处理数据流，你会如何设计队列、缓存和故障恢复机制？","question_type":"system_design","competencies_tested":["architecture"],"target_requirement_ids":["req_example"],"answer_plan":{"direct_answer":"我会先拆分数据接入、任务调度和结果评估三个环节。","selected_facts":["相关项目中有可复用的工程事实。"],"reasoning_or_tradeoffs":"这样可以在延迟、可靠性和实现复杂度之间做权衡。","result":"方案可通过离线指标和压力测试验证。","reflection_or_transfer":"我会把同样的评估习惯迁移到目标岗位场景中。"},"sample_answer":"我会先澄清输入规模、成功指标和失败恢复要求，再选择可以逐步验证的架构，并用延迟、吞吐和错误恢复指标持续迭代。","supporting_evidence_ids":["ev_example"],"experience_id":"exp_example"}],"resume_deep_dive_questions":[]}
""".strip()


class InterviewPrepAgentError(AgentExecutionError):
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


class InterviewPrepAgent:
    def __init__(
        self,
        model: Any | None = None,
        *,
        max_steps: int = MAX_REACT_AGENT_STEPS,
        max_attempts: int = 3,
    ) -> None:
        self.model = model or _DeterministicInterviewPrepChatModel()
        self.max_steps = max_steps
        self.max_attempts = max_attempts
        self.quality_gate = PublicOutputQualityGate()

    def run(self, state: AnalysisState) -> AnalysisState:
        if state.generated_assets is None:
            raise InterviewPrepAgentError(
                "Generated assets are required before interview prep.",
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
                agent_name="interview_prep",
                attempt_number=attempt_number,
            )
            tools = build_structured_react_tools(
                tool_state,
                "interview_prep",
                recorder,
            )
            agent = create_interview_prep_react_agent(self.model, tools)
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
                    config={"recursion_limit": self.max_steps * 2 + 6},
                )
                prep = _parse_final_prep(result)
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
                        "interview_prep",
                        "Return valid JSON matching the internal interview prep schema.",
                    )
                ]
                retry_feedback = quality_issues_to_retry_message(last_issues)
                if attempt_number == self.max_attempts:
                    raise InterviewPrepAgentError(
                        "Interview Prep Agent could not produce valid structured output.",
                        failed_tool="structured_output",
                        trace_summary=_trace_summary(all_steps),
                        code=ReActErrorCode.REACT_OUTPUT_PARSE_ERROR.value,
                    ) from exc
                continue

            _normalize_supporting_evidence_ids(tool_state, prep)
            all_steps.extend(recorder.steps)
            last_issues = _validate_prep(
                state=tool_state,
                prep=prep,
                tool_names=[step.tool_name for step in recorder.steps],
                quality_gate=self.quality_gate,
            )
            if not last_issues:
                public_prep = _to_application_interview_prep(prep)
                generated_assets = state.generated_assets.model_copy(
                    update={"interview_prep": public_prep}
                )
                final_recorder = TraceRecorder(agent_name="interview_prep")
                final_recorder.steps = all_steps
                updated = state.model_copy(
                    update={
                        "generated_assets": generated_assets,
                        "internal_interview_prep": prep,
                    }
                )
                return final_recorder.attach_to_state(
                    updated,
                    final_decision_summary=(
                        "Generated validated professional JD and resume deep-dive questions."
                    ),
                )

            retry_feedback = quality_issues_to_retry_message(last_issues)

        if any(step.status == "error" for step in all_steps):
            error_code = ReActErrorCode.REACT_TOOL_CALL_ERROR.value
        elif any(issue.code == "UNKNOWN_EVIDENCE_ID" for issue in last_issues):
            error_code = ReActErrorCode.REACT_EVIDENCE_VIOLATION.value
        else:
            error_code = ReActErrorCode.REACT_QUALITY_GATE_FAILED.value
        raise InterviewPrepAgentError(
            "Interview Prep Agent failed deterministic quality validation after 3 attempts.",
            failed_tool="quality_gate",
            trace_summary=_trace_summary(all_steps),
            code=error_code,
        )


def create_interview_prep_react_agent(model, tools):
    if create_agent is None:
        raise RuntimeError("langchain.agents.create_agent is unavailable.")
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=INTERVIEW_PREP_AGENT_PROMPT,
        response_format=react_response_format(model, InternalInterviewPrep),
        name="interview_prep",
    )


def _invocation_prompt(state: AnalysisState, retry_feedback: str) -> str:
    payload = {
        "requirement_catalog": [
            {
                "requirement_id": item.requirement_id,
                "verification_mode": item.verification_mode,
                "interviewability": item.interviewability,
                "question_focus": item.question_focus,
            }
            for item in state.jd_requirements
        ],
        "experience_catalog": [
            {
                "experience_id": item.experience_id,
                "experience_type": item.experience_type,
                "name": item.name,
                "company_name": item.company_name,
                "role_title": item.role_title,
            }
            for item in state.experience_records
        ],
    }
    prompt = (
        "Use tools to inspect this internal catalog, then return validated interview prep JSON:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    if retry_feedback:
        prompt += "\n\nPrevious output failed validation.\n" + retry_feedback
    return prompt


def _parse_final_prep(result: dict[str, Any]) -> InternalInterviewPrep:
    structured = result.get("structured_response")
    if structured is not None:
        return InternalInterviewPrep.model_validate(structured)
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
    return InternalInterviewPrep.model_validate(payload)


def _log_structured_output_parse_failure(
    exc: Exception,
    result: dict[str, Any] | None,
    state: AnalysisState,
    attempt_number: int,
) -> None:
    logger.warning(
        "event=interview_prep_structured_output_parse_failed "
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


def _normalize_supporting_evidence_ids(
    state: AnalysisState,
    prep: InternalInterviewPrep,
) -> None:
    questions = [*prep.jd_questions, *prep.resume_deep_dive_questions]
    evidence_by_requirement: dict[str, list[str]] = defaultdict(list)
    evidence_by_chunk: dict[str, list[str]] = defaultdict(list)
    for item in state.retrieved_evidence:
        if item.evidence_id not in state.allowed_evidence_ids:
            continue
        evidence_by_requirement[item.requirement_id].append(item.evidence_id)
        evidence_by_chunk[item.chunk_id].append(item.evidence_id)

    experience_chunks: dict[str, set[str]] = {
        item.experience_id: set(item.raw_source_chunk_ids)
        for item in state.experience_records
    }
    for question in questions:
        valid_ids = [
            evidence_id
            for evidence_id in dict.fromkeys(question.supporting_evidence_ids)
            if evidence_id in state.allowed_evidence_ids
        ]
        if not valid_ids:
            valid_ids = _fallback_evidence_ids(
                question,
                evidence_by_requirement,
                evidence_by_chunk,
                experience_chunks,
            )
        question.supporting_evidence_ids = valid_ids


def _fallback_evidence_ids(
    question: InternalInterviewQuestion,
    evidence_by_requirement: dict[str, list[str]],
    evidence_by_chunk: dict[str, list[str]],
    experience_chunks: dict[str, set[str]],
) -> list[str]:
    candidates: list[str] = []
    for requirement_id in question.target_requirement_ids:
        candidates.extend(evidence_by_requirement.get(requirement_id, []))
    if question.experience_id:
        for chunk_id in experience_chunks.get(question.experience_id, set()):
            candidates.extend(evidence_by_chunk.get(chunk_id, []))
    return list(dict.fromkeys(candidates))[:3]


def _validate_prep(
    *,
    state: AnalysisState,
    prep: InternalInterviewPrep,
    tool_names: list[str],
    quality_gate: PublicOutputQualityGate,
) -> list[QualityIssue]:
    jd_questions = prep.jd_questions
    deep_dive_questions = prep.resume_deep_dive_questions
    all_questions = [*jd_questions, *deep_dive_questions]
    issues = quality_gate.validate_evidence_allowlist(
        {
            f"interview_prep.questions.{index}.supporting_evidence_ids": (
                item.supporting_evidence_ids
            )
            for index, item in enumerate(all_questions)
        },
        state.allowed_evidence_ids,
    )

    all_requirement_ids = {item.requirement_id for item in state.jd_requirements}
    interviewable_ids = {
        item.requirement_id
        for item in state.jd_requirements
        if item.interviewability and item.verification_mode != "document_check"
    }
    experience_ids = {item.experience_id for item in state.experience_records}

    for index, item in enumerate(jd_questions):
        path = f"interview_prep.jd_questions.{index}"
        if not item.target_requirement_ids or not set(
            item.target_requirement_ids
        ).issubset(interviewable_ids):
            issues.append(
                _quality_issue(
                    "NON_INTERVIEWABLE_REQUIREMENT",
                    f"{path}.target_requirement_ids",
                    "Use only interviewable non-document-check requirements for JD questions.",
                )
            )

    for index, item in enumerate(deep_dive_questions):
        path = f"interview_prep.resume_deep_dive_questions.{index}"
        if item.target_requirement_ids and not set(
            item.target_requirement_ids
        ).issubset(all_requirement_ids):
            issues.append(
                _quality_issue(
                    "INVALID_REQUIREMENT_REFERENCE",
                    f"{path}.target_requirement_ids",
                    "Use only requirement IDs from the current analysis.",
                )
            )
        if item.experience_id not in experience_ids:
            issues.append(
                _quality_issue(
                    "UNKNOWN_EXPERIENCE_ID",
                    f"{path}.experience_id",
                    "Use an experience ID returned by get_experience.",
                )
            )

    for index, item in enumerate(all_questions):
        path = f"interview_prep.questions.{index}"
        if not item.competencies_tested:
            issues.append(
                _quality_issue(
                    "MISSING_COMPETENCY_FOCUS",
                    f"{path}.competencies_tested",
                    "State at least one concrete competency tested by the question.",
                )
            )
        if not item.supporting_evidence_ids:
            issues.append(
                _quality_issue(
                    "UNKNOWN_EVIDENCE_ID",
                    f"{path}.supporting_evidence_ids",
                    "Reference evidence returned by tools in the current invocation.",
                )
            )
        if not item.answer_plan.selected_facts:
            issues.append(
                _quality_issue(
                    "EMPTY_ANSWER_FACTS",
                    f"{path}.answer_plan.selected_facts",
                    "Select concise evidence facts before drafting the answer.",
                )
            )

    source_snippets = [item.snippet for item in state.retrieved_evidence]
    issues.extend(
        quality_gate.validate_interview_questions(
            jd_questions,
            source_snippets,
            field_prefix="interview_prep.jd_questions",
        )
    )
    issues.extend(
        quality_gate.validate_interview_questions(
            deep_dive_questions,
            source_snippets,
            field_prefix="interview_prep.resume_deep_dive_questions",
        )
    )
    for index, item in enumerate(all_questions):
        issues.extend(
            quality_gate.validate_answer_relevance(
                item.question,
                item.sample_answer,
                field_path=f"interview_prep.questions.{index}.sample_answer",
            )
        )

    visible_payload = {
        "jd_questions": [
            {"question": item.question, "sample_answer": item.sample_answer}
            for item in jd_questions
        ],
        "resume_deep_dive_questions": [
            {"question": item.question, "sample_answer": item.sample_answer}
            for item in deep_dive_questions
        ],
    }
    issues.extend(
        _quality_issue(
            "INTERNAL_ID_LEAK",
            path,
            "Rewrite the visible field without internal IDs.",
        )
        for path in InternalIdLeakDetector().find_leaks(visible_payload)
    )
    issues.extend(_duplicate_focus_issues(deep_dive_questions))

    if "get_interviewable_requirements" not in tool_names:
        issues.append(
            _quality_issue(
                "MISSING_REQUIRED_TOOL_CALL",
                "interview_prep",
                "Call get_interviewable_requirements before drafting questions.",
            )
        )
    if all_questions and "get_requirement_evidence" not in tool_names:
        issues.append(
            _quality_issue(
                "MISSING_EVIDENCE_TOOL_CALL",
                "interview_prep",
                "Call get_requirement_evidence before using resume facts in answers.",
            )
        )
    if deep_dive_questions and "get_experience" not in tool_names:
        issues.append(
            _quality_issue(
                "MISSING_EXPERIENCE_TOOL_CALL",
                "interview_prep.resume_deep_dive_questions",
                "Call get_experience before drafting a resume deep-dive question.",
            )
        )
    return sorted(issues, key=lambda issue: (issue.field_path, issue.code))


def _duplicate_focus_issues(
    questions: list[InternalInterviewQuestion],
) -> list[QualityIssue]:
    seen: dict[str, set[tuple[str, tuple[str, ...]]]] = defaultdict(set)
    issues: list[QualityIssue] = []
    for index, item in enumerate(questions):
        if item.experience_id is None:
            continue
        focus = (
            item.question_type.casefold(),
            tuple(sorted(value.casefold() for value in item.competencies_tested)),
        )
        if focus in seen[item.experience_id]:
            issues.append(
                _quality_issue(
                    "DUPLICATE_EXPERIENCE_FOCUS",
                    f"interview_prep.resume_deep_dive_questions.{index}",
                    "Choose a different technical, debugging, metrics, collaboration, or reflection focus.",
                )
            )
        seen[item.experience_id].add(focus)
    return issues


def _to_application_interview_prep(prep: InternalInterviewPrep) -> InterviewPrep:
    return InterviewPrep(
        jd_questions=[_to_application_question(item) for item in prep.jd_questions],
        resume_deep_dive_questions=[
            _to_application_question(item)
            for item in prep.resume_deep_dive_questions
        ],
    )


def _to_application_question(item: InternalInterviewQuestion) -> InterviewPrepQuestion:
    return InterviewPrepQuestion(
        question=item.question,
        sample_answer=item.sample_answer,
        supporting_evidence_ids=item.supporting_evidence_ids,
    )


def _quality_issue(code: str, field_path: str, instruction: str) -> QualityIssue:
    return QualityIssue(
        code=code,
        field_path=field_path,
        message="Interview preparation failed deterministic validation.",
        retry_instruction=instruction,
        severity="high",
    )


def _trace_summary(steps) -> str:
    tools = ",".join(step.tool_name for step in steps) or "none"
    statuses = ",".join(step.status for step in steps) or "none"
    return f"steps={len(steps)} tools={tools} statuses={statuses}"


class _DeterministicInterviewPrepChatModel(BaseChatModel):
    """Tool-calling local model; configured providers use ReActModelFactory."""

    @property
    def _llm_type(self) -> str:
        return "deterministic-interview-prep-tool-model"

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
        tool_payloads = _tool_payloads(messages)
        if not tool_payloads:
            tool_calls = [
                {
                    "name": "get_interviewable_requirements",
                    "args": {},
                    "id": "interviewable_requirements",
                    "type": "tool_call",
                }
            ]
            tool_calls.extend(
                {
                    "name": "get_requirement_evidence",
                    "args": {"requirement_id": item["requirement_id"]},
                    "id": f"requirement_evidence_{index}",
                    "type": "tool_call",
                }
                for index, item in enumerate(
                    catalog.get("requirement_catalog", []),
                    start=1,
                )
                if item.get("interviewability")
                and item.get("verification_mode") != "document_check"
            )
            tool_calls.extend(
                {
                    "name": "get_experience",
                    "args": {"experience_id": item["experience_id"]},
                    "id": f"experience_{index}",
                    "type": "tool_call",
                }
                for index, item in enumerate(
                    catalog.get("experience_catalog", []),
                    start=1,
                )
            )
            message = AIMessage(content="", tool_calls=tool_calls)
        else:
            message = AIMessage(
                content=json.dumps(
                    _deterministic_prep(tool_payloads),
                    ensure_ascii=False,
                )
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


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


def _deterministic_prep(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    requirements = [
        item
        for payload in payloads
        for item in payload.get("data", {}).get("requirements", [])
    ]
    evidence = [
        item
        for payload in payloads
        for item in payload.get("data", {}).get("evidence", [])
    ]
    experiences = [
        payload.get("data", {}).get("experience")
        for payload in payloads
        if payload.get("data", {}).get("experience")
    ]
    evidence_by_requirement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        evidence_by_requirement[item.get("requirement_id", "")].append(item)

    jd_questions = []
    for index, requirement in enumerate(requirements[:4]):
        supporting = evidence_by_requirement.get(requirement.get("requirement_id", ""), [])
        if not supporting:
            continue
        evidence_ids = [item["evidence_id"] for item in supporting[:2]]
        jd_focus = _deterministic_jd_focus(index)
        jd_questions.append(
            {
                "question": jd_focus["question"],
                "question_type": jd_focus["question_type"],
                "competencies_tested": jd_focus["competencies"],
                "target_requirement_ids": [requirement["requirement_id"]],
                "answer_plan": {
                    "direct_answer": "先明确目标、约束和失败模式，再分层设计。",
                    "selected_facts": ["已有相关项目或实习证据。"],
                    "reasoning_or_tradeoffs": "比较性能、复杂度、成本和可恢复性。",
                    "result": "使用离线指标、压力测试和故障注入验证。",
                    "reflection_or_transfer": "根据观测结果逐步调整系统边界。",
                },
                "sample_answer": jd_focus["sample_answer"],
                "supporting_evidence_ids": evidence_ids,
            }
        )

    deep_dive_questions = []
    for index, experience in enumerate(experiences[:4]):
        matching = [
            item
            for item in evidence
            if item.get("chunk_id") in experience.get("raw_source_chunk_ids", [])
        ]
        if not matching:
            continue
        deep_focus = _deterministic_deep_dive_focus(
            index,
            experience.get("name", "这段经历"),
        )
        deep_dive_questions.append(
            {
                "question": deep_focus["question"],
                "question_type": deep_focus["question_type"],
                "competencies_tested": deep_focus["competencies"],
                "target_requirement_ids": [matching[0]["requirement_id"]],
                "experience_id": experience["experience_id"],
                "answer_plan": {
                    "direct_answer": "围绕目标和约束选择可验证的最小方案。",
                    "selected_facts": ["承担了经历中的核心实现与验证工作。"],
                    "reasoning_or_tradeoffs": "比较效果、复杂度和迭代成本。",
                    "result": "使用任务指标和对照实验验证。",
                    "reflection_or_transfer": "补充边界场景并沉淀复现实验。",
                },
                "sample_answer": deep_focus["sample_answer"],
                "supporting_evidence_ids": [matching[0]["evidence_id"]],
            }
        )
    return {
        "jd_questions": jd_questions,
        "resume_deep_dive_questions": deep_dive_questions,
    }


def _deterministic_jd_focus(index: int) -> dict[str, Any]:
    focuses = [
        {
            "question": (
                "如果要把相关能力用于受延迟、资源和可靠性约束的 AI 服务，你会如何"
                "拆分架构、选择关键技术，并设计故障恢复方案？"
            ),
            "question_type": "system_design",
            "competencies": ["架构设计", "技术权衡", "可靠性"],
            "sample_answer": (
                "我会先定义输入输出、延迟预算和失败模式，再拆分数据、服务与监控层。"
                "技术选择需要比较吞吐、资源成本和恢复复杂度，并通过压力测试和故障注入"
                "验证。已有项目中的服务实现经验可以支撑原型落地，最终再依据真实负载迭代。"
            ),
        },
        {
            "question": (
                "当线上结果偶发异常但离线指标正常时，你会如何建立定位路径，区分数据、"
                "模型和服务问题，并控制修复过程的回归风险？"
            ),
            "question_type": "debugging",
            "competencies": ["故障定位", "可观测性", "回归验证"],
            "sample_answer": (
                "我会先按请求链路补齐日志、指标和可复现样本，再分别检查输入漂移、模型输出"
                "和依赖状态。每次只验证一个假设，修复后用历史失败样本、回归集和灰度指标"
                "共同确认，避免局部优化掩盖新的故障。"
            ),
        },
        {
            "question": (
                "如果业务方认为现有离线准确率不能反映真实效果，你会如何重构评估集、"
                "分群指标和线上实验，使模型改进可以被可靠归因？"
            ),
            "question_type": "evaluation_design",
            "competencies": ["指标设计", "实验方法", "结果归因"],
            "sample_answer": (
                "我会先明确业务错误成本，再按场景和难度分层构建评估集，避免单一平均指标"
                "掩盖弱项。离线阶段结合分群指标与错误分析，线上采用受控实验并监测护栏指标，"
                "只有数据、版本和流量条件可追溯时才判断改进来自模型方案。"
            ),
        },
        {
            "question": (
                "将已有技术方案迁移到数据分布和吞吐目标不同的新业务时，你会保留哪些"
                "模块、重做哪些假设，并如何安排跨团队交付顺序？"
            ),
            "question_type": "technical_behavioral",
            "competencies": ["方案迁移", "边界判断", "协作交付"],
            "sample_answer": (
                "我会保留接口稳定且有测试保护的通用模块，重新验证数据分布、容量和故障模式。"
                "先与上下游对齐契约和验收指标，再交付最小链路并逐步扩容；每个阶段记录假设、"
                "风险和回滚条件，使技术迁移与团队协作可以同步验证。"
            ),
        },
    ]
    return focuses[index % len(focuses)]


def _deterministic_deep_dive_focus(index: int, experience_name: str) -> dict[str, Any]:
    focuses = [
        {
            "question": (
                f"在{experience_name}中，你如何确定核心技术方案，比较了哪些替代路径，"
                "又如何验证结果可信度？"
            ),
            "question_type": "technical_deep_dive",
            "competencies": ["技术选型", "实验验证"],
            "sample_answer": (
                "我先把目标拆成可测指标，再用小规模实验比较候选方案的效果、复杂度和迭代"
                "成本。确定方案后，通过对照实验、错误分析和边界样本验证并记录失败条件；"
                "复盘时检查决策能否复现，以及迁移到新场景还需补充哪些数据。"
            ),
        },
        {
            "question": (
                f"回顾{experience_name}，最难复现的一次失败是什么？你如何缩小问题范围，"
                "排除错误假设并确认修复没有引入回归？"
            ),
            "question_type": "debugging",
            "competencies": ["问题定位", "假设验证", "复盘"],
            "sample_answer": (
                "我先固定输入、环境和版本以建立稳定复现，再按数据、算法与系统边界逐层增加"
                "观测。每轮只改变一个条件并保留对照，定位后补充针对性测试和历史样本回放；"
                "复盘重点是把临时排查步骤转成可重复的监控和检查清单。"
            ),
        },
        {
            "question": (
                f"在{experience_name}中，哪些指标真正影响了方案决策？如果核心指标与用户"
                "体验发生冲突，你会怎样重新设计实验？"
            ),
            "question_type": "metrics_deep_dive",
            "competencies": ["指标选择", "实验设计", "业务判断"],
            "sample_answer": (
                "我会区分模型指标、系统指标和用户结果，先确认指标与目标之间的因果链。"
                "发生冲突时按场景分群分析错误成本，补充护栏指标和定性样本，再通过对照实验"
                "验证取舍，而不是继续优化一个已经失真的平均数。"
            ),
        },
        {
            "question": (
                f"如果重新负责{experience_name}，你会如何调整个人职责、团队接口和交付节奏，"
                "以更早暴露技术风险？"
            ),
            "question_type": "reflection",
            "competencies": ["协作设计", "风险管理", "反思迁移"],
            "sample_answer": (
                "我会更早明确个人决策边界和上下游接口，把高风险假设安排在首个迭代验证。"
                "交付上采用可演示的垂直切片，并在评审中同步指标、失败条件和回滚方案；这样"
                "技术风险、协作依赖和结果预期都能在投入扩大前被发现。"
            ),
        },
    ]
    return focuses[index % len(focuses)]

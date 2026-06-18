from __future__ import annotations

from collections.abc import Callable

from backend.app.api.schemas import (
    EvidenceItem,
    InterviewPrep,
    InterviewPrepQuestion,
    JDRequirement,
)
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


INTERVIEW_PREP_AGENT_PROMPT = """
You are the Interview Prep Agent.
Use only get_high_priority_jd_requirements, get_matched_project_and_internship_evidence,
and draft_answer. Finish within at most 3 ReAct rounds.
Return separate jd_questions and resume_deep_dive_questions. Every question must include a
complete sample answer grounded in the JD and the candidate's experience, not a template or
walkthrough suggestion. Never display an evidence ID in question or answer text.
For project questions, focus on personal responsibility, technical challenges, results, and
reflection. For internship questions, focus on technology, work performed, and outcomes.
""".strip()


QuestionGenerator = Callable[
    [AnalysisState, list[JDRequirement], list[EvidenceItem]],
    InterviewPrep,
]


class InterviewPrepAgentError(AgentExecutionError):
    pass


class InterviewPrepAgent:
    def __init__(
        self,
        max_steps: int = MAX_REACT_AGENT_STEPS,
        question_generator: QuestionGenerator | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.question_generator = question_generator or _generate_questions

    def run(self, state: AnalysisState) -> AnalysisState:
        if state.generated_assets is None:
            raise InterviewPrepAgentError(
                "Generated assets are required before interview prep.",
                failed_tool="precondition_check",
                trace_summary="steps=0 tools=none statuses=none",
            )

        recorder = TraceRecorder(agent_name="interview_prep")
        toolbox = build_agent_toolbox(state, agent_name="interview_prep")
        high_priority_requirements = [
            item for item in state.jd_requirements if item.importance == "high"
        ]
        requirements = high_priority_requirements or state.jd_requirements
        evidence = [
            item
            for item in state.retrieved_evidence
            if item.section_type in {"project", "internship"}
        ]

        for _attempt in range(1, self.max_steps + 1):
            recorder.record(toolbox["get_high_priority_jd_requirements"]())
            recorder.record(toolbox["get_matched_project_and_internship_evidence"]())
            interview_prep = self.question_generator(state, requirements, evidence)
            if _is_qualified(interview_prep, requirements, evidence):
                for question, requirement, item in _draft_inputs(
                    interview_prep,
                    requirements,
                    evidence,
                ):
                    recorder.record(
                        toolbox["draft_answer"](
                            question=question,
                            evidence=item,
                            jd_requirement=requirement,
                        )
                    )
                next_assets = state.generated_assets.model_copy(
                    update={"interview_prep": interview_prep}
                )
                return recorder.attach_to_state(
                    state.model_copy(update={"generated_assets": next_assets}),
                    final_decision_summary=(
                        "Generated separate JD and resume deep-dive questions with grounded "
                        "sample answers."
                    ),
                )

        raise InterviewPrepAgentError(
            f"Interview Prep Agent produced no qualified output after {self.max_steps} attempts.",
            failed_tool="draft_answer",
            trace_summary=recorder.summary(),
        )


def create_interview_prep_react_agent(model, tools):
    if create_react_agent is None:
        raise RuntimeError("langgraph.prebuilt.create_react_agent is unavailable.")
    allowed_names = {
        "get_high_priority_jd_requirements",
        "get_matched_project_and_internship_evidence",
        "draft_answer",
    }
    if isinstance(tools, dict):
        selected_tools = [tool for name, tool in tools.items() if name in allowed_names]
    else:
        selected_tools = list(tools)
    return create_react_agent(
        model=model,
        tools=selected_tools,
        prompt=INTERVIEW_PREP_AGENT_PROMPT,
    )


def _generate_questions(
    state: AnalysisState,
    requirements: list[JDRequirement],
    evidence: list[EvidenceItem],
) -> InterviewPrep:
    if not requirements or not evidence:
        return InterviewPrep()
    jd_count = _question_count(len(requirements))
    evidence_count = _question_count(len(evidence))
    jd_questions = []
    for index, requirement in enumerate(requirements[:jd_count]):
        item = _matching_evidence(requirement, evidence, index)
        jd_questions.append(
            InterviewPrepQuestion(
                question=f"请结合你的经历，说明你如何满足岗位对{requirement.text}的要求？",
                sample_answer=_sample_answer(requirement, item),
                supporting_evidence_ids=[item.evidence_id],
            )
        )

    deep_dive_questions = []
    fallback_requirement = requirements[0] if requirements else None
    for item in evidence[:evidence_count]:
        requirement = _requirement_for_evidence(item, requirements) or fallback_requirement
        if requirement is None:
            continue
        deep_dive_questions.append(
            InterviewPrepQuestion(
                question=_deep_dive_question(item),
                sample_answer=_sample_answer(requirement, item),
                supporting_evidence_ids=[item.evidence_id],
            )
        )

    return InterviewPrep(
        jd_questions=jd_questions,
        resume_deep_dive_questions=deep_dive_questions,
    )


def _question_count(item_count: int) -> int:
    if item_count >= 3:
        return min(item_count, 4)
    return min(item_count, 2)


def _matching_evidence(
    requirement: JDRequirement,
    evidence: list[EvidenceItem],
    fallback_index: int,
) -> EvidenceItem:
    matching = [item for item in evidence if item.requirement_id == requirement.requirement_id]
    return matching[0] if matching else evidence[fallback_index % len(evidence)]


def _requirement_for_evidence(
    evidence: EvidenceItem,
    requirements: list[JDRequirement],
) -> JDRequirement | None:
    return next(
        (item for item in requirements if item.requirement_id == evidence.requirement_id),
        None,
    )


def _deep_dive_question(evidence: EvidenceItem) -> str:
    if evidence.section_type == "internship":
        return f"请深入介绍这段实习经历中的技术选择、具体工作和成果：{evidence.snippet}"
    return f"请深入介绍该项目中的个人职责、技术难点、结果和复盘：{evidence.snippet}"


def _sample_answer(requirement: JDRequirement, evidence: EvidenceItem) -> str:
    experience_type = "实习" if evidence.section_type == "internship" else "项目"
    return (
        f"在我的{experience_type}经历中，{evidence.snippet} "
        f"这段实践让我能够用具体行动说明自己具备{requirement.text}相关能力。"
        "面试时我会先交代目标和个人职责，再说明关键技术决策、执行过程与结果，"
        "最后复盘其中的取舍以及下一次可以改进的地方。"
    )


def _is_qualified(
    prep: InterviewPrep,
    requirements: list[JDRequirement],
    evidence: list[EvidenceItem],
) -> bool:
    if not requirements or not evidence:
        return False
    expected_jd_count = _question_count(len(requirements))
    expected_evidence_count = _question_count(len(evidence))
    if len(prep.jd_questions) != expected_jd_count:
        return False
    if len(prep.resume_deep_dive_questions) != expected_evidence_count:
        return False
    hidden_ids = {item.evidence_id for item in evidence}
    for item in [*prep.jd_questions, *prep.resume_deep_dive_questions]:
        if not item.question.strip() or not item.sample_answer.strip():
            return False
        visible_text = f"{item.question} {item.sample_answer}"
        if any(evidence_id in visible_text for evidence_id in hidden_ids):
            return False
    return True


def _draft_inputs(
    prep: InterviewPrep,
    requirements: list[JDRequirement],
    evidence: list[EvidenceItem],
):
    questions = [*prep.jd_questions, *prep.resume_deep_dive_questions]
    for index, question in enumerate(questions):
        item = evidence[index % len(evidence)]
        requirement = _requirement_for_evidence(item, requirements) or requirements[
            index % len(requirements)
        ]
        yield question.question, requirement, item

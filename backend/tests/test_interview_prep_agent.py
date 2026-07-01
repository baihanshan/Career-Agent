import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import Field

from backend.app.api.schemas import (
    EvidenceItem,
    GeneratedAssets,
    InterviewPrep,
    JDRequirement,
    ResumeBullet,
)
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.workflow.domain_models import ExperienceRecord
from backend.app.workflow.interview_prep_agent import (
    INTERVIEW_PREP_AGENT_PROMPT,
    InterviewPrepAgent,
    InterviewPrepAgentError,
    create_interview_prep_react_agent,
)
from backend.app.workflow.nodes import (
    WorkflowServices,
    finalize_response,
    generate_interview_prep,
    public_output_gate,
)
from backend.app.workflow.state import AnalysisState


def test_document_check_requirement_does_not_generate_jd_question():
    invalid_document_question = {
        "jd_questions": [
            {
                "question": "你如何满足计算机硕士或博士的学历要求？",
                "question_type": "qualification_check",
                "competencies_tested": ["学历核验"],
                "target_requirement_ids": ["req_degree"],
                "answer_plan": {
                    "direct_answer": "说明学历。",
                    "selected_facts": ["教育背景"],
                    "reasoning_or_tradeoffs": "无需技术权衡。",
                    "result": "由简历核验。",
                    "reflection_or_transfer": "不适用。",
                },
                "sample_answer": "我的学历信息已经列在简历教育背景中。",
                "supporting_evidence_ids": ["ev_degree"],
            }
        ],
        "resume_deep_dive_questions": [],
    }
    model = _fake_model(
        [
            _tool_calls(include_evidence=False, include_experience=False),
            _final(invalid_document_question),
            _tool_calls(include_evidence=False, include_experience=False),
            _final({"jd_questions": [], "resume_deep_dive_questions": []}),
        ]
    )
    state = _state(
        requirements=[
            _requirement(
                "req_degree",
                "计算机硕士或博士",
                verification_mode="document_check",
                interviewability=False,
                question_focus=None,
            )
        ],
        evidence=[],
    )

    result = InterviewPrepAgent(model=model).run(state)

    assert result.generated_assets.interview_prep.jd_questions == []
    assert [step.tool_name for step in result.agent_traces[-1].steps] == [
        "get_interviewable_requirements",
        "get_interviewable_requirements",
    ]
    assert any(
        "NON_INTERVIEWABLE_REQUIREMENT" in message.content
        for invocation in model.invocations
        for message in invocation
        if getattr(message, "type", "") == "human"
    )


@pytest.mark.parametrize(
    ("fixture_name", "required_terms"),
    [
        ("python_professional", ["高并发", "内存", "故障"]),
        ("multimodal_professional", ["多模态", "数据", "评估"]),
    ],
)
def test_jd_questions_are_professional_scenarios(fixture_name, required_terms):
    output = _fixture(fixture_name)
    requirement_id = output["jd_questions"][0]["target_requirement_ids"][0]
    text = "Python 与算法基础" if requirement_id == "req_python" else "多模态平台设计"
    model = _fake_model([_tool_calls(requirement_id=requirement_id), _final(output)])
    state = _state(
        requirements=[_requirement(requirement_id, text)],
        evidence=[_evidence("ev_project", requirement_id)],
        experiences=[_experience()],
    )

    result = InterviewPrepAgent(model=model).run(state)

    question = result.generated_assets.interview_prep.jd_questions[0].question
    assert all(term in question for term in required_terms)
    assert "你如何满足" not in question
    assert {step.tool_name for step in result.agent_traces[-1].steps} == {
        "get_interviewable_requirements",
        "get_requirement_evidence",
        "get_experience",
    }


def test_project_question_uses_name_without_copying_full_resume_snippet():
    output = _fixture("deep_dive")
    model = _fake_model([_tool_calls(), _final(output)])
    snippet = (
        "主导搭建端到端语义分割实验平台，完成 DeepLabV3+ 本地部署与可扩展环境设计，"
        "设计轻量级通道注意力模块，对不同膨胀率特征进行加权融合并开展网格搜索。"
    )
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python", snippet=snippet)],
        experiences=[_experience(name="自然环境语义分割")],
    )

    result = InterviewPrepAgent(model=model).run(state)

    question = result.generated_assets.interview_prep.resume_deep_dive_questions[0].question
    assert "自然环境语义分割" in question
    assert snippet not in question
    assert len(question) < len(snippet)


def test_same_experience_duplicate_focus_triggers_feedback_retry():
    invalid = _fixture("duplicate_focus")
    valid = _fixture("distinct_focus")
    model = _fake_model(
        [
            _tool_calls(),
            _final(invalid),
            _tool_calls(),
            _final(valid),
        ]
    )
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python")],
        experiences=[_experience()],
    )

    result = InterviewPrepAgent(model=model).run(state)

    questions = result.internal_interview_prep.resume_deep_dive_questions
    assert len(model.invocations) == 4
    assert len({tuple(item.competencies_tested) for item in questions}) == 2
    assert any(
        "DUPLICATE_EXPERIENCE_FOCUS" in message.content
        for invocation in model.invocations
        for message in invocation
        if getattr(message, "type", "") == "human"
    )


def test_answer_keeps_structured_plan_and_reorganizes_supported_facts():
    output = _fixture("deep_dive")
    model = _fake_model([_tool_calls(), _final(output)])
    snippet = (
        "主导搭建端到端语义分割实验平台，完成 DeepLabV3+ 本地部署，"
        "引入多尺度特征融合并实现平均 IoU 提升 17%。"
    )
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python", snippet=snippet)],
        experiences=[_experience(name="自然环境语义分割")],
    )

    result = InterviewPrepAgent(model=model).run(state)

    internal = result.internal_interview_prep.resume_deep_dive_questions[0]
    assert internal.answer_plan.direct_answer
    assert internal.answer_plan.selected_facts
    assert internal.answer_plan.reasoning_or_tradeoffs
    assert internal.answer_plan.result
    assert internal.answer_plan.reflection_or_transfer
    assert internal.sample_answer != snippet
    assert "权衡" in internal.sample_answer
    assert "验证" in internal.sample_answer


@pytest.mark.parametrize(
    "invalid_fixture",
    ["leaked_id", "requirement_restatement", "copied_answer"],
)
def test_invalid_output_gets_quality_feedback_and_regenerates(invalid_fixture):
    model = _fake_model(
        [
            _tool_calls(),
            _final(_fixture(invalid_fixture)),
            _tool_calls(),
            _final(_fixture("python_professional")),
        ]
    )
    snippet = _fixture("source")["snippet"]
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python", snippet=snippet)],
        experiences=[_experience()],
    )

    result = InterviewPrepAgent(model=model).run(state)

    assert result.generated_assets.interview_prep.jd_questions
    retry_prompts = [
        message.content
        for invocation in model.invocations
        for message in invocation
        if getattr(message, "type", "") == "human" and "Previous output" in message.content
    ]
    assert retry_prompts
    assert "ev_unknown" not in retry_prompts[0]


def test_prefixed_json_final_output_is_parsed_without_retry():
    output = _fixture("python_professional")
    model = _fake_model(
        [
            _tool_calls(),
            AIMessage(
                content=(
                    "Now I have enough evidence. Here is the final JSON: "
                    + json.dumps(output, ensure_ascii=False)
                )
            ),
        ]
    )
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python")],
        experiences=[_experience()],
    )

    result = InterviewPrepAgent(model=model, max_attempts=1).run(state)

    assert result.generated_assets.interview_prep.jd_questions
    assert len(model.invocations) == 2


def test_unknown_supporting_evidence_ids_are_normalized_from_target_requirement():
    model = _fake_model([_tool_calls(), _final(_fixture("unknown_evidence"))])
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python")],
        experiences=[_experience()],
    )

    result = InterviewPrepAgent(model=model, max_attempts=1).run(state)

    question = result.internal_interview_prep.jd_questions[0]
    assert question.supporting_evidence_ids == ["ev_project"]


def test_three_invalid_attempts_return_controlled_error():
    responses = []
    for _ in range(3):
        responses.extend([_tool_calls(), _final(_fixture("requirement_restatement"))])
    model = _fake_model(responses)
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python")],
        experiences=[_experience()],
    )

    with pytest.raises(InterviewPrepAgentError, match="3 attempts") as exc_info:
        InterviewPrepAgent(model=model).run(state)

    assert "req_python" not in str(exc_info.value)


def test_generate_interview_prep_node_uses_runtime_react_model():
    model = _fake_model(
        [_tool_calls(), _final(_fixture("python_professional"))]
    )
    services = WorkflowServices(
        retrieval_service=object(),
        llm_service=LLMService(client=_UnusedLLMClient()),
        react_model=model,
    )
    state = _state(
        requirements=[_requirement("req_python", "Python 与算法基础")],
        evidence=[_evidence("ev_project", "req_python")],
        experiences=[_experience()],
    )

    generated_state = generate_interview_prep(state, services)
    response = finalize_response(public_output_gate(generated_state, services))

    assert response.status == "completed"
    assert model.invocations


def test_factory_uses_langchain_create_agent(monkeypatch):
    calls = []

    def fake_create_agent(*, model, tools, system_prompt, response_format, name):
        calls.append(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "response_format": response_format,
                "name": name,
            }
        )
        return "compiled-agent"

    monkeypatch.setattr(
        "backend.app.workflow.interview_prep_agent.create_agent",
        fake_create_agent,
    )
    monkeypatch.setattr(
        "backend.app.workflow.interview_prep_agent.react_response_format",
        lambda model, schema: schema,
    )

    agent = create_interview_prep_react_agent(model="model", tools=["tool"])

    assert agent == "compiled-agent"
    assert calls[0]["model"] == "model"
    assert calls[0]["tools"] == ["tool"]
    assert calls[0]["name"] == "interview_prep"
    assert calls[0]["response_format"].__name__ == "InternalInterviewPrep"
    assert "professional" in calls[0]["system_prompt"].lower()
    assert INTERVIEW_PREP_AGENT_PROMPT == calls[0]["system_prompt"]


def test_prompt_contains_explicit_json_example_for_json_mode_providers():
    assert "json example" in INTERVIEW_PREP_AGENT_PROMPT.lower()
    assert '"jd_questions"' in INTERVIEW_PREP_AGENT_PROMPT
    assert '"resume_deep_dive_questions"' in INTERVIEW_PREP_AGENT_PROMPT


class _ToolCallingFakeModel(FakeMessagesListChatModel):
    invocations: list[list[object]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.invocations.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _fake_model(responses):
    return _ToolCallingFakeModel(responses=responses)


def _tool_calls(
    include_evidence=True,
    include_experience=True,
    requirement_id="req_python",
):
    calls = [
        {
            "name": "get_interviewable_requirements",
            "args": {},
            "id": "call_requirements",
            "type": "tool_call",
        }
    ]
    if include_evidence:
        calls.append(
            {
                "name": "get_requirement_evidence",
                "args": {"requirement_id": requirement_id},
                "id": "call_evidence",
                "type": "tool_call",
            }
        )
    if include_experience:
        calls.append(
            {
                "name": "get_experience",
                "args": {"experience_id": "exp_project"},
                "id": "call_experience",
                "type": "tool_call",
            }
        )
    return AIMessage(content="", tool_calls=calls)


def _final(payload):
    return AIMessage(content=json.dumps(payload, ensure_ascii=False))


def _fixture(name):
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "interview_prep_react_calls.json").read_text(
            encoding="utf-8"
        )
    )
    return payload[name]


def _state(requirements, evidence, experiences=None):
    evidence_ids = [item.evidence_id for item in evidence]
    bullet_evidence = evidence_ids[:1] or ["ev_placeholder"]
    assets = GeneratedAssets(
        match_summary="简历中存在与岗位相关的可追溯经历。",
        resume_bullets=[
            ResumeBullet(
                text=f"基于项目事实形成的简历要点 {index}。",
                target_requirement_ids=[requirements[0].requirement_id],
                evidence_ids=bullet_evidence,
                risk_level="low",
            )
            for index in range(3)
        ],
        interview_prep=InterviewPrep(),
    )
    return AnalysisState(
        analysis_id="analysis_interview",
        profile_documents=[
            ProfileDocument(
                source_name="resume.pdf",
                source_type="text",
                content="Structured resume fixture for interview preparation.",
            )
        ],
        job_description="Applied AI platform role",
        jd_requirements=requirements,
        retrieved_evidence=evidence,
        allowed_evidence_ids=set(evidence_ids),
        experience_records=experiences or [],
        generated_assets=assets,
    )


def _requirement(
    requirement_id,
    text,
    *,
    verification_mode="system_design",
    interviewability=True,
    question_focus="Architecture, constraints, trade-offs, and validation",
):
    return JDRequirement(
        requirement_id=requirement_id,
        category="qualification" if verification_mode == "document_check" else "hard_skill",
        text=text,
        importance="high",
        keywords=text.split(),
        capability_tags=["applied_ai"],
        verification_mode=verification_mode,
        interviewability=interviewability,
        question_focus=question_focus,
    )


def _experience(name="CareerPilot"):
    return ExperienceRecord(
        experience_id="exp_project",
        experience_type="project",
        name=name,
        objective="构建可靠的 AI 分析平台。",
        responsibilities=["负责核心工作流与服务设计。"],
        technologies=["Python", "FastAPI"],
        challenges=["平衡吞吐、延迟与可恢复性。"],
        actions=["设计分层架构并建立评估流程。"],
        outcomes=["完成可验证的端到端系统。"],
        raw_source_chunk_ids=["chunk_ev_project"],
        raw_text="负责 CareerPilot 项目的架构、实现与评估。",
    )


def _evidence(
    evidence_id,
    requirement_id,
    *,
    snippet="负责 CareerPilot 项目的 Python 服务、可靠性设计与评估。",
):
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.pdf",
        section_label="项目经历",
        section_type="project",
        snippet=snippet,
        score=0.9,
    )


class _UnusedLLMClient:
    def generate(self, prompt_key, prompt, variables):
        raise AssertionError("One-shot LLMService must not generate interview prep.")

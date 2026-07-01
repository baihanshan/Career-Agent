import json
import logging
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError
from pydantic import Field

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.core.errors import ReActErrorCode
from backend.app.documents.models import ProfileDocument
from backend.app.workflow.domain_models import ExperienceRecord, SupportType
from backend.app.workflow.resume_evidence_agent import (
    RESUME_EVIDENCE_AGENT_PROMPT,
    ResumeEvidenceAgent,
    ResumeEvidenceAgentError,
    create_resume_evidence_react_agent,
)
from backend.app.workflow.state import AnalysisState


def test_agent_calls_search_then_inspects_and_compares_after_insufficient_observation():
    fixture = _fixture("insufficient_then_compare")
    model = _fake_model(fixture["responses"])
    state = _state(
        [_requirement("req_python", "Python engineering", ["programming"])],
        experiences=[_experience("exp_api", "API Platform")],
    )
    service = _ScriptedRetrievalService(
        [[_evidence("ev_skill", "req_python", "skill", "Python skill list")]]
    )

    result = ResumeEvidenceAgent(model=model).run(state, service)

    assert [step.tool_name for step in result.agent_traces[0].steps] == [
        "search_resume_evidence",
        "get_experience",
        "compare_requirement_to_evidence",
    ]
    assert result.evidence_selections[0].support_level == "partial"
    assert result.allowed_evidence_ids == {"ev_skill"}
    serialized_trace = json.dumps(
        result.agent_traces[0].model_dump(mode="json"),
        ensure_ascii=False,
    )
    assert "requirement_id" not in serialized_trace
    assert "evidence_ids" not in serialized_trace


def test_multiple_python_projects_form_indirect_support_instead_of_missing():
    model = _fake_model(
        [
            _tool_call(
                "search_resume_evidence",
                {"query": "Python programming", "requirement_id": "req_python"},
                "call_search_python",
            ),
            _final(
                [
                    _selection(
                        "req_python",
                        ["ev_api", "ev_nlp"],
                        "strong",
                        ["indirect"],
                    )
                ]
            ),
        ]
    )
    state = _state(
        [_requirement("req_python", "扎实的 Python 编程基础", ["programming"])]
    )
    service = _ScriptedRetrievalService(
        [
            [
                _evidence("ev_api", "req_python", "project", "Built a Python API."),
                _evidence("ev_nlp", "req_python", "project", "Built an NLP classifier in Python."),
            ]
        ]
    )

    result = ResumeEvidenceAgent(model=model).run(state, service)

    selection = result.evidence_selections[0]
    assert selection.support_level == "strong"
    assert selection.support_types == [SupportType.INDIRECT]
    assert selection.selected_evidence_ids == ["ev_api", "ev_nlp"]


def test_multimodal_internship_is_direct_support_for_multimodal_requirement():
    model = _fake_model(
        [
            _tool_call(
                "search_resume_evidence",
                {"query": "multimodal", "requirement_id": "req_multimodal"},
                "call_search_multimodal",
            ),
            _final(
                [
                    _selection(
                        "req_multimodal",
                        ["ev_tencent"],
                        "strong",
                        ["direct"],
                    )
                ]
            ),
        ]
    )
    state = _state(
        [_requirement("req_multimodal", "多模态领域经验", ["multimodal"])]
    )
    service = _ScriptedRetrievalService(
        [
            [
                _evidence(
                    "ev_tencent",
                    "req_multimodal",
                    "internship",
                    "腾讯混元多模态团队图像转文本模型评估。",
                )
            ]
        ]
    )

    result = ResumeEvidenceAgent(model=model).run(state, service)

    assert result.evidence_selections[0].support_types == [SupportType.DIRECT]
    assert [item.evidence_id for item in result.retrieved_evidence] == ["ev_tencent"]


def test_education_or_other_observation_does_not_force_agent_to_stop_searching():
    model = _fake_model(
        [
            _tool_call(
                "search_resume_evidence",
                {"query": "machine learning", "requirement_id": "req_ml"},
                "call_search_all",
            ),
            _tool_call(
                "search_resume_evidence",
                {
                    "query": "machine learning project",
                    "requirement_id": "req_ml",
                    "section_types": ["project", "internship"],
                },
                "call_search_experience",
            ),
            _final(
                [_selection("req_ml", ["ev_project"], "strong", ["direct"])]
            ),
        ]
    )
    state = _state([_requirement("req_ml", "机器学习项目经验", ["machine_learning"])])
    service = _ScriptedRetrievalService(
        [
            [_evidence("ev_education", "req_ml", "education", "MSc Artificial Intelligence")],
            [_evidence("ev_project", "req_ml", "project", "Trained a segmentation model")],
        ]
    )

    result = ResumeEvidenceAgent(model=model).run(state, service)

    assert service.call_count == 2
    assert [step.tool_name for step in result.agent_traces[0].steps] == [
        "search_resume_evidence",
        "search_resume_evidence",
    ]
    assert result.evidence_selections[0].selected_evidence_ids == ["ev_project"]


def test_unknown_evidence_id_gets_quality_feedback_and_fails_after_three_attempts():
    responses = []
    for attempt in range(1, 4):
        responses.extend(
            [
                _tool_call(
                    "search_resume_evidence",
                    {"query": "Python", "requirement_id": "req_python"},
                    f"call_search_{attempt}",
                ),
                _final(
                    [_selection("req_python", ["ev_made_up"], "strong", ["direct"])]
                ),
            ]
        )
    model = _fake_model(responses)
    state = _state([_requirement("req_python", "Python engineering", ["programming"])])
    service = _ScriptedRetrievalService(
        [[_evidence("ev_real", "req_python", "project", "Built a Python API")]]
    )

    with pytest.raises(ResumeEvidenceAgentError) as exc_info:
        ResumeEvidenceAgent(model=model, max_attempts=3).run(state, service)

    assert exc_info.value.code == "REACT_EVIDENCE_VIOLATION"
    assert service.call_count == 3
    retry_prompts = [
        message.content
        for invocation in model.messages_seen
        for message in invocation
        if getattr(message, "type", "") == "human" and "UNKNOWN_EVIDENCE_ID" in message.content
    ]
    assert retry_prompts
    assert "ev_made_up" not in retry_prompts[0]


def test_invalid_final_output_is_not_misclassified_by_earlier_tool_error():
    responses = []
    for attempt in range(1, 4):
        responses.extend(
            [
                _tool_call(
                    "search_resume_evidence",
                    {"query": "Python", "requirement_id": "req_unknown"},
                    f"call_unknown_{attempt}",
                ),
                AIMessage(content="not valid JSON"),
            ]
        )
    model = _fake_model(responses)
    state = _state([_requirement("req_python", "Python engineering", ["programming"])])
    service = _ScriptedRetrievalService([])

    with pytest.raises(ResumeEvidenceAgentError) as exc_info:
        ResumeEvidenceAgent(model=model, max_attempts=3).run(state, service)

    assert exc_info.value.failed_tool == "structured_output"
    assert exc_info.value.code == "REACT_OUTPUT_PARSE_ERROR"


def test_invalid_final_output_logs_sanitized_model_content(caplog):
    responses = [
        _tool_call(
            "search_resume_evidence",
            {"query": "Python", "requirement_id": "req_python"},
            "call_search_python",
        ),
        AIMessage(
            content=(
                "I found evidence in Structured resume fixture with project and "
                "internship evidence. But here is prose instead of JSON."
            )
        ),
    ]
    model = _fake_model(responses)
    state = _state([_requirement("req_python", "Python engineering", ["programming"])])
    service = _ScriptedRetrievalService(
        [[_evidence("ev_real", "req_python", "project", "Built a Python API")]]
    )

    with caplog.at_level(
        logging.WARNING,
        logger="backend.app.workflow.resume_evidence_agent",
    ):
        with pytest.raises(ResumeEvidenceAgentError):
            ResumeEvidenceAgent(model=model, max_attempts=1).run(state, service)

    log_text = caplog.text
    assert "event=resume_evidence_structured_output_parse_failed" in log_text
    assert "exception=JSONDecodeError" in log_text
    assert "final_ai_message=" in log_text
    assert "[resume redacted]" in log_text
    assert "Structured resume fixture with project and internship evidence" not in log_text


def test_recursion_limit_scales_with_requirement_count(monkeypatch):
    captured_configs = []

    class RecordingAgent:
        def invoke(self, payload, config):
            captured_configs.append(config)
            return {
                "messages": [
                    _final(
                        [
                            _selection(
                                f"req_{index}",
                                ["ev_shared"],
                                "partial",
                                ["contextual"],
                            )
                            for index in range(1, 7)
                        ]
                    )
                ]
            }

    monkeypatch.setattr(
        "backend.app.workflow.resume_evidence_agent.create_resume_evidence_react_agent",
        lambda model, tools: RecordingAgent(),
    )
    requirements = [
        _requirement(f"req_{index}", f"Requirement {index}", ["programming"])
        for index in range(1, 7)
    ]
    state = _state(requirements).model_copy(
        update={
            "allowed_evidence_ids": {"ev_shared"},
            "retrieved_evidence": [
                _evidence("ev_shared", "req_1", "project", "Built a Python API")
            ],
        }
    )

    ResumeEvidenceAgent(model=object()).run(state, _ScriptedRetrievalService([]))

    assert captured_configs == [{"recursion_limit": 36}]


def test_graph_recursion_error_is_classified_separately(monkeypatch):
    class RecursingAgent:
        def invoke(self, payload, config):
            raise GraphRecursionError("Recursion limit reached")

    monkeypatch.setattr(
        "backend.app.workflow.resume_evidence_agent.create_resume_evidence_react_agent",
        lambda model, tools: RecursingAgent(),
    )
    state = _state([_requirement("req_python", "Python engineering", ["programming"])])

    with pytest.raises(ResumeEvidenceAgentError) as exc_info:
        ResumeEvidenceAgent(model=object(), max_attempts=1).run(
            state,
            _ScriptedRetrievalService([]),
        )

    assert exc_info.value.failed_tool == "recursion_limit"
    assert exc_info.value.code == ReActErrorCode.REACT_RECURSION_LIMIT_ERROR.value


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
        "backend.app.workflow.resume_evidence_agent.create_agent",
        fake_create_agent,
    )
    monkeypatch.setattr(
        "backend.app.workflow.resume_evidence_agent.react_response_format",
        lambda model, schema: schema,
    )

    agent = create_resume_evidence_react_agent(model="model", tools=["tool"])

    assert agent == "compiled-agent"
    assert calls[0]["model"] == "model"
    assert calls[0]["tools"] == ["tool"]
    assert calls[0]["name"] == "resume_evidence"
    assert calls[0]["response_format"].__name__ == "_EvidenceSelectionOutput"
    assert "semantic" in calls[0]["system_prompt"].lower()
    assert RESUME_EVIDENCE_AGENT_PROMPT == calls[0]["system_prompt"]


def test_prompt_contains_explicit_json_example_for_json_mode_providers():
    assert "json example" in RESUME_EVIDENCE_AGENT_PROMPT.lower()
    assert '"selections"' in RESUME_EVIDENCE_AGENT_PROMPT


class _ToolCallingFakeModel(FakeMessagesListChatModel):
    messages_seen: list[list[object]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.messages_seen.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _fake_model(responses):
    return _ToolCallingFakeModel(responses=[_message(item) for item in responses])


def _message(item):
    if isinstance(item, AIMessage):
        return item
    if "tool_call" in item:
        call = item["tool_call"]
        return _tool_call(call["name"], call["args"], call["id"])
    return AIMessage(content=json.dumps(item, ensure_ascii=False))


def _tool_call(name, args, call_id):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": call_id, "type": "tool_call"}
        ],
    )


def _final(selections):
    return AIMessage(
        content=json.dumps({"selections": selections}, ensure_ascii=False)
    )


def _selection(requirement_id, evidence_ids, level, support_types):
    return {
        "requirement_id": requirement_id,
        "selected_evidence_ids": evidence_ids,
        "support_level": level,
        "support_types": support_types,
        "rationale": "The selected evidence provides the stated semantic support.",
        "uncovered_aspects": [],
    }


def _fixture(name):
    payload = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "resume_evidence_react_calls.json"
        ).read_text(encoding="utf-8")
    )
    return payload[name]


def _state(requirements, experiences=None):
    return AnalysisState(
        analysis_id="analysis_resume_evidence",
        profile_documents=[
            ProfileDocument(
                source_name="resume.pdf",
                source_type="text",
                content="Structured resume fixture with project and internship evidence.",
            )
        ],
        job_description="Applied AI role",
        jd_requirements=requirements,
        experience_records=experiences or [],
    )


def _requirement(requirement_id, text, tags):
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text=text,
        importance="high",
        keywords=[],
        capability_tags=tags,
        verification_mode="technical_question",
        interviewability=True,
        question_focus="Applied technical depth and trade-offs",
    )


def _experience(experience_id, name):
    return ExperienceRecord(
        experience_id=experience_id,
        experience_type="project",
        name=name,
        responsibilities=["Built a Python API."],
        technologies=["Python"],
        outcomes=["Completed the system."],
        raw_source_chunk_ids=["chunk_api"],
        raw_text="Built a Python API for an applied AI system.",
    )


def _evidence(evidence_id, requirement_id, section_type, snippet):
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id=f"chunk_{evidence_id}",
        source_name="resume.pdf",
        section_type=section_type,
        snippet=snippet,
        score=0.9,
    )


class _ScriptedRetrievalService:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def retrieve_evidence(self, requirements, top_k, section_filter=None):
        index = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        return self.responses[index]

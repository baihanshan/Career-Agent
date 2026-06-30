import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import create_model

from backend.app.api.schemas import RunConfig
from backend.app.llm.react_model import (
    ReActModelFactory,
    ReActModelUnavailableError,
)
from backend.app.llm import react_model


class _RecordingChatModel:
    def __init__(self, **kwargs):
        self.config = kwargs
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self


def test_bind_react_tools_disables_parallel_calls_for_provider_models():
    class RecordingBindingModel:
        def __init__(self):
            self.calls = []

        def bind_tools(self, tools, **kwargs):
            self.calls.append((tools, kwargs))
            return "bound-model"

    model = RecordingBindingModel()

    result = react_model.bind_react_tools(model, ["search"])

    assert result == "bound-model"
    assert model.calls == [(["search"], {"parallel_tool_calls": False})]


def test_bind_react_tools_supports_test_models_without_parallel_keyword():
    class LegacyBindingModel:
        def __init__(self):
            self.calls = []

        def bind_tools(self, tools):
            self.calls.append(tools)
            return "legacy-bound-model"

    model = LegacyBindingModel()

    result = react_model.bind_react_tools(model, ["search"])

    assert result == "legacy-bound-model"
    assert model.calls == [["search"]]


def test_deepseek_provider_uses_json_mode_for_structured_output():
    output_schema = create_model("DeepSeekOutput", value=(str, ...))
    chat_model_cls = react_model._load_chat_openai("deepseek")
    model = chat_model_cls(
        model="deepseek-test",
        api_key="test-key",
        base_url="https://example.invalid",
    )

    runnable = model.with_structured_output(output_schema)

    assert runnable.first.kwargs["response_format"] == {"type": "json_object"}
    assert runnable.first.kwargs["ls_structured_output_format"]["kwargs"] == {
        "method": "json_mode"
    }


@pytest.mark.parametrize(
    ("run_config", "expected_model", "expected_base_url"),
    [
        (
            RunConfig(provider="openai", model="default", api_key="openai-key"),
            "gpt-4.1",
            None,
        ),
        (
            RunConfig(
                provider="deepseek",
                model="default",
                api_key="deepseek-key",
                base_url="https://api.deepseek.com/",
            ),
            "deepseek-v4-flash",
            "https://api.deepseek.com",
        ),
        (
            RunConfig(
                provider="openai_compatible",
                model="custom-tool-model",
                api_key="compatible-key",
                base_url="https://models.example.com/v1/",
            ),
            "custom-tool-model",
            "https://models.example.com/v1",
        ),
    ],
)
def test_factory_builds_provider_chat_model(
    run_config,
    expected_model,
    expected_base_url,
):
    model = ReActModelFactory(chat_model_cls=_RecordingChatModel).create(run_config)

    assert model.config["model"] == expected_model
    assert model.config["api_key"] == run_config.api_key
    assert model.config["temperature"] == run_config.temperature
    assert model.config["request_timeout"] == 180
    assert model.config.get("base_url") == expected_base_url
    assert model.bound_tools == []


@pytest.mark.parametrize("provider", ["openai", "deepseek", "openai_compatible", "local"])
def test_factory_rejects_missing_api_key_or_local_provider(provider):
    with pytest.raises(ReActModelUnavailableError) as exc_info:
        ReActModelFactory(chat_model_cls=_RecordingChatModel).create(
            RunConfig(provider=provider, model="tool-model")
        )

    assert exc_info.value.code == "REACT_MODEL_UNAVAILABLE"
    assert "API key" in str(exc_info.value) or "local" in str(exc_info.value)


def test_factory_rejects_model_without_tool_binding():
    class NoToolBindingModel:
        def __init__(self, **kwargs):
            self.config = kwargs

    with pytest.raises(ReActModelUnavailableError, match="tool calling"):
        ReActModelFactory(chat_model_cls=NoToolBindingModel).create(
            RunConfig(provider="openai", model="gpt-test", api_key="test-key")
        )


def test_factory_rejects_model_that_cannot_bind_tools():
    class BrokenToolBindingModel(_RecordingChatModel):
        def bind_tools(self, tools):
            raise NotImplementedError

    with pytest.raises(ReActModelUnavailableError, match="tool calling"):
        ReActModelFactory(chat_model_cls=BrokenToolBindingModel).create(
            RunConfig(provider="openai", model="gpt-test", api_key="test-key")
        )


def test_factory_accepts_injected_fake_model_with_tool_call_response():
    fake_model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_resume_evidence",
                        "args": {"query": "multimodal"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    model = ReActModelFactory(model_override=fake_model).create(RunConfig())

    response = model.invoke("Find evidence")

    assert response.tool_calls == [
        {
            "name": "search_resume_evidence",
            "args": {"query": "multimodal"},
            "id": "call_1",
            "type": "tool_call",
        }
    ]

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from backend.app.api.schemas import RunConfig
from backend.app.llm.react_model import (
    ReActModelFactory,
    ReActModelUnavailableError,
)


class _RecordingChatModel:
    def __init__(self, **kwargs):
        self.config = kwargs
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self


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

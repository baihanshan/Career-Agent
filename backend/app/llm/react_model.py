from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.api.schemas import RunConfig
from backend.app.llm.client import LLM_REQUEST_TIMEOUT_SECONDS


class ReActModelUnavailableError(RuntimeError):
    """Raised when a configured provider cannot supply a tool-calling model."""

    code = "REACT_MODEL_UNAVAILABLE"


def bind_react_tools(model: Any, tools: list[Any]) -> Any:
    """Bind allowlisted tools once and disable provider-side parallel fan-out."""
    bind_tools = getattr(model, "bind_tools", None)
    if not callable(bind_tools):
        return model
    try:
        return bind_tools(tools, parallel_tool_calls=False)
    except TypeError:
        return bind_tools(tools)


def react_response_format(model: Any, schema: type[Any]) -> type[Any] | None:
    """Use provider structured output only where the provider supports it reliably."""
    provider = getattr(model, "_career_agent_provider", None)
    if provider == "openai":
        return schema
    return None


class ReActModelFactory:
    """Create the ChatModel used by LangGraph ReAct agents."""

    def __init__(
        self,
        chat_model_cls: Callable[..., Any] | None = None,
        model_override: Any | None = None,
    ) -> None:
        self._chat_model_cls = chat_model_cls
        self._model_override = model_override

    def create(self, run_config: RunConfig) -> Any:
        # An explicit override is reserved for deterministic tests. Fake LangChain
        # models can emit tool calls but intentionally do not implement bind_tools.
        if self._model_override is not None:
            return self._model_override

        if run_config.provider == "local":
            raise ReActModelUnavailableError(
                "The local provider cannot run a real ReAct tool-calling agent."
            )
        if not run_config.api_key:
            raise ReActModelUnavailableError(
                "An API key is required to create a ReAct tool-calling model."
            )

        chat_model_cls = self._chat_model_cls or _load_chat_openai(run_config.provider)
        kwargs: dict[str, Any] = {
            "model": _model_name(run_config),
            "api_key": run_config.api_key,
            "temperature": run_config.temperature,
            "request_timeout": LLM_REQUEST_TIMEOUT_SECONDS,
        }
        base_url = _base_url(run_config)
        if base_url is not None:
            kwargs["base_url"] = base_url

        try:
            model = chat_model_cls(**kwargs)
        except Exception as exc:
            raise ReActModelUnavailableError(
                "The configured ReAct ChatModel could not be created."
            ) from exc
        try:
            setattr(model, "_career_agent_provider", run_config.provider)
        except Exception:
            pass

        bind_tools = getattr(model, "bind_tools", None)
        if not callable(bind_tools):
            raise ReActModelUnavailableError(
                "The configured ChatModel does not support tool calling."
            )
        try:
            bind_tools([])
        except Exception as exc:
            raise ReActModelUnavailableError(
                "The configured ChatModel does not support tool calling."
            ) from exc

        return model


def _load_chat_openai(provider: str) -> Callable[..., Any]:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ReActModelUnavailableError(
            "langchain-openai is required for the ReAct ChatModel runtime."
        ) from exc
    if provider != "deepseek":
        return ChatOpenAI

    class DeepSeekChatOpenAI(ChatOpenAI):
        """Use DeepSeek's supported JSON Object mode for Pydantic output."""

        def with_structured_output(self, schema=None, **kwargs):
            kwargs.setdefault("method", "json_mode")
            return super().with_structured_output(schema, **kwargs)

    return DeepSeekChatOpenAI


def _model_name(run_config: RunConfig) -> str:
    if run_config.model != "default":
        return run_config.model
    if run_config.provider == "openai":
        return "gpt-4.1"
    if run_config.provider == "deepseek":
        return "deepseek-v4-flash"
    return "default"


def _base_url(run_config: RunConfig) -> str | None:
    if run_config.provider == "openai":
        return None
    if run_config.provider == "deepseek":
        return (run_config.base_url or "https://api.deepseek.com").rstrip("/")
    return (run_config.base_url or "https://api.openai.com/v1").rstrip("/")

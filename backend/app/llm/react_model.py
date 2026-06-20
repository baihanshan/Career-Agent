from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.api.schemas import RunConfig


class ReActModelUnavailableError(RuntimeError):
    """Raised when a configured provider cannot supply a tool-calling model."""

    code = "REACT_MODEL_UNAVAILABLE"


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

        chat_model_cls = self._chat_model_cls or _load_chat_openai()
        kwargs: dict[str, Any] = {
            "model": _model_name(run_config),
            "api_key": run_config.api_key,
            "temperature": run_config.temperature,
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


def _load_chat_openai() -> Callable[..., Any]:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ReActModelUnavailableError(
            "langchain-openai is required for the ReAct ChatModel runtime."
        ) from exc
    return ChatOpenAI


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

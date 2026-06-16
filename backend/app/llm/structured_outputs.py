from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMOutputParseError(ValueError):
    pass


def parse_model(raw_output: str, model_type: type[ModelT]) -> ModelT:
    try:
        return model_type.model_validate_json(raw_output)
    except ValidationError as exc:
        raise LLMOutputParseError(str(exc)) from exc


def parse_model_list(raw_output: str, model_type: type[ModelT]) -> list[ModelT]:
    try:
        return TypeAdapter(list[model_type]).validate_json(raw_output)
    except ValidationError as exc:
        raise LLMOutputParseError(str(exc)) from exc

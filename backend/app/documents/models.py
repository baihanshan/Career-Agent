from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


SupportedProfileSourceType = Literal["text", "markdown"]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ProfileDocument(BaseModel):
    document_id: str = Field(default_factory=lambda: _new_id("doc"))
    source_name: str
    source_type: SupportedProfileSourceType
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_name", "content")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped


class ProfileChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_name: str
    section_label: str | None = None
    text: str
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    embedding_id: str | None = None

    @field_validator("chunk_id", "document_id", "source_name", "text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped

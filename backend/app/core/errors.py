from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ValidationErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"


class DocumentProcessingErrorCode(StrEnum):
    DOCUMENT_PROCESSING_ERROR = "DOCUMENT_PROCESSING_ERROR"
    PROFILE_CONTENT_SHORT = "PROFILE_CONTENT_SHORT"


class VectorStoreErrorCode(StrEnum):
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"


class LLMErrorCode(StrEnum):
    LLM_OUTPUT_PARSE_ERROR = "LLM_OUTPUT_PARSE_ERROR"


class WorkflowErrorCode(StrEnum):
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    WRITER_ERROR = "WRITER_ERROR"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    WORKFLOW_ERROR = "WORKFLOW_ERROR"


class AppError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ProcessingWarning(BaseModel):
    code: str
    message: str
    source: str | None = None

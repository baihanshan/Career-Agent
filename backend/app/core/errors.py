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
    JD_ANALYST_ERROR = "JD_ANALYST_ERROR"
    RESUME_EVIDENCE_AGENT_ERROR = "RESUME_EVIDENCE_AGENT_ERROR"
    MATCH_STRATEGIST_ERROR = "MATCH_STRATEGIST_ERROR"
    RESUME_BULLET_AGENT_ERROR = "RESUME_BULLET_AGENT_ERROR"
    INTERVIEW_PREP_AGENT_ERROR = "INTERVIEW_PREP_AGENT_ERROR"
    RISK_AUDITOR_AGENT_ERROR = "RISK_AUDITOR_AGENT_ERROR"
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    WRITER_ERROR = "WRITER_ERROR"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    WORKFLOW_ERROR = "WORKFLOW_ERROR"


class WorkflowWarningCode(StrEnum):
    COLLECTION_CLEANUP_FAILED = "COLLECTION_CLEANUP_FAILED"


class AgentExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failed_tool: str,
        trace_summary: str,
    ) -> None:
        super().__init__(message)
        self.failed_tool = failed_tool
        self.trace_summary = trace_summary


class AppError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ProcessingWarning(BaseModel):
    code: str
    message: str
    source: str | None = None

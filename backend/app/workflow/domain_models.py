from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class VerificationMode(str, Enum):
    DOCUMENT_CHECK = "document_check"
    EVIDENCE_CHECK = "evidence_check"
    TECHNICAL_QUESTION = "technical_question"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL_QUESTION = "behavioral_question"


class SupportType(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    CONTEXTUAL = "contextual"
    INSUFFICIENT = "insufficient"
    CONTRADICTION = "contradiction"


class NumericClaimType(str, Enum):
    PERFORMANCE_METRIC = "performance_metric"
    BUSINESS_IMPACT = "business_impact"
    DATASET_SIZE = "dataset_size"
    COUNT = "count"
    DATE = "date"
    DURATION = "duration"
    ORDINAL = "ordinal"
    MODEL_OR_VERSION = "model_or_version"
    OTHER = "other"


class ExperienceRecord(BaseModel):
    experience_id: str
    experience_type: str
    name: str
    company_name: str | None = None
    role_title: str | None = None
    date_range: str | None = None
    objective: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    raw_source_chunk_ids: list[str] = Field(default_factory=list)
    raw_text: str

    @field_validator("experience_type")
    @classmethod
    def require_known_experience_type(cls, value: str) -> str:
        if value not in {"project", "internship"}:
            raise ValueError("Experience type must be project or internship.")
        return value

    @field_validator("experience_id", "name", "raw_text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        return _non_empty(value)


class EvidenceSelection(BaseModel):
    requirement_id: str
    selected_evidence_ids: list[str] = Field(default_factory=list)
    support_level: str
    support_types: list[SupportType] = Field(default_factory=list)
    rationale: str
    uncovered_aspects: list[str] = Field(default_factory=list)

    @field_validator("support_level")
    @classmethod
    def require_known_support_level(cls, value: str) -> str:
        if value not in {"strong", "partial", "weak", "missing"}:
            raise ValueError("Unknown evidence support level.")
        return value

    @field_validator("requirement_id", "rationale")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        return _non_empty(value)

    @model_validator(mode="after")
    def validate_support_consistency(self) -> "EvidenceSelection":
        if self.support_level in {"strong", "partial"} and not self.selected_evidence_ids:
            raise ValueError("Strong or partial support requires selected evidence.")
        if self.support_level == "missing" and SupportType.DIRECT in self.support_types:
            raise ValueError("Missing support cannot claim direct support.")
        return self


class NumericClaim(BaseModel):
    value: str
    normalized_value: str
    claim_type: NumericClaimType
    context: str
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("value", "normalized_value", "context")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        return _non_empty(value)


class QualityIssue(BaseModel):
    code: str
    field_path: str
    message: str
    retry_instruction: str
    severity: str

    @field_validator("severity")
    @classmethod
    def require_known_severity(cls, value: str) -> str:
        if value not in {"low", "medium", "high"}:
            raise ValueError("Unknown quality issue severity.")
        return value

    @field_validator("code", "field_path", "message", "retry_instruction")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        return _non_empty(value)


class InterviewAnswerPlan(BaseModel):
    direct_answer: str
    selected_facts: list[str] = Field(default_factory=list)
    reasoning_or_tradeoffs: str
    result: str
    reflection_or_transfer: str

    @field_validator(
        "direct_answer",
        "reasoning_or_tradeoffs",
        "result",
        "reflection_or_transfer",
    )
    @classmethod
    def require_non_empty_plan_text(cls, value: str) -> str:
        return _non_empty(value)


class InternalInterviewQuestion(BaseModel):
    question: str
    question_type: str
    competencies_tested: list[str] = Field(default_factory=list)
    target_requirement_ids: list[str] = Field(default_factory=list)
    answer_plan: InterviewAnswerPlan
    sample_answer: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    experience_id: str | None = None

    @field_validator("question", "question_type", "sample_answer")
    @classmethod
    def require_non_empty_public_text(cls, value: str) -> str:
        return _non_empty(value)


class InternalInterviewPrep(BaseModel):
    jd_questions: list[InternalInterviewQuestion] = Field(default_factory=list)
    resume_deep_dive_questions: list[InternalInterviewQuestion] = Field(
        default_factory=list
    )


class InternalRiskItem(BaseModel):
    risk_type: str
    title: str
    jd_requirement_summary: str
    resume_current_state: str
    risk_reason: str
    recommendation: str
    severity: str
    requirement_ids: list[str] = Field(default_factory=list)
    internal_supporting_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("severity")
    @classmethod
    def require_known_severity(cls, value: str) -> str:
        if value not in {"low", "medium", "high"}:
            raise ValueError("Unknown risk severity.")
        return value

    @field_validator(
        "risk_type",
        "title",
        "jd_requirement_summary",
        "resume_current_state",
        "risk_reason",
        "recommendation",
    )
    @classmethod
    def require_non_empty_public_text(cls, value: str) -> str:
        return _non_empty(value)


class InternalRiskReport(BaseModel):
    risks: list[InternalRiskItem] = Field(default_factory=list)


def _non_empty(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Field must not be empty.")
    return stripped

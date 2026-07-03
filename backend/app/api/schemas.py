from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.documents.models import ProfileDocument


RequirementCategory = Literal[
    "responsibility",
    "hard_skill",
    "soft_skill",
    "qualification",
    "nice_to_have",
]
Importance = Literal["high", "medium", "low"]
MatchLevel = Literal["strong", "partial", "weak", "missing"]
RiskLevel = Literal["low", "medium", "high"]
AssetType = Literal["resume_bullet", "match_summary", "interview_prep"]
Severity = Literal["low", "medium", "high"]
ToolStatus = Literal["success", "error"]
OverallStatus = Literal["pass", "pass_with_warnings", "fail"]
AnalysisStatus = Literal["completed", "failed"]
LLMProvider = Literal["local", "openai", "deepseek", "openai_compatible"]
ResumeSectionType = Literal["internship", "project", "skill", "education", "other"]
VerificationModeValue = Literal[
    "document_check",
    "evidence_check",
    "technical_question",
    "system_design",
    "behavioral_question",
]
LogicalOperator = Literal["AND", "OR"]


class RunConfig(BaseModel):
    provider: LLMProvider = "local"
    model: str = "default"
    temperature: float = Field(default=0.2, ge=0, le=2)
    top_k: int = Field(default=5, ge=1, le=20)
    api_key: str | None = None
    base_url: str | None = None

    @field_validator("api_key", "base_url")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class JDRequirement(BaseModel):
    requirement_id: str
    category: RequirementCategory
    text: str
    importance: Importance
    keywords: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    verification_mode: VerificationModeValue = "evidence_check"
    interviewability: bool = False
    question_focus: str | None = None
    logical_operator: LogicalOperator = "AND"
    alternatives: list[str] = Field(default_factory=list)

    @field_validator("requirement_id", "text")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped

    @field_validator("question_focus")
    @classmethod
    def strip_optional_question_focus(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("keywords", "capability_tags", "alternatives")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @model_validator(mode="after")
    def validate_requirement_semantics(self) -> "JDRequirement":
        if self.verification_mode == "document_check" and self.interviewability:
            raise ValueError("Document checks cannot be marked interviewable.")
        if self.interviewability and not self.question_focus:
            raise ValueError("Interviewable requirements need a question focus.")
        if self.logical_operator == "OR" and len(self.alternatives) < 2:
            raise ValueError("OR requirements need at least two alternatives.")
        return self


class EvidenceItem(BaseModel):
    evidence_id: str
    requirement_id: str
    chunk_id: str
    source_name: str
    section_label: str | None = None
    section_type: ResumeSectionType = "other"
    snippet: str
    score: float = Field(ge=0, le=1)

    @field_validator("evidence_id", "requirement_id", "chunk_id", "source_name", "snippet")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped


class MatchItem(BaseModel):
    requirement_id: str
    match_level: MatchLevel
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    gap_note: str | None = None


class ResumeSectionMetadata(BaseModel):
    company_name: str | None = None
    role_title: str | None = None
    project_name: str | None = None
    technologies: list[str] = Field(default_factory=list)


class ResumeSection(BaseModel):
    section_type: ResumeSectionType
    section_title: str
    content: str
    metadata: ResumeSectionMetadata = Field(default_factory=ResumeSectionMetadata)

    @field_validator("section_title", "content")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped


class AgentToolResult(BaseModel):
    tool_name: str
    arguments_summary: str
    return_summary: str
    status: ToolStatus
    attempt_number: int = Field(default=1, ge=1)

    @field_validator("tool_name", "arguments_summary", "return_summary", "status")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped


class AgentTrace(BaseModel):
    agent_name: str
    steps: list[AgentToolResult] = Field(default_factory=list)
    final_decision_summary: str

    @model_validator(mode="before")
    @classmethod
    def convert_legacy_single_step_shape(cls, data):
        if not isinstance(data, dict):
            return data
        if "steps" in data or "tool_name" not in data:
            return data
        return {
            "agent_name": data.get("agent_name"),
            "steps": [
                {
                    "tool_name": data.get("tool_name"),
                    "arguments_summary": data.get("arguments_summary"),
                    "return_summary": data.get("observation_summary"),
                    "status": "success",
                }
            ],
            "final_decision_summary": data.get("final_decision_summary"),
        }

    @field_validator("agent_name", "final_decision_summary")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped


class MatchStrategyItem(BaseModel):
    evidence_id: str
    section_type: ResumeSectionType
    priority_score: float = Field(ge=0, le=1)
    rationale: str
    requirement_id: str | None = None


class MatchStrategy(BaseModel):
    ranked_evidence: list[MatchStrategyItem] = Field(default_factory=list)
    covered_requirement_ids: list[str] = Field(default_factory=list)
    missing_requirement_ids: list[str] = Field(default_factory=list)
    summary: str | None = None


class ResumeBullet(BaseModel):
    text: str
    target_requirement_ids: list[str]
    evidence_ids: list[str]
    risk_level: RiskLevel


class InterviewPrepQuestion(BaseModel):
    question: str
    sample_answer: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class InterviewPrep(BaseModel):
    jd_questions: list[InterviewPrepQuestion] = Field(default_factory=list)
    resume_deep_dive_questions: list[InterviewPrepQuestion] = Field(default_factory=list)


class RiskItem(BaseModel):
    risk_type: str
    title: str
    jd_requirement_summary: str
    resume_current_state: str
    risk_reason: str
    recommendation: str
    severity: Severity


class RiskReport(BaseModel):
    risks: list[RiskItem] = Field(default_factory=list, max_length=3)


class PublicJDRequirement(BaseModel):
    category: RequirementCategory
    text: str
    importance: Importance
    capability_tags: list[str] = Field(default_factory=list)
    verification_mode: VerificationModeValue
    interviewability: bool
    question_focus: str | None = None
    logical_operator: LogicalOperator
    alternatives: list[str] = Field(default_factory=list)


class PublicMatchItem(BaseModel):
    requirement_text: str
    match_level: MatchLevel
    rationale: str
    gap_note: str | None = None


class PublicResumeBullet(BaseModel):
    text: str
    risk_level: RiskLevel


class PublicInterviewPrepQuestion(BaseModel):
    question: str
    sample_answer: str


class PublicInterviewPrep(BaseModel):
    jd_questions: list[PublicInterviewPrepQuestion] = Field(default_factory=list)
    resume_deep_dive_questions: list[PublicInterviewPrepQuestion] = Field(
        default_factory=list
    )


class PublicGeneratedAssets(BaseModel):
    match_summary: str
    resume_bullets: list[PublicResumeBullet] = Field(default_factory=list, max_length=3)
    interview_prep: PublicInterviewPrep


class PublicGroundingWarning(BaseModel):
    asset_type: AssetType
    claim: str
    reason: str
    severity: Severity


class PublicCoverageGap(BaseModel):
    requirement_text: str
    reason: str
    severity: Severity


class PublicEvaluationReport(BaseModel):
    grounding_warnings: list[PublicGroundingWarning] = Field(default_factory=list)
    coverage_gaps: list[PublicCoverageGap] = Field(default_factory=list)
    specificity_notes: list[str] = Field(default_factory=list)
    risk_summary: str
    overall_status: OverallStatus


class PublicAnalysisResult(BaseModel):
    jd_requirements: list[PublicJDRequirement] = Field(default_factory=list)
    match_analysis: list[PublicMatchItem] = Field(default_factory=list)
    generated_assets: PublicGeneratedAssets | None = None
    evaluation_report: PublicEvaluationReport | None = None
    risk_report: RiskReport | None = None
    processing_warnings: list[dict[str, Any]] = Field(default_factory=list)
    agent_traces: list[AgentTrace] = Field(default_factory=list)


class GeneratedAssets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_summary: str
    resume_bullets: list[ResumeBullet] = Field(min_length=3, max_length=3)
    interview_prep: InterviewPrep


class GroundingWarning(BaseModel):
    asset_type: AssetType
    asset_id: str
    claim: str
    reason: str
    severity: Severity


class CoverageGap(BaseModel):
    requirement_id: str
    requirement_text: str | None = None
    reason: str
    severity: Severity = "medium"


class EvaluationReport(BaseModel):
    grounding_warnings: list[GroundingWarning]
    coverage_gaps: list[CoverageGap]
    specificity_notes: list[str]
    risk_summary: str
    overall_status: OverallStatus


class AnalysisRequest(BaseModel):
    profile_documents: list[ProfileDocument]
    job_description: str
    run_config: RunConfig = Field(default_factory=RunConfig)

    @field_validator("job_description")
    @classmethod
    def require_job_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Job description must not be empty.")
        return stripped

    @model_validator(mode="after")
    def require_profile_documents(self) -> "AnalysisRequest":
        if not self.profile_documents:
            raise ValueError("At least one profile document is required.")
        return self


class PDFParseResponse(BaseModel):
    source_name: str
    page_count: int = Field(ge=1)
    text: str

    @field_validator("source_name", "text")
    @classmethod
    def require_pdf_parse_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

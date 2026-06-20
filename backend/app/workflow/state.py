from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.api.schemas import (
    AgentTrace,
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    JDRequirement,
    MatchStrategy,
    MatchItem,
    ResumeSection,
    RiskReport,
    RunConfig,
)
from backend.app.core.errors import AppError, ProcessingWarning
from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.workflow.domain_models import (
    EvidenceSelection,
    ExperienceRecord,
    QualityIssue,
)


class WorkflowState(BaseModel):
    analysis_id: str
    profile_documents: list[ProfileDocument]
    job_description: str
    run_config: RunConfig = Field(default_factory=RunConfig)
    profile_index_id: str | None = None
    profile_chunks: list[ProfileChunk] = Field(default_factory=list)
    processing_warnings: list[ProcessingWarning] = Field(default_factory=list)
    jd_requirements: list[JDRequirement] = Field(default_factory=list)
    structured_resume_sections: list[ResumeSection] = Field(default_factory=list)
    experience_records: list[ExperienceRecord] = Field(default_factory=list)
    retrieved_evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_selections: list[EvidenceSelection] = Field(default_factory=list)
    allowed_evidence_ids: set[str] = Field(default_factory=set)
    match_analysis: list[MatchItem] = Field(default_factory=list)
    match_strategy: MatchStrategy | None = None
    generated_assets: GeneratedAssets | None = None
    risk_report: RiskReport | None = None
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    evaluation_report: EvaluationReport | None = None
    quality_issues: list[QualityIssue] = Field(default_factory=list)
    errors: list[AppError] = Field(default_factory=list)


class AnalysisState(WorkflowState):
    pass

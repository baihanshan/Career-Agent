from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.api.schemas import (
    EvaluationReport,
    EvidenceItem,
    GeneratedAssets,
    JDRequirement,
    MatchItem,
    RunConfig,
)
from backend.app.documents.models import ProfileChunk, ProfileDocument


class WorkflowState(BaseModel):
    analysis_id: str
    profile_documents: list[ProfileDocument]
    job_description: str
    run_config: RunConfig = Field(default_factory=RunConfig)
    profile_index_id: str | None = None
    profile_chunks: list[ProfileChunk] = Field(default_factory=list)
    processing_warnings: list[str] = Field(default_factory=list)
    jd_requirements: list[JDRequirement] = Field(default_factory=list)
    retrieved_evidence: list[EvidenceItem] = Field(default_factory=list)
    match_analysis: list[MatchItem] = Field(default_factory=list)
    generated_assets: GeneratedAssets | None = None
    evaluation_report: EvaluationReport | None = None
    errors: list[str] = Field(default_factory=list)


class AnalysisState(WorkflowState):
    pass

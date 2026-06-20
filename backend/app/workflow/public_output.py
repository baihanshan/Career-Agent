from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from backend.app.api.schemas import (
    AgentTrace,
    PublicAnalysisResult,
    PublicCoverageGap,
    PublicEvaluationReport,
    PublicGeneratedAssets,
    PublicGroundingWarning,
    PublicInterviewPrep,
    PublicInterviewPrepQuestion,
    PublicJDRequirement,
    PublicMatchItem,
    PublicResumeBullet,
    RiskItem,
    RiskReport,
)
from backend.app.workflow.domain_models import QualityIssue
from backend.app.workflow.state import WorkflowState


_INTERNAL_REFERENCE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:evidence_ids?|supporting_evidence_ids?|requirement_ids?|chunk_ids?|experience_ids?)\b\s*[:=]"
    ),
    re.compile(r"(?<![A-Za-z0-9])(?:req|ev|chunk|exp)_[A-Za-z0-9][A-Za-z0-9_.:-]*"),
)


class PublicOutputValidationError(ValueError):
    def __init__(self, issues: list[QualityIssue]) -> None:
        super().__init__("Public output contains internal references.")
        self.issues = issues


class InternalIdLeakDetector:
    def find_leaks(self, payload: Any) -> list[str]:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(mode="json")
        leaks: list[str] = []
        self._scan(payload, "", leaks)
        return leaks

    def _scan(self, value: Any, path: str, leaks: list[str]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                self._scan(item, _join_path(path, str(key)), leaks)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._scan(item, _join_path(path, str(index)), leaks)
            return
        if isinstance(value, str) and any(
            pattern.search(value) for pattern in _INTERNAL_REFERENCE_PATTERNS
        ):
            leaks.append(path or "$.")


def project_public_result(state: WorkflowState) -> PublicAnalysisResult:
    requirements_by_id = {
        item.requirement_id: item for item in state.jd_requirements
    }
    result = PublicAnalysisResult(
        jd_requirements=[
            PublicJDRequirement(
                category=item.category,
                text=item.text,
                importance=item.importance,
                capability_tags=item.capability_tags,
                verification_mode=item.verification_mode,
                interviewability=item.interviewability,
                question_focus=item.question_focus,
                logical_operator=item.logical_operator,
                alternatives=item.alternatives,
            )
            for item in state.jd_requirements
        ],
        match_analysis=[
            PublicMatchItem(
                requirement_text=requirements_by_id[item.requirement_id].text,
                match_level=item.match_level,
                rationale=item.rationale,
                gap_note=item.gap_note,
            )
            for item in state.match_analysis
            if item.requirement_id in requirements_by_id
        ],
        generated_assets=_project_generated_assets(state),
        evaluation_report=_project_evaluation_report(state, requirements_by_id),
        risk_report=_project_risk_report(state),
        processing_warnings=[
            item.model_dump(mode="json") for item in state.processing_warnings
        ],
        agent_traces=[_project_agent_trace(item) for item in state.agent_traces],
    )
    leak_paths = InternalIdLeakDetector().find_leaks(result)
    if leak_paths:
        issues = [
            QualityIssue(
                code="INTERNAL_ID_LEAK",
                field_path=path,
                message="A user-visible field contains an internal reference.",
                retry_instruction=(
                    "Rewrite the affected public field without evidence, requirement, "
                    "or chunk identifiers."
                ),
                severity="high",
            )
            for path in leak_paths
        ]
        state.quality_issues.extend(issues)
        raise PublicOutputValidationError(issues)
    return result


def _project_generated_assets(state: WorkflowState) -> PublicGeneratedAssets | None:
    assets = state.generated_assets
    if assets is None:
        return None
    return PublicGeneratedAssets(
        match_summary=assets.match_summary,
        resume_bullets=[
            PublicResumeBullet(text=item.text, risk_level=item.risk_level)
            for item in assets.resume_bullets
        ],
        interview_prep=PublicInterviewPrep(
            jd_questions=[
                PublicInterviewPrepQuestion(
                    question=item.question,
                    sample_answer=item.sample_answer,
                )
                for item in assets.interview_prep.jd_questions
            ],
            resume_deep_dive_questions=[
                PublicInterviewPrepQuestion(
                    question=item.question,
                    sample_answer=item.sample_answer,
                )
                for item in assets.interview_prep.resume_deep_dive_questions
            ],
        ),
    )


def _project_evaluation_report(
    state: WorkflowState,
    requirements_by_id: dict[str, Any],
) -> PublicEvaluationReport | None:
    report = state.evaluation_report
    if report is None:
        return None
    return PublicEvaluationReport(
        grounding_warnings=[
            PublicGroundingWarning(
                asset_type=item.asset_type,
                claim=item.claim,
                reason=item.reason,
                severity=item.severity,
            )
            for item in report.grounding_warnings
        ],
        coverage_gaps=[
            PublicCoverageGap(
                requirement_text=(
                    item.requirement_text
                    or requirements_by_id[item.requirement_id].text
                ),
                reason=item.reason,
                severity=item.severity,
            )
            for item in report.coverage_gaps
            if item.requirement_text or item.requirement_id in requirements_by_id
        ],
        specificity_notes=report.specificity_notes,
        risk_summary=report.risk_summary,
        overall_status=report.overall_status,
    )


def _project_risk_report(state: WorkflowState) -> RiskReport | None:
    if state.internal_risk_report is not None:
        return RiskReport(
            risks=[
                RiskItem(
                    risk_type=item.risk_type,
                    title=item.title,
                    jd_requirement_summary=item.jd_requirement_summary,
                    resume_current_state=item.resume_current_state,
                    risk_reason=item.risk_reason,
                    recommendation=item.recommendation,
                    severity=item.severity,
                )
                for item in state.internal_risk_report.risks[:3]
            ]
        )
    return state.risk_report


def _project_agent_trace(trace: AgentTrace) -> AgentTrace:
    return trace.model_copy(deep=True)


def _join_path(prefix: str, segment: str) -> str:
    return f"{prefix}.{segment}" if prefix else segment

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.core.errors import (
    AppError,
    DocumentProcessingErrorCode,
    LLMErrorCode,
    ProcessingWarning,
    VectorStoreErrorCode,
    WorkflowErrorCode,
)
from backend.app.documents.chunker import chunk_profile_document
from backend.app.documents.experience_parser import parse_experience_records
from backend.app.evaluation.evaluator import evaluate_generated_assets
from backend.app.llm.client import LLMService
from backend.app.llm.structured_outputs import LLMOutputParseError
from backend.app.retrieval.service import RetrievalService
from backend.app.workflow.match_scoring import build_match_strategy, score_matches
from backend.app.workflow.interview_prep_agent import (
    InterviewPrepAgent,
    InterviewPrepAgentError,
)
from backend.app.workflow.resume_evidence_agent import (
    ResumeEvidenceAgent,
    ResumeEvidenceAgentError,
)
from backend.app.workflow.risk_auditor_agent import (
    RiskAuditorAgent,
    RiskAuditorAgentError,
)
from backend.app.workflow.state import AnalysisState
from backend.app.workflow.writer import write_application as generate_application


SHORT_PROFILE_CONTENT_CHARS = 40
logger = logging.getLogger(__name__)


@dataclass
class WorkflowServices:
    retrieval_service: RetrievalService
    llm_service: LLMService
    interview_prep_agent: InterviewPrepAgent | None = None
    risk_auditor_agent: RiskAuditorAgent | None = None


def parse_inputs(request: AnalysisRequest) -> AnalysisState:
    return AnalysisState(
        analysis_id=f"analysis_{uuid4().hex}",
        profile_documents=request.profile_documents,
        job_description=request.job_description,
        run_config=request.run_config,
    )


def index_profile(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        processing_warnings = [
            warning
            for document in state.profile_documents
            for warning in _warnings_for_document(document)
        ]
        profile_chunks = [
            chunk
            for document in state.profile_documents
            for chunk in chunk_profile_document(document)
        ]
        experience_records = [
            record
            for document in state.profile_documents
            for record in parse_experience_records(
                document,
                [
                    chunk
                    for chunk in profile_chunks
                    if chunk.document_id == document.document_id
                ],
            )
        ]
        profile_index_id = services.retrieval_service.index_profile(profile_chunks)
        return state.model_copy(
            update={
                "profile_chunks": profile_chunks,
                "experience_records": experience_records,
                "profile_index_id": profile_index_id,
                "processing_warnings": processing_warnings,
            }
        )
    except Exception:
        return _append_error(
            state,
            VectorStoreErrorCode.VECTOR_STORE_ERROR.value,
            "Profile materials could not be indexed. Please try again.",
        )


def analyze_jd(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        jd_requirements = _extract_jd_requirements_with_retry(state, services)
        return state.model_copy(update={"jd_requirements": jd_requirements})
    except LLMOutputParseError as exc:
        _log_agent_failure("jd_analyst", exc, state, "extract_jd_requirements")
        return _append_error(
            state,
            LLMErrorCode.LLM_OUTPUT_PARSE_ERROR.value,
            "Job description could not be parsed into structured requirements.",
        )
    except Exception as exc:
        _log_agent_failure("jd_analyst", exc, state, "extract_jd_requirements")
        return _append_error(
            state,
            WorkflowErrorCode.JD_ANALYST_ERROR.value,
            "Job description analysis failed. Please try again.",
            details={"reason": str(exc)},
        )


def retrieve_evidence(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        return ResumeEvidenceAgent().run(state, services.retrieval_service)
    except ResumeEvidenceAgentError as exc:
        _log_agent_failure(
            "resume_evidence_agent", exc, state, "search_resume_evidence"
        )
        return _append_error(
            state,
            WorkflowErrorCode.RESUME_EVIDENCE_AGENT_ERROR.value,
            "Could not find usable resume evidence for this JD.",
            details={"reason": str(exc)},
        )
    except Exception as exc:
        _log_agent_failure(
            "resume_evidence_agent", exc, state, "search_resume_evidence"
        )
        return _append_error(
            state,
            WorkflowErrorCode.RESUME_EVIDENCE_AGENT_ERROR.value,
            "Evidence retrieval failed. Please try again.",
            details={"reason": str(exc)},
        )


def score_match(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        match_analysis = score_matches(
            requirements=state.jd_requirements,
            evidence_items=state.retrieved_evidence,
        )
        match_strategy = build_match_strategy(
            requirements=state.jd_requirements,
            evidence_items=state.retrieved_evidence,
            match_items=match_analysis,
        )
        return state.model_copy(
            update={"match_analysis": match_analysis, "match_strategy": match_strategy}
        )
    except Exception as exc:
        _log_agent_failure("match_strategist", exc, state, "score_matches")
        return _append_error(
            state,
            WorkflowErrorCode.MATCH_STRATEGIST_ERROR.value,
            "Match strategy could not be generated safely.",
            details={"reason": str(exc)},
        )


def write_application(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        generated_assets = generate_application(
            requirements=state.jd_requirements,
            evidence_items=state.retrieved_evidence,
            match_items=state.match_analysis,
            llm_service=services.llm_service,
        )
        return state.model_copy(update={"generated_assets": generated_assets})
    except Exception as exc:
        _log_agent_failure(
            "resume_bullet_agent", exc, state, "generate_application_assets"
        )
        return _append_error(
            state,
            WorkflowErrorCode.RESUME_BULLET_AGENT_ERROR.value,
            "Application assets could not be generated safely.",
            details={"reason": str(exc)},
        )


def generate_interview_prep(
    state: AnalysisState,
    services: WorkflowServices,
) -> AnalysisState:
    try:
        agent = services.interview_prep_agent or InterviewPrepAgent()
        return agent.run(state)
    except InterviewPrepAgentError as exc:
        _log_agent_failure("interview_prep_agent", exc, state, "draft_answer")
        return _append_error(
            state,
            WorkflowErrorCode.INTERVIEW_PREP_AGENT_ERROR.value,
            "Interview preparation could not be generated safely.",
            details={"reason": str(exc)},
        )
    except Exception as exc:
        _log_agent_failure("interview_prep_agent", exc, state, "draft_answer")
        return _append_error(
            state,
            WorkflowErrorCode.INTERVIEW_PREP_AGENT_ERROR.value,
            "Interview preparation could not be generated safely.",
            details={"reason": str(exc)},
        )


def evaluate_grounding(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        if state.generated_assets is None:
            return _append_error(
                state,
                WorkflowErrorCode.EVALUATION_ERROR.value,
                "Generated assets are missing and cannot be evaluated.",
            )
        evaluation_report = evaluate_generated_assets(
            assets=state.generated_assets,
            requirements=state.jd_requirements,
            evidence_items=state.retrieved_evidence,
            llm_service=services.llm_service,
        )
        return state.model_copy(update={"evaluation_report": evaluation_report})
    except Exception as exc:
        _log_agent_failure(
            "risk_auditor_agent", exc, state, "check_generated_claim_grounding"
        )
        return _append_error(
            state,
            WorkflowErrorCode.RISK_AUDITOR_AGENT_ERROR.value,
            "Generated assets could not be evaluated.",
            details={"reason": str(exc)},
        )


def audit_risks(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        agent = services.risk_auditor_agent or RiskAuditorAgent()
        return agent.run(state)
    except RiskAuditorAgentError as exc:
        _log_agent_failure("risk_auditor_agent", exc, state, "rank_top_risks")
        return _append_error(
            state,
            WorkflowErrorCode.RISK_AUDITOR_AGENT_ERROR.value,
            "Risk audit could not be completed safely.",
            details={"reason": str(exc)},
        )
    except Exception as exc:
        _log_agent_failure("risk_auditor_agent", exc, state, "rank_top_risks")
        return _append_error(
            state,
            WorkflowErrorCode.RISK_AUDITOR_AGENT_ERROR.value,
            "Risk audit could not be completed safely.",
            details={"reason": str(exc)},
        )


def finalize_response(state: AnalysisState) -> AnalysisResponse:
    if state.errors:
        error = state.errors[0]
        return AnalysisResponse(
            analysis_id=state.analysis_id,
            status="failed",
            error={"code": error.code, "message": error.message},
        )

    return AnalysisResponse(
        analysis_id=state.analysis_id,
        status="completed",
        result={
            "profile_chunks": [item.model_dump(mode="json") for item in state.profile_chunks],
            "jd_requirements": [
                item.model_dump(mode="json") for item in state.jd_requirements
            ],
            "match_analysis": [
                item.model_dump(mode="json") for item in state.match_analysis
            ],
            "match_strategy": (
                state.match_strategy.model_dump(mode="json")
                if state.match_strategy is not None
                else None
            ),
            "generated_assets": (
                state.generated_assets.model_dump(mode="json")
                if state.generated_assets is not None
                else None
            ),
            "evaluation_report": (
                state.evaluation_report.model_dump(mode="json")
                if state.evaluation_report is not None
                else None
            ),
            "risk_report": (
                state.risk_report.model_dump(mode="json")
                if state.risk_report is not None
                else None
            ),
            "processing_warnings": [
                warning.model_dump(mode="json") for warning in state.processing_warnings
            ],
            "agent_traces": [
                trace.model_dump(mode="json") for trace in state.agent_traces
            ],
        },
    )


def _extract_jd_requirements_with_retry(
    state: AnalysisState,
    services: WorkflowServices,
):
    try:
        return services.llm_service.extract_jd_requirements(state.job_description)
    except LLMOutputParseError:
        return services.llm_service.extract_jd_requirements(state.job_description)


def _append_error(
    state: AnalysisState,
    code: str,
    message: str,
    details: dict | None = None,
) -> AnalysisState:
    return state.model_copy(
        update={"errors": [*state.errors, AppError(code=code, message=message, details=details)]}
    )


def _log_agent_failure(
    agent_name: str,
    exc: Exception,
    state: AnalysisState,
    fallback_tool: str,
) -> None:
    failed_tool = getattr(exc, "failed_tool", fallback_tool)
    trace_summary = getattr(exc, "trace_summary", "steps=0 tools=none statuses=none")
    reason = _safe_log_text(str(exc), state)
    logger.error(
        "agent=%s tool=%s reason=%s trace_summary=%s",
        agent_name,
        failed_tool,
        reason,
        _safe_log_text(trace_summary, state),
    )


def _safe_log_text(value: str, state: AnalysisState, limit: int = 480) -> str:
    sanitized = value.replace("SYSTEM_PROMPT_SECRET", "[redacted]")
    if state.run_config.api_key:
        sanitized = sanitized.replace(state.run_config.api_key, "[redacted]")
    sanitized = " ".join(sanitized.split())
    return sanitized[:limit]


def _warnings_for_document(document) -> list[ProcessingWarning]:
    if len(document.content.strip()) >= SHORT_PROFILE_CONTENT_CHARS:
        return []
    return [
        ProcessingWarning(
            code=DocumentProcessingErrorCode.PROFILE_CONTENT_SHORT.value,
            message="Profile material is short; generated output may be less specific.",
            source=document.source_name,
        )
    ]

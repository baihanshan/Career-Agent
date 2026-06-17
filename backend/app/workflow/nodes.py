from __future__ import annotations

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
from backend.app.evaluation.evaluator import evaluate_generated_assets
from backend.app.llm.client import LLMService
from backend.app.llm.structured_outputs import LLMOutputParseError
from backend.app.retrieval.service import RetrievalService
from backend.app.workflow.match_scoring import score_matches
from backend.app.workflow.state import AnalysisState
from backend.app.workflow.writer import write_application as generate_application


SHORT_PROFILE_CONTENT_CHARS = 40


@dataclass
class WorkflowServices:
    retrieval_service: RetrievalService
    llm_service: LLMService


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
        profile_index_id = services.retrieval_service.index_profile(profile_chunks)
        return state.model_copy(
            update={
                "profile_chunks": profile_chunks,
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
    except LLMOutputParseError:
        return _append_error(
            state,
            LLMErrorCode.LLM_OUTPUT_PARSE_ERROR.value,
            "Job description could not be parsed into structured requirements.",
        )


def retrieve_evidence(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        evidence = services.retrieval_service.retrieve_evidence(
            requirements=state.jd_requirements,
            top_k=state.run_config.top_k,
        )
        return state.model_copy(update={"retrieved_evidence": evidence})
    except Exception:
        return _append_error(
            state,
            WorkflowErrorCode.RETRIEVAL_ERROR.value,
            "Evidence retrieval failed. Please try again.",
        )


def score_match(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    match_analysis = score_matches(
        requirements=state.jd_requirements,
        evidence_items=state.retrieved_evidence,
    )
    return state.model_copy(update={"match_analysis": match_analysis})


def write_application(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        generated_assets = generate_application(
            requirements=state.jd_requirements,
            evidence_items=state.retrieved_evidence,
            match_items=state.match_analysis,
            llm_service=services.llm_service,
        )
        return state.model_copy(update={"generated_assets": generated_assets})
    except Exception:
        return _append_error(
            state,
            WorkflowErrorCode.WRITER_ERROR.value,
            "Application assets could not be generated safely.",
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
    except Exception:
        return _append_error(
            state,
            WorkflowErrorCode.EVALUATION_ERROR.value,
            "Generated assets could not be evaluated.",
        )


def finalize_response(state: AnalysisState) -> AnalysisResponse:
    if state.errors:
        return AnalysisResponse(
            analysis_id=state.analysis_id,
            status="failed",
            error=state.errors[0].model_dump(mode="json"),
        )

    return AnalysisResponse(
        analysis_id=state.analysis_id,
        status="completed",
        result={
            "profile_chunks": [item.model_dump(mode="json") for item in state.profile_chunks],
            "jd_requirements": [
                item.model_dump(mode="json") for item in state.jd_requirements
            ],
            "evidence_table": [
                item.model_dump(mode="json") for item in state.retrieved_evidence
            ],
            "match_analysis": [
                item.model_dump(mode="json") for item in state.match_analysis
            ],
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


def _append_error(state: AnalysisState, code: str, message: str) -> AnalysisState:
    return state.model_copy(
        update={"errors": [*state.errors, AppError(code=code, message=message)]}
    )


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

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.documents.chunker import chunk_profile_document
from backend.app.evaluation.evaluator import evaluate_generated_assets
from backend.app.llm.client import LLMService
from backend.app.llm.structured_outputs import LLMOutputParseError
from backend.app.retrieval.service import RetrievalService
from backend.app.workflow.match_scoring import score_matches
from backend.app.workflow.state import AnalysisState
from backend.app.workflow.writer import write_application as generate_application


INDEXING_ERROR = "INDEXING_ERROR"
LLM_OUTPUT_PARSE_ERROR = "LLM_OUTPUT_PARSE_ERROR"
RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
WRITER_ERROR = "WRITER_ERROR"
EVALUATION_ERROR = "EVALUATION_ERROR"


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
            }
        )
    except Exception:
        return _append_error(
            state,
            INDEXING_ERROR,
            "Profile materials could not be indexed. Please try again.",
        )


def analyze_jd(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        jd_requirements = _extract_jd_requirements_with_retry(state, services)
        return state.model_copy(update={"jd_requirements": jd_requirements})
    except LLMOutputParseError:
        return _append_error(
            state,
            LLM_OUTPUT_PARSE_ERROR,
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
            RETRIEVAL_ERROR,
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
            WRITER_ERROR,
            "Application assets could not be generated safely.",
        )


def evaluate_grounding(state: AnalysisState, services: WorkflowServices) -> AnalysisState:
    try:
        if state.generated_assets is None:
            return _append_error(
                state,
                EVALUATION_ERROR,
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
            EVALUATION_ERROR,
            "Generated assets could not be evaluated.",
        )


def finalize_response(state: AnalysisState) -> AnalysisResponse:
    if state.errors:
        code, message = _split_error(state.errors[0])
        return AnalysisResponse(
            analysis_id=state.analysis_id,
            status="failed",
            error={"code": code, "message": message},
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
            "processing_warnings": state.processing_warnings,
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
    return state.model_copy(update={"errors": [*state.errors, f"{code}: {message}"]})


def _split_error(error: str) -> tuple[str, str]:
    code, _, message = error.partition(": ")
    return code, message or "Workflow failed."

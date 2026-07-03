from __future__ import annotations

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.workflow.nodes import (
    WorkflowServices,
    analyze_jd,
    audit_risks,
    evaluate_grounding,
    finalize_response,
    generate_interview_prep,
    index_profile,
    parse_inputs,
    public_output_gate,
    retrieve_evidence,
    score_match,
    write_application,
)
from backend.app.workflow.state import AnalysisState
from backend.app.core.errors import WorkflowWarningCode


logger = logging.getLogger(__name__)


WORKFLOW_NODE_ORDER = [
    "parse_inputs",
    "index_profile",
    "jd_analyst",
    "resume_evidence_agent",
    "match_strategist",
    "resume_bullet_agent",
    "interview_prep_agent",
    "risk_auditor_agent",
    "public_output_gate",
    "finalize_response",
]


class AnalysisGraphState(TypedDict, total=False):
    request: AnalysisRequest
    state: AnalysisState
    response: AnalysisResponse


def build_analysis_graph(services: WorkflowServices):
    graph = StateGraph(AnalysisGraphState)

    graph.add_node("parse_inputs", lambda graph_state: _parse_inputs_node(graph_state))
    graph.add_node("index_profile", lambda graph_state: _index_profile_node(graph_state, services))
    graph.add_node("jd_analyst", lambda graph_state: _jd_analyst_node(graph_state, services))
    graph.add_node(
        "resume_evidence_agent",
        lambda graph_state: _resume_evidence_agent_node(graph_state, services),
    )
    graph.add_node(
        "match_strategist",
        lambda graph_state: _match_strategist_node(graph_state, services),
    )
    graph.add_node(
        "resume_bullet_agent",
        lambda graph_state: _resume_bullet_agent_node(graph_state, services),
    )
    graph.add_node(
        "interview_prep_agent",
        lambda graph_state: _interview_prep_agent_node(graph_state, services),
    )
    graph.add_node(
        "risk_auditor_agent",
        lambda graph_state: _risk_auditor_agent_node(graph_state, services),
    )
    graph.add_node(
        "public_output_gate",
        lambda graph_state: _public_output_gate_node(graph_state, services),
    )
    graph.add_node("finalize_response", lambda graph_state: _finalize_response_node(graph_state))

    graph.set_entry_point("parse_inputs")
    graph.add_edge("parse_inputs", "index_profile")
    graph.add_conditional_edges(
        "index_profile",
        _error_route,
        {"error": "finalize_response", "ok": "jd_analyst"},
    )
    graph.add_conditional_edges(
        "jd_analyst",
        _error_route,
        {"error": "finalize_response", "ok": "resume_evidence_agent"},
    )
    graph.add_conditional_edges(
        "resume_evidence_agent",
        _error_route,
        {"error": "finalize_response", "ok": "match_strategist"},
    )
    graph.add_conditional_edges(
        "match_strategist",
        _error_route,
        {"error": "finalize_response", "ok": "resume_bullet_agent"},
    )
    graph.add_conditional_edges(
        "resume_bullet_agent",
        _error_route,
        {"error": "finalize_response", "ok": "interview_prep_agent"},
    )
    graph.add_conditional_edges(
        "interview_prep_agent",
        _error_route,
        {"error": "finalize_response", "ok": "risk_auditor_agent"},
    )
    graph.add_conditional_edges(
        "risk_auditor_agent",
        _error_route,
        {"error": "finalize_response", "ok": "public_output_gate"},
    )
    graph.add_conditional_edges(
        "public_output_gate",
        _error_route,
        {"error": "finalize_response", "ok": "finalize_response"},
    )
    graph.add_edge("finalize_response", END)

    return graph.compile()


def run_workflow(request: AnalysisRequest, services: WorkflowServices) -> AnalysisResponse:
    try:
        graph = build_analysis_graph(services)
        return graph.invoke({"request": request})["response"]
    finally:
        cleanup = getattr(services.retrieval_service, "cleanup", None)
        if callable(cleanup):
            try:
                cleanup()
            except Exception as exc:
                logger.warning(
                    "code=%s reason=%s",
                    WorkflowWarningCode.COLLECTION_CLEANUP_FAILED.value,
                    _safe_log_text(str(exc)),
                )


def _parse_inputs_node(graph_state: AnalysisGraphState) -> AnalysisGraphState:
    return {"state": parse_inputs(graph_state["request"])}


def _index_profile_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": index_profile(graph_state["state"], services)}


def _jd_analyst_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": analyze_jd(graph_state["state"], services)}


def _resume_evidence_agent_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": retrieve_evidence(graph_state["state"], services)}


def _match_strategist_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": score_match(graph_state["state"], services)}


def _resume_bullet_agent_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": write_application(graph_state["state"], services)}


def _interview_prep_agent_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": generate_interview_prep(graph_state["state"], services)}


def _risk_auditor_agent_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    evaluated_state = evaluate_grounding(graph_state["state"], services)
    if evaluated_state.errors:
        return {"state": evaluated_state}
    return {"state": audit_risks(evaluated_state, services)}


def _finalize_response_node(graph_state: AnalysisGraphState) -> AnalysisGraphState:
    return {"response": finalize_response(graph_state["state"])}


def _public_output_gate_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": public_output_gate(graph_state["state"], services)}


def _error_route(graph_state: AnalysisGraphState) -> str:
    return "error" if graph_state["state"].errors else "ok"


def _safe_log_text(value: str, limit: int = 320) -> str:
    sanitized = value.replace("SYSTEM_PROMPT_SECRET", "[redacted]")
    sanitized = " ".join(sanitized.split())
    return sanitized[:limit]

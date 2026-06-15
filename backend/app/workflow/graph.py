from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from backend.app.api.schemas import AnalysisRequest, AnalysisResponse
from backend.app.workflow.nodes import (
    WorkflowServices,
    analyze_jd,
    evaluate_grounding,
    finalize_response,
    index_profile,
    parse_inputs,
    retrieve_evidence,
    score_match,
    write_application,
)
from backend.app.workflow.state import AnalysisState


WORKFLOW_NODE_ORDER = [
    "parse_inputs",
    "index_profile",
    "analyze_jd",
    "retrieve_evidence",
    "score_match",
    "write_application",
    "evaluate_grounding",
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
    graph.add_node("analyze_jd", lambda graph_state: _analyze_jd_node(graph_state, services))
    graph.add_node(
        "retrieve_evidence",
        lambda graph_state: _retrieve_evidence_node(graph_state, services),
    )
    graph.add_node("score_match", lambda graph_state: _score_match_node(graph_state, services))
    graph.add_node(
        "write_application",
        lambda graph_state: _write_application_node(graph_state, services),
    )
    graph.add_node(
        "evaluate_grounding",
        lambda graph_state: _evaluate_grounding_node(graph_state, services),
    )
    graph.add_node("finalize_response", lambda graph_state: _finalize_response_node(graph_state))

    graph.set_entry_point("parse_inputs")
    graph.add_edge("parse_inputs", "index_profile")
    graph.add_conditional_edges(
        "index_profile",
        _error_route,
        {"error": "finalize_response", "ok": "analyze_jd"},
    )
    graph.add_conditional_edges(
        "analyze_jd",
        _error_route,
        {"error": "finalize_response", "ok": "retrieve_evidence"},
    )
    graph.add_conditional_edges(
        "retrieve_evidence",
        _error_route,
        {"error": "finalize_response", "ok": "score_match"},
    )
    graph.add_edge("score_match", "write_application")
    graph.add_conditional_edges(
        "write_application",
        _error_route,
        {"error": "finalize_response", "ok": "evaluate_grounding"},
    )
    graph.add_conditional_edges(
        "evaluate_grounding",
        _error_route,
        {"error": "finalize_response", "ok": "finalize_response"},
    )
    graph.add_edge("finalize_response", END)

    return graph.compile()


def run_workflow(request: AnalysisRequest, services: WorkflowServices) -> AnalysisResponse:
    graph = build_analysis_graph(services)
    return graph.invoke({"request": request})["response"]


def _parse_inputs_node(graph_state: AnalysisGraphState) -> AnalysisGraphState:
    return {"state": parse_inputs(graph_state["request"])}


def _index_profile_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": index_profile(graph_state["state"], services)}


def _analyze_jd_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": analyze_jd(graph_state["state"], services)}


def _retrieve_evidence_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": retrieve_evidence(graph_state["state"], services)}


def _score_match_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": score_match(graph_state["state"], services)}


def _write_application_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": write_application(graph_state["state"], services)}


def _evaluate_grounding_node(
    graph_state: AnalysisGraphState,
    services: WorkflowServices,
) -> AnalysisGraphState:
    return {"state": evaluate_grounding(graph_state["state"], services)}


def _finalize_response_node(graph_state: AnalysisGraphState) -> AnalysisGraphState:
    return {"response": finalize_response(graph_state["state"])}


def _error_route(graph_state: AnalysisGraphState) -> str:
    return "error" if graph_state["state"].errors else "ok"

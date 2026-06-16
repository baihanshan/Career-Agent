import json

from backend.app.api.schemas import AnalysisRequest
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import WORKFLOW_NODE_ORDER, build_analysis_graph, run_workflow
from backend.app.workflow.nodes import WorkflowServices


def test_workflow_graph_defines_expected_node_order():
    assert WORKFLOW_NODE_ORDER == [
        "parse_inputs",
        "index_profile",
        "analyze_jd",
        "retrieve_evidence",
        "score_match",
        "write_application",
        "evaluate_grounding",
        "finalize_response",
    ]


def test_sample_profile_and_jd_run_to_final_response():
    response = run_workflow(request=_request(), services=_services())

    assert response.status == "completed"
    assert response.result["jd_requirements"][0]["requirement_id"] == "req_python"
    assert response.result["evidence_table"][0]["chunk_id"] == "doc_resume:chunk:1"
    assert response.result["match_analysis"][0]["match_level"] == "strong"
    assert response.result["generated_assets"]["resume_bullets"][0]["evidence_ids"]
    assert response.result["evaluation_report"]["overall_status"] in {
        "pass",
        "pass_with_warnings",
        "fail",
    }


def test_build_analysis_graph_returns_compiled_langgraph():
    graph = build_analysis_graph(_services())

    response = graph.invoke({"request": _request()})["response"]

    assert response.status == "completed"


def test_run_analysis_service_uses_workflow_result():
    from backend.app.workflow.service import run_analysis

    response = run_analysis(_request())

    assert response["status"] == "completed"
    assert response["result"]["jd_requirements"]
    assert response["result"]["evidence_table"]
    assert response["result"]["generated_assets"]["resume_bullets"][0]["evidence_ids"]


def test_run_analysis_service_returns_chinese_generated_content():
    from backend.app.workflow.service import run_analysis

    response = run_analysis(_request())

    assets = response["result"]["generated_assets"]
    report = response["result"]["evaluation_report"]
    generated_texts = [
        assets["match_summary"],
        assets["resume_bullets"][0]["text"],
        assets["cover_letter"]["opening"],
        assets["cover_letter"]["body"][0],
        assets["cover_letter"]["closing"],
        assets["interview_prep"][0]["topic"],
        assets["interview_prep"][0]["why_it_matters"],
        assets["interview_prep"][0]["prep_suggestion"],
        report["risk_summary"],
    ]

    assert all(_contains_chinese(text) for text in generated_texts)


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="doc_resume",
                source_name="resume.md",
                source_type="markdown",
                content="## Projects\n\nBuilt Python API development with Python API services.",
            )
        ],
        job_description="We need Python API experience.",
    )


def _services() -> WorkflowServices:
    return WorkflowServices(
        retrieval_service=RetrievalService(
            embedding_client=FakeEmbeddingClient(),
            vector_store=InMemoryVectorStore(),
        ),
        llm_service=LLMService(client=_StaticLLMClient()),
    )


class _StaticLLMClient:
    def generate(self, prompt_key, prompt, variables):
        responses = {
            "extract_jd_requirements": [
                {
                    "requirement_id": "req_python",
                    "category": "hard_skill",
                    "text": "Python API development",
                    "importance": "high",
                    "keywords": ["Python", "API"],
                }
            ],
            "generate_application_assets": {
                "match_summary": "Strong fit for Python API work.",
                "resume_bullets": [
                    {
                        "text": "Built Python APIs backed by project evidence.",
                        "target_requirement_ids": ["req_python"],
                        "evidence_ids": ["req_python:evidence:1"],
                        "risk_level": "low",
                    }
                ],
                "cover_letter": {
                    "opening": "I am excited to apply.",
                    "body": ["My Python API project aligns with the role."],
                    "closing": "Thank you for your consideration.",
                    "evidence_ids": ["req_python:evidence:1"],
                },
                "interview_prep": [
                    {
                        "topic": "Python API project",
                        "why_it_matters": "The role asks for API development.",
                        "supporting_evidence_ids": ["req_python:evidence:1"],
                        "prep_suggestion": "Prepare a concise project walkthrough.",
                    }
                ],
            },
            "evaluate_claim_grounding": {
                "grounding_warnings": [],
                "coverage_gaps": [],
                "specificity_notes": [],
                "risk_summary": "No major grounding risks found.",
                "overall_status": "pass",
            },
        }
        return json.dumps(responses[prompt_key])

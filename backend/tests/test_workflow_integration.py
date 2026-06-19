import json

from backend.app.api.schemas import AnalysisRequest
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService, OpenAICompatibleChatClient, OpenAIResponsesClient
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import WORKFLOW_NODE_ORDER, build_analysis_graph, run_workflow
from backend.app.workflow.nodes import WorkflowServices
from backend.app.workflow.service import _default_services


def test_workflow_graph_defines_expected_node_order():
    assert WORKFLOW_NODE_ORDER == [
        "parse_inputs",
        "index_profile",
        "jd_analyst",
        "resume_evidence_agent",
        "match_strategist",
        "resume_bullet_agent",
        "interview_prep_agent",
        "risk_auditor_agent",
        "finalize_response",
    ]


def test_sample_profile_and_jd_run_to_final_response():
    response = run_workflow(request=_request(), services=_services())

    assert response.status == "completed"
    assert response.result["jd_requirements"][0]["requirement_id"] == "req_python"
    assert "evidence_table" not in response.result
    assert response.result["match_analysis"][0]["match_level"] == "strong"
    assert response.result["generated_assets"]["resume_bullets"][0]["evidence_ids"]
    assert response.result["evaluation_report"]["overall_status"] in {
        "pass",
        "pass_with_warnings",
        "fail",
    }


def test_run_workflow_cleans_retrieval_collection_after_analysis():
    services = _services()

    response = run_workflow(request=_request(), services=services)

    assert response.status == "completed"
    assert services.retrieval_service.vector_store.items == []


def test_build_analysis_graph_returns_compiled_langgraph():
    graph = build_analysis_graph(_services())

    response = graph.invoke({"request": _request()})["response"]

    assert response.status == "completed"


def test_run_analysis_service_uses_workflow_result():
    from backend.app.workflow.service import run_analysis

    response = run_analysis(_request())

    assert response["status"] == "completed"
    assert response["result"]["jd_requirements"]
    assert "evidence_table" not in response["result"]
    assert response["result"]["generated_assets"]["resume_bullets"][0]["evidence_ids"]


def test_run_analysis_service_returns_chinese_generated_content():
    from backend.app.workflow.service import run_analysis

    response = run_analysis(_request())

    assets = response["result"]["generated_assets"]
    report = response["result"]["evaluation_report"]
    generated_texts = [
        assets["match_summary"],
        assets["resume_bullets"][0]["text"],
        assets["interview_prep"]["jd_questions"][0]["question"],
        assets["interview_prep"]["jd_questions"][0]["sample_answer"],
        assets["interview_prep"]["resume_deep_dive_questions"][0]["question"],
        assets["interview_prep"]["resume_deep_dive_questions"][0]["sample_answer"],
        report["risk_summary"],
    ]

    assert all(_contains_chinese(text) for text in generated_texts)


def test_default_services_use_openai_client_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    request = _request(model="gpt-test", temperature=0.4)

    services = _default_services(request.run_config)

    assert isinstance(services.llm_service.client, OpenAIResponsesClient)
    assert services.llm_service.client.model == "gpt-test"
    assert services.llm_service.client.temperature == 0.4


def test_default_services_use_deepseek_client_from_request_config(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    request = _request(
        model="deepseek-v4-flash",
        temperature=0.5,
        provider="deepseek",
        api_key="user-deepseek-key",
    )

    services = _default_services(request.run_config)

    assert isinstance(services.llm_service.client, OpenAICompatibleChatClient)
    assert services.llm_service.client.api_key == "user-deepseek-key"
    assert services.llm_service.client.model == "deepseek-v4-flash"
    assert services.llm_service.client.base_url == "https://api.deepseek.com"
    assert services.llm_service.client.temperature == 0.5


def test_default_services_keep_deterministic_client_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    services = _default_services(_request().run_config)

    assert services.llm_service.client.__class__.__name__ == "_DeterministicWorkflowLLMClient"


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def _request(
    model: str = "default",
    temperature: float = 0.2,
    provider: str = "local",
    api_key: str | None = None,
) -> AnalysisRequest:
    run_config = {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "top_k": 5,
    }
    if api_key is not None:
        run_config["api_key"] = api_key

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
        run_config=run_config,
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
                        "text": f"Built Python APIs backed by project evidence {index}.",
                        "target_requirement_ids": ["req_python"],
                        "evidence_ids": ["req_python:evidence:1"],
                        "risk_level": "low",
                    }
                    for index in range(1, 4)
                ],
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

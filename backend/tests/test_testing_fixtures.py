from backend.app.api.schemas import GeneratedAssets
from backend.app.documents.chunker import chunk_profile_document
from backend.app.documents.models import ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
from backend.app.workflow.graph import run_workflow
from backend.app.workflow.nodes import WorkflowServices
from backend.tests.fixtures.loaders import (
    load_fake_llm_client,
    load_fake_llm_generated_assets,
    load_sample_jd,
    load_sample_profile,
)


def test_sample_profile_can_be_chunked():
    document = ProfileDocument(
        document_id="fixture_profile",
        source_name="sample_profile.md",
        source_type="markdown",
        content=load_sample_profile(),
    )

    chunks = chunk_profile_document(document)

    assert len(chunks) >= 4
    assert {"Education", "AI Course Project", "Skills", "GitHub Project"}.issubset(
        {chunk.section_label for chunk in chunks}
    )


def test_sample_jd_can_be_parsed_by_fake_llm():
    service = LLMService(client=load_fake_llm_client())

    requirements = service.extract_jd_requirements(load_sample_jd())

    assert [requirement.requirement_id for requirement in requirements] == [
        "req_python_api",
        "req_rag",
        "req_collaboration",
        "req_langgraph",
    ]


def test_fake_generated_assets_match_schema():
    assets = load_fake_llm_generated_assets()

    assert isinstance(assets, GeneratedAssets)
    assert assets.resume_bullets[0].evidence_ids == ["req_python_api:evidence:2"]


def test_complete_workflow_fixture_produces_evidence_bullet_and_evaluation():
    request = _fixture_request()

    response = run_workflow(request=request, services=_fixture_services())

    assert response.status == "completed"
    assert "evidence_table" not in response.result
    assert len(response.result["generated_assets"]["resume_bullets"]) >= 1
    assert "evidence_ids" not in response.result["generated_assets"]["resume_bullets"][0]
    assert response.result["agent_traces"][0]["agent_name"] == "resume_evidence"
    assert response.result["evaluation_report"]["overall_status"] in {
        "pass",
        "pass_with_warnings",
        "fail",
    }


def _fixture_request():
    from backend.app.api.schemas import AnalysisRequest

    return AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="fixture_profile",
                source_name="sample_profile.md",
                source_type="markdown",
                content=load_sample_profile(),
            )
        ],
        job_description=load_sample_jd(),
    )


def _fixture_services() -> WorkflowServices:
    return WorkflowServices(
        retrieval_service=RetrievalService(
            embedding_client=FakeEmbeddingClient(),
            vector_store=InMemoryVectorStore(),
        ),
        llm_service=LLMService(client=load_fake_llm_client()),
    )

import json

from backend.app.api.schemas import AgentToolResult
from backend.app.documents.chunker import chunk_profile_document
from backend.app.documents.models import ProfileDocument
from backend.app.retrieval.service import RetrievalService
from backend.app.workflow.graph import build_analysis_graph
from backend.tests.fixtures.loaders import (
    load_fake_llm_jd_requirements,
    load_sample_profile,
)
from backend.tests.test_testing_fixtures import _fixture_request, _fixture_services


def test_sprint2_profile_fixture_contains_project_internship_skill_and_education():
    chunks = chunk_profile_document(
        ProfileDocument(
            document_id="sprint2_profile",
            source_name="sample_profile.md",
            source_type="markdown",
            content=load_sample_profile(),
        )
    )

    assert {"project", "internship", "skill", "education"}.issubset(
        {chunk.section_type for chunk in chunks}
    )


def test_sprint2_jd_fixture_contains_all_requirement_priorities():
    requirements = load_fake_llm_jd_requirements()

    assert {item.importance for item in requirements} == {"high", "medium", "low"}


def test_fake_bge_and_chroma_fixtures_support_filtered_retrieval(
    fake_bge_embedding_client,
    fake_chroma_vector_store,
):
    service = RetrievalService(
        embedding_client=fake_bge_embedding_client,
        vector_store=fake_chroma_vector_store,
    )
    document = ProfileDocument(
        document_id="sprint2_profile",
        source_name="sample_profile.md",
        source_type="markdown",
        content=load_sample_profile(),
    )
    chunks = chunk_profile_document(document)
    service.index_profile(chunks)

    evidence = service.retrieve_evidence(
        requirements=load_fake_llm_jd_requirements(),
        top_k=5,
        section_filter=["project", "internship"],
    )

    assert evidence
    assert {item.section_type for item in evidence} <= {"project", "internship"}


def test_react_tool_call_fixtures_cover_all_three_agents(react_tool_call_fixtures):
    assert set(react_tool_call_fixtures) == {
        "resume_evidence",
        "interview_prep",
        "risk_auditor",
    }
    for steps in react_tool_call_fixtures.values():
        assert steps
        assert all(isinstance(step, AgentToolResult) for step in steps)


def test_complete_sprint2_workflow_matches_final_product_contract():
    services = _fixture_services()
    graph_result = build_analysis_graph(services).invoke({"request": _fixture_request()})
    response = graph_result["response"]
    state = graph_result["state"]

    assert response.status == "completed"
    assert "cover_letter" not in response.result["generated_assets"]
    assert "evidence_table" not in response.result

    bullets = response.result["generated_assets"]["resume_bullets"]
    assert len(bullets) == 3
    evidence_by_id = {item.evidence_id: item for item in state.retrieved_evidence}
    assert all(
        evidence_by_id[evidence_id].section_type in {"project", "internship"}
        for bullet in bullets
        for evidence_id in bullet["evidence_ids"]
    )

    risks = response.result["risk_report"]["risks"]
    assert len(risks) <= 3
    visible_risks = json.dumps(risks, ensure_ascii=False)
    assert not any(item.requirement_id in visible_risks for item in state.jd_requirements)

    serialized_traces = json.dumps(response.result["agent_traces"], ensure_ascii=False)
    assert serialized_traces
    assert {item["agent_name"] for item in response.result["agent_traces"]} == {
        "resume_evidence",
        "interview_prep",
        "risk_auditor",
    }

import json

from backend.app.api.schemas import AnalysisRequest, EvidenceItem, JDRequirement, RunConfig
from backend.app.documents.models import ProfileChunk, ProfileDocument
from backend.app.llm.client import LLMService
from backend.app.llm.structured_outputs import LLMOutputParseError
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore
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


def test_parse_inputs_generates_analysis_id_for_valid_request():
    state = parse_inputs(_request())

    assert state.analysis_id.startswith("analysis_")
    assert state.profile_documents[0].source_name == "resume.md"
    assert state.job_description == "We need Python API experience."
    assert state.run_config == RunConfig()


def test_index_profile_calls_document_processing_and_retrieval():
    state = parse_inputs(_request())
    services = _services()

    next_state = index_profile(state, services)

    assert next_state.profile_index_id == "profile-index-1"
    assert next_state.profile_chunks[0].source_name == "resume.md"
    assert services.retrieval_service.vector_store.items[0].metadata["chunk_id"]


def test_analyze_jd_retries_llm_parser_error_once():
    client = _SequentialLLMClient(
        {
            "extract_jd_requirements": [
                "{not json",
                json.dumps([_requirement("req_python").model_dump()]),
            ]
        }
    )
    state = parse_inputs(_request())
    services = WorkflowServices(
        retrieval_service=_retrieval_service(),
        llm_service=LLMService(client=client),
    )

    next_state = analyze_jd(state, services)

    assert [item.requirement_id for item in next_state.jd_requirements] == ["req_python"]
    assert client.call_counts["extract_jd_requirements"] == 2


def test_retrieve_evidence_writes_evidence_table():
    services = _services()
    chunk = _chunk("chunk_python", "Built Python FastAPI services.")
    services.retrieval_service.index_profile([chunk])
    state = parse_inputs(_request()).model_copy(
        update={"profile_chunks": [chunk], "jd_requirements": [_requirement("req_python")]}
    )

    next_state = retrieve_evidence(state, services)

    assert next_state.retrieved_evidence[0].chunk_id == "chunk_python"
    assert next_state.retrieved_evidence[0].requirement_id == "req_python"


def test_score_match_writes_match_analysis():
    state = parse_inputs(_request()).model_copy(
        update={
            "jd_requirements": [_requirement("req_python")],
            "retrieved_evidence": [_evidence("ev_python", "req_python", score=0.9)],
        }
    )

    next_state = score_match(state, _services())

    assert next_state.match_analysis[0].match_level == "strong"
    assert next_state.match_analysis[0].evidence_ids == ["ev_python"]
    assert next_state.match_strategy is not None
    assert next_state.match_strategy.covered_requirement_ids == ["req_python"]
    assert next_state.match_strategy.ranked_evidence[0].evidence_id == "ev_python"


def test_write_application_writes_generated_assets():
    state = parse_inputs(_request()).model_copy(
        update={
            "jd_requirements": [_requirement("req_python")],
            "retrieved_evidence": [_evidence("ev_python", "req_python", score=0.9)],
            "match_analysis": [_match("req_python", ["ev_python"])],
        }
    )

    next_state = write_application(state, _services())

    assert next_state.generated_assets is not None
    assert next_state.generated_assets.resume_bullets[0].evidence_ids == ["ev_python"]


def test_evaluate_grounding_writes_evaluation_report():
    state = parse_inputs(_request()).model_copy(
        update={"generated_assets": _generated_assets()}
    )

    next_state = evaluate_grounding(state, _services())

    assert next_state.evaluation_report is not None
    assert next_state.evaluation_report.overall_status in {"pass", "pass_with_warnings", "fail"}


def test_finalize_response_outputs_completed_api_response_result():
    state = parse_inputs(_request()).model_copy(
        update={
            "jd_requirements": [_requirement("req_python")],
            "retrieved_evidence": [_evidence("ev_python", "req_python", score=0.9)],
            "match_analysis": [_match("req_python", ["ev_python"])],
            "generated_assets": _generated_assets(),
        }
    )

    response = finalize_response(state)

    assert response.status == "completed"
    assert response.result["jd_requirements"][0]["requirement_id"] == "req_python"
    assert response.result["match_strategy"] is None
    assert response.result["generated_assets"]["resume_bullets"][0]["evidence_ids"] == [
        "ev_python"
    ]


def test_vector_store_failure_returns_indexing_error_response():
    state = parse_inputs(_request())
    services = WorkflowServices(
        retrieval_service=_FailingRetrievalService(),
        llm_service=_services().llm_service,
    )

    failed_state = index_profile(state, services)
    response = finalize_response(failed_state)

    assert response.status == "failed"
    assert response.error == {
        "code": "VECTOR_STORE_ERROR",
        "message": "Profile materials could not be indexed. Please try again.",
        "details": None,
    }


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        profile_documents=[
            ProfileDocument(
                document_id="doc_resume",
                source_name="resume.md",
                source_type="markdown",
                content="## Projects\n\nBuilt Python FastAPI services.",
            )
        ],
        job_description="We need Python API experience.",
    )


def _services() -> WorkflowServices:
    return WorkflowServices(
        retrieval_service=_retrieval_service(),
        llm_service=LLMService(
            client=_SequentialLLMClient(
                {
                    "extract_jd_requirements": [
                        json.dumps([_requirement("req_python").model_dump()])
                    ],
                    "generate_application_assets": [
                        json.dumps(_generated_assets().model_dump())
                    ],
                    "evaluate_claim_grounding": [
                        json.dumps(
                            {
                                "grounding_warnings": [],
                                "coverage_gaps": [],
                                "specificity_notes": [],
                                "risk_summary": "No major grounding risks found.",
                                "overall_status": "pass",
                            }
                        )
                    ],
                }
            )
        ),
    )


def _retrieval_service() -> RetrievalService:
    return RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )


def _requirement(requirement_id: str) -> JDRequirement:
    return JDRequirement(
        requirement_id=requirement_id,
        category="hard_skill",
        text="Python API development",
        importance="high",
        keywords=["Python", "API"],
    )


def _chunk(chunk_id: str, text: str) -> ProfileChunk:
    return ProfileChunk(
        chunk_id=chunk_id,
        document_id="doc_resume",
        source_name="resume.md",
        section_label="Projects",
        text=text,
    )


def _evidence(evidence_id: str, requirement_id: str, score: float) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        chunk_id="chunk_python",
        source_name="resume.md",
        section_label="Projects",
        snippet="Built Python FastAPI services.",
        score=score,
    )


def _match(requirement_id: str, evidence_ids: list[str]):
    from backend.app.api.schemas import MatchItem

    return MatchItem(
        requirement_id=requirement_id,
        match_level="strong",
        rationale="High-scoring evidence directly supports this requirement.",
        evidence_ids=evidence_ids,
        gap_note=None,
    )


def _generated_assets():
    from backend.app.api.schemas import (
        GeneratedAssets,
        InterviewPrepItem,
        ResumeBullet,
    )

    return GeneratedAssets(
        match_summary="Strong fit for Python API work.",
        resume_bullets=[
            ResumeBullet(
                text=f"Built Python APIs backed by project evidence {index}.",
                target_requirement_ids=["req_python"],
                evidence_ids=["ev_python"],
                risk_level="low",
            )
            for index in range(1, 4)
        ],
        interview_prep=[
            InterviewPrepItem(
                topic="Python API project",
                why_it_matters="The role asks for API development.",
                supporting_evidence_ids=["ev_python"],
                prep_suggestion="Prepare a concise project walkthrough.",
            )
        ],
    )


class _SequentialLLMClient:
    def __init__(self, responses: dict[str, list[str]]) -> None:
        self.responses = {key: list(value) for key, value in responses.items()}
        self.call_counts = {key: 0 for key in responses}

    def generate(self, prompt_key, prompt, variables):
        self.call_counts[prompt_key] += 1
        responses = self.responses[prompt_key]
        index = min(self.call_counts[prompt_key] - 1, len(responses) - 1)
        return responses[index]


class _FailingRetrievalService:
    def index_profile(self, chunks):
        raise RuntimeError("vector store unavailable")

    def retrieve_evidence(self, requirements, top_k):
        raise AssertionError("retrieve_evidence should not run after indexing failure")

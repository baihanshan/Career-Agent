from backend.app.api.schemas import JDRequirement
from backend.app.documents.models import ProfileChunk
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import InMemoryVectorStore


def test_fake_embedding_returns_stable_vectors_for_same_text():
    client = FakeEmbeddingClient()

    assert client.embed("Python FastAPI") == client.embed("Python FastAPI")


def test_index_profile_returns_index_id():
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )

    index_id = service.index_profile([_chunk("chunk_1", "Built Python APIs.")])

    assert index_id == "profile-index-1"


def test_indexed_metadata_includes_chunk_source_and_section_label():
    vector_store = InMemoryVectorStore()
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=vector_store,
    )
    chunk = _chunk("chunk_1", "Built Python APIs.", section_label="Projects")

    service.index_profile([chunk])

    stored = vector_store.items[0]
    assert stored.metadata["chunk_id"] == "chunk_1"
    assert stored.metadata["source_name"] == "resume.md"
    assert stored.metadata["section_label"] == "Projects"


def test_retrieve_evidence_returns_evidence_items_for_matching_requirements():
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )
    service.index_profile(
        [
            _chunk("chunk_python", "Built Python FastAPI services.", section_label="Projects"),
            _chunk("chunk_design", "Led product design workshops.", section_label="Experience"),
        ]
    )

    evidence = service.retrieve_evidence(
        [
            JDRequirement(
                requirement_id="req_python",
                category="hard_skill",
                text="Python API development",
                importance="high",
                keywords=["Python", "API"],
            )
        ],
        top_k=2,
    )

    assert len(evidence) == 1
    assert evidence[0].requirement_id == "req_python"
    assert evidence[0].chunk_id == "chunk_python"
    assert evidence[0].source_name == "resume.md"
    assert evidence[0].section_label == "Projects"
    assert evidence[0].snippet == "Built Python FastAPI services."
    assert 0 < evidence[0].score <= 1


def test_retrieve_evidence_returns_empty_list_when_nothing_matches():
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )
    service.index_profile([_chunk("chunk_design", "Led product design workshops.")])

    evidence = service.retrieve_evidence(
        [
            JDRequirement(
                requirement_id="req_python",
                category="hard_skill",
                text="Python API development",
                importance="high",
                keywords=["Python", "API"],
            )
        ],
        top_k=3,
    )

    assert evidence == []


def test_top_k_limits_evidence_per_requirement():
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )
    service.index_profile(
        [
            _chunk("chunk_1", "Python API service one."),
            _chunk("chunk_2", "Python API service two."),
            _chunk("chunk_3", "Python API service three."),
        ]
    )

    evidence = service.retrieve_evidence(
        [
            JDRequirement(
                requirement_id="req_python",
                category="hard_skill",
                text="Python API development",
                importance="high",
                keywords=["Python", "API"],
            )
        ],
        top_k=2,
    )

    assert [item.chunk_id for item in evidence] == ["chunk_1", "chunk_2"]


def _chunk(chunk_id: str, text: str, section_label: str | None = None) -> ProfileChunk:
    return ProfileChunk(
        chunk_id=chunk_id,
        document_id="doc_1",
        source_name="resume.md",
        section_label=section_label,
        text=text,
    )

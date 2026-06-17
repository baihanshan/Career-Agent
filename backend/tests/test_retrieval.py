from backend.app.api.schemas import JDRequirement
from backend.app.documents.models import ProfileChunk
from backend.app.retrieval.embeddings import BGEEmbeddingClient, FakeEmbeddingClient
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.vector_store import ChromaVectorStore, InMemoryVectorStore
from backend.app.workflow import service as workflow_service


def test_fake_embedding_returns_stable_vectors_for_same_text():
    client = FakeEmbeddingClient()

    assert client.embed("Python FastAPI") == client.embed("Python FastAPI")


def test_bge_embedding_client_mock_mode_returns_fixed_dimension_vector():
    client = BGEEmbeddingClient(mock_dimension=4)

    vector = client.embed("Python FastAPI")

    assert len(vector) == 4
    assert vector == client.embed("Python FastAPI")


def test_bge_embedding_client_reads_model_environment(monkeypatch):
    monkeypatch.setenv("BGE_MODEL_NAME", "test-bge")
    monkeypatch.setenv("BGE_MODEL_CACHE_DIR", "/tmp/test-bge-cache")

    client = BGEEmbeddingClient(mock_dimension=2)

    assert client.model_name == "test-bge"
    assert client.cache_dir == "/tmp/test-bge-cache"


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
    chunk = _chunk(
        "chunk_1",
        "Built Python APIs.",
        section_label="Projects",
        section_type="project",
        section_title="Projects",
        project_name="CareerPilot",
        technologies=["Python", "FastAPI"],
    )

    service.index_profile([chunk])

    stored = vector_store.items[0]
    assert stored.metadata["chunk_id"] == "chunk_1"
    assert stored.metadata["source_name"] == "resume.md"
    assert stored.metadata["section_label"] == "Projects"
    assert stored.metadata["section_type"] == "project"
    assert stored.metadata["section_title"] == "Projects"
    assert stored.metadata["project_name"] == "CareerPilot"
    assert stored.metadata["technologies"] == "Python, FastAPI"


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
    assert evidence[0].section_type == "project"
    assert evidence[0].snippet == "Built Python FastAPI services."
    assert 0 < evidence[0].score <= 1


def test_retrieve_evidence_can_filter_by_section_type():
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=InMemoryVectorStore(),
    )
    service.index_profile(
        [
            _chunk("chunk_project", "Python API project.", section_type="project"),
            _chunk("chunk_skill", "Python API skill list.", section_type="skill"),
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
        top_k=5,
        section_filter=["project"],
    )

    assert [item.chunk_id for item in evidence] == ["chunk_project"]


def test_chroma_vector_store_add_query_and_delete_collection():
    client = _FakeChromaClient()
    store = ChromaVectorStore(client=client, collection_name="analysis_test")

    store.add(
        item_id="chunk_1",
        text="Built Python APIs.",
        embedding=[1.0, 0.0],
        metadata={"chunk_id": "chunk_1", "source_name": "resume.md", "section_type": "project"},
    )

    results = store.search(query_embedding=[1.0, 0.0], top_k=1)

    assert results[0].item.item_id == "chunk_1"
    assert results[0].score == 1.0

    store.delete_collection()

    assert "analysis_test" not in client.collections


def test_chroma_vector_store_collections_do_not_pollute_each_other():
    client = _FakeChromaClient()
    left = ChromaVectorStore(client=client, collection_name="analysis_left")
    right = ChromaVectorStore(client=client, collection_name="analysis_right")

    left.add(
        item_id="left_chunk",
        text="Left Python project.",
        embedding=[1.0, 0.0],
        metadata={"chunk_id": "left_chunk", "source_name": "left.md"},
    )
    right.add(
        item_id="right_chunk",
        text="Right design project.",
        embedding=[0.0, 1.0],
        metadata={"chunk_id": "right_chunk", "source_name": "right.md"},
    )

    assert [result.item.item_id for result in left.search([1.0, 0.0], top_k=5)] == ["left_chunk"]
    assert [result.item.item_id for result in right.search([1.0, 0.0], top_k=5)] == []


def test_default_retrieval_service_uses_analysis_collection_name(monkeypatch):
    created_collection_names = []

    class _MockBGEEmbeddingClient:
        def embed(self, text):
            return [1.0, 0.0]

    class _MockChromaVectorStore(InMemoryVectorStore):
        def __init__(self, collection_name, persist_path):
            super().__init__()
            created_collection_names.append(collection_name)
            self.persist_path = persist_path

    monkeypatch.delenv("RETRIEVAL_BACKEND", raising=False)
    monkeypatch.setenv("CHROMA_PATH", "/tmp/chroma")
    monkeypatch.setattr(workflow_service, "BGEEmbeddingClient", _MockBGEEmbeddingClient)
    monkeypatch.setattr(workflow_service, "ChromaVectorStore", _MockChromaVectorStore)

    service = workflow_service._default_retrieval_service()

    assert isinstance(service, RetrievalService)
    assert created_collection_names[0].startswith("analysis_")


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


def _chunk(
    chunk_id: str,
    text: str,
    section_label: str | None = None,
    section_type: str = "project",
    section_title: str | None = None,
    project_name: str | None = None,
    technologies: list[str] | None = None,
) -> ProfileChunk:
    return ProfileChunk(
        chunk_id=chunk_id,
        document_id="doc_1",
        source_name="resume.md",
        section_label=section_label,
        section_type=section_type,
        section_title=section_title,
        project_name=project_name,
        technologies=technologies or [],
        text=text,
    )


class _FakeChromaClient:
    def __init__(self):
        self.collections = {}

    def get_or_create_collection(self, name):
        collection = self.collections.get(name)
        if collection is None:
            collection = _FakeChromaCollection()
            self.collections[name] = collection
        return collection

    def delete_collection(self, name):
        self.collections.pop(name, None)


class _FakeChromaCollection:
    def __init__(self):
        self.items = []

    def add(self, ids, documents, embeddings, metadatas):
        for item_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self.items.append(
                {
                    "id": item_id,
                    "document": document,
                    "embedding": embedding,
                    "metadata": metadata,
                }
            )

    def query(self, query_embeddings, n_results, where=None):
        query_embedding = query_embeddings[0]
        scored_items = [
            (item, _dot(query_embedding, item["embedding"]))
            for item in self.items
            if _matches_where(item["metadata"], where)
        ]
        scored_items = [
            (item, score)
            for item, score in sorted(scored_items, key=lambda pair: pair[1], reverse=True)
            if score > 0
        ][:n_results]
        return {
            "ids": [[item["id"] for item, _score in scored_items]],
            "documents": [[item["document"] for item, _score in scored_items]],
            "metadatas": [[item["metadata"] for item, _score in scored_items]],
            "distances": [[1 - score for _item, score in scored_items]],
        }


def _dot(left, right):
    return round(sum(left_value * right_value for left_value, right_value in zip(left, right)), 6)


def _matches_where(metadata, where):
    if not where:
        return True
    for key, value in where.items():
        if isinstance(value, dict) and "$in" in value:
            if metadata.get(key) not in value["$in"]:
                return False
        elif metadata.get(key) != value:
            return False
    return True

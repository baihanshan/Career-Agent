import pytest

from backend.app.retrieval.embeddings import BGEEmbeddingClient
from backend.app.retrieval.vector_store import EphemeralVectorStore
from backend.tests.fixtures.loaders import load_react_tool_call_fixtures


@pytest.fixture
def fake_bge_embedding_client():
    return BGEEmbeddingClient(mock_dimension=16, device="cpu")


@pytest.fixture
def fake_chroma_vector_store():
    return EphemeralVectorStore()


@pytest.fixture
def react_tool_call_fixtures():
    return load_react_tool_call_fixtures()

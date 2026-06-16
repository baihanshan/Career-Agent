from __future__ import annotations

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.documents.models import ProfileChunk
from backend.app.retrieval.embeddings import FakeEmbeddingClient
from backend.app.retrieval.vector_store import InMemoryVectorStore


class RetrievalService:
    def __init__(
        self,
        embedding_client: FakeEmbeddingClient,
        vector_store: InMemoryVectorStore,
    ) -> None:
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self._index_count = 0

    def index_profile(self, chunks: list[ProfileChunk]) -> str:
        self._index_count += 1
        index_id = f"profile-index-{self._index_count}"
        for chunk in chunks:
            self.vector_store.add(
                item_id=chunk.chunk_id,
                text=chunk.text,
                embedding=self.embedding_client.embed(chunk.text),
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "source_name": chunk.source_name,
                    "section_label": chunk.section_label,
                },
            )
        return index_id

    def retrieve_evidence(
        self,
        requirements: list[JDRequirement],
        top_k: int,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for requirement in requirements:
            query = _requirement_query(requirement)
            query_embedding = self.embedding_client.embed(query)
            for result_index, result in enumerate(
                self.vector_store.search(query_embedding=query_embedding, top_k=top_k),
                start=1,
            ):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"{requirement.requirement_id}:evidence:{result_index}",
                        requirement_id=requirement.requirement_id,
                        chunk_id=str(result.item.metadata["chunk_id"]),
                        source_name=str(result.item.metadata["source_name"]),
                        section_label=result.item.metadata["section_label"],
                        snippet=result.item.text,
                        score=round(result.score, 6),
                    )
                )
        return evidence


def _requirement_query(requirement: JDRequirement) -> str:
    return " ".join([requirement.text, *requirement.keywords]).strip()

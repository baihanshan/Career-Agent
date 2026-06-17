from __future__ import annotations

from backend.app.api.schemas import EvidenceItem, JDRequirement
from backend.app.documents.models import ProfileChunk
from backend.app.retrieval.embeddings import BGEEmbeddingClient, FakeEmbeddingClient
from backend.app.retrieval.vector_store import InMemoryVectorStore


class RetrievalService:
    def __init__(
        self,
        embedding_client: FakeEmbeddingClient | BGEEmbeddingClient,
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
                    "section_type": chunk.section_type,
                    "section_title": chunk.section_title,
                    "company_name": chunk.company_name,
                    "role_title": chunk.role_title,
                    "project_name": chunk.project_name,
                    "technologies": ", ".join(chunk.technologies),
                },
            )
        return index_id

    def retrieve_evidence(
        self,
        requirements: list[JDRequirement],
        top_k: int,
        section_filter: list[str] | None = None,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for requirement in requirements:
            query = _requirement_query(requirement)
            query_embedding = self.embedding_client.embed(query)
            for result_index, result in enumerate(
                self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    section_filter=section_filter,
                ),
                start=1,
            ):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"{requirement.requirement_id}:evidence:{result_index}",
                        requirement_id=requirement.requirement_id,
                        chunk_id=str(result.item.metadata["chunk_id"]),
                        source_name=str(result.item.metadata["source_name"]),
                        section_label=result.item.metadata["section_label"],
                        section_type=str(result.item.metadata.get("section_type") or "other"),
                        snippet=result.item.text,
                        score=round(result.score, 6),
                    )
                )
        return evidence

    def cleanup(self) -> None:
        delete_collection = getattr(self.vector_store, "delete_collection", None)
        if callable(delete_collection):
            delete_collection()


def _requirement_query(requirement: JDRequirement) -> str:
    return " ".join([requirement.text, *requirement.keywords]).strip()

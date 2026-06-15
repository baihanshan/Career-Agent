from __future__ import annotations

from dataclasses import dataclass

from backend.app.retrieval.embeddings import cosine_similarity


@dataclass(frozen=True)
class VectorStoreItem:
    item_id: str
    text: str
    embedding: dict[str, float]
    metadata: dict[str, str | None]


@dataclass(frozen=True)
class VectorSearchResult:
    item: VectorStoreItem
    score: float


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.items: list[VectorStoreItem] = []

    def add(
        self,
        item_id: str,
        text: str,
        embedding: dict[str, float],
        metadata: dict[str, str | None],
    ) -> None:
        self.items.append(
            VectorStoreItem(
                item_id=item_id,
                text=text,
                embedding=embedding,
                metadata=metadata,
            )
        )

    def search(self, query_embedding: dict[str, float], top_k: int) -> list[VectorSearchResult]:
        results = [
            VectorSearchResult(item=item, score=cosine_similarity(query_embedding, item.embedding))
            for item in self.items
        ]
        matching_results = [result for result in results if result.score > 0]
        return sorted(matching_results, key=lambda result: result.score, reverse=True)[:top_k]

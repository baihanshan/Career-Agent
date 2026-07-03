from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from backend.app.retrieval.embeddings import cosine_similarity, vector_cosine_similarity


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

    def search(
        self,
        query_embedding: dict[str, float],
        top_k: int,
        section_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        results = [
            VectorSearchResult(item=item, score=cosine_similarity(query_embedding, item.embedding))
            for item in self.items
            if _matches_section_filter(item.metadata, section_filter)
        ]
        matching_results = [result for result in results if result.score > 0]
        return sorted(matching_results, key=lambda result: result.score, reverse=True)[:top_k]

    def delete_collection(self) -> None:
        self.items.clear()


class ChromaVectorStore:
    def __init__(
        self,
        collection_name: str,
        persist_path: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.client = client or _create_chroma_client(persist_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add(
        self,
        item_id: str,
        text: str,
        embedding: Sequence[float],
        metadata: dict[str, str | None],
    ) -> None:
        self.collection.add(
            ids=[item_id],
            documents=[text],
            embeddings=[[float(value) for value in embedding]],
            metadatas=[_clean_metadata(metadata)],
        )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int,
        section_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        query = {
            "query_embeddings": [[float(value) for value in query_embedding]],
            "n_results": top_k,
        }
        if section_filter:
            query["where"] = {"section_type": {"$in": section_filter}}

        raw_results = self.collection.query(**query)
        ids = _first_result_list(raw_results, "ids")
        documents = _first_result_list(raw_results, "documents")
        metadatas = _first_result_list(raw_results, "metadatas")
        distances = _first_result_list(raw_results, "distances")

        results: list[VectorSearchResult] = []
        for index, item_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            text = documents[index] if index < len(documents) else ""
            distance = distances[index] if index < len(distances) else 1.0
            score = _score_from_chroma_distance(distance)
            item = VectorStoreItem(
                item_id=item_id,
                text=text,
                embedding={},
                metadata=metadata,
            )
            if score > 0:
                results.append(VectorSearchResult(item=item, score=score))
        return results

    def delete_collection(self) -> None:
        self.client.delete_collection(name=self.collection_name)


class EphemeralVectorStore:
    """Small list-backed vector store for testing Chroma-like behavior without chromadb."""

    def __init__(self) -> None:
        self.items: list[VectorStoreItem] = []

    def add(
        self,
        item_id: str,
        text: str,
        embedding: Sequence[float],
        metadata: dict[str, str | None],
    ) -> None:
        self.items.append(
            VectorStoreItem(
                item_id=item_id,
                text=text,
                embedding={str(index): float(value) for index, value in enumerate(embedding)},
                metadata=metadata,
            )
        )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int,
        section_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        query_values = list(query_embedding)
        results = []
        for item in self.items:
            if not _matches_section_filter(item.metadata, section_filter):
                continue
            item_values = [item.embedding[str(index)] for index in range(len(item.embedding))]
            score = vector_cosine_similarity(query_values, item_values)
            if score > 0:
                results.append(VectorSearchResult(item=item, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def delete_collection(self) -> None:
        self.items.clear()


def _create_chroma_client(persist_path: str | None):
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "chromadb is required for ChromaVectorStore. Install requirements-dev.txt "
            "or use InMemoryVectorStore/EphemeralVectorStore for tests."
        ) from exc
    return chromadb.PersistentClient(path=persist_path) if persist_path else chromadb.Client()


def _clean_metadata(metadata: dict[str, str | None]) -> dict[str, str]:
    return {key: value for key, value in metadata.items() if value is not None}


def _first_result_list(raw_results: dict[str, Any], key: str) -> list[Any]:
    values = raw_results.get(key) or [[]]
    return values[0] if values else []


def _score_from_chroma_distance(distance: float) -> float:
    return max(0.0, min(1.0, round(1 - float(distance), 6)))


def _matches_section_filter(
    metadata: dict[str, str | None],
    section_filter: list[str] | None,
) -> bool:
    if not section_filter:
        return True
    return metadata.get("section_type") in section_filter

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from math import sqrt
from typing import Sequence


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_BGE_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
DEFAULT_BGE_MODEL_CACHE_DIR = "/Users/baihanshan/Desktop/bge-models"


class FakeEmbeddingClient:
    """Deterministic token-count embeddings for tests and local MVP behavior."""

    def embed(self, text: str) -> dict[str, float]:
        counts = Counter(_tokenize(text))
        magnitude = sqrt(sum(value * value for value in counts.values()))
        if magnitude == 0:
            return {}
        return {token: count / magnitude for token, count in sorted(counts.items())}


class BGEEmbeddingClient:
    """Sentence-transformers backed BGE embeddings with a deterministic mock mode for tests."""

    def __init__(
        self,
        model_name: str | None = None,
        cache_dir: str | None = None,
        device: str | None = None,
        mock_dimension: int | None = None,
    ) -> None:
        self.model_name = model_name or os.getenv("BGE_MODEL_NAME", DEFAULT_BGE_MODEL_NAME)
        self.cache_dir = cache_dir or os.getenv(
            "BGE_MODEL_CACHE_DIR",
            DEFAULT_BGE_MODEL_CACHE_DIR,
        )
        self.device = device or _select_device()
        self.mock_dimension = mock_dimension
        self._model = None

    def embed(self, text: str) -> list[float]:
        if self.mock_dimension is not None:
            return _mock_embedding(text, self.mock_dimension)

        model = self._load_model()
        vector = model.encode(text, normalize_embeddings=True)
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        return [float(value) for value in vector]

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for BGE embeddings. "
                    "Install requirements-dev.txt or use the fake embedding path for tests."
                ) from exc

            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=self.cache_dir,
                device=self.device,
            )
        return self._model


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared_tokens = left.keys() & right.keys()
    return sum(left[token] * right[token] for token in shared_tokens)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def vector_cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_magnitude = sqrt(sum(value * value for value in left))
    right_magnitude = sqrt(sum(value * value for value in right))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0
    return dot / (left_magnitude * right_magnitude)


def _select_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"

    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _mock_embedding(text: str, dimension: int) -> list[float]:
    if dimension < 1:
        raise ValueError("mock_dimension must be greater than zero.")
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw_values = [digest[index % len(digest)] / 255 for index in range(dimension)]
    magnitude = sqrt(sum(value * value for value in raw_values))
    if magnitude == 0:
        return [0.0 for _index in range(dimension)]
    return [round(value / magnitude, 6) for value in raw_values]

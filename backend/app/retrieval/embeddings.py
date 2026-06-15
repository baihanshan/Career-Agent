from __future__ import annotations

import re
from collections import Counter
from math import sqrt


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class FakeEmbeddingClient:
    """Deterministic token-count embeddings for tests and local MVP behavior."""

    def embed(self, text: str) -> dict[str, float]:
        counts = Counter(_tokenize(text))
        magnitude = sqrt(sum(value * value for value in counts.values()))
        if magnitude == 0:
            return {}
        return {token: count / magnitude for token, count in sorted(counts.items())}


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared_tokens = left.keys() & right.keys()
    return sum(left[token] * right[token] for token in shared_tokens)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())

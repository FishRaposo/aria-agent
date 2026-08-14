"""Deterministic, dependency-free hashed-vector memory search."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryMatch:
    record_id: str
    content: str
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "content": self.content,
            "score": self.score,
        }


class LocalVectorIndex:
    def __init__(self, *, dimensions: int = 128) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions
        self._records: dict[str, str] = {}

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def add(self, record_id: str, content: str) -> None:
        self._records[record_id] = content

    def search(self, query: str, *, limit: int = 5) -> list[MemoryMatch]:
        query_vector = self._vector(query)
        scored = []
        for record_id, content in self._records.items():
            vector = self._vector(content)
            score = sum(a * b for a, b in zip(query_vector, vector, strict=True))
            scored.append(MemoryMatch(record_id, content, round(score, 6)))
        scored.sort(key=lambda item: (-item.score, item.record_id))
        return scored[: max(0, limit)]

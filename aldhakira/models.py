from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    id: int
    source: str
    title: str
    text: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "text": self.text,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        return cls(
            id=int(data["id"]),
            source=str(data.get("source") or ""),
            title=str(data.get("title") or ""),
            text=str(data.get("text") or ""),
            token_count=int(data.get("token_count") or 0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    matched_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = self.chunk.to_dict()
        data["score"] = round(self.score, 6)
        data["matched_terms"] = self.matched_terms
        return data


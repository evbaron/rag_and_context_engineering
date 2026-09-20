"""Retriever-only base: ranking helpers and a retrieval interface (no LLM calls)."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

RetrieverKind = Literal["bm25", "vector", "hybrid"]

# Defaults only. Override per experiment via RetrieverSpec / constructor args.
DEFAULT_TOP_K = 4
DEFAULT_CANDIDATE_POOL = 10
DEFAULT_WEIGHT_BM25 = 0.5
DEFAULT_WEIGHT_VECTOR = 0.5

_STOPWORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "so", "yet", "for",
    "in", "on", "at", "to", "of", "by", "with", "from", "into", "onto", "upon",
    "about", "above", "below", "between", "through", "during", "before", "after",
    "under", "over", "around", "along", "across", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "i", "we", "you", "he", "she", "it", "they", "me", "us", "him", "her", "them",
    "my", "our", "your", "his", "its", "their", "this", "that", "these", "those",
    "as", "if", "up", "out", "not", "no",
}


class ArticleCandidate(BaseModel):
    """An article discovered during retrieval but not yet accepted as evidence."""

    source_article: str = Field(min_length=1)
    representative_chunk: str | None = None

    retrieval_query: str = Field(min_length=1)
    discovered_by: Literal["vector", "graph"]

    rank: int = Field(ge=1)
    raw_score: float
    score_semantics: Literal[
        "higher_is_better",
        "lower_is_better",
        "rank_only",
        "unknown",
    ]

    # Used later when graph expansion discovers this article.
    seed_articles: list[str] = Field(default_factory=list)
    discovery_reasons: list[str] = Field(default_factory=list)


@dataclass
class RetrieverSpec:
    """One experiment: which retriever to run and with which knobs."""
    kind: RetrieverKind
    label: str
    top_k: int = DEFAULT_TOP_K
    candidate_pool: int = DEFAULT_CANDIDATE_POOL
    weight_bm25: float = DEFAULT_WEIGHT_BM25
    weight_vector: float = DEFAULT_WEIGHT_VECTOR
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {"bm25", "vector", "hybrid"}:
            raise ValueError("kind must be 'bm25', 'vector', or 'hybrid'.")
        if not self.label.strip():
            raise ValueError("label cannot be empty.")
        if self.top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if self.candidate_pool < 1:
            raise ValueError("candidate_pool must be at least 1.")
        if self.kind == "hybrid":
            if self.candidate_pool < self.top_k:
                raise ValueError("Hybrid candidate_pool must be greater than or equal to top_k.")
            if self.weight_bm25 < 0 or self.weight_vector < 0:
                raise ValueError("Hybrid weights cannot be negative.")
            if self.weight_bm25 + self.weight_vector == 0:
                raise ValueError("At least one hybrid weight must be greater than zero.")

    def as_dict(self) -> dict[str, Any]:
        settings = {
            "kind": self.kind,
            "label": self.label,
            "top_k": self.top_k,
        }
        if self.kind == "hybrid":
            settings.update(
                {
                    "candidate_pool": self.candidate_pool,
                    "weight_bm25": self.weight_bm25,
                    "weight_vector": self.weight_vector,
                }
            )
        settings.update(self.extra)
        return settings


def tokenize(text: str) -> list[str]:
    """Lowercase, split into alphanumeric tokens, drop stopwords (Lab 1.2)."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS]


def normalize_scores(scores: list[float], invert: bool = False) -> list[float]:
    """Min-max scale to [0, 1]. invert=True flips Chroma distance (lower = better)."""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [0.5] * len(scores)
    norm = [(s - lo) / (hi - lo) for s in scores]
    return [1.0 - n for n in norm] if invert else norm


class BaseRetriever(ABC):
    def __init__(self, top_k: int = DEFAULT_TOP_K, label: str | None = None):
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        self.top_k = top_k
        self.label = label or self.__class__.__name__

    @abstractmethod
    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        """Return (doc_id, content, score) for the top-k hits."""

    def retrievedContext(self, query: str, k: int | None = None) -> str:
        return self.format_context(self.getTopK(query, k))

    @staticmethod
    def format_context(results: list[tuple[str, str, float]]) -> str:
        """Format already-retrieved hits without running retrieval again."""
        return "\n\n---\n\n".join(f"[{name}]\n{content}" for name, content, _ in results)

    def settings(self) -> dict[str, Any]:
        return {"kind": self.label, "label": self.label, "top_k": self.top_k}

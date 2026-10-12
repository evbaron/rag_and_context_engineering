"""Hybrid retrieval: keyword and vector search combined. (Checkpoint 2)

Keyword search finds exact terms; vector search finds paraphrases. Hybrid asks both for
a pool of candidates, rescales each list's scores to 0..1 (best = 1), and adds them with
weights. A passage that both methods rank highly comes out on top.
"""

from __future__ import annotations

from typing import Any

from ragkit.retrievers.base import BaseRetriever, Hit, normalize


class HybridRetriever(BaseRetriever):
    name = "hybrid"

    def __init__(
        self,
        keyword: BaseRetriever,
        semantic: BaseRetriever,
        weight_keyword: float = 0.5,
        pool: int = 20,
    ):
        super().__init__()
        if not 0.0 <= weight_keyword <= 1.0:
            raise ValueError("weight_keyword must be between 0 and 1.")
        self.keyword = keyword
        self.semantic = semantic
        self.weight_keyword = weight_keyword
        self.pool = pool  # candidates asked from each retriever before combining

    def settings(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "keyword": self.keyword.name,
            "semantic": self.semantic.name,
            "weight_keyword": self.weight_keyword,
            "pool": self.pool,
        }

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        pool = max(self.pool, k)
        keyword_hits = normalize(self.keyword.retrieve(query, pool))
        semantic_hits = normalize(self.semantic.retrieve(query, pool))
        self.calls += self.keyword.take_calls() + self.semantic.take_calls()

        combined: dict[str, Hit] = {}
        for hits, weight in ((keyword_hits, self.weight_keyword), (semantic_hits, 1 - self.weight_keyword)):
            for hit in hits:
                if hit.doc.id in combined:
                    combined[hit.doc.id].score += weight * hit.score
                else:
                    combined[hit.doc.id] = Hit(hit.doc, weight * hit.score)
        return sorted(combined.values(), key=lambda hit: hit.score, reverse=True)[:k]

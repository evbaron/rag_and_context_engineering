"""BM25 keyword retrieval over Wikipedia (Lab 1.2, adapted from .txt emails)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from .base import DEFAULT_TOP_K, BaseRetriever, tokenize
from .corpus import WikiChunk, load_wikipedia_chunks


class Bm25Retriever(BaseRetriever):
    def __init__(
        self,
        wiki_dir: str | Path | None = None,
        chunks: list[WikiChunk] | None = None,
        top_k: int = DEFAULT_TOP_K,
        label: str | None = None,
    ):
        super().__init__(top_k=top_k, label=label or "bm25")
        self._chunks = chunks if chunks is not None else load_wikipedia_chunks(wiki_dir)
        if not self._chunks:
            raise ValueError("No Wikipedia chunks to index for BM25.")
        self._ids = [c.doc_id for c in self._chunks]
        self._contents = [c.text for c in self._chunks]
        self._bm25 = BM25Okapi([tokenize(text) for text in self._contents])
        n_articles = len({c.source for c in self._chunks})
        print(f"BM25 indexed {len(self._chunks)} chunks from {n_articles} Wikipedia articles.")

    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        k = self.top_k if k is None else k
        scores = self._bm25.get_scores(tokenize(query))
        top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self._ids[i], self._contents[i], float(scores[i])) for i in top if scores[i] > 0]

    def settings(self) -> dict[str, Any]:
        return {"kind": "bm25", "label": self.label, "top_k": self.top_k}

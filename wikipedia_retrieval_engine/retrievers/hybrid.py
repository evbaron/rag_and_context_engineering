"""Hybrid BM25 + vector retrieval over Wikipedia (Lab 2.2 fusion)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma

from .base import (
    DEFAULT_CANDIDATE_POOL,
    DEFAULT_TOP_K,
    DEFAULT_WEIGHT_BM25,
    DEFAULT_WEIGHT_VECTOR,
    BaseRetriever,
    normalize_scores,
)
from .bm25 import Bm25Retriever
from .corpus import DEFAULT_CHROMA_DB_NAME, WikiChunk, load_wikipedia_chunks
from .vector import VectorRetriever


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        wiki_dir: str | Path | None = None,
        db: Chroma | None = None,
        chunks: list[WikiChunk] | None = None,
        chroma_db_name: str = DEFAULT_CHROMA_DB_NAME,
        bm25_retriever: Bm25Retriever | None = None,
        vector_retriever: VectorRetriever | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int = DEFAULT_CANDIDATE_POOL,
        weight_bm25: float = DEFAULT_WEIGHT_BM25,
        weight_vector: float = DEFAULT_WEIGHT_VECTOR,
        label: str | None = None,
    ):
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if candidate_pool < top_k:
            raise ValueError("candidate_pool must be greater than or equal to top_k.")
        if weight_bm25 < 0 or weight_vector < 0:
            raise ValueError("Hybrid weights cannot be negative.")
        total_weight = weight_bm25 + weight_vector
        if total_weight == 0:
            raise ValueError("At least one hybrid weight must be greater than zero.")
        super().__init__(top_k=top_k, label=label or "hybrid")

        # Hybrid owns only fusion. Keyword and vector ranking stay in their classes.
        shared_chunks = chunks
        if bm25_retriever is None and shared_chunks is None:
            shared_chunks = load_wikipedia_chunks(wiki_dir)
        self.bm25_retriever = bm25_retriever or Bm25Retriever(
            wiki_dir=wiki_dir,
            chunks=shared_chunks,
            top_k=candidate_pool,
            label=f"{self.label}_bm25",
        )
        self.vector_retriever = vector_retriever or VectorRetriever(
            db=db,
            wiki_dir=wiki_dir,
            chroma_db_name=chroma_db_name,
            chunks=shared_chunks,
            top_k=candidate_pool,
            label=f"{self.label}_vector",
        )
        self.candidate_pool = candidate_pool
        self.chroma_db_name = chroma_db_name
        # Normalize weights so 7/3 and 0.7/0.3 describe the same experiment.
        self.weight_bm25 = weight_bm25 / total_weight
        self.weight_vector = weight_vector / total_weight
        print(
            "Hybrid retriever ready "
            f"[bm25={self.weight_bm25}, vector={self.weight_vector}, "
            f"pool={candidate_pool}, k={top_k}]."
        )

    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        """Fuse BM25 (higher-is-better) with inverted Chroma distance (Lab 2.2)."""
        k = self.top_k if k is None else k
        bm = self.bm25_retriever.getTopK(query, self.candidate_pool)
        vec = self.vector_retriever.getTopK(query, self.candidate_pool)

        content_by_name: dict[str, str] = {}
        bm_norm: dict[str, float] = {}
        vec_norm: dict[str, float] = {}

        if bm:
            for (name, content, _), val in zip(bm, normalize_scores([s for _, _, s in bm])):
                content_by_name[name] = content
                bm_norm[name] = val
        if vec:
            for (name, content, _), val in zip(
                vec, normalize_scores([d for _, _, d in vec], invert=True)
            ):
                content_by_name[name] = content
                vec_norm[name] = val

        fused = [
            (
                name,
                content,
                self.weight_bm25 * bm_norm.get(name, 0.0)
                + self.weight_vector * vec_norm.get(name, 0.0),
            )
            for name, content in content_by_name.items()
        ]
        fused.sort(key=lambda t: t[2], reverse=True)
        return fused[:k]

    def settings(self) -> dict[str, Any]:
        return {
            "kind": "hybrid",
            "label": self.label,
            "top_k": self.top_k,
            "candidate_pool": self.candidate_pool,
            "chroma_db_name": self.chroma_db_name,
            "weight_bm25": self.weight_bm25,
            "weight_vector": self.weight_vector,
        }

"""Wikipedia retrievers adapted from Labs 1.2, 2.1, and 2.2.

    from retrievers import RetrieverSpec, make_retriever
    from retrievers.llm import answer, make_llm

    spec = RetrieverSpec(kind="hybrid", label="hybrid_70_30", weight_bm25=0.7, weight_vector=0.3)
    retriever = make_retriever(spec)
    hits = retriever.getTopK("Where were the 1972 Winter Olympics held?")
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from langchain_chroma import Chroma

from .base import (
    DEFAULT_CANDIDATE_POOL,
    DEFAULT_TOP_K,
    DEFAULT_WEIGHT_BM25,
    DEFAULT_WEIGHT_VECTOR,
    ArticleCandidate,
    BaseRetriever,
    RetrieverKind,
    RetrieverSpec,
)
from .bm25 import Bm25Retriever
from .corpus import (
    DEFAULT_CHROMA_DB_NAME,
    DEFAULT_CHROMA_DB_ROOT,
    DEFAULT_CHROMA_DIR,
    DEFAULT_ARTICLE_TEXT_NAME,
    DEFAULT_ARTICLE_TEXT_ROOT,
    DEFAULT_WIKI_DIR,
    ArticleText,
    ArticleTextStore,
    WikiChunk,
    article_text_store_path,
    build_or_load_article_text_store,
    load_wikipedia_chunks,
    load_wikipedia_section_chunks,
)
from .hybrid import HybridRetriever
from .evidence import EvidenceLogger, format_articles, format_chunks
from .expansion import (
    article_name_from_doc_id,
    format_full_articles_context,
    load_retrieved_article_texts,
    retrieved_article_names,
)
from .vector import VectorRetriever, build_or_load_db, chroma_db_path


def make_retriever(
    spec: RetrieverSpec | RetrieverKind,
    *,
    wiki_dir: str | Path | None = None,
    chroma_db_name: str = DEFAULT_CHROMA_DB_NAME,
    chunks: list[WikiChunk] | None = None,
    db: Chroma | None = None,
    top_k: int | None = None,
    candidate_pool: int | None = None,
    weight_bm25: float | None = None,
    weight_vector: float | None = None,
    label: str | None = None,
) -> BaseRetriever:
    """Build a BM25, vector, or hybrid retriever. Pass a RetrieverSpec or a kind string.

    Shared ``chunks`` / ``db`` avoid reloading Wikipedia and Chroma for each experiment.
    """
    if isinstance(spec, str):
        spec = RetrieverSpec(
            kind=spec,
            label=label or spec,
            top_k=top_k if top_k is not None else DEFAULT_TOP_K,
            candidate_pool=candidate_pool if candidate_pool is not None else DEFAULT_CANDIDATE_POOL,
            weight_bm25=weight_bm25 if weight_bm25 is not None else DEFAULT_WEIGHT_BM25,
            weight_vector=weight_vector if weight_vector is not None else DEFAULT_WEIGHT_VECTOR,
        )
    else:
        # Do not mutate the caller's experiment definition when applying overrides.
        spec = replace(
            spec,
            top_k=top_k if top_k is not None else spec.top_k,
            candidate_pool=(
                candidate_pool if candidate_pool is not None else spec.candidate_pool
            ),
            weight_bm25=(weight_bm25 if weight_bm25 is not None else spec.weight_bm25),
            weight_vector=(
                weight_vector if weight_vector is not None else spec.weight_vector
            ),
            label=label if label is not None else spec.label,
        )

    if spec.kind == "bm25":
        return Bm25Retriever(
            wiki_dir=wiki_dir, chunks=chunks, top_k=spec.top_k, label=spec.label
        )
    if spec.kind == "vector":
        return VectorRetriever(
            db=db,
            wiki_dir=wiki_dir,
            chroma_db_name=chroma_db_name,
            chunks=chunks,
            top_k=spec.top_k,
            label=spec.label,
        )
    if spec.kind == "hybrid":
        bm25_retriever = Bm25Retriever(
            wiki_dir=wiki_dir,
            chunks=chunks,
            top_k=spec.candidate_pool,
            label=f"{spec.label}_bm25",
        )
        vector_retriever = VectorRetriever(
            db=db,
            wiki_dir=wiki_dir,
            chroma_db_name=chroma_db_name,
            chunks=chunks,
            top_k=spec.candidate_pool,
            label=f"{spec.label}_vector",
        )
        return HybridRetriever(
            bm25_retriever=bm25_retriever,
            vector_retriever=vector_retriever,
            top_k=spec.top_k,
            candidate_pool=spec.candidate_pool,
            weight_bm25=spec.weight_bm25,
            weight_vector=spec.weight_vector,
            label=spec.label,
        )
    raise ValueError(f"Unknown retriever kind {spec.kind!r}; use 'bm25', 'vector', or 'hybrid'.")


__all__ = [
    "BaseRetriever",
    "ArticleCandidate",
    "Bm25Retriever",
    "VectorRetriever",
    "HybridRetriever",
    "EvidenceLogger",
    "RetrieverKind",
    "RetrieverSpec",
    "WikiChunk",
    "ArticleText",
    "ArticleTextStore",
    "DEFAULT_WIKI_DIR",
    "DEFAULT_CHROMA_DIR",
    "DEFAULT_ARTICLE_TEXT_ROOT",
    "DEFAULT_ARTICLE_TEXT_NAME",
    "DEFAULT_CHROMA_DB_ROOT",
    "DEFAULT_CHROMA_DB_NAME",
    "DEFAULT_TOP_K",
    "DEFAULT_CANDIDATE_POOL",
    "DEFAULT_WEIGHT_BM25",
    "DEFAULT_WEIGHT_VECTOR",
    "build_or_load_db",
    "chroma_db_path",
    "load_wikipedia_chunks",
    "load_wikipedia_section_chunks",
    "article_text_store_path",
    "build_or_load_article_text_store",
    "make_retriever",
    "format_articles",
    "format_chunks",
    "article_name_from_doc_id",
    "format_full_articles_context",
    "load_retrieved_article_texts",
    "retrieved_article_names",
]

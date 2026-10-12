"""Opening the passages and building a retriever by name. (Checkpoint 2)

    documents, index_name = open_documents()           # the passages to search
    retriever = make_retriever("hybrid", documents, index_name)

Keyword and vector search must search the same passages. When a vector index exists,
the passages are rebuilt exactly the way the index recorded (same folder, passage size,
and file limit), so every retriever, and later the evaluation, sees the same corpus.
"""

from __future__ import annotations

from typing import Any

from ragkit import config
from ragkit.corpus import DEFAULT_CHUNK_SIZE, DEFAULT_OVERLAP, Document, load_corpus
from ragkit.retrievers.base import BaseRetriever
from ragkit.retrievers.bm25 import Bm25Retriever
from ragkit.retrievers.hybrid import HybridRetriever
from ragkit.retrievers.vector import VectorRetriever

KINDS = ("bm25", "vector", "hybrid")


def corpus_settings(
    chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP, limit: int | None = None
) -> dict[str, Any]:
    """How to read the corpus, in the form a vector index records it."""
    return {
        "scenario": config.scenario(),
        "folder": str(config.corpus_dir()),
        "chunk_size": chunk_size,
        "overlap": overlap,
        "limit": limit,
    }


def default_index_name(chunk_size: int = DEFAULT_CHUNK_SIZE, limit: int | None = None) -> str:
    return f"{config.scenario()}_c{chunk_size}_{limit or 'all'}"


def open_documents(index_name: str | None = None, limit: int | None = None) -> tuple[list[Document], str | None]:
    """The passages to search, and the vector index built from them (None if there is none yet).

    Without ``index_name``, the newest index for the current scenario is used.
    """
    if index_name is None:
        indexes = VectorRetriever.list_indexes(config.scenario())
        index_name = indexes[0]["name"] if indexes else None
    if index_name is None:
        return load_corpus(limit=limit), None
    info = VectorRetriever.info(index_name)
    if info is None:
        raise config.SetupError(
            f"There is no finished vector index named '{index_name}'. "
            "Build one with: python samples/cp2_build_index.py"
        )
    corpus = info["corpus"]
    documents = load_corpus(
        corpus["scenario"], corpus["folder"], chunk_size=corpus["chunk_size"], overlap=corpus["overlap"], limit=corpus["limit"]
    )
    return documents, index_name


def make_retriever(
    kind: str,
    documents: list[Document],
    index_name: str | None = None,
    *,
    weight_keyword: float = 0.5,
    pool: int = 20,
) -> BaseRetriever:
    """'bm25', 'vector', or 'hybrid' over ``documents`` (vector and hybrid need an index)."""
    if kind not in KINDS:
        raise ValueError(f"Unknown retriever '{kind}'; use one of: {', '.join(KINDS)}.")
    if kind == "bm25":
        return Bm25Retriever(documents)
    if index_name is None:
        raise config.SetupError(
            f"The '{kind}' retriever needs a vector index. Build one first: python samples/cp2_build_index.py"
        )
    vector = VectorRetriever(index_name)
    if kind == "vector":
        return vector
    return HybridRetriever(Bm25Retriever(documents), vector, weight_keyword=weight_keyword, pool=pool)

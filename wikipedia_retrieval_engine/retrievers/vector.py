"""Chroma vector retrieval over Wikipedia (Lab 2.1, adapted from .txt emails)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .base import DEFAULT_TOP_K, BaseRetriever
from .corpus import (
    DEFAULT_CHROMA_DB_NAME,
    DEFAULT_CHROMA_DB_ROOT,
    WikiChunk,
    load_wikipedia_chunks,
)
from .llm import get_embeddings

_EMBED_BATCH = 64
_VALID_DB_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def chroma_db_path(chroma_db_name: str = DEFAULT_CHROMA_DB_NAME) -> Path:
    """Return ``retrievers/db/<name>`` after validating the directory name."""
    if not _VALID_DB_NAME.fullmatch(chroma_db_name) or chroma_db_name in {".", ".."}:
        raise ValueError(
            "chroma_db_name must contain only letters, numbers, '.', '_', or '-', "
            "must start with a letter or number, and cannot be a path."
        )
    return DEFAULT_CHROMA_DB_ROOT / chroma_db_name


def build_or_load_db(
    wiki_dir: str | Path | None = None,
    chroma_db_name: str = DEFAULT_CHROMA_DB_NAME,
    chunks: list[WikiChunk] | None = None,
) -> Chroma:
    """Load the persisted Chroma DB if it exists; otherwise embed Wikipedia chunks."""
    chroma_path = chroma_db_path(chroma_db_name)
    if chroma_path.is_dir() and any(chroma_path.iterdir()):
        print(f"Loading existing vector DB from {chroma_path}/")
        return Chroma(persist_directory=str(chroma_path), embedding_function=get_embeddings())

    if chunks is None:
        print("Loading Wikipedia articles to build the vector DB...")
        chunks = load_wikipedia_chunks(wiki_dir)
    if not chunks:
        raise ValueError("No Wikipedia chunks to embed.")

    chroma_path.mkdir(parents=True, exist_ok=True)
    print(f"Building vector DB (first run — embedding {len(chunks)} chunks)...")
    embeddings = get_embeddings()
    db = Chroma(persist_directory=str(chroma_path), embedding_function=embeddings)
    for start in range(0, len(chunks), _EMBED_BATCH):
        batch = chunks[start : start + _EMBED_BATCH]
        docs = [
            Document(
                page_content=c.text,
                metadata={"source": c.doc_id, "title": c.title, "article": c.source},
            )
            for c in batch
        ]
        db.add_documents(docs)
        done = min(start + _EMBED_BATCH, len(chunks))
        print(f"  embedded {done}/{len(chunks)}")
    print(f"  Indexed {len(chunks)} chunks into {chroma_path}/")
    return db


class VectorRetriever(BaseRetriever):
    def __init__(
        self,
        db: Chroma | None = None,
        wiki_dir: str | Path | None = None,
        chroma_db_name: str = DEFAULT_CHROMA_DB_NAME,
        chunks: list[WikiChunk] | None = None,
        top_k: int = DEFAULT_TOP_K,
        label: str | None = None,
    ):
        super().__init__(top_k=top_k, label=label or "vector")
        self.chroma_db_name = chroma_db_name
        self._db = (
            db
            if db is not None
            else build_or_load_db(
                wiki_dir=wiki_dir,
                chroma_db_name=chroma_db_name,
                chunks=chunks,
            )
        )

    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        k = self.top_k if k is None else k
        results = self._db.similarity_search_with_score(query, k=k)
        return [
            (doc.metadata.get("source", "unknown"), doc.page_content, float(score))
            for doc, score in results
        ]

    def settings(self) -> dict[str, Any]:
        return {
            "kind": "vector",
            "label": self.label,
            "top_k": self.top_k,
            "chroma_db_name": self.chroma_db_name,
        }

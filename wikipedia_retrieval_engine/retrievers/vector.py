"""Chroma vector retrieval over Wikipedia (Lab 2.1, adapted from .txt emails)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .base import DEFAULT_TOP_K, ArticleCandidate, BaseRetriever
from .corpus import (
    DEFAULT_CHROMA_DB_NAME,
    DEFAULT_CHROMA_DB_ROOT,
    DEFAULT_SECTION_CHROMA_DB_NAME,
    DEFAULT_SECTION_MAX_CHARS,
    DEFAULT_SECTION_OVERLAP,
    WikiChunk,
    load_wikipedia_chunks,
    load_wikipedia_section_chunks,
)
from .llm import get_embeddings

_EMBED_BATCH = 64
_ARTICLE_CANDIDATE_MULTIPLIER = 4
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
                metadata={
                    "source": c.doc_id,
                    "title": c.title,
                    "article": c.source,
                    "section_title": c.section_title,
                    "section_path": " > ".join(c.section_path),
                },
            )
            for c in batch
        ]
        db.add_documents(docs)
        done = min(start + _EMBED_BATCH, len(chunks))
        print(f"  embedded {done}/{len(chunks)}")
    print(f"  Indexed {len(chunks)} chunks into {chroma_path}/")
    return db


def build_or_load_section_db(
    wiki_dir: str | Path | None = None,
    chroma_db_name: str = DEFAULT_SECTION_CHROMA_DB_NAME,
    *,
    max_section_chars: int = DEFAULT_SECTION_MAX_CHARS,
    overlap: int = DEFAULT_SECTION_OVERLAP,
) -> Chroma:
    """Load the section-aware index or build it from heading-based chunks.

    This wrapper prevents a missing section index from silently falling back to
    the character-based ``load_wikipedia_chunks`` strategy used by the baseline.
    """

    chroma_path = chroma_db_path(chroma_db_name)
    if chroma_path.is_dir() and any(chroma_path.iterdir()):
        return build_or_load_db(chroma_db_name=chroma_db_name)

    chunks = load_wikipedia_section_chunks(
        wiki_dir,
        max_section_chars=max_section_chars,
        overlap=overlap,
    )
    return build_or_load_db(
        wiki_dir=wiki_dir,
        chroma_db_name=chroma_db_name,
        chunks=chunks,
    )


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

    @classmethod
    def for_section_index(
        cls,
        wiki_dir: str | Path | None = None,
        chroma_db_name: str = DEFAULT_SECTION_CHROMA_DB_NAME,
        *,
        max_section_chars: int = DEFAULT_SECTION_MAX_CHARS,
        overlap: int = DEFAULT_SECTION_OVERLAP,
        top_k: int = DEFAULT_TOP_K,
        label: str | None = None,
    ) -> VectorRetriever:
        """Construct a retriever backed by the section-aware Checkpoint 5.1 index."""

        db = build_or_load_section_db(
            wiki_dir=wiki_dir,
            chroma_db_name=chroma_db_name,
            max_section_chars=max_section_chars,
            overlap=overlap,
        )
        return cls(
            db=db,
            chroma_db_name=chroma_db_name,
            top_k=top_k,
            label=label or "section_vector",
        )

    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        k = self.top_k if k is None else k
        results = self._db.similarity_search_with_score(query, k=k)
        return [
            (doc.metadata.get("source", "unknown"), doc.page_content, float(score))
            for doc, score in results
        ]

    def getArticlesTopK(
        self,
        query: str,
        k: int = 3,
        *,
        fetch_k: int | None = None,
    ) -> list[ArticleCandidate]:
        """Return the top-k unique articles as structured candidates.

        Chroma ranks chunks, so ``getTopK(query, 3)`` can return three chunks from
        one article. This method searches a larger chunk candidate pool and groups
        the ranked results by article. Each ``ArticleCandidate`` retains the best
        matching chunk, query, unique-article rank, and raw Chroma distance. Chroma
        distances are lower-is-better.

        ``fetch_k`` controls how many chunks are considered and defaults to four
        times the requested article count. The method can return fewer than ``k``
        articles when the candidate pool contains fewer unique article IDs. Increase
        ``fetch_k`` when long articles dominate the nearest chunk results.
        """

        if k < 1:
            raise ValueError("k must be at least 1.")
        chunk_candidates = (
            max(k, k * _ARTICLE_CANDIDATE_MULTIPLIER)
            if fetch_k is None
            else fetch_k
        )
        if chunk_candidates < k:
            raise ValueError("fetch_k must be greater than or equal to k.")

        results = self._db.similarity_search_with_score(
            query,
            k=chunk_candidates,
        )
        ranked_results = sorted(results, key=lambda item: float(item[1]))

        article_hits: list[ArticleCandidate] = []
        seen_articles: set[str] = set()
        for document, score in ranked_results:
            metadata = document.metadata
            article = str(metadata.get("article") or "").strip()
            if not article:
                source = str(metadata.get("source") or "unknown")
                article = source.split("#", 1)[0]
            if article in seen_articles:
                continue
            raw_section_path = metadata.get("section_path", "")
            if isinstance(raw_section_path, (list, tuple)):
                section_path = [
                    str(part).strip()
                    for part in raw_section_path
                    if str(part).strip()
                ]
            else:
                section_path = [
                    part.strip()
                    for part in str(raw_section_path).split(">")
                    if part.strip()
                ]
            seen_articles.add(article)
            article_hits.append(
                ArticleCandidate(
                    source_article=article,
                    representative_chunk=document.page_content,
                    representative_chunk_id=(
                        str(metadata.get("source")).strip()
                        if metadata.get("source")
                        else None
                    ),
                    section_title=(
                        str(metadata.get("section_title")).strip()
                        if metadata.get("section_title")
                        else (section_path[-1] if section_path else None)
                    ),
                    section_path=section_path,
                    retrieval_query=query,
                    discovered_by="vector",
                    rank=len(article_hits) + 1,
                    raw_score=float(score),
                    score_semantics="lower_is_better",
                )
            )
            if len(article_hits) == k:
                break
        return article_hits

    def getArticleSectionsTopK(
        self,
        query: str,
        source_article: str,
        k: int = 3,
    ) -> list[tuple[Document, float]]:
        """Return query-relevant chunks from one selected article.

        The initial search chooses articles. This second, metadata-filtered
        search chooses the useful sections inside each selected article, which
        avoids sending an entire article or an arbitrary character prefix to
        downstream nodes.
        """

        if not query.strip():
            raise ValueError("query must not be empty.")
        if not source_article.strip():
            raise ValueError("source_article must not be empty.")
        if k < 1:
            raise ValueError("k must be at least 1.")

        results = self._db.similarity_search_with_score(
            query,
            k=k,
            filter={"article": source_article},
        )
        return [
            (document, float(score))
            for document, score in results
        ]

    def settings(self) -> dict[str, Any]:
        return {
            "kind": "vector",
            "label": self.label,
            "top_k": self.top_k,
            "chroma_db_name": self.chroma_db_name,
        }

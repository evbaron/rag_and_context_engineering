"""Human-readable experiment logs for comparing retrieval configurations."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseRetriever
from .corpus import (
    ArticleText,
    ArticleTextStore,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_WIKI_DIR,
    WikiChunk,
)
from .llm import EMBEDDING_MODEL, LLM_MODEL, SYSTEM_PROMPT, TEMPERATURE
from .vector import chroma_db_path

Hit = tuple[str, str, float]


def _slug(value: object) -> str:
    text = str(value).strip().lower().replace(".", "p")
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    return text.strip("-") or "unnamed"


def _number_slug(value: float) -> str:
    """Format a compact filename number: 70.0 → 70, 33.333 → 33p333."""
    return _slug(f"{value:g}")


def _article_name(doc_id: str) -> str:
    """Convert ``article.html#chunk`` into ``article.html``."""
    return doc_id.split("#", 1)[0]


def format_articles(hits: list[Hit]) -> str:
    """List unique retrieved articles in first-hit rank order."""
    articles: list[tuple[str, int, list[int]]] = []
    positions: dict[str, int] = {}
    for chunk_rank, (doc_id, _, _) in enumerate(hits, 1):
        article = _article_name(doc_id)
        if article not in positions:
            positions[article] = len(articles)
            articles.append((article, chunk_rank, [chunk_rank]))
        else:
            articles[positions[article]][2].append(chunk_rank)
    if not articles:
        return "  (no articles retrieved)"
    return "\n".join(
        f"  {article_rank}. {article} "
        f"(first chunk rank={first_rank}; chunk ranks={chunk_ranks})"
        for article_rank, (article, first_rank, chunk_ranks) in enumerate(articles, 1)
    )


def format_chunks(hits: list[Hit], snippet_chars: int = 600) -> str:
    if not hits:
        return "  (no chunks retrieved)"
    lines: list[str] = []
    for rank, (doc_id, text, score) in enumerate(hits, 1):
        snippet = " ".join(text.split())[:snippet_chars]
        lines.append(f"  {rank}. {doc_id}  score={score:.6f}\n     {snippet}")
    return "\n".join(lines)


def format_full_articles(
    articles: list[ArticleText], snippet_chars: int = 600
) -> str:
    if not articles:
        return "  (no full articles)"
    lines: list[str] = []
    for number, article in enumerate(articles, 1):
        snippet = " ".join(article.text.split())[:snippet_chars]
        lines.append(
            f"  {number}. {article.source}\n"
            f"     text_file={article.path}\n"
            f"     characters={len(article.text)}\n"
            f"     preview={snippet}"
        )
    return "\n".join(lines)


class EvidenceLogger:
    """One append-only evidence file for one retriever configuration."""

    def __init__(
        self,
        *,
        log_dir: str | Path,
        run_id: str,
        retriever: BaseRetriever,
        chunks: list[WikiChunk],
        question_count: int,
        chroma_db_name: str,
        chunking_strategy: str = "character_windows",
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        wiki_dir: str | Path = DEFAULT_WIKI_DIR,
        snippet_chars: int = 600,
        context_strategy: str = "retrieved_chunks",
        article_text_store: ArticleTextStore | None = None,
    ) -> None:
        self.retriever = retriever
        self.snippet_chars = snippet_chars
        settings = retriever.settings()
        kind = settings["kind"]
        retriever_part = f"{kind}-k{settings['top_k']}"
        if kind == "hybrid":
            bm_percent = _number_slug(round(settings["weight_bm25"] * 100, 3))
            vector_percent = _number_slug(round(settings["weight_vector"] * 100, 3))
            retriever_part += (
                f"-p{settings['candidate_pool']}"
                f"-bm{bm_percent}-vec{vector_percent}"
            )
        if kind == "bm25":
            index_part = (
                f"sections-max{chunk_size}-o{chunk_overlap}"
                if chunking_strategy == "article_headers"
                else f"chars{chunk_size}-o{chunk_overlap}"
            )
        else:
            index_part = f"index-{_slug(chroma_db_name)}"
        context_part = (
            "" if context_strategy == "retrieved_chunks" else f"__ctx-{_slug(context_strategy)}"
        )

        log_root = Path(log_dir)
        filename_stem = f"{run_id}__{retriever_part}__{index_part}{context_part}"
        self.path = log_root / f"{filename_stem}.log"
        collision_number = 2
        while self.path.exists():
            self.path = log_root / f"{filename_stem}__{collision_number}.log"
            collision_number += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        article_count = len({chunk.source for chunk in chunks})
        score_direction = {
            "bm25": "higher is better (raw BM25 score)",
            "vector": "lower is better (Chroma distance)",
            "hybrid": "higher is better (normalized fused score)",
        }[kind]
        chunking_configuration: dict[str, Any] = {
            "strategy": chunking_strategy,
            "overlap_characters_for_oversized_chunks": chunk_overlap,
        }
        if chunking_strategy == "article_headers":
            chunking_configuration["maximum_section_chunk_characters"] = chunk_size
        else:
            chunking_configuration["chunk_size_characters"] = chunk_size
            chunking_configuration["chunk_overlap_characters"] = chunk_overlap

        configuration: dict[str, Any] = {
            "run_id": run_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "retriever": settings,
            "score_interpretation": score_direction,
            "corpus_directory": str(Path(wiki_dir).resolve()),
            "article_count": article_count,
            "chunk_count": len(chunks),
            "chunking": chunking_configuration,
            "chroma": {
                "database_name": chroma_db_name if kind != "bm25" else None,
                "directory": (
                    str(chroma_db_path(chroma_db_name)) if kind != "bm25" else None
                ),
                "embedding_model": EMBEDDING_MODEL if kind != "bm25" else None,
            },
            "llm": {
                "model": LLM_MODEL,
                "temperature": TEMPERATURE,
                "system_prompt": SYSTEM_PROMPT,
            },
            "question_count": question_count,
            "context_strategy": context_strategy,
            "article_text_store": (
                {
                    "directory": str(article_text_store.root),
                    "article_count": len(article_text_store),
                    "format": "one complete non-overlapping UTF-8 text file per article",
                }
                if article_text_store is not None
                else None
            ),
            "logged_chunk_snippet_characters": snippet_chars,
        }
        header = (
            "RETRIEVAL EXPERIMENT CONFIGURATION\n"
            + "=" * 80
            + "\n"
            + json.dumps(configuration, indent=2, ensure_ascii=False)
            + "\n"
            + "=" * 80
            + "\n\n"
        )
        self.path.write_text(header, encoding="utf-8")

    def log_question(
        self,
        *,
        number: int,
        query: str,
        hits: list[Hit],
        answer: str,
        full_articles: list[ArticleText] | None = None,
    ) -> None:
        expanded_section = ""
        if full_articles is not None:
            expanded_chars = sum(len(article.text) for article in full_articles)
            expanded_section = (
                "FULL ARTICLE TEXTS SENT TO LLM:\n"
                f"  articles={[article.source for article in full_articles]}\n"
                f"  article_count={len(full_articles)}\n"
                f"  text_characters={expanded_chars}\n"
                f"{format_full_articles(full_articles, self.snippet_chars)}\n\n"
            )
        entry = (
            f"QUESTION {number}\n"
            f"{'-' * 80}\n"
            f"QUERY:\n{query}\n\n"
            f"RETRIEVED ARTICLES (unique; ranked by first matching chunk):\n"
            f"{format_articles(hits)}\n\n"
            f"RETRIEVED CHUNKS:\n{format_chunks(hits, self.snippet_chars)}\n\n"
            f"{expanded_section}"
            f"GROUNDED ANSWER:\n{answer}\n"
            f"{'=' * 80}\n\n"
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(entry)

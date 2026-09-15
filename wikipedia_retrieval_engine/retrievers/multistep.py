"""Chroma vector retrieval over Wikipedia (Lab 2.1, adapted from .txt emails)."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from .base import DEFAULT_TOP_K, BaseRetriever, normalize_scores
from .corpus import (
    DEFAULT_CHROMA_DB_NAME,
    DEFAULT_CHROMA_DB_ROOT,
    WikiChunk,
    load_wikipedia_chunks,
)
from .llm import decompose_query, get_embeddings

_EMBED_BATCH = 64
_VALID_DB_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


_SYSTEM_PROMPT = """
You are a helpful assistant that decomposes a query into a list of sub-queries to assist with a vector search retrieval of correct articles.
Produce 2–4 sub-queries, one per distinct entity / sub-topic / article the question needs. IMPORTANT: Do not rephrase the same sub-query.
The sub-queries should be:
- specific to original query
- provide terminology that would assist with vector search retrieval of correct articles
- list specific terms and topics of interest to the original query

In addition to sub-queries, analyze the original query and provide detailed instructions for the reasoning model to use once article retrieved.
These instructions should be steps needed to answer the original query. 
Subqueries will be used for vector search retrival only, the reasoning instructions will be sent along with the original query to the reasoning model to synthesize the answer.
Return Original Query, Sub-queries, and Reasoning instructions in a structured format with each item on a new line.

Example:

Original Query: "List the best picture and best actor Oscar winners for the last 10 years. Are there best actor/best picture matches where the best actor won staring for the best picture?"
Sub-queries: ["Academy Award/Oscar best picture winner starting with year 2016 to 2026", "Best Actor Academy Award/Oscar winner starting with year 2016 to 2026"]
Reasoning instructions: "List the best picture and best actor for each year since 2016. Keep track of the best actor movie they won for. Flag any best actor/best picture matches where the best actor won staring for the best picture."

"""


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


def _parse_decomposition(text: str, fallback_query: str) -> tuple[list[str], str]:
    """Pull the sub-queries list and reasoning instructions out of the LLM's free-text
    decomposition. Degrades to [fallback_query] if the sub-queries can't be parsed, so
    retrieval still runs (as plain single-query search) instead of crashing."""
    sub_queries: list[str] = []
    match = re.search(r"Sub-?queries\s*:\s*(\[.*?\])", text, re.I | re.S)
    if match:
        try:
            sub_queries = [str(s).strip() for s in json.loads(match.group(1)) if str(s).strip()]
        except (json.JSONDecodeError, ValueError):
            pass
    reason = re.search(r"Reasoning instructions\s*:\s*(.+)", text, re.I | re.S)
    reasoning = reason.group(1).strip().strip('"') if reason else ""
    return (sub_queries or [fallback_query]), reasoning


class MultiStepRetriever(BaseRetriever):
    def __init__(
        self, 
        llm: ChatOpenAI | None = None,
        db: Chroma | None = None,
        wiki_dir: str | Path | None = None,
        chroma_db_name: str = DEFAULT_CHROMA_DB_NAME,
        chunks: list[WikiChunk] | None = None,
        top_k: int = DEFAULT_TOP_K,
        label: str | None = None,
    ):
        super().__init__(top_k=top_k, label=label or "vector")
        self.llm = llm
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

    def retrieve_with_reasoning(
        self, query: str, k: int | None = None
    ) -> tuple[list[tuple[str, str, float]], str]:
        """Decompose the query, run each sub-query's vector search in parallel, and merge.

        Returns ``(hits, reasoning_instructions)`` so a caller gets both atomically — no
        shared state, safe under concurrent evaluation. ``getTopK`` wraps this and drops
        the reasoning to satisfy the BaseRetriever contract.
        """
        k = self.top_k if k is None else k

        # Step 1: decompose into sub-queries (+ reasoning instructions for the answer step)
        raw = decompose_query(query, _SYSTEM_PROMPT, query, self.llm)
        sub_queries, reasoning = _parse_decomposition(raw, query)
        print(f"Sub-queries: {sub_queries}")

        # Step 2: run vector search for each sub-query IN PARALLEL (embedding calls are I/O-bound)
        pool = max(3 * k, k)  # wider candidate pool per sub-query, merged down to k below
        with ThreadPoolExecutor(max_workers=min(8, len(sub_queries))) as executor:
            per_subquery = list(
                executor.map(
                    lambda sub_query: self._db.similarity_search_with_score(sub_query, k=pool),
                    sub_queries,
                )
            )

        # Step 3: merge. Chroma returns DISTANCE (lower = better), so invert to a [0,1]
        # similarity first; summing similarities lets a chunk found by several sub-queries
        # rank higher. Then take the global top-k.
        summed: dict[str, float] = {}
        content: dict[str, str] = {}
        for results in per_subquery:
            similarities = normalize_scores([distance for _, distance in results], invert=True)
            for (doc, _), similarity in zip(results, similarities):
                source = doc.metadata.get("source", "unknown")
                summed[source] = summed.get(source, 0.0) + similarity
                content[source] = doc.page_content
        ranked = sorted(summed.items(), key=lambda kv: kv[1], reverse=True)[:k]
        hits = [(source, content[source], score) for source, score in ranked]
        return hits, reasoning

    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        """BaseRetriever contract: hits only. Use retrieve_with_reasoning to also get
        the reasoning instructions."""
        hits, _ = self.retrieve_with_reasoning(query, k)
        return hits

    def settings(self) -> dict[str, Any]:
        return {
            "kind": "vector_multistep",
            "label": self.label,
            "top_k": self.top_k,
            "chroma_db_name": self.chroma_db_name,
        }

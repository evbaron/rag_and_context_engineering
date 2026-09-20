"""Deterministic helpers for the Checkpoint 5.1 table-reader branch."""

from __future__ import annotations

from pathlib import Path
import re

from wikipedia_retrieval_engine.utils.wiki_table_store import (
    TableArtifactStore,
    TableCatalogEntry,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import TableRequest


def resolve_source_article(
    source_article: str,
    table_store: TableArtifactStore,
) -> str:
    """Resolve a model-supplied article label to one stored article filename.

    The assessor is instructed to preserve the exact source filename, but this
    small normalization boundary also accepts harmless variations such as spaces
    instead of underscores or an omitted ``.html`` suffix. Ambiguous or unknown
    labels are rejected rather than guessed.
    """

    supplied = Path(source_article.strip()).name
    if table_store.has_article(supplied):
        return supplied

    normalized = _article_key(supplied)
    matches = [
        article
        for article in table_store.list_articles()
        if _article_key(article) == normalized
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"No table artifact exists for article: {source_article}")
    raise ValueError(
        f"Article label {source_article!r} is ambiguous in the table store: {matches}"
    )


def find_table_candidates(
    request: TableRequest,
    table_store: TableArtifactStore,
    *,
    limit: int = 3,
) -> list[TableCatalogEntry]:
    """Return the best catalog entries for one structured table request.

    Explicit table IDs are treated as authoritative. Otherwise the immutable
    artifact is ranked using catalog metadata and normalized row text. Row text
    is necessary for Wikipedia layout tables that have no caption and only
    generic column names such as ``column_1``.
    """

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    source_article = resolve_source_article(request.source_article, table_store)
    article_tables = table_store.list_tables(source_article)

    if request.table_id:
        matches = [
            entry
            for entry in article_tables
            if entry.table_id == request.table_id
            or entry.artifact_id == request.table_id
        ]
        if not matches:
            raise KeyError(
                f"Table {request.table_id!r} is not present in {source_article}"
            )
        return matches[:limit]

    expected_caption = (request.expected_caption or "").strip().casefold()
    if expected_caption:
        caption_matches = [
            entry
            for entry in article_tables
            if (entry.caption or "").strip().casefold() == expected_caption
            or any(
                section.strip().casefold() == expected_caption
                for section in entry.section_path
            )
        ]
        if caption_matches:
            return caption_matches[:limit]

    query_parts = [
        request.missing_fact,
        request.expected_caption or "",
        *request.columns_needed,
        *request.row_filters.keys(),
        *request.row_filters.values(),
        request.comparison_key or "",
    ]
    query = " ".join(part.strip() for part in query_parts if part.strip())
    query_tokens = _search_tokens(query)
    normalized_by_id = {
        table.table_id: table
        for table in table_store.load_article(source_article)
        if table.table_role != "legend"
    }

    filter_values = [
        " ".join(value.casefold().split())
        for value in request.row_filters.values()
        if value.strip()
    ]
    ranked: list[tuple[int, int, int, int, TableCatalogEntry]] = []
    for position, entry in enumerate(article_tables):
        metadata_text = " ".join(
            [
                entry.caption or "",
                *entry.section_path,
                *entry.columns,
                *entry.legend_meanings,
            ]
        )
        metadata_overlap = len(query_tokens & _search_tokens(metadata_text))

        table = normalized_by_id.get(entry.table_id)
        row_overlap = 0
        filter_matches = 0
        if table is not None:
            row_text = " ".join(
                value
                for row in table.rows
                for value in row.values()
            )
            row_tokens = {
                token
                for token in _search_tokens(row_text)
            }
            row_overlap = len(query_tokens & row_tokens)
            normalized_row_text = " ".join(row_text.casefold().split())
            filter_matches = sum(
                value in normalized_row_text
                for value in filter_values
            )

        # Exact requested values are the strongest signal. Metadata and row text
        # then contribute equally so captionless/layout tables remain eligible.
        score = (filter_matches * 6) + (metadata_overlap * 2) + (row_overlap * 2)
        if score:
            ranked.append(
                (score, filter_matches, metadata_overlap, -position, entry)
            )

    ranked.sort(key=lambda item: item[:4], reverse=True)
    return [entry for _, _, _, _, entry in ranked[:limit]]


def _article_key(value: str) -> str:
    """Canonical comparison key for an article filename or display label."""

    name = Path(value.strip()).name
    if name.casefold().endswith(".html"):
        name = name[:-5]
    return "_".join(name.replace("_", " ").split()).casefold()


def _search_tokens(value: str) -> set[str]:
    """Return small, comparison-oriented tokens without adding an NLP dependency."""

    aliases = {
        "nominated": "nominate",
        "nomination": "nominate",
        "nominations": "nominate",
        "nominee": "nominate",
        "nominees": "nominate",
        "winning": "win",
        "winner": "win",
        "winners": "win",
        "won": "win",
    }
    stop_words = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "is",
        "of",
        "the",
        "to",
        "was",
        "were",
        "which",
        "who",
    }
    tokens: set[str] = set()
    for raw_token in re.findall(r"\w+", value.casefold()):
        token = aliases.get(raw_token, raw_token)
        if len(token) > 1 and token not in stop_words:
            tokens.add(token)
    return tokens

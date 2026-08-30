"""Expand retrieved seed chunks into complete article context."""
from __future__ import annotations

from .corpus import ArticleText, ArticleTextStore

Hit = tuple[str, str, float]


def article_name_from_doc_id(doc_id: str) -> str:
    return doc_id.split("#", 1)[0]


def retrieved_article_names(seed_hits: list[Hit]) -> list[str]:
    """Return unique article names in the rank order in which they were discovered."""
    names: list[str] = []
    seen: set[str] = set()
    for doc_id, _, _ in seed_hits:
        article = article_name_from_doc_id(doc_id)
        if article not in seen:
            seen.add(article)
            names.append(article)
    return names


def load_retrieved_article_texts(
    seed_hits: list[Hit], article_store: ArticleTextStore
) -> list[ArticleText]:
    """Load each discovered article once from its complete extracted text file."""
    return [
        article_store.load(source)
        for source in retrieved_article_names(seed_hits)
        if article_store.has_article(source)
    ]


def format_full_articles_context(articles: list[ArticleText]) -> str:
    """Format complete, non-overlapping article texts for a single LLM call."""
    return ("\n\n" + "=" * 80 + "\n\n").join(
        article.text.strip() for article in articles
    )

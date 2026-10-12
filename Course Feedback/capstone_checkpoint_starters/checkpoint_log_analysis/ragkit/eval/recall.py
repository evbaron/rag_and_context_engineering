"""Retrieval recall: did retrieval bring back the articles that hold the answer? (Checkpoint 3)

Recall is measured separately from answer quality because the two fail for different
reasons. Low recall means the answer never had a chance: improve retrieval. High
recall with a wrong answer means retrieval did its job: improve how the answer is
produced from what was found.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ragkit.corpus import normalize_source


def retrieved_sources(hits: Iterable[Any]) -> set[str]:
    """The normalized source names of retrieved passages (Hit objects or logged dicts)."""
    found = set()
    for hit in hits:
        source = hit.get("source") if isinstance(hit, dict) else hit.doc.source
        if source:
            found.add(normalize_source(source))
    return found


def article_recall(hits: Iterable[Any], expected_sources: Iterable[str]) -> float | None:
    """The share of the expected source articles found among ``hits`` (0.0 to 1.0).

    None when the question lists no source articles (recall cannot be measured).
    """
    expected = {normalize_source(source) for source in expected_sources if source.strip()}
    if not expected:
        return None
    return len(expected & retrieved_sources(hits)) / len(expected)

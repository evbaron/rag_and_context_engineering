"""What every retriever shares. (Checkpoint 2)

A retriever does one job: given a question, return the best passages. It does not call
the chat model to answer and keeps no conversation; pipelines do that. Because every
retriever has the same ``retrieve(query, k)``, any of them plugs into the same pipeline,
chat, and evaluation.

Scores are always "higher is better", whatever the method measures underneath.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ragkit.corpus import Document
from ragkit.pipelines.base import LLMCall


@dataclass
class Hit:
    """One retrieved passage and how well it matched."""

    doc: Document
    score: float  # higher is better
    via: str = "retrieval"  # how it was found: "retrieval", or "graph" from Checkpoint 4


class BaseRetriever(ABC):
    name = "retriever"

    def __init__(self) -> None:
        self.calls: list[LLMCall] = []  # model or embedding calls made while retrieving
        self.last_details: dict[str, Any] = {}  # what the last search did, for the log

    def settings(self) -> dict[str, Any]:
        return {"name": self.name}

    @abstractmethod
    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        """The ``k`` best passages for ``query``, best first."""

    def take_calls(self) -> list[LLMCall]:
        """The calls made since the last time this was asked, so a pipeline can log them."""
        calls, self.calls = self.calls, []
        return calls


def normalize(hits: list[Hit]) -> list[Hit]:
    """Rescale scores to 0..1 (best = 1), so scores from different retrievers can be added."""
    if not hits:
        return []
    high = max(hit.score for hit in hits)
    low = min(hit.score for hit in hits)
    if high == low:
        return [Hit(hit.doc, 1.0, hit.via) for hit in hits]
    return [Hit(hit.doc, (hit.score - low) / (high - low), hit.via) for hit in hits]


def sources_of(hits: list[Hit]) -> list[str]:
    """The distinct source files of ``hits``, in rank order."""
    seen: list[str] = []
    for hit in hits:
        if hit.doc.source not in seen:
            seen.append(hit.doc.source)
    return seen

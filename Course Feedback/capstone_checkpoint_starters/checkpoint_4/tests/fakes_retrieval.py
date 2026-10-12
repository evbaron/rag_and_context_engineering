"""A stand-in retriever for tests (Checkpoint 2 on)."""

from __future__ import annotations

from ragkit.pipelines.base import LLMCall
from ragkit.retrievers.base import BaseRetriever


class FixedRetriever(BaseRetriever):
    """Returns the hits it was given; records one embedding call per search."""

    def __init__(self, name, hits):
        super().__init__()
        self.name = name
        self.hits = hits

    def retrieve(self, query, k=5):
        self.calls.append(LLMCall("embedding", "fake", 3, 0, 0.0))
        return self.hits[:k]

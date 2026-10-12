"""The shapes every pipeline shares. (Checkpoint 1)

A pipeline is anything that answers a question: a plain model call (Checkpoint 1), a
retriever plus a model (Checkpoint 2), an agent (Checkpoint 5). They all take the same
input and return the same ``Answer``, so the chat, the run log, and the evaluation work
with every one of them without changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

# One earlier turn of a conversation: (question, answer).
Turn = tuple[str, str]


@dataclass
class LLMCall:
    """One model call, as it is logged: who made it, how big it was, how long it took."""

    role: str  # what the call was for: "answer", "judge", "decompose", "embedding", ...
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    cached_tokens: int = 0  # input tokens the provider served from its cache (cheaper)


@dataclass
class Answer:
    """What a pipeline returns.

    ``question`` is the question exactly as the pipeline used it. Today that is what was
    asked. A later safeguard may clean the question first; the chat history then keeps
    the cleaned version, so nothing harmful is replayed in later turns.
    """

    text: str
    question: str
    hits: list = field(default_factory=list)  # retrieved passages (Checkpoint 2 on)
    calls: list[LLMCall] = field(default_factory=list)  # every model call made
    metadata: dict[str, Any] = field(default_factory=dict)  # anything worth logging


class Pipeline(ABC):
    """Base class for everything that answers questions."""

    name = "pipeline"

    def settings(self) -> dict[str, Any]:
        """The settings that identify this pipeline in logs and reports."""
        return {"name": self.name}

    @abstractmethod
    def answer(self, question: str, history: Sequence[Turn] = ()) -> Answer:
        """Answer ``question``. ``history`` holds the earlier turns to take into account."""

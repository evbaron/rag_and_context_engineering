"""The no-retrieval pipeline: the model answers from its training alone. (Checkpoint 1)

This is the Checkpoint 1.1 baseline. It shows what a model does without the corpus:
made-up facts, missing knowledge, outdated knowledge, and answers that change when the
question is rephrased. Every later pipeline is measured against what this one gets wrong.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ragkit import config
from ragkit.llm import DEFAULT_SYSTEM_PROMPT, ask, build_messages, make_llm
from ragkit.pipelines.base import Answer, Pipeline, Turn


class LLMOnlyPipeline(Pipeline):
    name = "llm_only"

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.2,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        llm: Any = None,
    ):
        self.model = model or config.model()
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.llm = llm or make_llm(self.model, temperature)

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "temperature": self.temperature}

    def answer(self, question: str, history: Sequence[Turn] = ()) -> Answer:
        messages = build_messages(question, history=history, system_prompt=self.system_prompt)
        text, call = ask(self.llm, messages)
        return Answer(text=text, question=question, calls=[call])

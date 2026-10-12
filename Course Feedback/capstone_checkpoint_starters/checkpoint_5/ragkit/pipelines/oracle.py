"""The oracle: answers with the question's source articles handed over directly. (Checkpoint 3)

There is no retrieval. For each question in a question set, the oracle gives the model
the full text of the articles the set lists as its sources. Its quality is the best the
answer step can do when retrieval is perfect. When the oracle also gets a question
wrong, a better retriever will not fix it: the problem is in how the answer is produced
from the evidence (or in the question set itself).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ragkit import config
from ragkit.corpus import Document, normalize_source
from ragkit.eval.questions import EvalQuestion
from ragkit.llm import ask, build_messages, make_llm
from ragkit.pipelines.base import Answer, Pipeline, Turn
from ragkit.pipelines.rag import RAG_SYSTEM_PROMPT, format_context
from ragkit.retrievers.base import Hit


def whole_articles(documents: Sequence[Document]) -> dict[str, Document]:
    """Join each source's sections (or pages) back into one Document per source."""
    groups: dict[str, list[Document]] = {}
    for document in documents:
        groups.setdefault(normalize_source(document.source), []).append(document)
    articles = {}
    for key, parts in groups.items():
        first = parts[0]
        text = "\n\n".join(
            f"## {part.metadata['section']}\n{part.text}" if part.metadata.get("section") else part.text for part in parts
        )
        articles[key] = Document(first.source, text, {"source": first.source, "title": first.metadata.get("title", ""), "section": "whole article"})
    return articles


class OraclePipeline(Pipeline):
    name = "oracle"

    def __init__(
        self,
        documents: Sequence[Document],
        questions: Sequence[EvalQuestion],
        model: str | None = None,
        temperature: float = 0.2,
        max_context_chars: int = 120_000,
        system_prompt: str = RAG_SYSTEM_PROMPT,
        llm: Any = None,
    ):
        self.articles = whole_articles(documents)
        self.questions = {_key(question.question): question for question in questions}
        self.model = model or config.model()
        self.temperature = temperature
        self.max_context_chars = max_context_chars  # very long articles are cut to keep the cost bounded
        self.system_prompt = system_prompt
        self.llm = llm or make_llm(self.model, temperature)

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "max_context_chars": self.max_context_chars}

    def answer(self, question: str, history: Sequence[Turn] = ()) -> Answer:
        item = self.questions.get(_key(question))
        if item is None:
            raise ValueError("The oracle can only answer questions from its question set.")
        hits = [Hit(self.articles[key], 1.0) for key in map(normalize_source, item.sources) if key in self.articles]
        missing = [source for source in item.sources if normalize_source(source) not in self.articles]
        context = format_context(hits)
        truncated = len(context) > self.max_context_chars
        context = context[: self.max_context_chars]
        messages = build_messages(question, context=context, history=history, system_prompt=self.system_prompt)
        text, call = ask(self.llm, messages)
        metadata = {"context_chars": len(context), "truncated": truncated, "missing_sources": missing}
        return Answer(text=text, question=question, hits=hits, calls=[call], metadata=metadata)


def _key(text: str) -> str:
    return " ".join(text.split()).lower()

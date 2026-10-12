"""Multistep retrieval: split a question into simpler searches, then merge. (Checkpoint 4)

"Who hosted both the 68th and the 74th Academy Awards?" needs two articles, but one
search for the whole sentence tends to find only one. Here the model first writes a few
short searches, one for each thing the question needs; each runs through the base
retriever. Each search's best passage is kept first, so every part of the question is
represented; the remaining places go to the passages with the highest combined score.
The original question is always searched too.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage

from ragkit import config
from ragkit.llm import ask, make_llm
from ragkit.retrievers.base import BaseRetriever, Hit, normalize

DECOMPOSE_PROMPT = """Break the question into at most {n} short search queries that together find everything needed to answer it.
Name each person, place, work, or event explicitly in its own query.
If the question needs only one search, return the question itself.
Return only the queries, one per line, with no numbering or commentary.

Question: {question}"""


class MultiStepRetriever(BaseRetriever):
    name = "multistep"

    def __init__(self, base: BaseRetriever, model: str | None = None, max_queries: int = 4, pool: int = 10, llm: Any = None):
        super().__init__()
        self.base = base
        self.model = model or config.model()
        self.max_queries = max_queries
        self.pool = pool  # passages asked from the base retriever for each search
        self.llm = llm or make_llm(self.model, temperature=0.0)

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "base": self.base.name, "max_queries": self.max_queries, "pool": self.pool, "model": self.model}

    def decompose(self, question: str) -> list[str]:
        text, call = ask(self.llm, [HumanMessage(content=DECOMPOSE_PROMPT.format(n=self.max_queries, question=question))], role="decompose")
        self.calls.append(call)
        queries: list[str] = []
        for line in text.splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"')
            if line and line.lower() not in {q.lower() for q in queries}:
                queries.append(line)
        return queries[: self.max_queries]

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        searches = [query] + [q for q in self.decompose(query) if q.lower() != query.lower()]
        per_search = [normalize(self.base.retrieve(search, max(self.pool, k))) for search in searches]
        self.calls += self.base.take_calls()

        combined: dict[str, Hit] = {}
        for hits in per_search:
            for hit in hits:
                if hit.doc.id in combined:
                    combined[hit.doc.id].score += hit.score
                else:
                    combined[hit.doc.id] = Hit(hit.doc, hit.score)
        chosen: list[Hit] = []
        for hits in per_search:  # the best passage of every search first
            if hits and hits[0].doc.id not in {h.doc.id for h in chosen} and len(chosen) < k:
                chosen.append(combined[hits[0].doc.id])
        for hit in sorted(combined.values(), key=lambda h: h.score, reverse=True):
            if len(chosen) >= k:
                break
            if hit.doc.id not in {h.doc.id for h in chosen}:
                chosen.append(hit)
        self.last_details = {"searches": searches}
        return chosen

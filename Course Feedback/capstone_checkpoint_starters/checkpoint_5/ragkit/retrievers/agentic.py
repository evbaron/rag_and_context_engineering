"""An agentic retriever: search, look at what was found, decide whether to search again. (Checkpoint 5)

A fixed retriever runs one search. This one loops, as in Lab 5.1:

    search ──▶ assess ──(something missing)──▶ search again, with a new query
                  │
                  └──(enough, or the round limit)──▶ done

The assessment is a form the model fills in (``Assessment``): is the evidence enough,
and if not, what is missing and what to search for next. The loop is a LangGraph graph.
Everything found in every round is returned, in the order found, up to ``max_hits``.
Because it is a retriever, it plugs into RAGPipeline, the chat, and the evaluation
unchanged.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ragkit import config
from ragkit.corpus import Document
from ragkit.llm import make_llm
from ragkit.pipelines.rag import format_context
from ragkit.retrievers.base import BaseRetriever, Hit
from ragkit.structured import ask_structured

ASSESS_PROMPT = """Decide whether these passages are enough to answer the question completely.

Question: {question}

Passages found so far:
{passages}

Searches already run: {searches}

If something is missing, say what, and write ONE new search query that would find it.
Name the specific person, place, work, or event in the query. Do not repeat a search."""


class Assessment(BaseModel):
    enough: bool = Field(description="True when the passages contain everything needed to answer the question")
    missing: str = Field(default="", description="What information is still missing, if anything")
    next_query: str = Field(default="", description="One new search query for what is missing; empty when enough")


class _State(TypedDict):
    question: str
    query: str
    k: int
    hits: list[Hit]
    searches: list[str]
    rounds: list[dict[str, Any]]
    done: bool


class AgenticRetriever(BaseRetriever):
    name = "agentic"

    def __init__(self, base: BaseRetriever, model: str | None = None, max_rounds: int = 3,
                 max_hits: int | None = None, llm: Any = None):
        super().__init__()
        self.base = base
        self.model = model or config.model()
        self.max_rounds = max_rounds
        self.max_hits = max_hits  # None: 2 x k
        self.llm = llm or make_llm(self.model, temperature=0.0)
        self.graph = self._build_graph()

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "base": self.base.name, "max_rounds": self.max_rounds, "model": self.model}

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        state = self.graph.invoke({"question": query, "query": query, "k": k, "hits": [], "searches": [], "rounds": [], "done": False})
        self.last_details = {"rounds": state["rounds"]}
        return state["hits"][: self.max_hits or 2 * k]

    def _build_graph(self):
        graph = StateGraph(_State)
        graph.add_node("search", self._search)
        graph.add_node("assess", self._assess)
        graph.add_edge(START, "search")
        graph.add_edge("search", "assess")
        graph.add_conditional_edges("assess", lambda state: "done" if state["done"] else "again", {"again": "search", "done": END})
        return graph.compile()

    def _search(self, state: _State) -> dict[str, Any]:
        seen = {hit.doc.id for hit in state["hits"]}
        new = [hit for hit in self.base.retrieve(state["query"], state["k"]) if hit.doc.id not in seen]
        self.calls += self.base.take_calls()
        return {"hits": state["hits"] + new, "searches": state["searches"] + [state["query"]],
                "rounds": state["rounds"] + [{"query": state["query"], "new_passages": len(new)}]}

    def _assess(self, state: _State) -> dict[str, Any]:
        prompt = ASSESS_PROMPT.format(question=state["question"], passages=_preview(state["hits"]),
                                      searches="; ".join(state["searches"]))
        assessment, call = ask_structured(self.llm, [HumanMessage(content=prompt)], Assessment, role="assess")
        self.calls.append(call)
        rounds = state["rounds"][:-1] + [{**state["rounds"][-1], "enough": assessment.enough, "missing": assessment.missing}]
        next_query = assessment.next_query.strip()
        done = (assessment.enough or not next_query or len(state["searches"]) >= self.max_rounds
                or next_query.lower() in {s.lower() for s in state["searches"]})
        return {"rounds": rounds, "done": done, "query": next_query or state["query"]}


def _preview(hits: list[Hit], limit: int = 600) -> str:
    """Passages shortened for the assessment: enough to judge, cheaper than full text."""
    shortened = [Hit(Document(hit.doc.id, hit.doc.text[:limit], hit.doc.metadata), hit.score) for hit in hits]
    return format_context(shortened) or "(none)"

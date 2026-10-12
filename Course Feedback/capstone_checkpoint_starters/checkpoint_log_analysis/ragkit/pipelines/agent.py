"""A tool-using agent: the model plans every step, as in Lab 5.2. (Checkpoint 5)

On each step the model fills in a ``Plan`` form choosing one action:

    search    run the retriever with a query the model writes
    read      read one whole source document already found (a full article or paper)
    answer    write the final answer from the evidence gathered
    clarify   ask the user a question, when the request is ambiguous

    plan ──▶ search ─┐
     ▲       read ───┤
     └───────────────┘
    plan ──▶ answer ──▶ done
    plan ──▶ clarify ──▶ done

A clarifying question is returned as an ordinary answer, so the chat loop needs no
change: the user's reply simply arrives as the next turn, with the history. Evaluation
switches clarify off (allow_clarify=False). The step limit keeps the loop bounded: when
it is reached, the agent answers with what it has. Planning sees shortened passages;
only the final answer sees them in full, which keeps each planning call cheap.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ragkit import config
from ragkit.corpus import Document, load_emails, load_papers, load_wikipedia
from ragkit.llm import ask, build_messages, make_llm
from ragkit.pipelines.base import Answer, LLMCall, Pipeline, Turn
from ragkit.pipelines.oracle import whole_articles
from ragkit.pipelines.rag import RAG_SYSTEM_PROMPT, format_context
from ragkit.retrievers.base import BaseRetriever, Hit
from ragkit.structured import ask_structured

PLAN_PROMPT = """You are a research agent answering a question from a document collection.
Every fact in the final answer must come from the evidence, not from memory.

Earlier turns of the conversation, oldest first:
{history}

Current question: {question}
If the current question continues an earlier turn (it answers a clarifying question, or
follows up with words such as "it", "he", or "and who won?"), read it together with the
earlier turns, and search for the combined meaning.

Evidence gathered so far (step {step} of {max_steps}):
{evidence}

Actions taken so far:
{actions}

Choose the next action:
- search: find passages; give a short, specific query naming the person, place, work, or event
- read: read one whole source when a passage looks right but incomplete; give its file name exactly as shown after "source:"
- answer: the evidence is enough, or nothing more can be found{clarify}"""

CLARIFY_OPTION = ("\n- clarify: when the question cannot be answered without knowing what it refers to "
                  "(for example \"it\" with nothing earlier to refer to); give the question to ask the user")


class Plan(BaseModel):
    action: Literal["search", "read", "answer", "clarify"]
    argument: str = Field(default="", description="search: the query; read: the source file name; clarify: the question for the user; answer: empty")
    reason: str = Field(default="", description="One short sentence on why this action")


class _State(TypedDict):
    question: str
    history: list[Turn]
    evidence: list[Hit]
    actions: list[dict[str, Any]]
    plan: dict[str, Any]
    answer: str


class AgentPipeline(Pipeline):
    name = "agent"

    def __init__(self, retriever: BaseRetriever, k: int = 5, model: str | None = None, max_steps: int = 5,
                 allow_clarify: bool = True, max_read_chars: int = 20_000, corpus_folder: Path | None = None,
                 scenario: str | None = None, llm: Any = None):
        self.retriever = retriever
        self.k = k
        self.model = model or config.model()
        self.max_steps = max_steps
        self.allow_clarify = allow_clarify
        self.max_read_chars = max_read_chars  # a very long source is cut, to bound the cost
        self.corpus_folder = corpus_folder
        self.scenario = scenario
        self.llm = llm or make_llm(self.model, temperature=0.2)
        self.graph = self._build_graph()
        self._calls: list[LLMCall] = []

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "retriever": self.retriever.name, "k": self.k, "model": self.model,
                "max_steps": self.max_steps, "allow_clarify": self.allow_clarify}

    def answer(self, question: str, history: Sequence[Turn] = ()) -> Answer:
        self._calls = []
        state = self.graph.invoke({"question": question, "history": list(history), "evidence": [], "actions": [], "plan": {}, "answer": ""},
                                  config={"recursion_limit": 4 * self.max_steps + 10})
        clarify = state["plan"].get("action") == "clarify"
        text = state["plan"].get("argument", "") if clarify else state["answer"]
        metadata = {"context_chars": len(format_context(state["evidence"])), "steps": state["actions"], "needs_clarification": clarify}
        return Answer(text=text, question=question, hits=state["evidence"], calls=self._calls, metadata=metadata)

    def _build_graph(self):
        graph = StateGraph(_State)
        graph.add_node("plan", self._plan)
        graph.add_node("search", self._search)
        graph.add_node("read", self._read)
        graph.add_node("answer", self._answer)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges("plan", lambda state: state["plan"]["action"],
                                    {"search": "search", "read": "read", "answer": "answer", "clarify": END})
        graph.add_edge("search", "plan")
        graph.add_edge("read", "plan")
        graph.add_edge("answer", END)
        return graph.compile()

    def _plan(self, state: _State) -> dict[str, Any]:
        step = len(state["actions"]) + 1
        if step > self.max_steps:
            return {"plan": {"action": "answer", "argument": "", "reason": "step limit reached"}}
        history = "\n".join(f"Q: {q}\nA: {a[:200]}" for q, a in state["history"][-3:]) or "none"
        actions = "\n".join(f"{i}. {a['action']} {a['argument']!r}: {a.get('result', '')}" for i, a in enumerate(state["actions"], 1))
        evidence = [Hit(Document(h.doc.id, h.doc.text[:500], h.doc.metadata), h.score) for h in state["evidence"]]
        prompt = PLAN_PROMPT.format(question=state["question"], history=history, step=step, max_steps=self.max_steps,
                                    evidence=format_context(evidence) or "none yet", actions=actions or "none yet",
                                    clarify=CLARIFY_OPTION if self.allow_clarify else "")
        plan, call = ask_structured(self.llm, [HumanMessage(content=prompt)], Plan, role="plan")
        self._calls.append(call)
        if plan.action == "clarify" and not self.allow_clarify:
            plan = Plan(action="answer", reason="clarifying is switched off")
        return {"plan": plan.model_dump()}

    def _search(self, state: _State) -> dict[str, Any]:
        query = state["plan"]["argument"] or state["question"]
        seen = {hit.doc.id for hit in state["evidence"]}
        new = [hit for hit in self.retriever.retrieve(query, self.k) if hit.doc.id not in seen]
        self._calls.extend(self.retriever.take_calls())
        return {"evidence": state["evidence"] + new,
                "actions": state["actions"] + [{**state["plan"], "result": f"{len(new)} new passage(s)"}]}

    def _read(self, state: _State) -> dict[str, Any]:
        name = Path(state["plan"]["argument"].strip()).name
        document = self.read_source(name)
        if document is None or document.id in {hit.doc.id for hit in state["evidence"]}:
            result = "not found" if document is None else "already read"
            return {"actions": state["actions"] + [{**state["plan"], "result": result}]}
        return {"evidence": state["evidence"] + [Hit(document, 1.0, via="read")],
                "actions": state["actions"] + [{**state["plan"], "result": f"read {len(document.text):,} characters"}]}

    def _answer(self, state: _State) -> dict[str, Any]:
        messages = build_messages(state["question"], context=format_context(state["evidence"]) or "(no evidence found)",
                                  history=state["history"], system_prompt=RAG_SYSTEM_PROMPT)
        text, call = ask(self.llm, messages)
        self._calls.append(call)
        return {"answer": text, "actions": state["actions"] + [{**state["plan"], "result": "answered"}]}

    def read_source(self, file_name: str) -> Document | None:
        """The whole text of one corpus file, read fresh from the corpus folder."""
        folder = self.corpus_folder or config.corpus_dir()
        path = folder / file_name
        if not file_name or not path.is_file():
            return None
        loader = {"wikipedia": load_wikipedia, "papers": load_papers, "emails": load_emails}[self.scenario or config.scenario()]
        articles = whole_articles(list(loader([path])))
        if not articles:
            return None
        article = next(iter(articles.values()))
        return Document(article.id, article.text[: self.max_read_chars], article.metadata)

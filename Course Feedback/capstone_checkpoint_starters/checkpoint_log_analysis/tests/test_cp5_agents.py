from pathlib import Path

import pytest

from ragkit.corpus import Document
from ragkit.pipelines.agent import AgentPipeline, Plan
from ragkit.retrievers.agentic import AgenticRetriever, Assessment
from ragkit.retrievers.base import Hit
from ragkit.retrievers.bm25 import Bm25Retriever
from ragkit.structured import ask_structured
from tests.fakes_agents import FakeFormLLM

FIXTURES = Path(__file__).parent / "fixtures"
DOCS = [
    Document("68#0", "The 68th Academy Awards ceremony was hosted by Whoopi Goldberg.", {"source": "68th.html", "title": "68th"}),
    Document("74#0", "The 74th Academy Awards ceremony was hosted by Whoopi Goldberg.", {"source": "74th.html", "title": "74th"}),
    Document("x#0", "Sprinting and relay races.", {"source": "x.html", "title": "Sprinting"}),
]


def test_ask_structured_returns_the_form_and_the_call():
    form, call = ask_structured(FakeFormLLM([Assessment(enough=True)]), [], Assessment, role="assess")
    assert form.enough is True and call.role == "assess" and call.input_tokens == 20


def test_agentic_retriever_searches_again_for_what_is_missing():
    llm = FakeFormLLM([
        Assessment(enough=False, missing="the 74th ceremony", next_query="74th Academy Awards host"),
        Assessment(enough=True),
    ])
    retriever = AgenticRetriever(Bm25Retriever(DOCS), model="fake/model", llm=llm)
    hits = retriever.retrieve("68th Academy Awards host", k=1)
    assert [h.doc.source for h in hits] == ["68th.html", "74th.html"]
    rounds = retriever.last_details["rounds"]
    assert [r["query"] for r in rounds] == ["68th Academy Awards host", "74th Academy Awards host"]
    assert rounds[0]["enough"] is False and rounds[1]["enough"] is True
    assert [c.role for c in retriever.take_calls()] == ["assess", "assess"]


def test_agentic_retriever_stops_at_the_round_limit_or_a_repeated_query():
    llm = FakeFormLLM([Assessment(enough=False, next_query="sprinting")] * 5)
    retriever = AgenticRetriever(Bm25Retriever(DOCS), model="fake/model", max_rounds=3, llm=llm)
    retriever.retrieve("relay races", k=1)
    assert len(retriever.last_details["rounds"]) == 2  # the second "sprinting" query would repeat


def test_agent_searches_reads_and_answers(monkeypatch):
    monkeypatch.setenv("RAG_SCENARIO", "wikipedia")
    llm = FakeFormLLM(
        forms=[Plan(action="search", argument="Alpha Sprint record"),
               Plan(action="read", argument="Alpha_Sprint.html"),
               Plan(action="answer")],
        replies=["Ann Runner holds the record [1]."],
    )
    agent = AgentPipeline(Bm25Retriever(DOCS), k=1, model="fake/model", corpus_folder=FIXTURES / "wikipedia", llm=llm)
    answer = agent.answer("Who holds the Alpha Sprint world record?")
    assert answer.text == "Ann Runner holds the record [1]."
    assert [s["action"] for s in answer.metadata["steps"]] == ["search", "read", "answer"]
    assert answer.hits[-1].via == "read" and "World records, Men: Ann Runner" in answer.hits[-1].doc.text
    assert [c.role for c in answer.calls] == ["plan", "plan", "plan", "answer"]
    assert answer.metadata["needs_clarification"] is False


def test_agent_clarifying_question_is_an_ordinary_answer():
    llm = FakeFormLLM([Plan(action="clarify", argument="Which ceremony do you mean?")])
    answer = AgentPipeline(Bm25Retriever(DOCS), model="fake/model", llm=llm).answer("Who hosted it?")
    assert answer.text == "Which ceremony do you mean?" and answer.metadata["needs_clarification"] is True


def test_agent_answers_at_the_step_limit_and_when_clarify_is_off():
    llm = FakeFormLLM(forms=[Plan(action="search", argument="hosts")] * 2 + [Plan(action="clarify", argument="?")],
                      replies=["Whoopi Goldberg."])
    agent = AgentPipeline(Bm25Retriever(DOCS), k=1, model="fake/model", max_steps=2, allow_clarify=False, llm=llm)
    answer = agent.answer("Who hosted both?")
    assert answer.text == "Whoopi Goldberg."
    assert answer.metadata["steps"][-1]["reason"] == "step limit reached"

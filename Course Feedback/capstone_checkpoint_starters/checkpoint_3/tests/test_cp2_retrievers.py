from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from ragkit import config
from ragkit.corpus import Document, load_corpus
from ragkit.pipelines.rag import RAGPipeline, format_context
from ragkit.retrievers.base import Hit, normalize, sources_of
from ragkit.retrievers.bm25 import Bm25Retriever
from ragkit.retrievers.factory import corpus_settings, make_retriever, open_documents
from ragkit.retrievers.hybrid import HybridRetriever
from ragkit.retrievers.vector import VectorRetriever
from tests.fakes import FakeLLM
from tests.fakes_retrieval import FixedRetriever

FIXTURES = Path(__file__).parent / "fixtures"
DOCS = [
    Document("a#0", "Usain Bolt holds the 100 metres world record of 9.58 seconds.", {"source": "100_metres.html", "title": "100 metres", "section": "Records"}),
    Document("b#0", "The Beta Relay is a team race with a baton.", {"source": "Beta_Relay.html", "title": "Beta Relay", "section": "Introduction"}),
    Document("c#0", "In 1580 a comet was observed over Europe.", {"source": "1580.html", "title": "1580", "section": "Events"}),
]


def test_bm25_ranks_the_matching_passage_first():
    hits = Bm25Retriever(DOCS).retrieve("Who holds the 100 metres world record?", k=2)
    assert hits[0].doc.id == "a#0"
    assert all(hit.score > 0 for hit in hits)
    assert Bm25Retriever(DOCS).retrieve("zebra quantum", k=3) == []


def test_normalize_and_sources():
    hits = normalize([Hit(DOCS[0], 4.0), Hit(DOCS[1], 2.0), Hit(DOCS[0], 1.0)])
    assert [round(h.score, 3) for h in hits] == [1.0, 0.333, 0.0]
    assert sources_of(hits) == ["100_metres.html", "Beta_Relay.html"]


def test_hybrid_adds_weighted_normalized_scores():
    keyword = FixedRetriever("bm25", [Hit(DOCS[0], 10.0), Hit(DOCS[1], 5.0)])
    semantic = FixedRetriever("vector", [Hit(DOCS[1], 0.9), Hit(DOCS[2], 0.1)])
    hybrid = HybridRetriever(keyword, semantic, weight_keyword=0.5, pool=5)
    hits = hybrid.retrieve("q", k=3)
    scores = {h.doc.id: round(h.score, 3) for h in hits}
    assert scores == {"a#0": 0.5, "b#0": 0.5, "c#0": 0.0}
    assert len(hybrid.take_calls()) == 2 and hybrid.take_calls() == []
    with pytest.raises(ValueError):
        HybridRetriever(keyword, semantic, weight_keyword=1.5)


def test_vector_index_builds_records_and_searches(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=32)
    settings = {"scenario": "wikipedia", "folder": "x", "chunk_size": 1500, "overlap": 150, "limit": None}
    built = VectorRetriever.build("test_index", DOCS, settings, embeddings=embeddings, folder=tmp_path, progress=lambda _: None)
    assert built.count() == 3
    info = VectorRetriever.info("test_index", folder=tmp_path)
    assert info["passages"] == 3 and info["corpus"] == settings
    assert [i["name"] for i in VectorRetriever.list_indexes("wikipedia", folder=tmp_path)] == ["test_index"]

    reopened = VectorRetriever("test_index", embeddings=embeddings, folder=tmp_path)
    hits = reopened.retrieve(DOCS[2].text, k=2)
    assert hits[0].doc.id == "c#0" and hits[0].doc.source == "1580.html"
    assert hits[0].score == pytest.approx(1.0, abs=1e-4)  # identical text: distance 0
    assert [call.role for call in reopened.take_calls()] == ["embedding"]

    messages = []
    VectorRetriever.build("test_index", DOCS, settings, embeddings=embeddings, folder=tmp_path, progress=messages.append)
    assert "3 passages already indexed; 0 to add" in messages[0]


def test_factory_needs_an_index_for_vector_and_hybrid(monkeypatch):
    monkeypatch.setenv("RAG_SCENARIO", "wikipedia")
    monkeypatch.setenv("RAG_CORPUS_DIR", str(FIXTURES / "wikipedia"))
    documents, index_name = open_documents()
    assert index_name is None and {d.source for d in documents} == {"Alpha_Sprint.html", "Beta_Relay.html"}
    assert make_retriever("bm25", documents).name == "bm25"
    with pytest.raises(config.SetupError):
        make_retriever("hybrid", documents)
    with pytest.raises(ValueError):
        make_retriever("magic", documents)
    assert corpus_settings(limit=5)["limit"] == 5


def test_open_documents_rebuilds_the_passages_an_index_recorded(monkeypatch):
    monkeypatch.setenv("RAG_SCENARIO", "wikipedia")
    monkeypatch.setenv("RAG_CORPUS_DIR", str(FIXTURES / "wikipedia"))
    settings = corpus_settings(chunk_size=200, overlap=20, limit=1)
    passages = load_corpus(chunk_size=200, overlap=20, limit=1)
    VectorRetriever.build("small", passages, settings, embeddings=DeterministicFakeEmbedding(size=16), progress=lambda _: None)
    documents, index_name = open_documents()
    assert index_name == "small"
    assert [d.id for d in documents] == [d.id for d in passages]


def test_rag_pipeline_numbers_passages_and_logs_every_call():
    retriever = FixedRetriever("bm25", [Hit(DOCS[0], 3.0), Hit(DOCS[2], 1.0)])
    retriever.last_details = {"note": "x"}
    llm = FakeLLM(["Usain Bolt [1]."])
    pipeline = RAGPipeline(retriever, k=2, model="fake/model", llm=llm)
    answer = pipeline.answer("Who holds the record?", history=[("hi", "hello")])
    sent = llm.sent[0][-1].content
    assert sent.startswith("Context:\n[1] 100 metres > Records (source: 100_metres.html)\nUsain Bolt")
    assert "[2] 1580 > Events (source: 1580.html)" in sent
    assert [call.role for call in answer.calls] == ["embedding", "answer"]
    assert answer.metadata["context_chars"] == len(format_context(answer.hits))
    assert answer.metadata["retrieval"] == {"note": "x"}
    assert pipeline.settings()["retriever"] == "bm25" and pipeline.settings()["k"] == 2

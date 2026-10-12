from pathlib import Path

from ragkit.corpus import Document, load_wikipedia
from ragkit.retrievers.base import Hit
from ragkit.retrievers.bm25 import Bm25Retriever
from ragkit.retrievers.graph import GraphRetriever, link_graph, mention_graph
from ragkit.retrievers.multistep import MultiStepRetriever
from tests.fakes import FakeLLM
from tests.fakes_retrieval import FixedRetriever

FIXTURES = Path(__file__).parent / "fixtures"
DOCS = [
    Document("68#0", "The 68th Academy Awards ceremony was hosted by Whoopi Goldberg in 1996.", {"source": "68th.html", "title": "68th Academy Awards"}),
    Document("68#1", "Braveheart won Best Picture at the 68th Academy Awards.", {"source": "68th.html", "title": "68th Academy Awards"}),
    Document("74#0", "The 74th Academy Awards ceremony in 2002 was hosted by Whoopi Goldberg.", {"source": "74th.html", "title": "74th Academy Awards"}),
    Document("x#0", "An unrelated text about sprinting and relay races.", {"source": "x.html", "title": "Sprinting"}),
]


def test_decompose_cleans_numbering_and_duplicates():
    llm = FakeLLM(["1. 68th Academy Awards host\n2) 74th Academy Awards host\n- 68th academy awards host\n"])
    retriever = MultiStepRetriever(Bm25Retriever(DOCS), model="fake/model", llm=llm)
    assert retriever.decompose("Who hosted both?") == ["68th Academy Awards host", "74th Academy Awards host"]
    assert [call.role for call in retriever.take_calls()] == ["decompose"]


def test_multistep_keeps_the_best_passage_of_every_search():
    llm = FakeLLM(["68th Academy Awards\n74th Academy Awards"])
    retriever = MultiStepRetriever(Bm25Retriever(DOCS), model="fake/model", llm=llm)
    hits = retriever.retrieve("Who hosted both the 68th and the 74th Academy Awards?", k=2)
    assert {hit.doc.source for hit in hits} == {"68th.html", "74th.html"}
    assert retriever.last_details["searches"][0].startswith("Who hosted both")
    assert len(retriever.last_details["searches"]) == 3


def test_link_graph_and_graph_retriever_add_the_linked_article():
    documents = list(load_wikipedia(sorted((FIXTURES / "wikipedia").glob("*.html"))))
    graph = link_graph(documents)
    assert graph.has_edge("Alpha_Sprint.html", "Beta_Relay.html")
    alpha = [d for d in documents if d.source == "Alpha_Sprint.html"]
    base = FixedRetriever("bm25", [Hit(alpha[0], 2.0)])
    retriever = GraphRetriever(base, documents, graph, max_neighbors=2)
    hits = retriever.retrieve("What happens if a runner drops the baton?", k=1)
    assert [h.doc.source for h in hits] == ["Alpha_Sprint.html", "Beta_Relay.html"]
    assert hits[1].via == "graph" and "Dropping the baton" in hits[1].doc.text  # the best-matching section
    assert retriever.last_details == {"seeds": ["Alpha_Sprint.html"], "added": ["Beta_Relay.html"]}
    assert [c.role for c in retriever.take_calls()] == ["embedding"]


def test_mention_graph_links_documents_that_name_each_other():
    docs = [
        Document("a#0", "We extend the method of A Tiny Paper on Sketching to loops.", {"source": "a.pdf", "title": "Loops and Holes in Programs"}),
        Document("b#0", "Holes are filled by a synthesizer.", {"source": "b.pdf", "title": "A Tiny Paper on Sketching"}),
        Document("c#0", "Nothing related.", {"source": "c.pdf", "title": "Short"}),
    ]
    graph = mention_graph(docs)
    assert graph.has_edge("a.pdf", "b.pdf") and graph.degree("c.pdf") == 0

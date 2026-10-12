"""Graph retrieval: follow links from what was found to related articles. (Checkpoint 4)

Search finds passages that match the question's words. Some answers also need an
article the question never mentions, one that a found article links to. A graph
records which documents are related; after the base search, this retriever adds the
best-matching passage of each related document. The graph passages come after the
base passages, marked ``via="graph"``, so a retriever asked for k passages returns up
to k + max_neighbors.

Graph builders:
    link_graph(documents)     Wikipedia: an edge for every link between two corpus articles
    mention_graph(documents)  any corpus: an edge when one document's text contains another
                              document's title; for papers, this approximates citations
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import networkx as nx

from ragkit.corpus import Document
from ragkit.retrievers.base import BaseRetriever, Hit, sources_of
from ragkit.retrievers.bm25 import tokenize


def link_graph(documents: Sequence[Document]) -> nx.Graph:
    """Articles as nodes, hyperlinks between corpus articles as edges."""
    graph = nx.Graph()
    for document in documents:
        graph.add_node(document.source)
        for target in document.metadata.get("links", []):
            if target != document.source:
                graph.add_edge(document.source, target)
    return graph


def mention_graph(documents: Sequence[Document], min_title_chars: int = 12) -> nx.Graph:
    """An edge from A to B when A's text contains B's title (titles shorter than
    ``min_title_chars`` are ignored: short titles match by accident). Compares every
    pair of documents, so it suits corpora of a few hundred documents."""
    texts: dict[str, list[str]] = {}
    titles: dict[str, str] = {}
    for document in documents:
        texts.setdefault(document.source, []).append(document.text.lower())
        title = " ".join(str(document.metadata.get("title", "")).split()).lower()
        if len(title) >= min_title_chars:
            titles.setdefault(document.source, title)
    graph = nx.Graph()
    graph.add_nodes_from(texts)
    joined = {source: "\n".join(parts) for source, parts in texts.items()}
    for source, text in joined.items():
        for other, title in titles.items():
            if other != source and title in text:
                graph.add_edge(source, other)
    return graph


class GraphRetriever(BaseRetriever):
    name = "graph"

    def __init__(self, base: BaseRetriever, documents: Sequence[Document], graph: nx.Graph, seeds: int = 3, max_neighbors: int = 3):
        super().__init__()
        self.base = base
        self.graph = graph
        self.seeds = seeds  # how many of the top sources to follow links from
        self.max_neighbors = max_neighbors  # how many related documents to add
        self.by_source: dict[str, list[Document]] = {}
        self.words: dict[str, set[str]] = {}
        for document in documents:
            self.by_source.setdefault(document.source, []).append(document)
            self.words[document.id] = set(tokenize(document.text))

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "base": self.base.name, "seeds": self.seeds, "max_neighbors": self.max_neighbors,
                "graph_edges": self.graph.number_of_edges()}

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        hits = self.base.retrieve(query, k)
        self.calls += self.base.take_calls()
        found = sources_of(hits)
        seeds = found[: self.seeds]
        query_words = set(tokenize(query))
        candidates = []
        for neighbor in {n for seed in seeds if seed in self.graph for n in self.graph.neighbors(seed)}:
            if neighbor in found or neighbor not in self.by_source:
                continue
            best = max(self.by_source[neighbor], key=lambda doc: len(query_words & self.words[doc.id]))
            overlap = len(query_words & self.words[best.id])
            if overlap:
                candidates.append(Hit(best, overlap / max(len(query_words), 1), via="graph"))
        candidates.sort(key=lambda hit: hit.score, reverse=True)
        added = candidates[: self.max_neighbors]
        self.last_details = {"seeds": seeds, "added": [hit.doc.source for hit in added]}
        return hits + added

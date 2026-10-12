"""Keyword retrieval with BM25. (Checkpoint 2)

BM25 scores a passage by the question's words it contains, giving more weight to rare
words and less to very long passages. It is fast, needs no API calls, and is strong on
exact names, numbers, and terms; it misses paraphrases ("sprint" vs "100-metre dash").
"""

from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

from ragkit.corpus import Document
from ragkit.retrievers.base import BaseRetriever, Hit

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for", "by", "with",
    "from", "as", "is", "are", "was", "were", "be", "been", "it", "its", "this", "that",
    "these", "those", "what", "which", "who", "whom", "when", "where", "why", "how", "did",
    "do", "does", "has", "have", "had", "not", "no", "into", "about", "than", "then",
}


def tokenize(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOPWORDS]


class Bm25Retriever(BaseRetriever):
    name = "bm25"

    def __init__(self, documents: list[Document]):
        super().__init__()
        self.documents = documents
        self.index = BM25Okapi([tokenize(document.text) for document in documents])

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        scores = self.index.get_scores(tokenize(query))
        best = np.argsort(scores)[::-1][:k]
        return [Hit(self.documents[i], float(scores[i])) for i in best if scores[i] > 0]

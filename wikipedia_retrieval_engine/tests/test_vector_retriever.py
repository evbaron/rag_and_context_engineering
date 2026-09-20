from __future__ import annotations

import unittest

from langchain_core.documents import Document

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever


class FakeVectorDB:
    def __init__(self, results: list[tuple[Document, float]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def similarity_search_with_score(
        self,
        query: str,
        *,
        k: int,
    ) -> list[tuple[Document, float]]:
        self.calls.append((query, k))
        return self.results[:k]


class VectorRetrieverArticleTests(unittest.TestCase):
    def test_get_articles_top_k_deduplicates_chunks_by_article(self) -> None:
        db = FakeVectorDB(
            [
                (
                    Document(
                        page_content="Best chunk from article A",
                        metadata={"source": "A.html#2", "article": "A.html"},
                    ),
                    0.10,
                ),
                (
                    Document(
                        page_content="Another chunk from article A",
                        metadata={"source": "A.html#7", "article": "A.html"},
                    ),
                    0.12,
                ),
                (
                    Document(
                        page_content="Best chunk from article B",
                        metadata={"source": "B.html#0", "article": "B.html"},
                    ),
                    0.20,
                ),
                (
                    Document(
                        page_content="Best chunk from article C",
                        metadata={"source": "C.html#4", "article": "C.html"},
                    ),
                    0.30,
                ),
            ]
        )
        retriever = VectorRetriever(db=db)

        hits = retriever.getArticlesTopK("question", k=3)

        self.assertEqual(db.calls, [("question", 12)])
        self.assertTrue(all(isinstance(hit, ArticleCandidate) for hit in hits))
        self.assertEqual(
            [hit.source_article for hit in hits],
            ["A.html", "B.html", "C.html"],
        )
        self.assertEqual([hit.rank for hit in hits], [1, 2, 3])
        self.assertEqual(hits[0].representative_chunk, "Best chunk from article A")
        self.assertEqual(hits[0].retrieval_query, "question")
        self.assertEqual(hits[0].raw_score, 0.10)
        self.assertEqual(hits[0].score_semantics, "lower_is_better")
        self.assertEqual(hits[0].discovered_by, "vector")

    def test_get_articles_top_k_uses_source_when_article_metadata_is_missing(self) -> None:
        db = FakeVectorDB(
            [
                (
                    Document(
                        page_content="Legacy-index chunk",
                        metadata={"source": "Legacy.html#3"},
                    ),
                    0.25,
                )
            ]
        )
        retriever = VectorRetriever(db=db)

        hits = retriever.getArticlesTopK("question", k=1, fetch_k=1)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].source_article, "Legacy.html")
        self.assertEqual(hits[0].representative_chunk, "Legacy-index chunk")
        self.assertEqual(hits[0].raw_score, 0.25)

    def test_get_articles_top_k_validates_candidate_counts(self) -> None:
        retriever = VectorRetriever(db=FakeVectorDB([]))

        with self.assertRaisesRegex(ValueError, "k must be at least 1"):
            retriever.getArticlesTopK("question", k=0)
        with self.assertRaisesRegex(ValueError, "fetch_k.*greater than or equal"):
            retriever.getArticlesTopK("question", k=3, fetch_k=2)


if __name__ == "__main__":
    unittest.main()

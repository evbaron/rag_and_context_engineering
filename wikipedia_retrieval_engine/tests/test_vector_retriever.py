from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from langchain_core.documents import Document

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.corpus import WikiChunk
from wikipedia_retrieval_engine.retrievers.vector import (
    VectorRetriever,
    build_or_load_section_db,
)


class FakeVectorDB:
    def __init__(self, results: list[tuple[Document, float]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, dict[str, Any] | None]] = []

    def similarity_search_with_score(
        self,
        query: str,
        *,
        k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        self.calls.append((query, k, filter))
        return self.results[:k]


class VectorRetrieverArticleTests(unittest.TestCase):
    def test_get_articles_top_k_deduplicates_chunks_by_article(self) -> None:
        db = FakeVectorDB(
            [
                (
                    Document(
                        page_content="Best chunk from article A",
                        metadata={
                            "source": "A.html#section-002-00",
                            "article": "A.html",
                            "section_title": "Results",
                            "section_path": "Tournament > Results",
                        },
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

        self.assertEqual(db.calls, [("question", 12, None)])
        self.assertTrue(all(isinstance(hit, ArticleCandidate) for hit in hits))
        self.assertEqual(
            [hit.source_article for hit in hits],
            ["A.html", "B.html", "C.html"],
        )
        self.assertEqual([hit.rank for hit in hits], [1, 2, 3])
        self.assertEqual(hits[0].representative_chunk, "Best chunk from article A")
        self.assertEqual(
            hits[0].representative_chunk_id,
            "A.html#section-002-00",
        )
        self.assertEqual(hits[0].section_title, "Results")
        self.assertEqual(hits[0].section_path, ["Tournament", "Results"])
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

    def test_get_article_sections_top_k_filters_to_one_article(self) -> None:
        document = Document(
            page_content="The winner is shown in this section.",
            metadata={
                "source": "Awards.html#Winners-0",
                "article": "Awards.html",
                "section_title": "Winners",
                "section_path": "Ceremony > Winners",
            },
        )
        db = FakeVectorDB([(document, 0.08)])
        retriever = VectorRetriever(db=db)

        hits = retriever.getArticleSectionsTopK(
            "Who won?",
            "Awards.html",
            k=2,
        )

        self.assertEqual(
            db.calls,
            [("Who won?", 2, {"article": "Awards.html"})],
        )
        self.assertEqual(hits, [(document, 0.08)])

    def test_get_article_sections_top_k_validates_inputs(self) -> None:
        retriever = VectorRetriever(db=FakeVectorDB([]))

        with self.assertRaisesRegex(ValueError, "query must not be empty"):
            retriever.getArticleSectionsTopK(" ", "Awards.html")
        with self.assertRaisesRegex(ValueError, "source_article must not be empty"):
            retriever.getArticleSectionsTopK("Who won?", " ")
        with self.assertRaisesRegex(ValueError, "k must be at least 1"):
            retriever.getArticleSectionsTopK("Who won?", "Awards.html", k=0)

    def test_get_exact_article_section_filters_article_and_heading(self) -> None:
        document = Document(
            page_content="The winner is shown in this section.",
            metadata={
                "source": "Awards.html#Winners-0",
                "article": "Awards.html",
                "section_title": "Winners and nominees",
            },
        )
        db = FakeVectorDB([(document, 0.04)])
        retriever = VectorRetriever(db=db)

        hits = retriever.getArticleSectionTopK(
            "Who won?",
            "Awards.html",
            "Winners and nominees",
            k=2,
        )

        self.assertEqual(
            db.calls,
            [
                (
                    "Who won?",
                    2,
                    {
                        "$and": [
                            {"article": {"$eq": "Awards.html"}},
                            {
                                "section_title": {
                                    "$eq": "Winners and nominees"
                                }
                            },
                        ]
                    },
                )
            ],
        )
        self.assertEqual(hits, [(document, 0.04)])

    def test_get_exact_article_section_validates_heading(self) -> None:
        retriever = VectorRetriever(db=FakeVectorDB([]))

        with self.assertRaisesRegex(ValueError, "section_title must not be empty"):
            retriever.getArticleSectionTopK("Who won?", "Awards.html", " ")

    def test_section_db_builder_uses_heading_chunks_when_cache_is_missing(self) -> None:
        section_chunk = WikiChunk(
            doc_id="Awards.html#section-000-00",
            source="Awards.html",
            title="Awards",
            text="Article: Awards\nSection: Winners\n\nWinner text",
            chunk_index=0,
            section_title="Winners",
            section_path=("Winners",),
        )
        fake_db = object()

        with TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing-section-index"
            with (
                patch(
                    "wikipedia_retrieval_engine.retrievers.vector.chroma_db_path",
                    return_value=missing_path,
                ),
                patch(
                    "wikipedia_retrieval_engine.retrievers.vector.load_wikipedia_section_chunks",
                    return_value=[section_chunk],
                ) as load_sections,
                patch(
                    "wikipedia_retrieval_engine.retrievers.vector.build_or_load_db",
                    return_value=fake_db,
                ) as build_db,
            ):
                result = build_or_load_section_db(
                    chroma_db_name="section-test",
                    max_section_chars=4000,
                    overlap=100,
                )

        self.assertIs(result, fake_db)
        load_sections.assert_called_once_with(
            None,
            max_section_chars=4000,
            overlap=100,
        )
        build_db.assert_called_once_with(
            wiki_dir=None,
            chroma_db_name="section-test",
            chunks=[section_chunk],
        )


if __name__ == "__main__":
    unittest.main()

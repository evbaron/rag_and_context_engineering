from __future__ import annotations

import unittest

from wikipedia_retrieval_engine.wiki_agents.agentic_models import ArticleReview, EvidenceItem
from wikipedia_retrieval_engine.wiki_agents.answer_context import (
    WHOLE_ARTICLE_STAGE,
    articles_to_send_whole,
    build_answer_evidence,
)

TEXTS = {"Bio.html": "Whole biography.", "Awards.html": "Whole awards list.", "Other.html": "Whole other."}


def _review(article: str, *, relevant: bool = True, table: bool = False) -> ArticleReview:
    return ArticleReview(
        source_article=article,
        relevant=relevant,
        reason="test",
        needs_table_reader=table,
    )


def _item(article: str, number: int, stage: str = "toc_selected_section") -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"{article}#{number}",
        source_article=article,
        content=f"{article} section {number}",
        metadata={"retrieval_stage": stage},
    )


def _state(reviews: list[ArticleReview], evidence: list[EvidenceItem]) -> dict:
    return {"question": "q", "article_reviews": reviews, "evidence": evidence}


def _ids(evidence: list[EvidenceItem]) -> list[str]:
    return [item.evidence_id for item in evidence]


class ArticlesToSendWholeTests(unittest.TestCase):
    def test_sections_rule_sends_nothing_whole(self) -> None:
        state = _state([_review("Bio.html")], [])

        self.assertEqual(articles_to_send_whole(state, "sections"), [])

    def test_per_question_sends_every_kept_article_when_no_table_is_needed(self) -> None:
        state = _state([_review("Bio.html"), _review("Other.html", relevant=False), _review("Awards.html")], [])

        self.assertEqual(articles_to_send_whole(state, "whole_per_question"), ["Bio.html", "Awards.html"])

    def test_per_question_sends_nothing_when_any_kept_article_needs_a_table(self) -> None:
        state = _state([_review("Bio.html"), _review("Awards.html", table=True)], [])

        self.assertEqual(articles_to_send_whole(state, "whole_per_question"), [])

    def test_per_article_sends_only_the_articles_without_a_table(self) -> None:
        state = _state([_review("Bio.html"), _review("Awards.html", table=True)], [])

        self.assertEqual(articles_to_send_whole(state, "whole_per_article"), ["Bio.html"])

    def test_table_ids_or_names_also_count_as_needing_a_table(self) -> None:
        by_id = ArticleReview(source_article="A.html", relevant=True, reason="t", relevant_table_ids=["t1"])
        by_name = ArticleReview(source_article="B.html", relevant=True, reason="t", relevant_table_names=["Winners"])

        self.assertEqual(articles_to_send_whole(_state([by_id, by_name], []), "whole_per_article"), [])

    def test_unknown_rule_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            articles_to_send_whole(_state([], []), "whole_everything")  # type: ignore[arg-type]


class BuildAnswerEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = [
            _item("Bio.html", 1),
            _item("Awards.html", 1),
            _item("Bio.html", 2, stage="broadened_article_sections"),
            _item("Awards.html", 2, stage="table_computation"),
            _item("Neighbor.html", 1, stage="graph_seeded_sections"),
        ]

    def test_sections_rule_returns_the_5_1_evidence_unchanged(self) -> None:
        state = _state([_review("Bio.html")], self.evidence)

        self.assertEqual(build_answer_evidence(state, "sections", TEXTS.get), self.evidence)

    def test_whole_article_replaces_an_articles_items_in_place(self) -> None:
        state = _state([_review("Bio.html"), _review("Awards.html")], self.evidence)

        evidence = build_answer_evidence(state, "whole_per_question", TEXTS.get)

        self.assertEqual(
            _ids(evidence),
            [f"{WHOLE_ARTICLE_STAGE}:Bio.html", f"{WHOLE_ARTICLE_STAGE}:Awards.html", "Neighbor.html#1"],
        )
        self.assertEqual(evidence[0].content, "Whole biography.")
        self.assertEqual(evidence[0].section_path, ["(whole article)"])
        self.assertEqual(evidence[0].metadata["retrieval_stage"], WHOLE_ARTICLE_STAGE)

    def test_per_article_keeps_the_table_articles_sections_and_computations(self) -> None:
        state = _state([_review("Bio.html"), _review("Awards.html", table=True)], self.evidence)

        evidence = build_answer_evidence(state, "whole_per_article", TEXTS.get)

        self.assertEqual(
            _ids(evidence),
            [f"{WHOLE_ARTICLE_STAGE}:Bio.html", "Awards.html#1", "Awards.html#2", "Neighbor.html#1"],
        )

    def test_per_question_leaves_a_mixed_question_unchanged(self) -> None:
        state = _state([_review("Bio.html"), _review("Awards.html", table=True)], self.evidence)

        self.assertEqual(build_answer_evidence(state, "whole_per_question", TEXTS.get), self.evidence)

    def test_article_without_text_keeps_its_sections(self) -> None:
        state = _state([_review("Bio.html"), _review("Awards.html")], self.evidence)

        evidence = build_answer_evidence(state, "whole_per_question", {"Bio.html": "Whole biography."}.get)

        self.assertEqual(
            _ids(evidence),
            [f"{WHOLE_ARTICLE_STAGE}:Bio.html", "Awards.html#1", "Awards.html#2", "Neighbor.html#1"],
        )

    def test_kept_article_without_evidence_is_appended(self) -> None:
        state = _state([_review("Bio.html"), _review("Other.html")], [_item("Bio.html", 1)])

        evidence = build_answer_evidence(state, "whole_per_question", TEXTS.get)

        self.assertEqual(
            _ids(evidence),
            [f"{WHOLE_ARTICLE_STAGE}:Bio.html", f"{WHOLE_ARTICLE_STAGE}:Other.html"],
        )


if __name__ == "__main__":
    unittest.main()

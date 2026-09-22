from __future__ import annotations

import unittest
from typing import get_type_hints

from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    ArticleReview,
    ArticleReviewBatch,
    AnswerVerification,
    EvidenceItem,
    TablePredicate,
    TableQueryPlan,
    initial_agent_state,
    retrieval_attempt_count,
    table_attempt_count,
)


class AgenticModelsTests(unittest.TestCase):
    def test_evidence_item_preserves_score_and_table_provenance(self) -> None:
        item = EvidenceItem(
            evidence_id="2020_NFL_draft.html#table-002:r1",
            source_article="2020_NFL_draft.html",
            content="Joe Burrow was pick 1 and is marked as a Pro Bowler.",
            evidence_type="table",
            retriever="table",
            rank=1,
            raw_score=0.12,
            score_semantics="lower_is_better",
            table_id="table-002",
            source_cells=["table-002:r1:Player", "table-002:r1:Pick"],
        )

        self.assertEqual(item.evidence_type, "table")
        self.assertEqual(item.score_semantics, "lower_is_better")
        self.assertEqual(len(item.source_cells), 2)

    def test_initial_agent_state_defaults_attempt_counts_to_zero(self) -> None:
        state = initial_agent_state("Who won?")
        self.assertEqual(state["question"], "Who won?")
        self.assertEqual(state["retrieval_attempts"], 0)
        self.assertEqual(state["table_attempts"], 0)
        self.assertEqual(retrieval_attempt_count({}), 0)
        self.assertEqual(retrieval_attempt_count({"question": "x"}), 0)
        self.assertEqual(table_attempt_count({}), 0)
        self.assertEqual(table_attempt_count({"question": "x"}), 0)

    def test_agent_state_annotations_resolve(self) -> None:
        annotations = get_type_hints(AgentState)
        self.assertIn("question", annotations)
        self.assertIn("retrieval_attempts", annotations)
        self.assertIs(annotations["retrieval_attempts"], int)
        self.assertIn("table_attempts", annotations)
        self.assertIs(annotations["table_attempts"], int)

        verification = AnswerVerification(
            supported=True,
            explanation="Every answer claim cites retrieved evidence.",
        )
        self.assertEqual(verification.unsupported_claims, [])

    def test_article_review_captures_section_and_table_decision(self) -> None:
        review = ArticleReview(
            source_article="96th Academy Awards",
            relevant=True,
            reason="Contains the winners and nominees needed by the question.",
            relevant_sections=["Winners and nominees"],
            relevant_table_names=["Awards"],
            needs_table_reader=True,
        )
        self.assertTrue(review.relevant)
        self.assertEqual(review.relevant_sections, ["Winners and nominees"])
        self.assertEqual(review.relevant_table_names, ["Awards"])
        self.assertTrue(review.needs_table_reader)

    def test_article_review_batch_groups_candidate_reviews(self) -> None:
        batch = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="96th Academy Awards",
                    relevant=True,
                    reason="Contains the requested winner information.",
                    relevant_sections=["Winners and nominees"],
                    relevant_table_names=["Awards"],
                    needs_table_reader=True,
                ),
                ArticleReview(
                    source_article="Academy Award",
                    relevant=False,
                    reason="General background does not answer the question.",
                ),
            ]
        )

        self.assertEqual(len(batch.reviews), 2)
        self.assertTrue(batch.reviews[0].relevant)
        self.assertFalse(batch.reviews[1].relevant)
        self.assertEqual(batch.reviews[1].relevant_sections, [])

    def test_table_query_plan_carries_deterministic_predicates(self) -> None:
        plan = TableQueryPlan(
            artifact_id="Scores.html::table-001",
            operation="filter",
            selected_columns=["Team", "Points"],
            predicates=[
                TablePredicate(column="Points", op="num_gte", value=1000),
            ],
        )

        self.assertEqual(plan.predicates[0].column, "Points")
        self.assertEqual(plan.predicates[0].op, "num_gte")


if __name__ == "__main__":
    unittest.main()

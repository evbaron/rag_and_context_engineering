from __future__ import annotations

import unittest
from datetime import datetime
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from langchain_core.language_models.chat_models import BaseChatModel

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agent_graph import (
    build_evidence_intake_graph,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    ArticleReview,
    ArticleReviewBatch,
    EvidenceAssessment,
    initial_agent_state,
)
from wikipedia_retrieval_engine.wiki_agents.run_logging import AgentRunLogger


class EvidenceIntakeGraphTests(unittest.TestCase):
    def test_graph_runs_retrieval_review_collection_and_assessment(self) -> None:
        candidate = ArticleCandidate(
            source_article="96th_Academy_Awards.html",
            representative_chunk="Oppenheimer won Best Picture.",
            representative_chunk_id="96th_Academy_Awards.html#section-004-00",
            section_title="Winners and nominees",
            section_path=["Awards", "Winners and nominees"],
            retrieval_query="Who won Best Picture?",
            discovered_by="vector",
            rank=1,
            raw_score=0.07,
            score_semantics="lower_is_better",
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = [candidate]

        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="96th_Academy_Awards.html",
                    relevant=True,
                    reason="The retrieved section contains the requested result.",
                )
            ]
        )
        assessment_runner = Mock()
        assessment_runner.invoke.return_value = EvidenceAssessment(
            ready_to_answer=True,
            supported_requirements=["The Best Picture winner is supported."],
            missing_requirements=[],
            retrieval_requests=[],
            table_requests=[],
            unresolved_conflicts=[],
            explanation="The evidence directly states the winner.",
        )
        llm = Mock(spec=BaseChatModel)

        def structured_output(schema: type, **kwargs):
            self.assertEqual(kwargs, {"method": "function_calling"})
            if schema is ArticleReviewBatch:
                return review_runner
            if schema is EvidenceAssessment:
                return assessment_runner
            raise AssertionError(f"Unexpected structured schema: {schema}")

        llm.with_structured_output.side_effect = structured_output

        with TemporaryDirectory() as directory:
            logger = AgentRunLogger(
                directory,
                started_at=datetime(2026, 9, 20, 1, 2, 3),
            )
            graph = build_evidence_intake_graph(retriever, llm, logger)
            result = graph.invoke(initial_agent_state("Who won Best Picture?"))
            log_files = list(logger.run_directory.glob("*.evidence.json"))

        self.assertEqual(result["retrieval_attempts"], 1)
        self.assertEqual(
            result["selected_articles"],
            ["96th_Academy_Awards.html"],
        )
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(
            result["evidence"][0].evidence_id,
            "96th_Academy_Awards.html#section-004-00",
        )
        self.assertTrue(result["assessment"].ready_to_answer)
        self.assertEqual(len(log_files), 1)


if __name__ == "__main__":
    unittest.main()

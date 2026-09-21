from __future__ import annotations

import unittest
from datetime import datetime
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.graph import GraphParams, WikiGraph
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agent_graph import (
    build_evidence_intake_graph,
    build_retrieval_benchmark_graph,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    ArticleReview,
    ArticleReviewBatch,
    EvidenceAssessment,
    RetrievalRequest,
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

    def test_retrieval_benchmark_runs_vector_graph_and_multistep_sections(self) -> None:
        candidate = ArticleCandidate(
            source_article="Seed.html",
            representative_chunk="The seed article identifies the event.",
            representative_chunk_id="Seed.html#section-001-00",
            section_title="Overview",
            section_path=["Overview"],
            retrieval_query="When did the related event occur?",
            discovered_by="vector",
            rank=1,
            raw_score=0.07,
            score_semantics="lower_is_better",
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = [candidate]
        retriever.getArticleSectionsTopK.return_value = [
            (
                Document(
                    page_content="The graph neighbor describes the event but not its date.",
                    metadata={
                        "source": "Neighbor.html#section-002-00",
                        "article": "Neighbor.html",
                        "section_title": "Event",
                        "section_path": "History > Event",
                    },
                ),
                0.09,
            )
        ]

        wiki_graph = Mock(spec=WikiGraph)
        wiki_graph.expand.return_value = [
            ("Neighbor.html", 1.1, ["link"]),
        ]
        multistep = Mock(spec=MultiStepRetriever)
        multistep.retrieve_with_reasoning.return_value = (
            [
                (
                    "Date_Source.html#section-003-00",
                    "The related event occurred on June 1, 2020.",
                    0.92,
                )
            ],
            "Find the exact event date.",
        )

        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="Seed.html",
                    relevant=True,
                    reason="The seed identifies the event.",
                )
            ]
        )
        assessment_runner = Mock()
        assessment_runner.invoke.side_effect = [
            EvidenceAssessment(
                ready_to_answer=False,
                supported_requirements=["The event is identified."],
                missing_requirements=["The date is missing."],
                retrieval_requests=[
                    RetrievalRequest(
                        missing_fact="The event date",
                        query="related event exact date",
                        preferred_retriever="graph",
                    )
                ],
                table_requests=[],
                unresolved_conflicts=[],
                explanation="Follow related articles.",
            ),
            EvidenceAssessment(
                ready_to_answer=False,
                supported_requirements=["The event is identified."],
                missing_requirements=["The exact date is still missing."],
                retrieval_requests=[
                    RetrievalRequest(
                        missing_fact="The exact event date",
                        query="related event June exact date",
                        preferred_retriever="vector",
                    )
                ],
                table_requests=[],
                unresolved_conflicts=[],
                explanation="Use targeted multi-step retrieval.",
            ),
            EvidenceAssessment(
                ready_to_answer=True,
                supported_requirements=[
                    "The event and its exact date are supported."
                ],
                missing_requirements=[],
                retrieval_requests=[],
                table_requests=[],
                unresolved_conflicts=[],
                explanation="The accumulated section evidence is sufficient.",
            ),
        ]
        llm = Mock(spec=BaseChatModel)

        def structured_output(schema: type, **kwargs):
            self.assertEqual(kwargs, {"method": "function_calling"})
            if schema is ArticleReviewBatch:
                return review_runner
            if schema is EvidenceAssessment:
                return assessment_runner
            raise AssertionError(f"Unexpected structured schema: {schema}")

        llm.with_structured_output.side_effect = structured_output
        graph_params = GraphParams(max_neighbors=2)

        with TemporaryDirectory() as directory:
            logger = AgentRunLogger(
                directory,
                started_at=datetime(2026, 9, 21, 1, 2, 3),
            )
            graph = build_retrieval_benchmark_graph(
                retriever,
                multistep,
                wiki_graph,
                llm,
                logger,
                graph_params=graph_params,
                sections_per_neighbor=2,
                multistep_hits_per_request=6,
            )
            result = graph.invoke(
                initial_agent_state("When did the related event occur?")
            )
            log_files = list(logger.run_directory.glob("*.evidence.json"))

        self.assertEqual(result["retrieval_attempts"], 3)
        self.assertEqual(len(result["assessment_history"]), 3)
        self.assertEqual(len(result["evidence"]), 3)
        self.assertEqual(
            [item.metadata["retrieval_stage"] for item in result["evidence"]],
            [
                "initial_article_retrieval",
                "graph_seeded_sections",
                "targeted_multistep_sections",
            ],
        )
        wiki_graph.expand.assert_called_once_with(["Seed.html"], graph_params)
        multistep.retrieve_with_reasoning.assert_called_once_with(
            "related event June exact date",
            k=6,
        )
        self.assertTrue(result["assessment"].ready_to_answer)
        self.assertEqual(len(log_files), 1)


if __name__ == "__main__":
    unittest.main()

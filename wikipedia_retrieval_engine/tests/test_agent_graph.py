from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.corpus import MarkdownArticleStore
from wikipedia_retrieval_engine.retrievers.graph import GraphParams, WikiGraph
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.utils.wiki_table_store import (
    TableArtifactStore,
    build_table_artifact_store,
)
from wikipedia_retrieval_engine.wiki_agents.agent_graph import (
    build_evidence_intake_graph,
    build_retrieval_benchmark_graph,
    make_retrieval_benchmark_router,
    retrieval_stage_name,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    ArticleReview,
    ArticleReviewBatch,
    EvidenceAssessment,
    RetrievalRequest,
    TablePredicate,
    TableQueryPlan,
    TableRequest,
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

        def sections_for(query: str, article: str, k: int):
            # The initial-stage deepen step retrieves inside the selected seed;
            # graph expansion retrieves inside the neighbor. Return distinct
            # sections per article so both contributions are visible.
            if article == "Seed.html":
                return [
                    (
                        Document(
                            page_content="Seed article detail about the event.",
                            metadata={
                                "source": "Seed.html#section-001-05",
                                "article": "Seed.html",
                                "section_title": "Detail",
                                "section_path": "Overview > Detail",
                            },
                        ),
                        0.05,
                    )
                ]
            if article == "Neighbor.html":
                return [
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
            return []

        retriever.getArticleSectionsTopK.side_effect = sections_for
        retriever.getArticleSectionTopK.side_effect = (
            lambda query, article, section_title, k: sections_for(query, article, k)
        )

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
                    relevant_sections=["Overview"],
                )
            ]
        )
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {
            "sections": [{"level": 2, "id": "Overview", "title": "Overview"}],
            "tables": [],
        }
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
                markdown_store=markdown_store,
                table_store=Mock(spec=TableArtifactStore),
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
                "toc_selected_section",
                "graph_seeded_sections",
                "targeted_multistep_sections",
            ],
        )
        # The TOC review judged the article from its section list, not a snippet.
        markdown_store.load_metadata.assert_called_with("Seed.html")
        wiki_graph.expand.assert_called_once_with(["Seed.html"], graph_params)
        multistep.retrieve_with_reasoning.assert_called_once_with(
            "related event June exact date",
            k=6,
        )
        self.assertTrue(result["assessment"].ready_to_answer)
        self.assertEqual(len(log_files), 1)


class ConfigurableRetrieverTests(unittest.TestCase):
    def test_terminal_stage_name_uses_configured_retriever_sequence(self) -> None:
        self.assertEqual(
            retrieval_stage_name(
                1,
                initial_retriever="multistep_entity",
                repeated_retrievers=("multistep", "graph_seeded"),
            ),
            "multistep_entity_initial",
        )
        self.assertEqual(
            retrieval_stage_name(
                2,
                initial_retriever="vector",
                repeated_retrievers=("multistep", "graph_seeded"),
            ),
            "targeted_multistep_sections",
        )
        self.assertEqual(
            retrieval_stage_name(
                3,
                initial_retriever="vector",
                repeated_retrievers=("multistep", "graph_seeded"),
            ),
            "graph_seeded_sections",
        )

    def test_router_follows_configured_repeated_sequence(self) -> None:
        not_ready = EvidenceAssessment(
            ready_to_answer=False,
            missing_requirements=["x"],
            retrieval_requests=[RetrievalRequest(missing_fact="x", query="x")],
            explanation="not ready",
        )
        ready = EvidenceAssessment(ready_to_answer=True, explanation="ready")

        one_stage = make_retrieval_benchmark_router(("graph_seeded",))
        self.assertEqual(
            one_stage({"assessment": not_ready, "retrieval_attempts": 1}),
            "retrieve_graph_seeded_sections",
        )
        # Only one repeated stage configured -> finish after it.
        self.assertEqual(
            one_stage({"assessment": not_ready, "retrieval_attempts": 2}),
            "finish",
        )
        # Ready short-circuits regardless of attempt count.
        self.assertEqual(
            one_stage({"assessment": ready, "retrieval_attempts": 1}),
            "finish",
        )

        two_stage = make_retrieval_benchmark_router(("graph_seeded", "multistep"))
        self.assertEqual(
            two_stage({"assessment": not_ready, "retrieval_attempts": 2}),
            "retrieve_multistep_sections",
        )

    def test_router_prioritizes_table_work_and_honors_its_budget(self) -> None:
        table_request = TableRequest(
            missing_fact="Teams with at least 1,000 points",
            source_article="Scores.html",
            table_id="Scores.html::table-001",
            operation="filter",
            columns_needed=["Team", "Points"],
        )
        table_only = EvidenceAssessment(
            ready_to_answer=False,
            missing_requirements=["The qualifying rows are not computed."],
            table_requests=[table_request],
            explanation="Run the deterministic table executor.",
        )
        table_and_retrieval = table_only.model_copy(
            update={
                "retrieval_requests": [
                    RetrievalRequest(missing_fact="More context", query="scores")
                ]
            }
        )
        router = make_retrieval_benchmark_router(
            ("graph_seeded",),
            max_table_rounds=1,
        )

        self.assertEqual(
            router(
                {
                    "assessment": table_only,
                    "retrieval_attempts": 1,
                    "table_attempts": 0,
                }
            ),
            "compute_requested_tables",
        )
        self.assertEqual(
            router(
                {
                    "assessment": table_only,
                    "retrieval_attempts": 1,
                    "table_attempts": 1,
                }
            ),
            "finish",
        )
        self.assertEqual(
            router(
                {
                    "assessment": table_and_retrieval,
                    "retrieval_attempts": 1,
                    "table_attempts": 1,
                }
            ),
            "retrieve_graph_seeded_sections",
        )

    def test_graph_executes_table_request_then_reassesses(self) -> None:
        article_html = """
        <div class="mw-parser-output">
          <h2>Scores</h2>
          <table class="wikitable"><caption>Season scores</caption>
            <tr><th>Team</th><th>Points</th></tr>
            <tr><td>Team A</td><td>1,200</td></tr>
            <tr><td>Team B</td><td>800</td></tr>
          </table>
        </div>
        """
        candidate = ArticleCandidate(
            source_article="Scores.html",
            representative_chunk="The article contains season scores.",
            representative_chunk_id="Scores.html#section-001-00",
            section_title="Scores",
            section_path=["Scores"],
            retrieval_query="Which teams scored at least 1,000 points?",
            discovered_by="vector",
            rank=1,
            raw_score=0.04,
            score_semantics="lower_is_better",
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = [candidate]
        retriever.getArticleSectionTopK.return_value = [
            (
                Document(
                    page_content="The season scores appear in the table.",
                    metadata={
                        "source": "Scores.html#section-001-00",
                        "article": "Scores.html",
                        "section_title": "Scores",
                        "section_path": "Scores",
                    },
                ),
                0.04,
            )
        ]
        multistep = Mock(spec=MultiStepRetriever)
        wiki_graph = Mock(spec=WikiGraph)
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {
            "sections": [{"level": 2, "id": "Scores", "title": "Scores"}],
            "tables": [],
        }

        with TemporaryDirectory() as directory:
            wiki_dir = Path(directory) / "Wikipedia Library"
            wiki_dir.mkdir()
            (wiki_dir / "Scores.html").write_text(article_html, encoding="utf-8")
            table_store = build_table_artifact_store(
                wiki_dir,
                Path(directory) / "table_artifacts",
            )
            table_entry = table_store.list_tables("Scores.html")[0]

            review_runner = Mock()
            review_runner.invoke.return_value = ArticleReviewBatch(
                reviews=[
                    ArticleReview(
                        source_article="Scores.html",
                        relevant=True,
                        reason="The Scores section contains the required rows.",
                        relevant_sections=["Scores"],
                        relevant_table_ids=[table_entry.artifact_id],
                        needs_table_reader=True,
                    )
                ]
            )
            assessment_runner = Mock()
            assessment_runner.invoke.side_effect = [
                EvidenceAssessment(
                    ready_to_answer=False,
                    supported_requirements=["The source table is present."],
                    missing_requirements=["Qualifying rows must be filtered."],
                    table_requests=[
                        TableRequest(
                            missing_fact="Teams with at least 1,000 points",
                            source_article="Scores.html",
                            table_id=table_entry.artifact_id,
                            operation="filter",
                            columns_needed=["Team", "Points"],
                        )
                    ],
                    explanation="Compute the numeric threshold.",
                ),
                EvidenceAssessment(
                    ready_to_answer=True,
                    supported_requirements=["The filtered row is computed."],
                    explanation="The computed table evidence is sufficient.",
                ),
            ]
            planner_runner = Mock()
            planner_runner.invoke.return_value = TableQueryPlan(
                artifact_id=table_entry.artifact_id,
                operation="filter",
                selected_columns=["Team", "Points"],
                predicates=[
                    TablePredicate(column="Points", op="num_gte", value=1000)
                ],
            )
            llm = Mock(spec=BaseChatModel)

            def structured_output(schema: type, **kwargs):
                self.assertEqual(kwargs, {"method": "function_calling"})
                if schema is ArticleReviewBatch:
                    return review_runner
                if schema is EvidenceAssessment:
                    return assessment_runner
                if schema is TableQueryPlan:
                    return planner_runner
                raise AssertionError(f"Unexpected structured schema: {schema}")

            llm.with_structured_output.side_effect = structured_output
            logger = AgentRunLogger(
                directory,
                started_at=datetime(2026, 9, 22, 1, 2, 3),
            )
            graph = build_retrieval_benchmark_graph(
                retriever,
                multistep,
                wiki_graph,
                llm,
                logger,
                markdown_store=markdown_store,
                table_store=table_store,
                repeated_retrievers=(),
                max_table_rounds=1,
            )
            result = graph.invoke(
                initial_agent_state("Which teams scored at least 1,000 points?")
            )
            log_files = list(logger.run_directory.glob("*.evidence.json"))

        computed = [
            item
            for item in result["evidence"]
            if item.metadata.get("retrieval_stage") == "table_computation"
        ]
        self.assertEqual(result["table_attempts"], 1)
        self.assertEqual(len(result["assessment_history"]), 2)
        self.assertTrue(result["assessment"].ready_to_answer)
        self.assertEqual(len(computed), 1)
        self.assertIn("Team A", computed[0].content)
        self.assertNotIn('"Team": "Team B"', computed[0].content)
        self.assertTrue(computed[0].source_cells)
        self.assertEqual(len(log_files), 1)

    def test_multistep_initial_decomposes_before_retrieval(self) -> None:
        candidate = ArticleCandidate(
            source_article="Barack_Obama.html",
            representative_chunk="Obama served as the 44th president.",
            representative_chunk_id="Barack_Obama.html#section-000-00",
            section_title="Lead",
            section_path=["Lead"],
            retrieval_query="Barack Obama",
            discovered_by="vector",
            rank=1,
            raw_score=0.30,
            score_semantics="lower_is_better",
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = [candidate]
        retriever.getArticleSectionsTopK.return_value = [
            (
                Document(
                    page_content="Obama detail section.",
                    metadata={
                        "source": "Barack_Obama.html#section-001-00",
                        "article": "Barack_Obama.html",
                        "section_title": "Presidency",
                        "section_path": "Presidency",
                    },
                ),
                0.10,
            )
        ]
        multistep = Mock(spec=MultiStepRetriever)
        multistep.decompose.return_value = (["Barack Obama"], "")
        wiki_graph = Mock(spec=WikiGraph)
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {"sections": [], "tables": []}

        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="Barack_Obama.html",
                    relevant=True,
                    reason="Names the person.",
                )
            ]
        )
        assess_runner = Mock()
        assess_runner.invoke.return_value = EvidenceAssessment(
            ready_to_answer=True,
            supported_requirements=["The connection is supported."],
            explanation="Sufficient.",
        )
        llm = Mock(spec=BaseChatModel)

        def structured_output(schema: type, **kwargs):
            if schema is ArticleReviewBatch:
                return review_runner
            if schema is EvidenceAssessment:
                return assess_runner
            raise AssertionError(f"Unexpected schema: {schema}")

        llm.with_structured_output.side_effect = structured_output

        with TemporaryDirectory() as directory:
            logger = AgentRunLogger(
                directory, started_at=datetime(2026, 9, 21, 1, 2, 3)
            )
            graph = build_retrieval_benchmark_graph(
                retriever,
                multistep,
                wiki_graph,
                llm,
                logger,
                markdown_store=markdown_store,
                table_store=Mock(spec=TableArtifactStore),
                initial_retriever="multistep",
                repeated_retrievers=("graph_seeded",),
            )
            result = graph.invoke(
                initial_agent_state(
                    "Which person connects Bill Clinton and Barack Obama?"
                )
            )

        multistep.decompose.assert_called_once()
        self.assertEqual(result["retrieval_attempts"], 1)
        self.assertTrue(result["assessment"].ready_to_answer)
        self.assertIn(
            "Barack_Obama.html",
            [item.source_article for item in result["evidence"]],
        )

    def test_multistep_entity_initial_uses_entity_decomposition(self) -> None:
        candidate = ArticleCandidate(
            source_article="Barack_Obama.html",
            representative_chunk="Obama served as the 44th president.",
            representative_chunk_id="Barack_Obama.html#section-000-00",
            section_title="Lead",
            section_path=["Lead"],
            retrieval_query="Barack Obama",
            discovered_by="vector",
            rank=1,
            raw_score=0.30,
            score_semantics="lower_is_better",
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = [candidate]
        retriever.getArticleSectionsTopK.return_value = [
            (
                Document(
                    page_content="Obama detail section.",
                    metadata={
                        "source": "Barack_Obama.html#section-001-00",
                        "article": "Barack_Obama.html",
                        "section_title": "Presidency",
                        "section_path": "Presidency",
                    },
                ),
                0.10,
            )
        ]
        multistep = Mock(spec=MultiStepRetriever)
        multistep.decompose_entities.return_value = (["Barack Obama"], "")
        wiki_graph = Mock(spec=WikiGraph)
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {"sections": [], "tables": []}

        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="Barack_Obama.html",
                    relevant=True,
                    reason="Names the person.",
                )
            ]
        )
        assess_runner = Mock()
        assess_runner.invoke.return_value = EvidenceAssessment(
            ready_to_answer=True,
            supported_requirements=["Supported."],
            explanation="Sufficient.",
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.side_effect = (
            lambda schema, **kw: review_runner
            if schema is ArticleReviewBatch
            else assess_runner
        )

        with TemporaryDirectory() as directory:
            logger = AgentRunLogger(
                directory, started_at=datetime(2026, 9, 21, 1, 2, 3)
            )
            graph = build_retrieval_benchmark_graph(
                retriever,
                multistep,
                wiki_graph,
                llm,
                logger,
                markdown_store=markdown_store,
                table_store=Mock(spec=TableArtifactStore),
                initial_retriever="multistep_entity",
                repeated_retrievers=("graph_seeded",),
            )
            graph.invoke(
                initial_agent_state(
                    "Which person connects Bill Clinton and Barack Obama?"
                )
            )

        multistep.decompose_entities.assert_called_once()
        multistep.decompose.assert_not_called()


if __name__ == "__main__":
    unittest.main()

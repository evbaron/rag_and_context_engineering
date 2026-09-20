import unittest
from unittest.mock import Mock

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    ArticleReview,
    ArticleReviewBatch,
    EvidenceAssessment,
    RetrievalRequest,
    TableRequest,
)
from wikipedia_retrieval_engine.wiki_agents.retrieval_nodes import (
    assess_evidence,
    article_review_update,
    collect_initial_evidence,
    retrieve_initial_articles,
    retrieve_selected_article_sections,
    review_article_candidates,
    route_after_evidence_assessment,
)


class RetrievalNodesTests(unittest.TestCase):
    def test_retrieve_initial_articles_returns_partial_update(self) -> None:
        candidate = ArticleCandidate(
            source_article="Academy Awards",
            representative_chunk="The Academy Awards are presented annually.",
            retrieval_query="Who won the Academy Award?",
            discovered_by="vector",
            rank=1,
            raw_score=0.15,
            score_semantics="lower_is_better",
        )

        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = [candidate]

        state: AgentState = {
            "question": "  Who won the Academy Award?  ",
            "retrieval_attempts": 0,
        }

        update = retrieve_initial_articles(state, retriever)

        retriever.getArticlesTopK.assert_called_once_with(
            "Who won the Academy Award?",
            k=3,
        )

        self.assertEqual(update["article_candidates"], [candidate])
        self.assertEqual(update["retrieval_attempts"], 1)

        # The node returns only its changes, not the entire state.
        self.assertNotIn("question", update)

    def test_article_review_update_separates_selected_and_rejected(self) -> None:
        review_batch = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="96th Academy Awards",
                    relevant=True,
                    reason="Contains the requested winner information.",
                    relevant_sections=["Winners and nominees"],
                    needs_table_reader=True,
                ),
                ArticleReview(
                    source_article="Academy Award",
                    relevant=False,
                    reason="Only provides general background.",
                ),
            ]
        )

        update = article_review_update(review_batch)

        self.assertEqual(
            update["selected_articles"],
            ["96th Academy Awards"],
        )
        self.assertEqual(
            update["rejected_articles"],
            ["Academy Award"],
        )
        self.assertEqual(update["article_reviews"], review_batch.reviews)

    def test_review_article_candidates_uses_structured_output(self) -> None:
        candidate = ArticleCandidate(
            source_article="96th Academy Awards",
            representative_chunk="The winners are listed by category in a table.",
            retrieval_query="Who won best picture?",
            discovered_by="vector",
            rank=1,
            raw_score=0.1,
            score_semantics="lower_is_better",
        )
        review_batch = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="96th Academy Awards",
                    relevant=True,
                    reason="The excerpt contains the requested award results.",
                    needs_table_reader=True,
                )
            ]
        )

        structured_reviewer = Mock()
        structured_reviewer.invoke.return_value = review_batch
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_reviewer

        state: AgentState = {
            "question": "Who won best picture?",
            "article_candidates": [candidate],
        }

        update = review_article_candidates(state, llm)

        llm.with_structured_output.assert_called_once_with(
            ArticleReviewBatch,
            method="function_calling",
        )
        structured_reviewer.invoke.assert_called_once()
        messages = structured_reviewer.invoke.call_args.args[0]
        self.assertIn("Who won best picture?", messages[1].content)
        self.assertIn("96th Academy Awards", messages[1].content)
        self.assertEqual(update["selected_articles"], ["96th Academy Awards"])
        self.assertEqual(update["rejected_articles"], [])

    def test_review_article_candidates_rejects_incomplete_llm_output(self) -> None:
        candidate = ArticleCandidate(
            source_article="96th Academy Awards",
            representative_chunk="The winners are listed by category in a table.",
            retrieval_query="Who won best picture?",
            discovered_by="vector",
            rank=1,
            raw_score=0.1,
            score_semantics="lower_is_better",
        )

        structured_reviewer = Mock()
        structured_reviewer.invoke.return_value = ArticleReviewBatch()
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_reviewer

        state: AgentState = {
            "question": "Who won best picture?",
            "article_candidates": [candidate],
        }

        with self.assertRaisesRegex(
            ValueError,
            "must return exactly one review",
        ):
            review_article_candidates(state, llm)

    def test_retrieve_selected_article_sections_creates_evidence(self) -> None:
        document = Document(
            page_content="Oppenheimer won Best Picture.",
            metadata={
                "source": "96th_Academy_Awards.html#Winners-0",
                "article": "96th_Academy_Awards.html",
                "section_title": "Winners and nominees",
                "section_path": "Awards > Winners and nominees",
            },
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionsTopK.return_value = [(document, 0.07)]
        state: AgentState = {
            "question": "Who won Best Picture?",
            "selected_articles": ["96th_Academy_Awards.html"],
        }

        update = retrieve_selected_article_sections(state, retriever)

        retriever.getArticleSectionsTopK.assert_called_once_with(
            "Who won Best Picture?",
            "96th_Academy_Awards.html",
            k=3,
        )
        evidence = update["evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(
            evidence[0].evidence_id,
            "96th_Academy_Awards.html#Winners-0",
        )
        self.assertEqual(
            evidence[0].section_path,
            ["Awards", "Winners and nominees"],
        )
        self.assertEqual(evidence[0].retriever, "vector")
        self.assertEqual(evidence[0].score_semantics, "lower_is_better")

    def test_collect_initial_evidence_uses_selected_representative_chunks(self) -> None:
        selected = ArticleCandidate(
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
        rejected = ArticleCandidate(
            source_article="Academy_Award.html",
            representative_chunk="General award background.",
            representative_chunk_id="Academy_Award.html#section-000-00",
            section_title="History",
            section_path=["History"],
            retrieval_query="Who won Best Picture?",
            discovered_by="vector",
            rank=2,
            raw_score=0.15,
            score_semantics="lower_is_better",
        )
        state: AgentState = {
            "question": "Who won Best Picture?",
            "article_candidates": [selected, rejected],
            "selected_articles": ["96th_Academy_Awards.html"],
        }

        update = collect_initial_evidence(state)

        evidence = update["evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(
            evidence[0].evidence_id,
            "96th_Academy_Awards.html#section-004-00",
        )
        self.assertEqual(evidence[0].title, "Winners and nominees")
        self.assertEqual(
            evidence[0].metadata["retrieval_stage"],
            "initial_article_retrieval",
        )

    def test_assess_evidence_uses_structured_output(self) -> None:
        assessment = EvidenceAssessment(
            ready_to_answer=True,
            supported_requirements=["The Best Picture winner is supported."],
            missing_requirements=[],
            retrieval_requests=[],
            table_requests=[],
            unresolved_conflicts=[],
            explanation="The retrieved section directly states the winner.",
        )
        structured_assessor = Mock()
        structured_assessor.invoke.return_value = assessment
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_assessor
        state: AgentState = {
            "question": "Who won Best Picture?",
            "article_reviews": [
                ArticleReview(
                    source_article="96th_Academy_Awards.html",
                    relevant=True,
                    reason="Contains the award results.",
                )
            ],
            "evidence": [],
        }

        update = assess_evidence(state, llm)

        llm.with_structured_output.assert_called_once_with(
            EvidenceAssessment,
            method="function_calling",
        )
        structured_assessor.invoke.assert_called_once()
        messages = structured_assessor.invoke.call_args.args[0]
        self.assertIn("Who won Best Picture?", messages[1].content)
        self.assertEqual(update["assessment"], assessment)

    def test_route_after_evidence_assessment_selects_each_branch(self) -> None:
        ready = EvidenceAssessment(
            ready_to_answer=True,
            supported_requirements=["All facts are supported."],
            missing_requirements=[],
            retrieval_requests=[],
            table_requests=[],
            unresolved_conflicts=[],
            explanation="Ready.",
        )
        table = EvidenceAssessment(
            ready_to_answer=False,
            supported_requirements=[],
            missing_requirements=["The winning row is missing."],
            retrieval_requests=[],
            table_requests=[
                TableRequest(
                    missing_fact="The winning film",
                    source_article="96th_Academy_Awards.html",
                    operation="lookup",
                    columns_needed=["Category", "Winner"],
                )
            ],
            unresolved_conflicts=[],
            explanation="Read the awards table.",
        )
        retrieval = EvidenceAssessment(
            ready_to_answer=False,
            supported_requirements=[],
            missing_requirements=["The ceremony date is missing."],
            retrieval_requests=[
                RetrievalRequest(
                    missing_fact="The ceremony date",
                    query="96th Academy Awards ceremony date",
                    keywords=["ceremony", "date"],
                    preferred_retriever="graph",
                )
            ],
            table_requests=[],
            unresolved_conflicts=[],
            explanation="Retrieve another relevant section or article.",
        )

        self.assertEqual(
            route_after_evidence_assessment({"assessment": ready}),
            "ready_to_answer",
        )
        self.assertEqual(
            route_after_evidence_assessment({"assessment": table}),
            "need_table_reader",
        )
        self.assertEqual(
            route_after_evidence_assessment({"assessment": retrieval}),
            "need_more_evidence",
        )


if __name__ == "__main__":
    unittest.main()

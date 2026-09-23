import unittest
from unittest.mock import Mock

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.corpus import MarkdownArticleStore
from wikipedia_retrieval_engine.retrievers.graph import GraphParams, WikiGraph
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.utils.wiki_table_parser import (
    CellAnnotation,
    NormalizedCell,
    NormalizedTable,
    TableLegend,
)
from wikipedia_retrieval_engine.utils.wiki_table_store import (
    TableArtifactStore,
    TableCatalogEntry,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    ArticleReview,
    ArticleReviewBatch,
    EvidenceAssessment,
    EvidenceItem,
    RetrievalRequest,
    TableRequest,
)
from wikipedia_retrieval_engine.wiki_agents.retrieval_nodes import (
    assess_evidence,
    article_review_update,
    collect_initial_evidence,
    load_selected_sections,
    load_selected_tables,
    retrieve_broadened_article_sections,
    retrieve_graph_seeded_evidence,
    retrieve_initial_articles,
    retrieve_initial_articles_decomposed,
    retrieve_selected_article_sections,
    review_and_select_from_toc,
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

    def test_graph_seeded_retrieval_adds_only_relevant_neighbor_sections(self) -> None:
        existing = EvidenceItem(
            evidence_id="Seed.html#section-001-00",
            source_article="Seed.html",
            content="Initial vector evidence.",
            retrieval_query="Original question",
            retriever="vector",
        )
        assessment = EvidenceAssessment(
            ready_to_answer=False,
            supported_requirements=["The seed entity is identified."],
            missing_requirements=["The related event date is missing."],
            retrieval_requests=[
                RetrievalRequest(
                    missing_fact="The related event date",
                    query="related event exact date",
                    target_articles=[],
                    keywords=["event", "date"],
                    preferred_retriever="graph",
                )
            ],
            table_requests=[],
            unresolved_conflicts=[],
            explanation="Follow related articles and retrieve the date section.",
        )
        state: AgentState = {
            "question": "Original question",
            "retrieval_attempts": 1,
            "selected_articles": ["Seed.html"],
            "evidence": [existing],
            "assessment": assessment,
        }
        graph_params = GraphParams(max_neighbors=2)
        graph = Mock(spec=WikiGraph)
        graph.expand.return_value = [
            ("Neighbor.html", 1.25, ["link", "entity:Event(2)"])
        ]
        section = Document(
            page_content="The related event occurred on June 1, 2020.",
            metadata={
                "source": "Neighbor.html#section-004-00",
                "article": "Neighbor.html",
                "section_title": "History",
                "section_path": "Events > History",
            },
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionsTopK.return_value = [(section, 0.08)]

        update = retrieve_graph_seeded_evidence(
            state,
            retriever,
            graph,
            graph_params=graph_params,
            sections_per_neighbor=2,
        )

        graph.expand.assert_called_once_with(["Seed.html"], graph_params)
        retriever.getArticleSectionsTopK.assert_called_once_with(
            "related event exact date",
            "Neighbor.html",
            k=2,
        )
        self.assertEqual(update["retrieval_attempts"], 2)
        self.assertEqual(len(update["evidence"]), 2)
        graph_evidence = update["evidence"][1]
        self.assertEqual(graph_evidence.evidence_type, "graph")
        self.assertEqual(graph_evidence.source_article, "Neighbor.html")
        self.assertEqual(graph_evidence.section_path, ["Events", "History"])
        self.assertEqual(graph_evidence.retriever, "graph")
        self.assertEqual(
            graph_evidence.metadata["retrieval_stage"],
            "graph_seeded_sections",
        )
        self.assertEqual(
            graph_evidence.metadata["seed_articles"],
            ["Seed.html"],
        )

    def test_retrieve_initial_articles_decomposed_merges_subquery_candidates(
        self,
    ) -> None:
        multistep = Mock()
        multistep.decompose.return_value = (["Barack Obama", "Bill Clinton"], "")

        def article(name: str, query: str, distance: float, rank: int = 1):
            return ArticleCandidate(
                source_article=name,
                retrieval_query=query,
                discovered_by="vector",
                rank=rank,
                raw_score=distance,
                score_semantics="lower_is_better",
            )

        def top_k(query: str, k: int):
            if query == "Barack Obama":
                return [article("Barack_Obama.html", query, 0.30)]
            if query == "Bill Clinton":
                return [article("Bill_Clinton.html", query, 0.20)]
            # the full-question query returns the blunt result that buries Obama
            return [
                article("Bill_Clinton.html", query, 0.25),
                article("George_W._Bush.html", query, 0.40, rank=2),
            ]

        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.side_effect = top_k

        update = retrieve_initial_articles_decomposed(
            {
                "question": "Which person connects Bill Clinton and Barack Obama?",
                "retrieval_attempts": 0,
            },
            retriever,
            multistep,
            top_k=4,
            per_subquery_k=2,
            max_candidates=8,
        )

        articles = [c.source_article for c in update["article_candidates"]]
        # Both named entities are surfaced (Obama would be buried by the blunt query).
        self.assertIn("Barack_Obama.html", articles)
        self.assertIn("Bill_Clinton.html", articles)
        # Deduplicated across queries, keeping the best (lowest) distance.
        self.assertEqual(len(articles), len(set(articles)))
        self.assertEqual(articles[0], "Bill_Clinton.html")  # 0.20 is closest
        self.assertEqual(update["article_candidates"][0].rank, 1)
        self.assertEqual(update["retrieval_attempts"], 1)
        multistep.decompose.assert_called_once()

    def test_decompose_entities_parses_full_name_queries(self) -> None:
        llm = Mock()
        llm.invoke.return_value = Mock(
            content=(
                "Original Query: q\n"
                'Sub-queries: ["Bill Clinton", "Barack Obama"]\n'
                "Reasoning instructions: NONE"
            )
        )
        retriever = MultiStepRetriever(llm=llm, db=Mock())

        queries, reasoning = retriever.decompose_entities(
            "Which person connects Bill Clinton and Barack Obama?"
        )

        self.assertEqual(queries, ["Bill Clinton", "Barack Obama"])
        self.assertEqual(reasoning, "")

    def test_decomposed_entity_mode_uses_entity_decomposition(self) -> None:
        multistep = Mock(spec=MultiStepRetriever)
        multistep.decompose_entities.return_value = (["Barack Obama"], "")

        def top_k(query: str, k: int):
            if query == "Barack Obama":
                return [
                    ArticleCandidate(
                        source_article="Barack_Obama.html",
                        retrieval_query=query,
                        discovered_by="vector",
                        rank=1,
                        raw_score=0.30,
                        score_semantics="lower_is_better",
                    )
                ]
            return [
                ArticleCandidate(
                    source_article="Bill_Clinton.html",
                    retrieval_query=query,
                    discovered_by="vector",
                    rank=1,
                    raw_score=0.25,
                    score_semantics="lower_is_better",
                )
            ]

        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.side_effect = top_k

        update = retrieve_initial_articles_decomposed(
            {
                "question": "Which person connects Bill Clinton and Barack Obama?",
                "retrieval_attempts": 0,
            },
            retriever,
            multistep,
            decompose_mode="entity",
        )

        multistep.decompose_entities.assert_called_once()
        multistep.decompose.assert_not_called()
        articles = [c.source_article for c in update["article_candidates"]]
        self.assertIn("Barack_Obama.html", articles)
        self.assertIn("Bill_Clinton.html", articles)

    def test_retrieve_initial_articles_forwards_top_k(self) -> None:
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticlesTopK.return_value = []

        update = retrieve_initial_articles(
            {"question": "Who won?", "retrieval_attempts": 0},
            retriever,
            top_k=4,
        )

        retriever.getArticlesTopK.assert_called_once_with("Who won?", k=4)
        self.assertEqual(update["retrieval_attempts"], 1)

    def test_graph_seeded_retrieval_ranks_and_caps_neighbor_sections(self) -> None:
        assessment = EvidenceAssessment(
            ready_to_answer=False,
            supported_requirements=[],
            missing_requirements=["Need the related fact."],
            retrieval_requests=[
                RetrievalRequest(
                    missing_fact="related fact",
                    query="related fact query",
                    preferred_retriever="graph",
                )
            ],
            table_requests=[],
            unresolved_conflicts=[],
            explanation="Expand and retrieve the missing fact.",
        )
        state: AgentState = {
            "question": "Original question",
            "retrieval_attempts": 1,
            "selected_articles": ["Seed.html"],
            "evidence": [],
            "assessment": assessment,
        }
        graph = Mock(spec=WikiGraph)
        # Two neighbors: one on-topic (close match), one adjacent-but-wrong (far).
        graph.expand.return_value = [
            ("Good.html", 2.0, ["link"]),
            ("Wrong.html", 1.9, ["link"]),
        ]
        good = Document(
            page_content="On-topic neighbor content.",
            metadata={
                "source": "Good.html#s1",
                "article": "Good.html",
                "section_title": "A",
                "section_path": "A",
            },
        )
        wrong = Document(
            page_content="Off-topic sibling content.",
            metadata={
                "source": "Wrong.html#s1",
                "article": "Wrong.html",
                "section_title": "B",
                "section_path": "B",
            },
        )

        def sections_for(query: str, article: str, k: int):
            if article == "Good.html":
                return [(good, 0.05)]
            if article == "Wrong.html":
                return [(wrong, 0.90)]
            return []

        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionsTopK.side_effect = sections_for

        update = retrieve_graph_seeded_evidence(
            state,
            retriever,
            graph,
            graph_params=GraphParams(max_neighbors=2),
            sections_per_neighbor=2,
            max_graph_sections=1,
        )

        added = [
            item
            for item in update["evidence"]
            if item.metadata.get("retrieval_stage") == "graph_seeded_sections"
        ]
        # Only the single globally-best section survives the cap; the far,
        # off-topic neighbor is dropped rather than contributing a distractor.
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].source_article, "Good.html")
        self.assertEqual(update["retrieval_attempts"], 2)

    def test_review_and_select_from_toc_judges_by_toc_not_snippet(self) -> None:
        candidate = ArticleCandidate(
            source_article="68th_Academy_Awards.html",
            retrieval_query="68th Academy Awards",
            discovered_by="vector",
            rank=1,
            raw_score=0.30,
            score_semantics="lower_is_better",
        )
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {
            "sections": [
                {"title": "Winners and nominees"},
                {"title": "See also"},
            ],
            "tables": [{"caption": "Winners"}],
        }
        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="68th_Academy_Awards.html",
                    relevant=True,
                    reason="Correct ceremony article.",
                    relevant_sections=["Winners and nominees"],
                    needs_table_reader=True,
                )
            ]
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = review_runner

        update = review_and_select_from_toc(
            {
                "question": "Who was nominated at the 68th Academy Awards?",
                "article_candidates": [candidate],
            },
            llm,
            markdown_store,
        )

        self.assertEqual(update["selected_articles"], ["68th_Academy_Awards.html"])
        review = update["article_reviews"][0]
        self.assertEqual(review.relevant_sections, ["Winners and nominees"])
        self.assertTrue(review.needs_table_reader)
        # The section list (TOC), not a snippet, was shown to the model.
        human_message = review_runner.invoke.call_args.args[0][1].content
        self.assertIn("Winners and nominees", human_message)
        self.assertIn("Table of contents", human_message)

    def test_review_and_select_from_toc_never_rejects_all(self) -> None:
        candidates = [
            ArticleCandidate(
                source_article=name,
                retrieval_query="q",
                discovered_by="vector",
                rank=rank,
                raw_score=0.1 * rank,
                score_semantics="lower_is_better",
            )
            for rank, name in enumerate(["A.html", "B.html"], start=1)
        ]
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {"sections": [], "tables": []}
        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(source_article="A.html", relevant=False, reason="no"),
                ArticleReview(source_article="B.html", relevant=False, reason="no"),
            ]
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = review_runner

        update = review_and_select_from_toc(
            {"question": "q", "article_candidates": candidates},
            llm,
            markdown_store,
        )

        # An empty selection would starve graph expansion, so the best-ranked
        # candidate is kept even when the model rejects everything.
        self.assertEqual(update["selected_articles"], ["A.html"])

    def test_toc_review_ranks_late_decade_tables_before_prompt_truncation(self) -> None:
        candidate = ArticleCandidate(
            source_article="Academy_Award_for_Best_Actor.html",
            retrieval_query="actors from 2000 through 2020",
            discovered_by="vector",
            rank=1,
            raw_score=0.1,
            score_semantics="lower_is_better",
        )
        markdown_store = Mock(spec=MarkdownArticleStore)
        markdown_store.has_article.return_value = True
        markdown_store.load_metadata.return_value = {
            "sections": [
                {"title": "Winners and nominees"},
                {"title": "2000s"},
                {"title": "2010s"},
                {"title": "2020s"},
            ],
            "tables": [],
        }
        entries = [
            TableCatalogEntry(
                artifact_id=f"artifact-{decade}",
                source_article="Academy_Award_for_Best_Actor.html",
                table_id=f"table-{index:03d}",
                table_role="data",
                caption=None,
                section_path=["Winners and nominees", f"{decade}s"],
                columns=["Year", "Actor", "Film"],
                row_count=50,
            )
            for index, decade in enumerate(range(1920, 2030, 10), start=2)
        ]
        table_store = Mock(spec=TableArtifactStore)
        table_store.list_tables.return_value = entries

        selected_ids = ["artifact-2000", "artifact-2010", "artifact-2020"]
        review_runner = Mock()
        review_runner.invoke.return_value = ArticleReviewBatch(
            reviews=[
                ArticleReview(
                    source_article="Academy_Award_for_Best_Actor.html",
                    relevant=True,
                    reason="The requested decades are listed here.",
                    relevant_sections=["2000s", "2010s", "2020s"],
                    relevant_table_ids=selected_ids,
                )
            ]
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = review_runner

        update = review_and_select_from_toc(
            {
                "question": "Which actors won from 2000 through 2020?",
                "article_candidates": [candidate],
            },
            llm,
            markdown_store,
            table_store=table_store,
            max_tables_listed=3,
        )

        prompt = review_runner.invoke.call_args.args[0][1].content
        for artifact_id in selected_ids:
            self.assertIn(f"Artifact ID: {artifact_id}", prompt)
        self.assertEqual(
            update["article_reviews"][0].relevant_table_ids,
            selected_ids,
        )

    def test_load_selected_sections_pulls_named_sections(self) -> None:
        review = ArticleReview(
            source_article="68th_Academy_Awards.html",
            relevant=True,
            reason="Correct source.",
            relevant_sections=["Winners and nominees"],
            relevant_table_names=["Table 1: Winners"],
            needs_table_reader=True,
        )
        document = Document(
            page_content="Best Picture: Braveheart ...",
            metadata={
                "source": "68th_Academy_Awards.html#Winners_and_nominees-0",
                "article": "68th_Academy_Awards.html",
                "section_title": "Winners and nominees",
                "section_path": "Winners and nominees",
            },
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionTopK.return_value = [(document, 0.05)]

        update = load_selected_sections(
            {
                "question": "Who was nominated at the 68th Academy Awards?",
                "article_reviews": [review],
                "evidence": [],
            },
            retriever,
        )

        retriever.getArticleSectionTopK.assert_called_once_with(
            "Who was nominated at the 68th Academy Awards?",
            "68th_Academy_Awards.html",
            "Winners and nominees",
            k=1,
        )
        evidence = update["evidence"]
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.metadata["retrieval_stage"], "toc_selected_section")
        self.assertEqual(item.metadata["requested_section"], "Winners and nominees")
        self.assertTrue(item.metadata["needs_table_reader"])

    def test_broaden_adds_more_sections_additively(self) -> None:
        # The breadth route widens the selected article beyond its picked section,
        # keeping existing evidence and bumping the retrieval counter.
        existing = EvidenceItem(
            evidence_id="Barack_Obama.html#Early_life-0",
            source_article="Barack_Obama.html",
            content="Early life ...",
            metadata={"retrieval_stage": "toc_selected_section"},
        )
        docs = [
            (Document(page_content="Political career ...", metadata={
                "source": "Barack_Obama.html#Political_career-0",
                "article": "Barack_Obama.html", "section_title": "Political career"}), 0.10),
            (Document(page_content="Presidency ...", metadata={
                "source": "Barack_Obama.html#Presidency-0",
                "article": "Barack_Obama.html", "section_title": "Presidency"}), 0.20),
        ]
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionsTopK.return_value = docs

        update = retrieve_broadened_article_sections(
            {
                "question": "How did Obama's career progress?",
                "selected_articles": ["Barack_Obama.html"],
                "evidence": [existing],
                "retrieval_attempts": 1,
            },
            retriever,
            broaden_k=8,
        )

        retriever.getArticleSectionsTopK.assert_called_once_with(
            "How did Obama's career progress?", "Barack_Obama.html", k=8
        )
        evidence = update["evidence"]
        self.assertEqual(len(evidence), 3)  # existing + 2 broadened
        stages = [it.metadata["retrieval_stage"] for it in evidence]
        self.assertEqual(stages.count("broadened_article_sections"), 2)
        self.assertIn("toc_selected_section", stages)  # existing preserved
        self.assertEqual(update["retrieval_attempts"], 2)

    def test_broaden_dedups_already_loaded_sections(self) -> None:
        # A section already in evidence must not be duplicated by the breadth route.
        existing = EvidenceItem(
            evidence_id="Barack_Obama.html#Presidency-0",
            source_article="Barack_Obama.html",
            content="Presidency ...",
            metadata={"retrieval_stage": "toc_selected_section"},
        )
        docs = [
            (Document(page_content="Presidency ...", metadata={
                "source": "Barack_Obama.html#Presidency-0", "article": "Barack_Obama.html"}), 0.10),
            (Document(page_content="Post-presidency ...", metadata={
                "source": "Barack_Obama.html#Post_presidency-0", "article": "Barack_Obama.html"}), 0.20),
        ]
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionsTopK.return_value = docs

        update = retrieve_broadened_article_sections(
            {
                "question": "What did Obama do?",
                "selected_articles": ["Barack_Obama.html"],
                "evidence": [existing],
                "retrieval_attempts": 2,
            },
            retriever,
        )

        ids = [it.evidence_id for it in update["evidence"]]
        self.assertEqual(len(ids), 2)  # existing + only the new one
        self.assertEqual(ids.count("Barack_Obama.html#Presidency-0"), 1)
        self.assertIn("Barack_Obama.html#Post_presidency-0", ids)

    def test_load_selected_sections_does_not_accept_a_different_heading(self) -> None:
        review = ArticleReview(
            source_article="Academy_Award_for_Best_Actor.html",
            relevant=True,
            reason="Correct source.",
            relevant_sections=["2000s"],
        )
        retriever = Mock(spec=VectorRetriever)
        retriever.getArticleSectionTopK.return_value = []

        update = load_selected_sections(
            {
                "question": "Who won between 2000 and 2009?",
                "article_reviews": [review],
                "evidence": [],
            },
            retriever,
        )

        retriever.getArticleSectionTopK.assert_called_once_with(
            "Who won between 2000 and 2009?",
            "Academy_Award_for_Best_Actor.html",
            "2000s",
            k=1,
        )
        retriever.getArticleSectionsTopK.assert_not_called()
        self.assertEqual(update["evidence"], [])

    def test_load_selected_tables_adds_json_table_evidence(self) -> None:
        review = ArticleReview(
            source_article="Lists_of_earthquakes.html",
            relevant=True,
            reason="Contains the deadliest-earthquakes table.",
            relevant_sections=["Deadliest earthquakes"],
            relevant_table_names=["deadliest fatalities"],
            needs_table_reader=True,
        )
        entry = TableCatalogEntry(
            artifact_id="art-1",
            source_article="Lists_of_earthquakes.html",
            table_id="table-001",
            table_role="wikitable",
            caption="Deadliest earthquakes",
            section_path=["Deadliest earthquakes"],
            columns=["Event", "Date", "Fatalities"],
            row_count=2,
        )
        normalized = Mock()
        normalized.columns = ["Event", "Date", "Fatalities"]
        normalized.rows = [
            {"Event": "1976 Tangshan earthquake", "Date": "July 27, 1976", "Fatalities": "300,000+"},
            {"Event": "2004 Indian Ocean", "Date": "December 26, 2004", "Fatalities": "227,898"},
        ]
        normalized.row_cells = []
        normalized.legends = []
        store = Mock(spec=TableArtifactStore)
        store.has_article.return_value = True
        store.list_tables.return_value = [entry]
        store.load_artifact.return_value = normalized

        update = load_selected_tables(
            {
                "question": "which earthquakes since 1976 had over 100,000 deaths",
                "article_reviews": [review],
                "evidence": [],
            },
            store,
        )

        evidence = update["evidence"]
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.evidence_type, "table")
        self.assertEqual(item.table_id, "art-1")
        self.assertEqual(item.metadata["retrieval_stage"], "toc_selected_table")
        self.assertTrue(item.metadata["needs_table_reader"])
        # Rendered as aligned JSON rows keyed by column, not flattened prose.
        self.assertIn("Tangshan", item.content)
        self.assertIn('"Event"', item.content)

    def test_load_selected_tables_skips_unflagged_articles(self) -> None:
        review = ArticleReview(
            source_article="A.html", relevant=True, reason="kept but no table need"
        )  # needs_table_reader defaults False, no relevant_table_names
        store = Mock(spec=TableArtifactStore)  # must not be queried

        update = load_selected_tables(
            {"question": "q", "article_reviews": [review], "evidence": []},
            store,
        )

        self.assertEqual(update["evidence"], [])
        store.list_tables.assert_not_called()

    def test_load_selected_tables_honors_all_explicit_artifact_ids(self) -> None:
        artifact_ids = ["artifact-2000", "artifact-2010", "artifact-2020"]
        review = ArticleReview(
            source_article="Academy_Award_for_Best_Actor.html",
            relevant=True,
            reason="All three decades are required.",
            relevant_table_ids=artifact_ids,
        )
        entries = [
            TableCatalogEntry(
                artifact_id=artifact_id,
                source_article="Academy_Award_for_Best_Actor.html",
                table_id=f"table-{index}",
                table_role="data",
                caption=None,
                section_path=["Winners and nominees", decade],
                columns=["Year", "Actor"],
                row_count=1,
            )
            for index, (artifact_id, decade) in enumerate(
                zip(artifact_ids, ["2000s", "2010s", "2020s"]),
                start=10,
            )
        ]
        tables = {
            entry.artifact_id: NormalizedTable(
                artifact_id=entry.artifact_id,
                source_article=entry.source_article,
                table_id=entry.table_id,
                caption=None,
                section_path=entry.section_path,
                columns=entry.columns,
                rows=[{"Year": entry.section_path[-1], "Actor": "Winner"}],
                warnings=[],
                source_hash="hash",
                parser_version="test",
                html_hash="html",
            )
            for entry in entries
        }
        store = Mock(spec=TableArtifactStore)
        store.has_article.return_value = True
        store.list_tables.return_value = entries
        store.load_artifact.side_effect = tables.__getitem__

        update = load_selected_tables(
            {
                "question": "Which actors won from 2000 through 2020?",
                "article_reviews": [review],
                "evidence": [],
            },
            store,
            max_tables_per_article=1,
        )

        table_evidence = [
            item for item in update["evidence"] if item.evidence_type == "table"
        ]
        self.assertEqual(
            [item.table_id for item in table_evidence],
            artifact_ids,
        )

    def test_table_json_retains_winner_markers_legends_and_annotations(self) -> None:
        review = ArticleReview(
            source_article="Academy_Awards.html",
            relevant=True,
            reason="Contains the winner table.",
            relevant_table_ids=["artifact-awards"],
        )
        entry = TableCatalogEntry(
            artifact_id="artifact-awards",
            source_article="Academy_Awards.html",
            table_id="table-001",
            table_role="data",
            caption="Winners and nominees",
            section_path=["Awards"],
            columns=["Film"],
            row_count=1,
            legend_meanings=["Indicates the winner"],
        )
        winner_cell = NormalizedCell(
            text="Moonlight",
            display_text="Moonlight ‡",
            is_header=False,
            is_bold=True,
            bold_text=["Moonlight"],
            annotations=[
                CellAnnotation(
                    position="superscript",
                    text="‡",
                    role="marker",
                    note="Indicates the winner",
                )
            ],
            legend_matches=["Indicates the winner"],
            origin_row=1,
            origin_column=0,
        )
        table = NormalizedTable(
            artifact_id=entry.artifact_id,
            source_article=entry.source_article,
            table_id=entry.table_id,
            caption=entry.caption,
            section_path=entry.section_path,
            columns=entry.columns,
            rows=[{"Film": "Moonlight"}],
            warnings=[],
            source_hash="hash",
            parser_version="test",
            row_cells=[{"Film": winner_cell}],
            legends=[
                TableLegend(
                    kind="symbol",
                    symbol="‡",
                    meaning="Indicates the winner",
                )
            ],
            html_hash="html",
        )
        store = Mock(spec=TableArtifactStore)
        store.has_article.return_value = True
        store.list_tables.return_value = [entry]
        store.load_artifact.return_value = table

        update = load_selected_tables(
            {
                "question": "Which film won?",
                "article_reviews": [review],
                "evidence": [],
            },
            store,
        )

        content = update["evidence"][0].content
        self.assertIn('"is_bold": true', content)
        self.assertIn('"display_text": "Moonlight ‡"', content)
        self.assertIn('"legend_matches": ["Indicates the winner"]', content)
        self.assertIn('"source_cell": "table-001:r2:c1"', content)

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

    def test_assess_evidence_gateway_forces_extraction_for_each_flagged_table(
        self,
    ) -> None:
        # Single-table gateway: a "read it directly" assessment over relevant
        # flagged tables is overridden into one auto table_request per table id,
        # so the executor runs before we answer.
        assessment = EvidenceAssessment(
            ready_to_answer=True,
            explanation="The rows are present; I can read the answer directly.",
        )
        structured_assessor = Mock()
        structured_assessor.invoke.return_value = assessment
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_assessor
        state: AgentState = {
            "question": "Which nominees appear at all three ceremonies?",
            "article_reviews": [
                ArticleReview(
                    source_article="68th_Academy_Awards.html",
                    relevant=True,
                    reason="Has the nominee table.",
                    relevant_table_ids=["table-001", "table-002"],
                ),
                ArticleReview(
                    source_article="70th_Academy_Awards.html",
                    relevant=True,
                    reason="Has the nominee table.",
                    relevant_table_ids=["table-003"],
                ),
                ArticleReview(
                    source_article="off_topic.html",
                    relevant=False,
                    reason="Not relevant.",
                    relevant_table_ids=["table-999"],
                ),
            ],
            "evidence": [],
        }

        update = assess_evidence(state, llm)
        result = update["assessment"]

        self.assertFalse(result.ready_to_answer)
        # One request per table id, only for relevant reviews (irrelevant skipped).
        self.assertEqual(len(result.table_requests), 3)
        self.assertTrue(
            all(req.operation == "auto" for req in result.table_requests)
        )
        self.assertEqual(
            {req.table_id for req in result.table_requests},
            {"table-001", "table-002", "table-003"},
        )

    def test_assess_evidence_gateway_stands_down_after_computation(self) -> None:
        # Once a table_computation result exists, the gateway must not re-fire, so
        # a genuine "ready" answer over the computed evidence can proceed.
        assessment = EvidenceAssessment(
            ready_to_answer=True,
            explanation="The computed table result answers the question.",
        )
        structured_assessor = Mock()
        structured_assessor.invoke.return_value = assessment
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_assessor
        state: AgentState = {
            "question": "Which nominees appear at all three ceremonies?",
            "article_reviews": [
                ArticleReview(
                    source_article="68th_Academy_Awards.html",
                    relevant=True,
                    reason="Has the nominee table.",
                    relevant_table_ids=["table-001"],
                ),
            ],
            "evidence": [
                EvidenceItem(
                    evidence_id="68th_Academy_Awards.html#table-001#computed-x",
                    source_article="68th_Academy_Awards.html",
                    content="Deterministic table-computation result. ...",
                    evidence_type="table",
                    metadata={"retrieval_stage": "table_computation"},
                )
            ],
        }

        update = assess_evidence(state, llm)
        result = update["assessment"]

        self.assertTrue(result.ready_to_answer)
        self.assertEqual(result.table_requests, [])

    def _ready_non_table_state(self, attempts: int):
        assessment = EvidenceAssessment(
            ready_to_answer=True,
            explanation="One section looks sufficient.",
        )
        structured = Mock()
        structured.invoke.return_value = assessment
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured
        state: AgentState = {
            "question": "How did the program evolve over time?",
            "article_reviews": [
                ArticleReview(
                    source_article="Some_Process.html",
                    relevant=True,
                    reason="Describes the process.",
                )  # no relevant_table_ids -> a non-table synthesis question
            ],
            "selected_articles": ["Some_Process.html"],
            "evidence": [],
            "retrieval_attempts": attempts,
        }
        return state, llm

    def test_breadth_nudge_denies_first_pass_ready_for_non_table_question(self) -> None:
        # With the nudge on, a non-table question cannot finish on its initial single
        # section: readiness is denied so the loop takes one breadth escalation.
        state, llm = self._ready_non_table_state(attempts=1)
        update = assess_evidence(state, llm, breadth_nudge=True)
        self.assertFalse(update["assessment"].ready_to_answer)

    def test_breadth_nudge_off_by_default(self) -> None:
        # Default (e.g. the simple intake graph, which has no breadth route): the
        # assessor's first-pass "ready" is honored.
        state, llm = self._ready_non_table_state(attempts=1)
        update = assess_evidence(state, llm)
        self.assertTrue(update["assessment"].ready_to_answer)

    def test_breadth_nudge_stands_down_after_one_escalation(self) -> None:
        # Once the question has escalated (attempts >= 2), the nudge no longer fires,
        # so a genuine "ready" over the broadened evidence proceeds (bounded loop).
        state, llm = self._ready_non_table_state(attempts=2)
        update = assess_evidence(state, llm, breadth_nudge=True)
        self.assertTrue(update["assessment"].ready_to_answer)

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

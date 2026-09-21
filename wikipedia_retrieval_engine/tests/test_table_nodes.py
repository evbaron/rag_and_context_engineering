from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from langchain_core.language_models.chat_models import BaseChatModel

from wikipedia_retrieval_engine.utils.wiki_table_store import (
    build_table_artifact_store,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    TableQueryPlan,
    TableRequest,
)
from wikipedia_retrieval_engine.wiki_agents.table_nodes import (
    execute_table_query_plan,
    find_table_candidates,
    plan_table_query,
    resolve_source_article,
)


ARTICLE_HTML = """
<div class="mw-parser-output">
  <table><tr><td>†</td><td>Pro Bowler</td></tr></table>
  <h2>Awards</h2>
  <table class="wikitable"><caption>Winners and nominees</caption>
    <tr><th>Category</th><th>Film</th></tr>
    <tr><td>Best Picture</td><td><b>Film A</b></td></tr>
  </table>
  <h2>Presenters</h2>
  <table class="wikitable"><caption>Presenters</caption>
    <tr><th>Name</th><th>Category</th></tr>
    <tr><td>Person A</td><td>Best Picture</td></tr>
    <tr><td>Person B</td><td>Best Director</td></tr>
  </table>
  <h2>Scores</h2>
  <table class="wikitable"><caption>Scores</caption>
    <tr><th>Name</th><th>Points</th></tr>
    <tr><td>Team A</td><td>1,200</td></tr>
    <tr><td>Team B</td><td>800</td></tr>
  </table>
  <h2>Draft</h2>
  <table class="wikitable"><caption>Draft players</caption>
    <tr><th>Player</th><th>Position</th></tr>
    <tr><td>Player A<sup>†</sup></td><td>QB</td></tr>
    <tr><td>Player B</td><td>WR</td></tr>
  </table>
</div>
"""


class TableNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        wiki_dir = root / "Wikipedia Library"
        wiki_dir.mkdir()
        (wiki_dir / "95th_Academy_Awards.html").write_text(
            ARTICLE_HTML,
            encoding="utf-8",
        )
        self.store = build_table_artifact_store(
            wiki_dir,
            root / "table_artifacts",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_resolve_source_article_accepts_harmless_label_variations(self) -> None:
        self.assertEqual(
            resolve_source_article("95th Academy Awards", self.store),
            "95th_Academy_Awards.html",
        )

    def test_find_table_candidates_honors_an_explicit_table_id(self) -> None:
        presenters = self.store.find_tables(
            "Presenters",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        request = TableRequest(
            missing_fact="Who presented Best Picture?",
            source_article="95th_Academy_Awards.html",
            table_id=presenters.table_id,
            operation="lookup",
            columns_needed=["Name", "Category"],
        )

        candidates = find_table_candidates(request, self.store)

        self.assertEqual(
            [candidate.table_id for candidate in candidates],
            [presenters.table_id],
        )

    def test_find_table_candidates_uses_request_metadata(self) -> None:
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th Academy Awards",
            expected_caption="Winners and nominees",
            operation="lookup",
            columns_needed=["Category", "Film"],
            row_filters={"Category": "Best Picture"},
        )

        candidates = find_table_candidates(request, self.store)

        self.assertEqual(candidates[0].caption, "Winners and nominees")
        self.assertEqual(candidates[0].columns, ["Category", "Film"])

    def test_find_table_candidates_can_use_normalized_row_text(self) -> None:
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th Academy Awards",
            operation="lookup",
            columns_needed=["Film"],
            row_filters={"Category": "Best Picture"},
        )

        candidates = find_table_candidates(request, self.store)

        self.assertEqual(candidates[0].caption, "Winners and nominees")

    def test_find_table_candidates_rejects_an_unknown_explicit_table_id(self) -> None:
        request = TableRequest(
            missing_fact="Which film won?",
            source_article="95th_Academy_Awards.html",
            table_id="table-does-not-exist",
            operation="lookup",
        )

        with self.assertRaisesRegex(KeyError, "not present"):
            find_table_candidates(request, self.store)

    def test_plan_table_query_uses_structured_output(self) -> None:
        winners = self.store.find_tables(
            "Winners and nominees",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th_Academy_Awards.html",
            operation="lookup",
            columns_needed=["Category", "Film"],
            row_filters={"Category": "Best Picture"},
        )
        expected_plan = TableQueryPlan(
            artifact_id=winners.artifact_id,
            operation="lookup",
            selected_columns=["Category", "Film"],
            filters={"Category": "Best Picture"},
        )
        structured_planner = Mock()
        structured_planner.invoke.return_value = expected_plan
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner

        plan = plan_table_query(
            "Which film won Best Picture?",
            request,
            self.store,
            llm,
        )

        llm.with_structured_output.assert_called_once_with(
            TableQueryPlan,
            method="function_calling",
        )
        messages = structured_planner.invoke.call_args.args[0]
        self.assertIn(winners.artifact_id, messages[1].content)
        self.assertIn('"bold_text"', messages[1].content)
        self.assertEqual(plan, expected_plan)

    def test_plan_table_query_rejects_an_unknown_artifact(self) -> None:
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th_Academy_Awards.html",
            operation="lookup",
            row_filters={"Category": "Best Picture"},
        )
        structured_planner = Mock()
        structured_planner.invoke.return_value = TableQueryPlan(
            artifact_id="not-a-candidate",
            operation="lookup",
            selected_columns=["Film"],
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner

        with self.assertRaisesRegex(ValueError, "not supplied"):
            plan_table_query("Which film won?", request, self.store, llm)

    def test_plan_table_query_rejects_invented_columns(self) -> None:
        winners = self.store.find_tables(
            "Winners and nominees",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th_Academy_Awards.html",
            operation="lookup",
            row_filters={"Category": "Best Picture"},
        )
        structured_planner = Mock()
        structured_planner.invoke.return_value = TableQueryPlan(
            artifact_id=winners.artifact_id,
            operation="lookup",
            selected_columns=["Invented Winner Column"],
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner

        with self.assertRaisesRegex(ValueError, "invented columns"):
            plan_table_query("Which film won?", request, self.store, llm)

    def test_execute_lookup_preserves_rich_cell_provenance(self) -> None:
        winners = self.store.find_tables(
            "Winners and nominees",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=winners.artifact_id,
            operation="lookup",
            selected_columns=["Film"],
            filters={"Category": "Best Picture"},
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-001",
        )

        self.assertTrue(evidence.sufficient)
        self.assertEqual(evidence.result_rows, [{"Film": "Film A"}])
        self.assertEqual(len(evidence.source_cells), 2)
        film_detail = next(
            detail for detail in evidence.cell_details if detail.column == "Film"
        )
        self.assertTrue(film_detail.is_bold)
        self.assertEqual(film_detail.bold_text, ["Film A"])

    def test_execute_lookup_reports_no_matching_rows(self) -> None:
        winners = self.store.find_tables(
            "Winners and nominees",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=winners.artifact_id,
            operation="lookup",
            selected_columns=["Film"],
            filters={"Category": "Missing category"},
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-002",
        )

        self.assertFalse(evidence.sufficient)
        self.assertEqual(evidence.result_rows, [])
        self.assertIn("No table rows matched", evidence.warnings[-1])

    def test_execute_sort_orders_rows_without_losing_source_cells(self) -> None:
        presenters = self.store.find_tables(
            "Presenters",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=presenters.artifact_id,
            operation="sort",
            selected_columns=["Name"],
            sort_column="Name",
            sort_direction="descending",
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-003",
        )

        self.assertEqual(
            evidence.result_rows,
            [{"Name": "Person B"}, {"Name": "Person A"}],
        )
        self.assertEqual(len(evidence.source_cells), 2)

    def test_execute_aggregate_performs_numeric_work_in_python(self) -> None:
        scores = self.store.find_tables(
            "Scores Points",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=scores.artifact_id,
            operation="aggregate",
            selected_columns=["Points"],
            calculation="sum",
            calculation_column="Points",
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-004",
        )

        self.assertTrue(evidence.sufficient)
        self.assertEqual(evidence.result_rows, [{"sum_Points": 2000}])
        self.assertEqual(evidence.calculation, "sum(Points)")
        self.assertEqual(len(evidence.source_cells), 2)

    def test_execute_filter_matches_legends_and_annotations(self) -> None:
        draft = self.store.find_tables(
            "Draft players",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=draft.artifact_id,
            operation="filter",
            selected_columns=["Player", "Position"],
            filters={"Player": "Pro Bowler"},
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-005",
        )

        self.assertTrue(evidence.sufficient)
        self.assertEqual(
            evidence.result_rows,
            [{"Player": "Player A", "Position": "QB"}],
        )
        player_detail = next(
            detail for detail in evidence.cell_details if detail.column == "Player"
        )
        self.assertEqual(player_detail.annotations[0]["text"], "†")
        self.assertEqual(player_detail.legend_matches, ["Pro Bowler"])


if __name__ == "__main__":
    unittest.main()

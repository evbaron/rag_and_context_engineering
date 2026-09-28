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
    TablePredicate,
    TableQueryPlan,
    TableRequest,
)
from langchain_core.messages import AIMessage

from wikipedia_retrieval_engine.wiki_agents.agentic_models import EvidenceAssessment
from wikipedia_retrieval_engine.wiki_agents.table_nodes import (
    INCOMPLETE_COMPUTATION_HEADER,
    compute_requested_tables,
    execute_table_query_plan,
    find_table_candidates,
    plan_table_query,
    repair_plan_arguments,
    resolve_source_article,
)


def _raw_output(arguments: dict) -> dict:
    """What ``with_structured_output(..., include_raw=True)`` returns on a parse failure."""

    return {
        "raw": AIMessage(content="", tool_calls=[{"name": "TableQueryPlan", "args": arguments, "id": "c1"}]),
        "parsed": None,
        "parsing_error": ValueError("predicates.0.op Field required"),
    }


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
  <h2>Ranges</h2>
  <table class="wikitable"><caption>Historical adjustments</caption>
    <tr><th>Name</th><th>Years</th><th>Change</th></tr>
    <tr><td>Early</td><td>1998–2004</td><td>−12.5</td></tr>
    <tr><td>Recent</td><td>2012–2018</td><td>.5</td></tr>
    <tr><td>Accounting</td><td>2020</td><td>($1,200.50)</td></tr>
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

    # -- Checkpoint 6.1: plan repair, one corrected retry, incomplete labels ------------
    def _scores(self):
        return self.store.find_tables("Scores", source_article="95th_Academy_Awards.html", limit=1)[0]

    def test_repair_plan_arguments_reads_the_op_from_its_key(self) -> None:
        repaired = repair_plan_arguments(
            {
                "artifact_id": "t",
                "predicates": [
                    {"column": "Year", "year_between": [2000, 2020]},
                    {"column": "Location", "contains": "India"},
                    {"column": "Points", "op": "num_gt", "value": 5},
                    {"column": "Points", "num_gt": 5, "num_lt": 9},
                ],
            }
        )

        self.assertEqual(
            repaired["predicates"],
            [
                {"column": "Year", "op": "year_between", "value": 2000, "value2": 2020},
                {"column": "Location", "op": "contains", "value": "India"},
                {"column": "Points", "op": "num_gt", "value": 5},
                {"column": "Points", "num_gt": 5, "num_lt": 9},
            ],
        )

    def test_plan_table_query_repairs_the_op_slip_without_another_call(self) -> None:
        scores = self._scores()
        request = TableRequest(missing_fact="Who scored over 1,000?", source_article="95th_Academy_Awards.html", table_id=scores.artifact_id, operation="auto")
        structured_planner = Mock()
        structured_planner.invoke.return_value = _raw_output(
            {
                "artifact_id": scores.artifact_id,
                "operation": "filter",
                "selected_columns": ["Name", "Points"],
                "predicates": [{"column": "Points", "num_gt": 1000}],
            }
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner

        plan = plan_table_query("Who scored over 1,000?", request, self.store, llm, repair_invalid_plan=True)

        llm.with_structured_output.assert_called_once_with(TableQueryPlan, method="function_calling", include_raw=True)
        self.assertEqual(structured_planner.invoke.call_count, 1)
        self.assertEqual(plan.predicates, [TablePredicate(column="Points", op="num_gt", value=1000)])

    def test_plan_table_query_retries_once_with_the_rejection(self) -> None:
        scores = self._scores()
        request = TableRequest(missing_fact="How many teams?", source_article="95th_Academy_Awards.html", table_id=scores.artifact_id, operation="auto")
        invented = TableQueryPlan(artifact_id=scores.artifact_id, operation="aggregate", selected_columns=["count"], calculation="count")
        corrected = TableQueryPlan(artifact_id=scores.artifact_id, operation="aggregate", selected_columns=["Name"], calculation="count")
        structured_planner = Mock()
        structured_planner.invoke.side_effect = [
            {"raw": AIMessage(content=""), "parsed": invented, "parsing_error": None},
            {"raw": AIMessage(content=""), "parsed": corrected, "parsing_error": None},
        ]
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner

        plan = plan_table_query("How many teams?", request, self.store, llm, repair_invalid_plan=True)

        self.assertEqual(plan, corrected)
        retry_messages = structured_planner.invoke.call_args_list[1].args[0]
        self.assertIn("was rejected", retry_messages[-1].content)
        self.assertIn("invented columns", retry_messages[-1].content)

    def test_plan_table_query_raises_when_the_retry_also_fails(self) -> None:
        scores = self._scores()
        request = TableRequest(missing_fact="How many teams?", source_article="95th_Academy_Awards.html", table_id=scores.artifact_id, operation="auto")
        invented = TableQueryPlan(artifact_id=scores.artifact_id, operation="lookup", selected_columns=["count"])
        structured_planner = Mock()
        structured_planner.invoke.return_value = {"raw": AIMessage(content=""), "parsed": invented, "parsing_error": None}
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner

        with self.assertRaisesRegex(ValueError, "invented columns"):
            plan_table_query("How many teams?", request, self.store, llm, repair_invalid_plan=True)
        self.assertEqual(structured_planner.invoke.call_count, 2)

    def _state_for_empty_result(self) -> dict:
        scores = self._scores()
        request = TableRequest(missing_fact="Who scored over 5,000?", source_article="95th_Academy_Awards.html", table_id=scores.artifact_id, operation="filter")
        return {
            "question": "Who scored over 5,000?",
            "assessment": EvidenceAssessment(ready_to_answer=False, table_requests=[request], explanation="needs rows"),
            "evidence": [],
        }

    def _planner_with_no_matches(self) -> Mock:
        structured_planner = Mock()
        structured_planner.invoke.return_value = TableQueryPlan(
            artifact_id=self._scores().artifact_id,
            operation="filter",
            selected_columns=["Name", "Points"],
            predicates=[TablePredicate(column="Points", op="num_gt", value=5000)],
        )
        llm = Mock(spec=BaseChatModel)
        llm.with_structured_output.return_value = structured_planner
        return llm

    def test_empty_result_is_labelled_incomplete_when_asked(self) -> None:
        state = compute_requested_tables(
            self._state_for_empty_result(), self.store, self._planner_with_no_matches(), label_incomplete=True
        )

        item = state["evidence"][0]
        self.assertFalse(item.metadata["table_computation_sufficient"])
        self.assertTrue(item.content.startswith(INCOMPLETE_COMPUTATION_HEADER))

    def test_empty_result_keeps_the_5_1_header_by_default(self) -> None:
        state = compute_requested_tables(self._state_for_empty_result(), self.store, self._planner_with_no_matches())

        self.assertTrue(state["evidence"][0].content.startswith("Deterministic table-computation result."))

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

    def test_execute_numeric_predicate_preserves_signed_values(self) -> None:
        adjustments = self.store.find_tables(
            "Historical adjustments",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=adjustments.artifact_id,
            operation="filter",
            selected_columns=["Name", "Change"],
            predicates=[
                TablePredicate(column="Change", op="num_lt", value=0),
            ],
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-signed",
        )

        self.assertTrue(evidence.sufficient)
        self.assertEqual(
            evidence.result_rows,
            [
                {"Name": "Early", "Change": "−12.5"},
                {"Name": "Accounting", "Change": "($1,200.50)"},
            ],
        )
        self.assertTrue(evidence.source_cells)

    def test_execute_year_predicate_uses_years_inside_ranges(self) -> None:
        adjustments = self.store.find_tables(
            "Historical adjustments",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=adjustments.artifact_id,
            operation="filter",
            selected_columns=["Name", "Years"],
            predicates=[
                TablePredicate(column="Years", op="year_min_gte", value=2010),
            ],
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-years",
        )

        self.assertEqual(
            evidence.result_rows,
            [
                {"Name": "Recent", "Years": "2012–2018"},
                {"Name": "Accounting", "Years": "2020"},
            ],
        )

    def test_execute_equals_predicate_compares_the_plain_cell_value(self) -> None:
        adjustments = self.store.find_tables(
            "Historical adjustments",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=adjustments.artifact_id,
            operation="filter",
            selected_columns=["Name", "Change"],
            predicates=[
                TablePredicate(column="Name", op="equals", value="recent"),
            ],
        )

        evidence = execute_table_query_plan(
            plan,
            self.store,
            request_id="table-request-equals",
        )

        self.assertEqual(
            evidence.result_rows,
            [{"Name": "Recent", "Change": ".5"}],
        )

    def test_execute_predicate_rejects_unknown_column(self) -> None:
        adjustments = self.store.find_tables(
            "Historical adjustments",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        plan = TableQueryPlan(
            artifact_id=adjustments.artifact_id,
            operation="filter",
            selected_columns=["Name"],
            predicates=[
                TablePredicate(column="Invented", op="num_gt", value=1),
            ],
        )

        with self.assertRaisesRegex(ValueError, "unknown columns"):
            execute_table_query_plan(
                plan,
                self.store,
                request_id="table-request-unknown",
            )


if __name__ == "__main__":
    unittest.main()

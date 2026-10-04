"""The efficiency analyzer must reproduce the numbers README 7.1 computed by hand.

Two kinds of tests:

- synthetic frames for the logic (question sets, paths, dominance, verdicts, the
  Wilcoxon tie handling, the routing simulation);
- the recorded runs, skipped when they are not on disk: the GT baseline (README 7.1,
  "Baseline on the GT test set") and the validation routing policies (README 7.1,
  Finding 3). These figures were computed with one-off scripts before the analyzer
  existed, so agreement checks the tool against an independent calculation.
"""

from __future__ import annotations

import math
import unittest
from pathlib import Path

import pandas as pd

from wikipedia_retrieval_engine.utils import analyze_ragas_experiments_efficiency as eff

ENGINE = Path(__file__).resolve().parents[1]
GT_BASELINE = ENGINE / "Capstone Checkpoint 7.1" / "cost_efficiency" / "wikipedia_GT"
VALIDATION_DIRS = [
    ENGINE / "Capstone Checkpoint 6.1" / "cost_tests" / "wikipedia_GT_validation_set",
    ENGINE / "Capstone Checkpoint 7.1" / "cost_tests" / "wikipedia_GT_validation_set",
]


class LogicTests(unittest.TestCase):
    def test_question_sets_are_split_by_prefix(self) -> None:
        self.assertEqual(eff.question_set_of("GT07"), "GT test set")
        self.assertEqual(eff.question_set_of("VAL24"), "Validation set")
        self.assertEqual(eff.question_set_of("X1"), "X questions")

    def test_path_comes_from_the_table_flag_and_the_route(self) -> None:
        self.assertEqual(eff.path_of(pd.Series({"tables_flagged": "True", "route_trace": "ready_to_answer"})), eff.PATH_TABLE)
        self.assertEqual(eff.path_of(pd.Series({"tables_flagged": False, "route_trace": "ready_to_answer"})), eff.PATH_TEXT_READY)
        self.assertEqual(
            eff.path_of(pd.Series({"tables_flagged": "False", "route_trace": "need_more_evidence -> ready_to_answer"})),
            eff.PATH_TEXT_ESCALATED,
        )

    def test_dominance_needs_both_axes(self) -> None:
        frame = pd.DataFrame(
            {
                "configuration": ["cheap good", "pricey worse", "pricey better"],
                "list_cost": [0.04, 0.05, 0.15],
                "quality": [0.80, 0.70, 0.95],
            }
        )
        self.assertEqual(eff.dominance(frame, "list_cost"), ["", "cheap good", ""])

    def test_tradeoff_verdicts(self) -> None:
        self.assertIn("dominated", eff.tradeoff_verdict(-0.08, 0.002))
        self.assertIn("dominates", eff.tradeoff_verdict(0.05, -0.01))
        self.assertEqual(eff.tradeoff_verdict(0.1, 0.11), "pays $0.1100 per question for each +0.10 quality")
        self.assertEqual(eff.tradeoff_verdict(-0.1, -0.02), "saves $0.0200 per question for each -0.10 quality")

    def test_wilcoxon_treats_equal_means_as_ties(self) -> None:
        # (0 + 0.5 + 0.5) / 3 and 1 / 3 differ by floating-point noise; unrounded, scipy
        # would rank them apart and switch methods (0.180 instead of 0.188 on the GT data).
        noisy = [(0 + 0.5 + 0.5) / 3 - 2 / 3, -1 / 3, -1 / 3, -1 / 3, -2 / 3, -1 / 6, 0.5, 1 / 6]
        exact = [-1 / 3, -1 / 3, -1 / 3, -1 / 3, -2 / 3, -1 / 6, 0.5, 1 / 6]
        self.assertAlmostEqual(eff.wilcoxon_p(noisy), eff.wilcoxon_p(exact), places=12)
        self.assertTrue(math.isnan(eff.wilcoxon_p([0.0, 0.0])))

    def test_report_tables_are_never_read_as_runs(self) -> None:
        self.assertTrue(eff.is_report_output("reports/gt_baseline_tables/question_runs.csv"))
        self.assertTrue(eff.is_report_output("x/efficiency_report_tables/gt_test_set__1_frontier.csv"))
        self.assertFalse(eff.is_report_output("wikipedia_GT/experiments/eager_torvalds.csv"))
        self.assertTrue(eff.is_report_output("failed_runs/keen_perlis__route_check_0.5__partial.csv"))

    def test_nice_axis_steps(self) -> None:
        top, step = eff.nice_axis(0.0654)  # about five ticks: 0.02 apart, up to 0.08
        self.assertAlmostEqual(top, 0.08)
        self.assertAlmostEqual(step, 0.02)
        self.assertEqual(eff.nice_axis(17.9), (20.0, 5.0))

    def test_routing_simulation(self) -> None:
        rows = pd.DataFrame(
            {
                "label": ["cheap"] * 2 + ["strong"] * 2,
                "question_id": ["Q1", "Q2", "Q1", "Q2"],
                "category": ["Direct fact", "Temporal aggregation"] * 2,
                "path": [eff.PATH_TEXT_READY, eff.PATH_TABLE, eff.PATH_TEXT_READY, eff.PATH_TABLE],
                "quality": [1.0, 0.0, 1.0, 1.0],
                "cost_list_usd": [0.02, 0.05, 0.08, 0.20],
                "agent_seconds": [8.0, 14.0, 15.0, 28.0],
                "evidence_notice_flag": [False, True, False, False],
            }
        )
        policies = eff.simulate_policies(rows, ["cheap"], "strong").set_index("policy")
        table_route = policies.loc["Route on the cheap run's table flag"]
        self.assertAlmostEqual(table_route["quality"], 1.0)
        self.assertAlmostEqual(table_route["list_per_question"], (0.02 + 0.20) / 2)
        notice = policies.loc["Escalate on the evidence notice"]
        self.assertAlmostEqual(notice["list_per_question"], (0.02 + 0.05 + 0.20) / 2)
        self.assertAlmostEqual(notice["paid_twice"], 0.5)
        perfect = policies.loc["Perfect router (hindsight)"]
        self.assertAlmostEqual(perfect["list_per_question"], table_route["list_per_question"])


# The six runs of README 7.1, "Baseline on the GT test set". Later runs land in the same
# folder (other models, routers), so the baseline tests pin these by name.
GT_BASELINE_RUNS = (
    "eager_torvalds", "admiring_diffie", "hardcore_page", "eloquent_hoare", "confident_stallman", "confident_zuckerberg",
)


def only_runs(data: eff.EfficiencyData, runs: tuple[str, ...]) -> eff.EfficiencyData:
    return eff.EfficiencyData(
        rows=data.rows[data.rows["run_name"].isin(runs)],
        calls=data.calls[data.calls["run_name"].isin(runs)],
        runs=data.runs[data.runs["run"].isin(runs)],
        included_files=data.included_files,
        excluded_files=data.excluded_files,
        warnings=data.warnings,
    )


@unittest.skipUnless(GT_BASELINE.is_dir(), "GT baseline runs not on disk")
class GTBaselineTests(unittest.TestCase):
    """README 7.1, 'Baseline on the GT test set'."""

    @classmethod
    def setUpClass(cls) -> None:
        data = only_runs(eff.load_efficiency_data([GT_BASELINE]), GT_BASELINE_RUNS)
        cls.report = eff.build_set_report(data, "GT test set", baseline="6.1 survivor")

    def test_frontier(self) -> None:
        frontier = self.report.frontier.set_index("configuration")
        self.assertAlmostEqual(frontier.loc["6.1 survivor", "quality"], 0.789, places=3)
        self.assertAlmostEqual(frontier.loc["7.1 final", "quality"], 0.711, places=3)
        self.assertAlmostEqual(frontier.loc["6.1 survivor", "list_cost"], 0.0485, places=4)
        self.assertAlmostEqual(frontier.loc["7.1 final", "list_cost"], 0.0502, places=4)
        self.assertEqual(frontier.loc["7.1 final", "dominated_on_cost_by"], "6.1 survivor")

    def test_paired(self) -> None:
        paired = self.report.paired.set_index("configuration").loc["7.1 final"]
        self.assertEqual((paired["questions_better"], paired["questions_worse"], paired["questions_unchanged"]), (2, 6, 11))
        self.assertAlmostEqual(paired["delta_quality"], -0.079, places=3)
        self.assertAlmostEqual(paired["p_quality"], 0.19, places=2)

    def test_paths(self) -> None:
        paths = self.report.paths.set_index(["configuration", "path"])["question_runs"]
        self.assertEqual(paths[("6.1 survivor", eff.PATH_TEXT_READY)], 13)
        self.assertEqual(paths[("6.1 survivor", eff.PATH_TEXT_ESCALATED)], 1)
        self.assertEqual(paths[("6.1 survivor", eff.PATH_TABLE)], 43)

    def test_grounding_false_alarms(self) -> None:
        final = self.report.safeguards.set_index("configuration").loc["7.1 final"]
        self.assertEqual((final["grounding_flagged"], final["flagged_pass"]), (10, 8))

    def test_cost_efficiency_root_reads_only_the_runs(self) -> None:
        # The root holds reports/<stem>_tables/question_runs.csv beside the runs.
        from_root = eff.load_efficiency_data([GT_BASELINE.parent])
        from_runs = eff.load_efficiency_data([GT_BASELINE])
        self.assertEqual(set(from_root.rows["run_name"]), set(from_runs.rows["run_name"]))
        self.assertEqual(len(from_root.rows), len(from_runs.rows))

    def test_runs_ordered_from_the_manifest(self) -> None:
        runs = self.report.runs.sort_values("order")  # orders the six pinned runs
        self.assertEqual(runs["run"].tolist()[:2], ["eager_torvalds", "admiring_diffie"])
        self.assertEqual(set(runs["time_source"]), {"run_manifest.csv"})


@unittest.skipUnless(all(path.is_dir() for path in VALIDATION_DIRS), "validation runs not on disk")
class FindingThreeTests(unittest.TestCase):
    """README 7.1, Finding 3: four mini runs (6.1 x3, 7.1 x1), gpt-5.4 as the strong path."""

    def test_policies_reproduce_the_hand_calculation(self) -> None:
        data = eff.load_efficiency_data(VALIDATION_DIRS)
        report = eff.build_set_report(
            data, "Validation set",
            route_cheap=["6.1 survivor", "7.1 final"],
            route_strong="6.1 survivor, gpt-5.4",
        )
        policies = report.policies.set_index("policy")
        expected = {
            "All cheap": (0.870, 0.0431),
            "All strong": (0.960, 0.1524),
            "Route on the cheap run's table flag": (0.960, 0.1094),
            "Route on the strong runs' table flag": (0.935, 0.1108),
            "Route on the question's category": (0.955, 0.1165),
            "Escalate on the evidence notice": (0.910, 0.0821),
        }
        for policy, (quality, cost) in expected.items():
            with self.subTest(policy=policy):
                self.assertAlmostEqual(policies.loc[policy, "quality"], quality, places=3)
                self.assertAlmostEqual(policies.loc[policy, "list_per_question"], cost, places=4)


class RepricingTests(unittest.TestCase):
    def test_long_prompt_tier_reproduces_the_billed_gpt_5_4_calls(self) -> None:
        import sys

        sys.path.insert(0, str(ENGINE / "Capstone Checkpoint 6.1"))
        try:
            from usage_accounting import call_cost, load_prices, price_for
        finally:
            sys.path.pop(0)
        price = price_for("openai/gpt-5.4-20260305", load_prices())
        # The two GT09 calls above 272K tokens in the 7.1 GT run, and what OpenRouter billed.
        self.assertAlmostEqual(call_cost(293694, 151168, 448, price)["billed"], 0.798294, places=6)
        self.assertAlmostEqual(call_cost(293129, 0, 329, price)["billed"], 1.473048, places=5)
        below = call_cost(50000, 0, 300, price)["list"]
        self.assertAlmostEqual(below, (50000 * 2.5 + 300 * 15) / 1e6)


if __name__ == "__main__":
    unittest.main()

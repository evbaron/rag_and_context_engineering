"""The 7.1 entry points must actually redirect the run, not merely intend to.

Both runners build an argument list and hand it to the 6.1 starter. The first version of
that worked only if the starter honoured the list: `security_test_starter.parse_args` still
called `parser.parse_args()` with no argument, so argparse read `sys.argv` instead and the
injected `--survivor final` and `--output-dir` were silently discarded. A 99-turn run went
to the 5.1 baseline and wrote into Checkpoint 6.1, and nothing complained.

These tests fail if that regresses: they check that each starter honours a passed argv, and
that each 7.1 runner's forwarded arguments actually parse to the final survivor and a
Checkpoint 7.1 output directory.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
for _path in (str(ENGINE / "Capstone Checkpoint 6.1"), str(ENGINE / "Capstone Checkpoint 7.1")):
    if _path not in sys.path:
        sys.path.insert(0, _path)


class StarterArgvTests(unittest.TestCase):
    """A starter that ignores its argv cannot be driven by another entry point."""

    def test_security_starter_honours_a_passed_argv(self) -> None:
        from security_test_starter import parse_args

        args = parse_args(["--survivor", "final", "--repeats", "3", "--output-dir", "/tmp/x"])
        self.assertEqual(args.survivor, "final")
        self.assertEqual(args.repeats, 3)
        self.assertEqual(str(args.output_dir), "/tmp/x")

    def test_security_starter_does_not_read_sys_argv_when_given_one(self) -> None:
        from security_test_starter import parse_args

        original = sys.argv
        try:
            sys.argv = ["security_test_starter.py", "--survivor", "5.1"]
            args = parse_args(["--survivor", "final"])
        finally:
            sys.argv = original
        self.assertEqual(args.survivor, "final")

    def test_cost_starter_honours_a_passed_argv(self) -> None:
        from cost_test_starter import parse_args

        args = parse_args(["--survivor", "final", "--grounding", "off", "--limit", "2"])
        self.assertEqual(args.survivor, "final")
        self.assertEqual(args.grounding, "off")
        self.assertEqual(args.limit, 2)


class SecurityEntryPointTests(unittest.TestCase):
    def forwarded(self, argv: list[str]) -> list[str]:
        import security_test_final

        captured: dict[str, list[str]] = {}
        original = security_test_final.run_security_tests
        security_test_final.run_security_tests = lambda passed: captured.update(argv=passed)
        try:
            security_test_final.main(argv)
        finally:
            security_test_final.run_security_tests = original
        return captured["argv"]

    def test_it_forces_the_final_survivor(self) -> None:
        from security_test_starter import parse_args

        args = parse_args(self.forwarded(["--scenario", "all", "--repeats", "3"]))
        self.assertEqual(args.survivor, "final")

    def test_it_writes_under_checkpoint_7_1(self) -> None:
        from security_test_starter import parse_args

        args = parse_args(self.forwarded(["--scenario", "all"]))
        self.assertIn("Capstone Checkpoint 7.1", str(args.output_dir))

    def test_user_arguments_survive(self) -> None:
        from security_test_starter import parse_args

        args = parse_args(self.forwarded(["--scenario", "plant_buried", "--repeats", "2"]))
        self.assertEqual(args.scenario, "plant_buried")
        self.assertEqual(args.repeats, 2)

    def test_an_explicit_output_dir_is_respected(self) -> None:
        from security_test_starter import parse_args

        args = parse_args(self.forwarded(["--output-dir", "/tmp/mine"]))
        self.assertEqual(str(args.output_dir), "/tmp/mine")

    def test_another_survivor_is_refused_rather_than_silently_run(self) -> None:
        import security_test_final

        with self.assertRaises(SystemExit):
            security_test_final.main(["--survivor", "5.1"])


class CostEntryPointTests(unittest.TestCase):
    def forwarded(self, argv: list[str]) -> list[str]:
        """The argv the runner hands to the 6.1 harness, captured without running it.

        ``main`` does ``asyncio.run(run_cost_test(arguments))``, so the capture replaces
        ``run_cost_test`` with a plain function that records its argument and returns
        None, and ``asyncio.run`` with a no-op that accepts it.
        """

        import cost_test_final

        captured: dict[str, list[str]] = {}
        original_runner = cost_test_final.run_cost_test
        original_run = cost_test_final.asyncio.run
        cost_test_final.run_cost_test = lambda passed: captured.update(argv=list(passed))
        cost_test_final.asyncio.run = lambda _result: None
        try:
            cost_test_final.main(argv)
        finally:
            cost_test_final.run_cost_test = original_runner
            cost_test_final.asyncio.run = original_run
        return captured["argv"]

    def test_it_forces_the_final_survivor(self) -> None:
        from cost_test_starter import parse_args

        args = parse_args(self.forwarded([]))
        self.assertEqual(args.survivor, "final")

    def test_it_writes_under_checkpoint_7_1_keeping_the_gt_set_layout(self) -> None:
        from cost_test_starter import parse_args

        args = parse_args(self.forwarded([]))
        self.assertIn("Capstone Checkpoint 7.1", str(args.output_dir))
        self.assertTrue(str(args.output_dir).endswith("wikipedia_GT_validation_set"))

    def test_another_survivor_is_refused(self) -> None:
        import cost_test_final

        with self.assertRaises(SystemExit):
            cost_test_final.main(["--survivor", "6.1"])


if __name__ == "__main__":
    unittest.main()


class AnalyzerSelfCheckTests(unittest.TestCase):
    """The analyzers' own offline checks must run with the suite, not only by hand."""

    def test_compare_security_runs_self_check_passes(self) -> None:
        sys.path.insert(0, str(ENGINE / "Capstone Checkpoint 7.1" / "analyzers"))
        import compare_security_runs

        self.assertEqual(compare_security_runs._self_check(), 0)

    def test_compare_security_runs_rejects_a_logs_directory(self) -> None:
        sys.path.insert(0, str(ENGINE / "Capstone Checkpoint 7.1" / "analyzers"))
        import compare_security_runs

        # Pointing at logs/ instead of a results directory is the mistake that produced
        # "No CSV files found"; it must fail with an explanation, not a stack trace.
        with self.assertRaises(SystemExit) as caught:
            compare_security_runs.load_run(ENGINE / "Capstone Checkpoint 6.1" / "logs", "BEFORE")
        self.assertIn("security_results.csv", str(caught.exception))

    def test_needs_both_runs_or_self_check(self) -> None:
        sys.path.insert(0, str(ENGINE / "Capstone Checkpoint 7.1" / "analyzers"))
        import compare_security_runs

        self.assertEqual(compare_security_runs.main(["--before", "/x"]), 2)


class SurvivorLabelTests(unittest.TestCase):
    """A 7.1 RAGAS run must record itself as the final survivor, not as 6.1."""

    def test_the_6_1_case_function_defaults_to_6_1(self) -> None:
        import inspect

        from survivor_6_1 import build_experiment_6_1

        self.assertEqual(inspect.signature(build_experiment_6_1).parameters["survivor_label"].default, "6.1")

    def test_the_final_experiment_passes_its_own_label(self) -> None:
        source = (ENGINE / "Capstone Checkpoint 7.1" / "survivor_agent_final.py").read_text(encoding="utf-8")
        self.assertIn('survivor_label="final"', source)

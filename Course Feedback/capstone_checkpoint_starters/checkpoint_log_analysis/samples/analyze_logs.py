"""Log analysis sample: what every run since Checkpoint 1 cost, and how long it took.

    python samples/analyze_logs.py                         # every logged run
    python samples/analyze_logs.py --checkpoint 3 4 5      # the evaluated runs only
    python samples/analyze_logs.py --since 2026-10-01

Prints the headline numbers and writes the performance report (Markdown) and two CSV
files (runs, roles) under RAG_WORK_DIR/reports/. Questions to ask of the report:

  1. Which role spends the most? (answer, plan, decompose, embedding, ...)
  2. Is the most accurate run worth its extra cost and time, given how much repeated
     runs of the same configuration vary?
  3. Which questions are slowest, and what did the system do on them (see their log lines)?
"""

from __future__ import annotations

import argparse

from ragkit import config
from ragkit.pricing import load_prices, record_cost
from ragkit.reports.performance import EVALUATION_ROLES, build_report, select_logs, write
from ragkit.runlog import read_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze every logged run.")
    parser.add_argument("--checkpoint", nargs="+", default=[], help="only runs from these checkpoints")
    parser.add_argument("--experiment", default=None, help="only runs whose name starts with this")
    parser.add_argument("--since", default=None, help="only runs on or after this date (YYYY-MM-DD)")
    args = parser.parse_args()

    paths = select_logs(args.checkpoint, args.experiment, args.since)
    if not paths:
        raise SystemExit(f"No matching logs in {config.logs_dir()}. Run the samples of earlier checkpoints first.")
    records = read_records(paths)
    prices = load_prices()
    system = [record_cost(r, prices, exclude_roles=EVALUATION_ROLES) for r in records]
    judge = [record_cost(r, prices, roles=EVALUATION_ROLES) for r in records]
    print(f"{len(paths)} run(s), {len(records)} logged question(s), {sum(1 for r in records if r.get('error'))} error(s)")
    print(f"Estimated spend: system ${sum(c for c in system if c):.4f}, evaluation (judge) ${sum(c for c in judge if c):.4f}")

    text, run_rows, roles = build_report(records)
    if roles:
        top = next((r for r in roles if r["system_share"] is not None), None)
        if top:
            print(f"Largest system cost: '{top['role']}' calls, {top['system_share']:.0%} of the system's cost")
    print(f"Report: {write(text, run_rows, roles)}")


if __name__ == "__main__":
    main()

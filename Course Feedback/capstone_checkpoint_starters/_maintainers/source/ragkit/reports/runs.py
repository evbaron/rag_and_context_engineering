"""Compare runs side by side. (Checkpoint 1)

    python -m ragkit.reports.runs                  # the 2 most recent runs
    python -m ragkit.reports.runs --last 4
    python -m ragkit.reports.runs LOG.jsonl LOG.jsonl

Writes a Markdown report to RAG_WORK_DIR/reports/ (open it in the editor's Markdown
preview). The report starts with one row per run: questions, errors, tokens, estimated
cost, and time. Then, for every question, each run's answer follows the others, with
the sources it retrieved, so differences between runs are visible at a glance.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ragkit.pricing import PRICES_FILE, load_prices, record_cost
from ragkit.reports.common import (
    describe_pipeline,
    group_runs,
    md_table,
    number,
    question_key,
    resolve_logs,
    run_label,
    usd,
    write_report,
)
from ragkit.runlog import read_records

ANSWER_LIMIT = 1500  # characters of each answer shown in the report


def summarize_run(records: Sequence[dict[str, Any]], prices: dict[str, Any]) -> dict[str, Any]:
    ok = [record for record in records if not record.get("error")]
    calls = [call for record in ok for call in record.get("calls", [])]
    costs = [record_cost(record, prices) for record in ok]
    known = [cost for cost in costs if cost is not None]
    latencies = [record.get("latency_s", 0.0) for record in ok]
    return {
        "questions": len(records),
        "errors": len(records) - len(ok),
        "input_tokens": sum(call.get("input_tokens", 0) for call in calls),
        "output_tokens": sum(call.get("output_tokens", 0) for call in calls),
        "cost": sum(known) if known and len(known) == len(costs) else None,
        "mean_latency": sum(latencies) / len(latencies) if latencies else None,
    }


def build_report(records: Sequence[dict[str, Any]], title: str = "Run comparison") -> str:
    prices = load_prices()
    runs = group_runs(records)
    labels = {run_id: run_label(run_id, rows) for run_id, rows in runs.items()}
    with PRICES_FILE.open(encoding="utf-8") as handle:
        as_of = json.load(handle).get("as_of", "?")

    lines = [
        f"# {title}",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} from {len(runs)} run(s). Cost is an estimate "
        f"at list prices (ragkit/pricing.json, as of {as_of}).",
        "",
    ]
    rows = []
    for run_id, run_records in runs.items():
        summary = summarize_run(run_records, prices)
        rows.append(
            [
                labels[run_id],
                describe_pipeline(run_records[0].get("pipeline") or {}),
                summary["questions"],
                summary["errors"],
                number(summary["input_tokens"]),
                number(summary["output_tokens"]),
                usd(summary["cost"]),
                number(summary["mean_latency"], 1),
            ]
        )
    lines.append(
        md_table(
            ["Run", "Pipeline", "Questions", "Errors", "Input tokens", "Output tokens", "Est. cost", "Mean time (s)"],
            rows,
        )
    )

    # Every question once, in the order first seen, with each run's answer under it.
    order: list[str] = []
    by_question: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for run_id, run_records in runs.items():
        for record in run_records:
            key = question_key(record)
            if key not in by_question:
                order.append(key)
                by_question[key] = {}
            by_question[key].setdefault(run_id, []).append(record)

    lines += ["", "## Answers"]
    for number_, key in enumerate(order, start=1):
        first = next(iter(by_question[key].values()))[0]
        heading = first.get("question", key)
        if first.get("question_id"):
            heading = f"{first['question_id']}: {heading}"
        lines += ["", f"### {number_}. {' '.join(heading.split())}"]
        for run_id, run_records in by_question[key].items():
            for record in run_records:
                lines += ["", _answer_block(labels[run_id], record, prices)]
    return "\n".join(lines) + "\n"


def _answer_block(label: str, record: dict[str, Any], prices: dict[str, Any]) -> str:
    if record.get("error"):
        return f"**{label}** · error: {record['error']}"
    calls = record.get("calls", [])
    tokens = sum(call.get("input_tokens", 0) + call.get("output_tokens", 0) for call in calls)
    facts = [f"{len(calls)} call(s)", f"{tokens:,} tokens", usd(record_cost(record, prices)), f"{record.get('latency_s', 0):.1f} s"]
    if record.get("history_turns"):
        facts.append(f"{record['history_turns']} earlier turn(s) sent")
    scores = record.get("scores") or {}
    if scores:
        facts += [f"{name}={value}" for name, value in scores.items() if not isinstance(value, (dict, list))]
    block = [f"**{label}** · " + " · ".join(facts)]
    sources = []
    for hit in record.get("retrieved", []):
        if hit.get("source") and hit["source"] not in sources:
            sources.append(hit["source"])
    if sources:
        block.append(f"Sources retrieved: {', '.join(sources)}")
    answer = (record.get("answer") or "").strip()
    if len(answer) > ANSWER_LIMIT:
        answer = answer[:ANSWER_LIMIT] + " [...]"
    block.append("\n".join("> " + line for line in (answer.splitlines() or [""])))
    return "\n\n".join(block)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare runs side by side.")
    parser.add_argument("logs", nargs="*", help="log files (default: the most recent runs)")
    parser.add_argument("--last", type=int, default=2, help="how many recent runs to compare")
    parser.add_argument("--name", default="runs", help="report file name")
    args = parser.parse_args(argv)
    paths = resolve_logs(args.logs, args.last)
    path = write_report(build_report(read_records(paths)), args.name)
    print(f"Report: {path}")


if __name__ == "__main__":
    main()

"""Retrieval recall and answer quality, per run and per question. (Checkpoint 3)

    python -m ragkit.reports.quality                # the 3 most recent runs
    python -m ragkit.reports.quality --last 6
    python -m ragkit.reports.quality LOG.jsonl LOG.jsonl

Quality: PASS = 1, PARTIAL = 0.5, FAIL = 0, averaged over the questions. Recall: the
share of a question's source articles that retrieval brought back. Read together, the
two say which half of the system failed on each question:

                              answer PASS       answer PARTIAL or FAIL
    every source retrieved    working           answer problem
    a source missed           suspicious (*)    retrieval problem

    (*) answered from the model's memory, or the question set lists the wrong sources.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ragkit.pricing import load_prices, record_cost
from ragkit.reports.common import (
    cell,
    describe_pipeline,
    group_runs,
    md_table,
    number,
    resolve_logs,
    run_label,
    usd,
    write_report,
)
from ragkit.runlog import read_records

CELLS = [
    ("found", "pass", "working"),
    ("found", "fail", "answer problem"),
    ("missed", "pass", "suspicious"),
    ("missed", "fail", "retrieval problem"),
]


def _scored(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if not r.get("error") and (r.get("scores") or {}).get("quality") is not None]


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def diagnosis(records: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    """Question ids in each cell of the table above (questions without recall are left out)."""
    cells: dict[str, list[str]] = {name: [] for _, _, name in CELLS}
    for record in _scored(records):
        scores = record["scores"]
        if scores.get("recall") is None:
            continue
        found = "found" if scores["recall"] >= 1.0 else "missed"
        verdict = "pass" if scores.get("verdict") == "PASS" else "fail"
        name = next(n for f, v, n in CELLS if f == found and v == verdict)
        cells[name].append(record.get("question_id") or "?")
    return cells


def build_report(records: Sequence[dict[str, Any]], title: str = "Quality report") -> str:
    prices = load_prices()
    runs = {run_id: rows for run_id, rows in group_runs(records).items() if _scored(rows)}
    if not runs:
        return f"# {title}\n\nNo scored runs among these logs. Quality reports need runs from run_eval (Checkpoint 3 on).\n"
    labels = {run_id: run_label(run_id, rows) for run_id, rows in runs.items()}

    lines = [
        f"# {title}",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} from {len(runs)} run(s). Quality: PASS = 1, PARTIAL = 0.5, "
        "FAIL = 0, averaged. Recall: share of a question's source articles that retrieval found. "
        "Cost: estimated at list prices, excluding the judge.",
        "",
        "## Runs",
        "",
    ]
    rows = []
    for run_id, run_records in runs.items():
        for dataset in ("gt", "validation"):
            scored = [r for r in _scored(run_records) if r.get("dataset") == dataset]
            if not scored:
                continue
            recalls = [r["scores"]["recall"] for r in scored if r["scores"].get("recall") is not None]
            costs = [record_cost(r, prices, exclude_roles={"judge"}) for r in scored]
            rows.append([
                labels[run_id],
                describe_pipeline(run_records[0].get("pipeline") or {}),
                dataset,
                len(scored),
                number(_mean([r["scores"]["quality"] for r in scored]), 3),
                f"{sum(r['scores'].get('verdict') == 'PASS' for r in scored) / len(scored):.0%}",
                number(_mean(recalls), 3),
                usd(_mean(costs)) if None not in costs else "n/a",
                number(_mean([r.get("latency_s", 0.0) for r in scored]), 1),
            ])
    lines.append(md_table(["Run", "Pipeline", "Set", "Questions", "Quality", "PASS", "Recall", "Cost / question", "Time (s)"], rows))

    lines += ["", "## Which half failed", "",
              "Every source retrieved = recall 1.0. Each cell lists the question ids that fall in it.", ""]
    for run_id, run_records in runs.items():
        cells = diagnosis(run_records)
        if not any(cells.values()):
            continue
        lines += [
            f"**{labels[run_id]}**",
            "",
            md_table(
                ["", "Answer PASS", "Answer PARTIAL or FAIL"],
                [
                    ["Every source retrieved", _ids("working", cells), _ids("answer problem", cells)],
                    ["A source missed", _ids("suspicious", cells), _ids("retrieval problem", cells)],
                ],
            ),
            "",
        ]

    lines += ["## Per question", "", "Each cell: verdict and recall. 'Differs' marks questions whose verdict changed between runs.", ""]
    order: list[str] = []
    by_question: dict[str, dict[str, dict[str, Any]]] = {}
    for run_id, run_records in runs.items():
        for record in _scored(run_records):
            key = record.get("question_id") or record.get("question", "")
            if key not in by_question:
                order.append(key)
                by_question[key] = {}
            by_question[key][run_id] = record
    question_rows = []
    for key in order:
        cells_by_run = by_question[key]
        first = next(iter(cells_by_run.values()))
        verdicts = {r["scores"].get("verdict") for r in cells_by_run.values()}
        row = [key, cell(first.get("question", ""), 70), first.get("dataset", "")]
        for run_id in runs:
            record = cells_by_run.get(run_id)
            if record is None:
                row.append("")
                continue
            recall = record["scores"].get("recall")
            row.append(f"{record['scores'].get('verdict')} · r{recall:.2f}" if recall is not None else record["scores"].get("verdict"))
        row.append("yes" if len(verdicts) > 1 else "")
        question_rows.append(row)
    lines.append(md_table(["ID", "Question", "Set", *[labels[r] for r in runs], "Differs"], question_rows))

    categories = sorted({r.get("category") for rs in runs.values() for r in _scored(rs) if r.get("category")})
    if categories:
        lines += ["", "## By category", "", "Mean quality (and number of questions) per category of question.", ""]
        category_rows = []
        for category in categories:
            row = [category]
            for run_id, run_records in runs.items():
                scored = [r for r in _scored(run_records) if r.get("category") == category]
                row.append(f"{_mean([r['scores']['quality'] for r in scored]):.2f} ({len(scored)})" if scored else "")
            category_rows.append(row)
        lines.append(md_table(["Category", *[labels[r] for r in runs]], category_rows))

    repeated = _repeats(runs)
    if repeated:
        lines += ["", "## Repeated runs", "",
                  "The same experiment run several times. The spread is how much the result moves by chance alone: "
                  "a difference between two configurations smaller than this spread is not evidence.", ""]
        lines.append(md_table(["Experiment", "Set", "Runs", "Quality per run", "Mean", "Spread (max - min)"], repeated))
    return "\n".join(lines) + "\n"


def _ids(name: str, cells: dict[str, list[str]]) -> str:
    ids = cells[name]
    return f"{len(ids)}: {', '.join(ids)}" if ids else "0"


def _repeats(runs: dict[str, list[dict[str, Any]]]) -> list[list[Any]]:
    by_experiment: dict[tuple[str, str], list[float]] = {}
    for run_records in runs.values():
        experiment = run_records[0].get("experiment", "?")
        for dataset in ("gt", "validation"):
            scored = [r for r in _scored(run_records) if r.get("dataset") == dataset]
            if scored:
                base = experiment.rsplit("_r", 1)[0] if experiment.rsplit("_r", 1)[-1].isdigit() else experiment
                by_experiment.setdefault((base, dataset), []).append(_mean([r["scores"]["quality"] for r in scored]))
    rows = []
    for (experiment, dataset), values in by_experiment.items():
        if len(values) > 1:
            rows.append([experiment, dataset, len(values), ", ".join(f"{v:.3f}" for v in values),
                         f"{_mean(values):.3f}", f"{max(values) - min(values):.3f}"])
    return rows


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Recall and answer quality across runs.")
    parser.add_argument("logs", nargs="*", help="log files (default: the most recent runs)")
    parser.add_argument("--last", type=int, default=3, help="how many recent runs to include")
    parser.add_argument("--name", default="quality", help="report file name")
    args = parser.parse_args(argv)
    path = write_report(build_report(read_records(resolve_logs(args.logs, args.last))), args.name)
    print(f"Report: {path}")


if __name__ == "__main__":
    main()

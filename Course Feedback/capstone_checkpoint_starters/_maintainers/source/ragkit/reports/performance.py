"""Cost and latency across every logged run. (Log analysis)

    python -m ragkit.reports.performance                      # every run in RAG_WORK_DIR/logs/
    python -m ragkit.reports.performance --checkpoint 3 4 5   # only those checkpoints
    python -m ragkit.reports.performance --experiment cp3_    # runs whose name starts with cp3_
    python -m ragkit.reports.performance LOG.jsonl LOG.jsonl

Every log line holds the model calls one question needed, with their tokens and time.
This report adds them up per run and per role (answer, plan, decompose, embedding,
judge, ...), and puts cost and time next to quality wherever the run was scored. The
judge's cost is shown, but kept out of the system's own cost: it is the price of
measuring, not of answering.

It also writes two CSV files next to the report (runs and roles), for charts in Excel
or Google Sheets.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ragkit import config
from ragkit.pricing import call_cost, load_prices, record_cost
from ragkit.reports.common import cell, describe_pipeline, group_runs, md_table, number, run_label, usd
from ragkit.runlog import list_logs, read_records

EVALUATION_ROLES = {"judge"}


def percentile(values: Sequence[float], share: float) -> float | None:
    """The value below which ``share`` (0..1) of ``values`` fall (nearest rank)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(share * len(ordered)) - 1))]


def summarize_run(records: Sequence[dict[str, Any]], prices: dict[str, Any]) -> dict[str, Any]:
    ok = [r for r in records if not r.get("error")]
    scored = [r for r in ok if (r.get("scores") or {}).get("quality") is not None]
    recalls = [r["scores"]["recall"] for r in scored if r["scores"].get("recall") is not None]
    system_costs = [record_cost(r, prices, exclude_roles=EVALUATION_ROLES) for r in ok]
    judge_costs = [record_cost(r, prices, roles=EVALUATION_ROLES) for r in ok]
    latencies = [r.get("latency_s", 0.0) for r in ok]
    system_calls = [c for r in ok for c in r.get("calls", []) if c.get("role") not in EVALUATION_ROLES]
    n = len(ok)
    return {
        "questions": len(records),
        "errors": len(records) - n,
        "quality": sum(r["scores"]["quality"] for r in scored) / len(scored) if scored else None,
        "recall": sum(recalls) / len(recalls) if recalls else None,
        "calls": len(system_calls) / n if n else None,
        "tokens": sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in system_calls) / n if n else None,
        "cost": sum(system_costs) / n if n and None not in system_costs else None,
        "judge_cost": sum(judge_costs) / n if n and None not in judge_costs else None,
        "p50": percentile(latencies, 0.5),
        "p95": percentile(latencies, 0.95),
    }


def role_rows(records: Sequence[dict[str, Any]], prices: dict[str, Any]) -> list[dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    for record in records:
        for c in record.get("calls", []):
            row = roles.setdefault(c.get("role", "?"), {"calls": 0, "input": 0, "output": 0, "cached": 0, "cost": 0.0, "priced": True, "latency": 0.0})
            row["calls"] += 1
            row["input"] += c.get("input_tokens", 0)
            row["output"] += c.get("output_tokens", 0)
            row["cached"] += c.get("cached_tokens", 0)
            row["latency"] += c.get("latency_s", 0.0)
            usd = call_cost(c, prices)
            if usd is None:
                row["priced"] = False
            else:
                row["cost"] += usd
    system_total = sum(r["cost"] for role, r in roles.items() if role not in EVALUATION_ROLES)
    rows = []
    for role, r in sorted(roles.items(), key=lambda item: item[1]["cost"], reverse=True):
        share = r["cost"] / system_total if role not in EVALUATION_ROLES and system_total else None
        rows.append({"role": role, "calls": r["calls"], "input_tokens": r["input"], "output_tokens": r["output"],
                     "cached_tokens": r["cached"], "cost": r["cost"] if r["priced"] else None, "system_share": share,
                     "mean_latency": r["latency"] / r["calls"] if r["calls"] else None})
    return rows


def build_report(records: Sequence[dict[str, Any]], title: str = "Performance report") -> tuple[str, list[dict], list[dict]]:
    """The Markdown report, plus the run rows and role rows for the CSV files."""
    prices = load_prices()
    runs = group_runs(records)
    lines = [
        f"# {title}",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} from {len(runs)} run(s), {len(records)} logged question(s). "
        "Cost is estimated at list prices (ragkit/pricing.json); 'per question' averages exclude failed questions. "
        "System cost leaves out the judge.",
        "",
        "## Runs",
        "",
    ]
    run_rows = []
    for run_id, run_records in runs.items():
        s = summarize_run(run_records, prices)
        run_rows.append({"run": run_label(run_id, run_records), "run_id": run_id,
                         "checkpoint": run_records[0].get("checkpoint", ""),
                         "pipeline": describe_pipeline(run_records[0].get("pipeline") or {}), **s})
    lines.append(md_table(
        ["Run", "Checkpoint", "Pipeline", "Questions", "Errors", "Quality", "Recall", "Calls / q", "Tokens / q",
         "Cost / q", "Judge / q", "Time p50 (s)", "Time p95 (s)"],
        [[r["run"], r["checkpoint"], r["pipeline"], r["questions"], r["errors"], number(r["quality"], 3),
          number(r["recall"], 3), number(r["calls"], 1), number(r["tokens"]), usd(r["cost"]), usd(r["judge_cost"]),
          number(r["p50"], 1), number(r["p95"], 1)] for r in run_rows],
    ))

    scored = sorted((r for r in run_rows if r["quality"] is not None), key=lambda r: r["quality"], reverse=True)
    if scored:
        lines += ["", "## Quality against cost and time", "",
                  "Scored runs, best quality first. A higher-quality run is worth its extra cost and time only if "
                  "the difference is larger than the spread between repeated runs (see the quality report).", ""]
        lines.append(md_table(["Run", "Quality", "Recall", "Cost / q", "Time p50 (s)"],
                              [[r["run"], number(r["quality"], 3), number(r["recall"], 3), usd(r["cost"]), number(r["p50"], 1)] for r in scored]))

    roles = role_rows(records, prices)
    lines += ["", "## Where the money goes", "",
              "All calls in these runs, by role. 'Share' is the role's part of the system cost (the judge is not part of it).", ""]
    lines.append(md_table(
        ["Role", "Calls", "Input tokens", "Output tokens", "Cached tokens", "Est. cost", "Share", "Mean time (s)"],
        [[r["role"], r["calls"], number(r["input_tokens"]), number(r["output_tokens"]), number(r["cached_tokens"]),
          usd(r["cost"]), f"{r['system_share']:.0%}" if r["system_share"] is not None else "", number(r["mean_latency"], 2)]
         for r in roles],
    ))

    slow = sorted((r for r in records if not r.get("error")), key=lambda r: r.get("latency_s", 0.0), reverse=True)[:10]
    if slow:
        lines += ["", "## Slowest questions", ""]
        lines.append(md_table(["Run", "Question", "Time (s)", "Calls"],
                              [[run_label(r.get("run_id", "?"), [r]), cell(r.get("question", ""), 80),
                                number(r.get("latency_s"), 1), len(r.get("calls", []))] for r in slow]))

    unpriced = sorted({c.get("model", "?") for r in records for c in r.get("calls", []) if call_cost(c, prices) is None})
    if unpriced:
        lines += ["", f"Models without a price in pricing.json (their cost shows as n/a): {', '.join(unpriced)}."]
    return "\n".join(lines) + "\n", run_rows, roles


def select_logs(checkpoints: Sequence[str] = (), experiment: str | None = None, since: str | None = None) -> list[Path]:
    """Log files filtered by checkpoint, experiment-name prefix, and date (YYYY-MM-DD)."""
    selected = []
    for path in list_logs():
        if since and path.name[:10] < since:
            continue
        first = next(iter(read_records([path])), None)
        if first is None:
            continue
        if checkpoints and str(first.get("checkpoint", "")) not in checkpoints:
            continue
        if experiment and not str(first.get("experiment", "")).startswith(experiment):
            continue
        selected.append(path)
    return selected


def write(text: str, run_rows: list[dict], roles: list[dict], name: str = "performance") -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = config.reports_dir()
    report = folder / f"{stamp}_{name}.md"
    report.write_text(text, encoding="utf-8")
    for rows, suffix in ((run_rows, "runs"), (roles, "roles")):
        if rows:
            with (folder / f"{stamp}_{name}_{suffix}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    return report


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cost and latency across logged runs.")
    parser.add_argument("logs", nargs="*", help="log files (default: every log, filtered by the options)")
    parser.add_argument("--checkpoint", nargs="+", default=[], help="only runs from these checkpoints")
    parser.add_argument("--experiment", default=None, help="only runs whose name starts with this")
    parser.add_argument("--since", default=None, help="only runs on or after this date (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    paths = [Path(p) for p in args.logs] or select_logs(args.checkpoint, args.experiment, args.since)
    if not paths:
        raise SystemExit(f"No matching logs in {config.logs_dir()}.")
    text, run_rows, roles = build_report(read_records(paths))
    print(f"Report: {write(text, run_rows, roles)}")


if __name__ == "__main__":
    main()

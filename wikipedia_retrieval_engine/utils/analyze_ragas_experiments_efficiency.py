#!/usr/bin/env python3
"""Accuracy against cost and latency: the trade-off report for Checkpoint 7.1 onwards.

``analyze_ragas_experiments.py`` tracks accuracy across checkpoints. This companion reads
the same experiment CSVs, plus the telemetry the cost starters write next to them, and
reports the trade-offs between quality, cost, and time:

1. **Frontier.** Quality against list cost and against seconds, one point per run plus
   the configuration mean. A configuration that another one matches or beats on both
   axes is marked dominated.
2. **Paired against a baseline.** Per-question differences in quality, cost, and time;
   questions better, worse, and unchanged; Wilcoxon signed-rank p-values; the price of
   each quality point gained (or saved).
3. **Where the cost goes.** Calls, tokens, cost, and model time by agent role.
4. **By path.** Text questions ready at the first assessment, text questions that
   escalated, and table questions.
5. **Tail and waste.** p50, p90, and maximum cost and time per question-run; the most
   expensive question-runs; the spend on failed answers; the cost of one passing answer.
6. **Comparability.** Run order, cached share, billed against list, and per-call latency
   by role in every run, with warnings when a difference is more likely the provider or
   the run order than the system.
7. **Safeguard markers.** Evidence notices, grounding-check flags (and the flagged answers
   the judge passed), input-sanitizer hits.
8. **Routing.** What-if routing policies simulated on saved runs (``--route-cheap`` and
   ``--route-strong``), and the route mix once runs carry a ``route`` column.

Question sets are never pooled. GT test and validation question-runs are reported in
separate sections, identified by the question id prefix (``GT``, ``VAL``), even when the
same experiment name ran on both.

Example (from ``rag_and_context_engineering/``)::

    python wikipedia_retrieval_engine/utils/analyze_ragas_experiments_efficiency.py \\
        --experiments-dir "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_efficiency/wikipedia_GT" \\
        --baseline "6.1 survivor" \\
        --output "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_efficiency/reports/gt_baseline.pdf"

Writes the PDF and one CSV per table (``<output stem>_tables/``). Reads files only: no
LLM or network calls. Requires pandas and reportlab, as the original; scipy for the
Wilcoxon p-values, which are reported as n/a without it.
"""

from __future__ import annotations

import argparse
import html
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

try:  # imported as wikipedia_retrieval_engine.utils.analyze_ragas_experiments_efficiency
    from . import analyze_ragas_experiments as base
except ImportError:  # run as a script from utils/
    import analyze_ragas_experiments as base

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
)

ENGINE_DIR = Path(__file__).resolve().parents[1]
COST_EFFICIENCY_DIR = ENGINE_DIR / "Capstone Checkpoint 7.1" / "cost_efficiency"
DEFAULT_EXPERIMENTS_DIR = COST_EFFICIENCY_DIR / "wikipedia_GT"
DEFAULT_OUTPUT = COST_EFFICIENCY_DIR / "reports" / "efficiency_report.pdf"

QUESTION_SET_BY_PREFIX = {"GT": "GT test set", "VAL": "Validation set"}
QUESTION_SET_ORDER = {"GT test set": 10, "Validation set": 20}

# Display names for the experiment names the cost starters write. ``--alias`` adds to or
# overrides these; an unknown name is shown as it is.
DEFAULT_ALIASES = {
    "survivor_cost_6_1": "5.1 survivor",
    "survivor_6_1": "6.1 survivor",
    "survivor_6_1__gpt-5.4": "6.1 survivor, gpt-5.4",
    "survivor_6_1__gpt-5.4-nano": "6.1 survivor, gpt-5.4-nano",
    "survivor_6_1__planner_gpt-5.4": "6.1 survivor, planner gpt-5.4",
    "survivor_6_1__nemotron-3-super-120b-a12b__first5": "6.1 survivor, free nemotron (first 5)",
    "survivor_final__grounding_surface": "7.1 final",
    "survivor_final__grounding_surface__gpt-5.4": "7.1 final, gpt-5.4",
    "survivor_final__grounding_surface__route_type": "7.1 router by question type",
    "survivor_final__grounding_surface__route_b": "7.1 Router B (assessor + answer)",
    "survivor_final__grounding_surface__route_check_0.5": "7.1 answer check 0.5 + large to gpt-5.4",
    "survivor_final__grounding_surface__route_b_check_0.5": "7.1 Router B + answer check 0.5",
}

ROLE_ORDER = ("router", "decomposer", "toc_reviewer", "assessor", "table_planner", "answer")
ROLE_SHORT = {"decomposer": "Decomp.", "toc_reviewer": "TOC", "assessor": "Assessor", "table_planner": "Planner",
              "answer": "Answer", "router": "Router"}

PATH_TEXT_READY = "Text, ready at first assessment"
PATH_TEXT_ESCALATED = "Text, escalated"
PATH_TABLE = "Table"
PATH_ORDER = (PATH_TEXT_READY, PATH_TEXT_ESCALATED, PATH_TABLE)

# The categories README 7.1 Finding 3 treated as text questions for its category-routing
# policy. The router's real labels are still to be decided; ``--text-categories`` replaces
# this set.
FINDING_3_TEXT_CATEGORIES = (
    "Direct fact",
    "Direct fact and quotation",
    "Process explanation",
    "Inference limitation",
    "Diagnostic reasoning and limitations",
    "People connection: intermediary person",
    "People connection: shared work and roles",
)

# A role whose prompt no configuration changes much: its per-call latency across runs
# shows how fast the provider was, independently of the system under test.
LATENCY_PROBE_ROLE = "decomposer"
LATENCY_DRIFT_WARNING = 1.25  # slowest probe median / fastest probe median
CACHE_SPREAD_WARNING = 0.20  # max - min cached share across runs of one set

PALETTE = (
    HexColor("#3B6EA5"),
    HexColor("#D89C36"),
    HexColor("#3C8D6B"),
    HexColor("#8E5EA2"),
    HexColor("#C65B55"),
    HexColor("#2A9D8F"),
    HexColor("#7A6F5A"),
    HexColor("#E07A5F"),
)
PATH_COLORS = {PATH_TEXT_READY: base.GREEN, PATH_TEXT_ESCALATED: base.AMBER, PATH_TABLE: base.BLUE}
VERDICT_COLORS = {"pass": base.GREEN, "partial": base.AMBER, "fail": base.RED}
DOMINATED_GRAY = HexColor("#A9B1B8")
CONTENT_WIDTH = base.PAGE_WIDTH - 1.1 * inch


# ---------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------


@dataclass
class EfficiencyData:
    """Every question-run, LLM call, and run found, with the derived columns."""

    rows: pd.DataFrame
    calls: pd.DataFrame
    runs: pd.DataFrame
    included_files: list[Path]
    excluded_files: list[tuple[Path, str]]
    warnings: list[str]

    def question_sets(self) -> list[str]:
        names = self.rows["question_set"].dropna().unique().tolist()
        return sorted(names, key=lambda name: (QUESTION_SET_ORDER.get(name, 90), name))


def question_set_of(question_id: Any) -> str:
    """``GT07`` -> GT test set; ``VAL24`` -> Validation set; anything else by its prefix."""

    match = re.match(r"[A-Za-z]+", base._as_text(question_id))
    prefix = match.group(0).upper() if match else ""
    return QUESTION_SET_BY_PREFIX.get(prefix, f"{prefix or 'Unlabeled'} questions")


def flag(value: Any) -> bool:
    """CSV booleans arrive as bools, strings, or numbers; empty means False."""

    if isinstance(value, bool):
        return value
    text = base._as_text(value).lower()
    return text in {"true", "1", "yes"}


def path_of(row: pd.Series) -> str:
    """The question-run's path through the agent, from its own route.

    A question-run is a table question when the TOC review flagged a table. A text
    question escalated when any assessment asked for more evidence
    (``need_more_evidence`` in ``route_trace``); otherwise it was ready at its first
    assessment.
    """

    if flag(row.get("tables_flagged")):
        return PATH_TABLE
    if "need_more_evidence" in base._as_text(row.get("route_trace")):
        return PATH_TEXT_ESCALATED
    return PATH_TEXT_READY


def is_report_output(relative_path: Any) -> bool:
    """A CSV that is not a run: this analyzer's tables, or a failed run's fragment.

    ``question_runs.csv`` has ``question_id`` and ``score`` columns, so without this guard
    a report written inside an experiments directory is read back as an extra run. The
    same holds for ``failed_runs/``, where an interrupted run's partial CSV is kept.
    """

    return any(part in ("reports", "failed_runs") or part.endswith("_tables")
               for part in Path(str(relative_path)).parts[:-1])


def _locate_run_files(roots: Iterable[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for root in roots:
        root = Path(root).expanduser().resolve()
        for path in sorted(root.rglob("*.csv")):
            if not path.name.endswith(base.TELEMETRY_SUFFIXES) and not is_report_output(path.relative_to(root)):
                found.setdefault(path.stem, path)
    return found


def _manifest_entry(run_path: Path, cache: dict[Path, pd.DataFrame | None]) -> dict[str, Any]:
    """Start and finish times from a ``run_manifest.csv`` above the run, when there is one."""

    for parent in list(run_path.parents)[:4]:
        manifest = parent / "run_manifest.csv"
        if manifest not in cache:
            try:
                cache[manifest] = pd.read_csv(manifest) if manifest.is_file() else None
            except Exception:
                cache[manifest] = None
        table = cache[manifest]
        if table is None or "results_csv" not in table.columns:
            continue
        match = table[table["results_csv"].astype(str) == run_path.name]
        if not match.empty:
            entry = match.iloc[0]
            return {
                "started": pd.to_datetime(entry.get("started"), errors="coerce"),
                "finished": pd.to_datetime(entry.get("finished"), errors="coerce"),
                "time_source": "run_manifest.csv",
            }
    return {}


def load_efficiency_data(
    experiments_dirs: Iterable[Path],
    *,
    aliases: dict[str, str] | None = None,
) -> EfficiencyData:
    """Load runs with the original analyzer, then add sets, labels, paths, calls, and runs."""

    roots = [Path(root).expanduser().resolve() for root in experiments_dirs]
    loaded = base.load_experiments(roots)
    names = {**DEFAULT_ALIASES, **(aliases or {})}
    report_files = loaded.rows["run_file"].map(is_report_output)
    skipped = sorted(set(loaded.rows.loc[report_files, "run_file"]))
    rows = loaded.rows[~report_files].copy()
    if rows.empty:
        raise ValueError("No experiment runs found (only report tables) under: " + ", ".join(map(str, roots)))
    rows["question_set"] = rows["question_id"].map(question_set_of)
    rows["label"] = rows["configuration"].map(lambda name: names.get(name, name))
    files = _locate_run_files(roots)
    rows["run_path"] = rows["run_name"].map(lambda stem: str(files.get(stem, "")))
    rows["path"] = rows.apply(path_of, axis=1)
    for column in ("evidence_notice", "grounding_acted", "grounding_ok", "input_sanitized"):
        rows[f"{column}_flag"] = rows[column].map(flag) if column in rows.columns else False
    rows["has_grounding"] = rows["grounding_ok"].notna() if "grounding_ok" in rows.columns else False

    calls = _load_calls(rows)
    warnings = list(loaded.warnings)
    rows = _reprice(rows, calls, warnings)
    rows = _add_router_cost(rows)
    runs = _build_runs(rows, calls)
    return EfficiencyData(
        rows=rows,
        calls=calls,
        runs=runs,
        included_files=[path for path in loaded.included_files if str(path) not in skipped],
        excluded_files=[*loaded.excluded_files, *[(Path(path), "report table written by this analyzer") for path in skipped]],
        warnings=warnings,
    )


def _reprice(rows: pd.DataFrame, calls: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """List cost per question recomputed from its calls with the current price table.

    The telemetry records list cost at run time, with the price table of that day. Pricing
    every run's calls with one table keeps them comparable, and picks up rules the earlier
    table lacked: ``gpt-5.4``'s long-prompt tier doubled two GT09 calls of the 7.1 GT run.
    The recorded figure stays in ``cost_list_recorded_usd``.
    """

    if calls.empty:
        return rows
    sys.path.insert(0, str(ENGINE_DIR / "Capstone Checkpoint 6.1"))
    try:
        from usage_accounting import call_cost, load_prices, price_for
    finally:
        sys.path.pop(0)
    prices = load_prices()
    priced = calls.copy()
    priced["list_repriced"] = [
        call_cost(int(row.input_tokens), int(row.cached_input_tokens), int(row.output_tokens),
                  price_for(str(row.model), prices))["list"]
        for row in priced.itertuples()
    ]
    if priced["list_repriced"].isna().any():
        return rows  # a model without a price: keep the recorded figures
    per_question = priced.groupby(["run_name", "question_id"])["list_repriced"].sum().rename("list_repriced")
    rows = rows.merge(per_question, on=["run_name", "question_id"], how="left")
    rows["cost_list_recorded_usd"] = rows["cost_list_usd"]
    has_calls = rows["list_repriced"].notna()
    rows.loc[has_calls, "cost_list_usd"] = rows.loc[has_calls, "list_repriced"]
    for run_name, group in rows[has_calls].groupby("run_name"):
        recorded, repriced = group["cost_list_recorded_usd"].sum(), group["cost_list_usd"].sum()
        if recorded and abs(repriced / recorded - 1) > 0.005:
            warnings.append(
                f"{run_name}: list cost repriced from its calls with the current price table "
                f"(${recorded:.4f} recorded -> ${repriced:.4f}, {repriced / recorded - 1:+.1%})."
            )
    return rows.drop(columns="list_repriced")


def _add_router_cost(rows: pd.DataFrame) -> pd.DataFrame:
    """Add Jev's cost (``router_cost_usd``, recorded by the routing in the results CSV).

    Jev is called over plain HTTP, so the LangChain telemetry never sees it. Its cost is a
    fraction of a cent, but a routed configuration's cost must include its router.
    """

    if "router_cost_usd" not in rows.columns:
        return rows
    router = pd.to_numeric(rows["router_cost_usd"], errors="coerce").fillna(0.0)
    rows = rows.copy()
    for column in ("cost_list_usd", "cost_billed_usd"):
        rows[column] = pd.to_numeric(rows[column], errors="coerce") + router
    return rows


def _load_calls(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per chat-model call, from each run's ``<run>__llm_calls.csv``."""

    frames: list[pd.DataFrame] = []
    for (run_name, run_path), _ in rows.groupby(["run_name", "run_path"], sort=False):
        if not run_path:
            continue
        telemetry = Path(run_path).parent.parent / "telemetry" / f"{run_name}__llm_calls.csv"
        if not telemetry.is_file():
            continue
        frame = pd.read_csv(telemetry)
        frame["run_name"] = run_name
        frames.append(frame)
    columns = ["run_name", "question_id", "role", "model", "latency_s", "list_cost_usd", "input_tokens",
               "output_tokens", "cached_input_tokens", "question_set", "label"]
    if not frames:
        return pd.DataFrame(columns=columns)
    calls = pd.concat(frames, ignore_index=True)
    for column in ("latency_s", "list_cost_usd", "input_tokens", "output_tokens", "cached_input_tokens"):
        calls[column] = pd.to_numeric(calls.get(column), errors="coerce")
    meta = rows[["run_name", "question_id", "question_set", "label"]].drop_duplicates()
    return calls.merge(meta, on=["run_name", "question_id"], how="inner")


def _build_runs(rows: pd.DataFrame, calls: pd.DataFrame) -> pd.DataFrame:
    """One row per run and question set: totals, timing, and per-role call latency."""

    records: list[dict[str, Any]] = []
    manifest_cache: dict[Path, pd.DataFrame | None] = {}
    for (question_set, label, run_name), group in rows.groupby(
        ["question_set", "label", "run_name"], sort=False
    ):
        measured = group[group["cost_list_usd"].notna()]
        run_path = Path(group["run_path"].iloc[0]) if group["run_path"].iloc[0] else None
        timing = _manifest_entry(run_path, manifest_cache) if run_path else {}
        finished = timing.get("finished")
        if finished is None or pd.isna(finished):
            finished = pd.Timestamp(datetime.fromtimestamp(float(group["run_mtime"].iloc[0])))
            timing = {"started": pd.NaT, "finished": finished, "time_source": "file time (finish)"}
        record: dict[str, Any] = {
            "question_set": question_set,
            "configuration": label,
            "run": run_name,
            "question_runs": len(group),
            "quality": float(group["quality"].mean()),
            "has_telemetry": not measured.empty,
            "list_cost": _mean(measured, "cost_list_usd"),
            "billed_cost": _mean(measured, "cost_billed_usd"),
            "cached_share": _ratio(measured, "telemetry_cached_tokens", "telemetry_input_tokens"),
            "seconds": _mean(measured, "agent_seconds"),
            "calls": _mean(measured, "telemetry_calls"),
            "input_tokens": _mean(measured, "telemetry_input_tokens"),
            "started": timing.get("started"),
            "finished": timing.get("finished"),
            "time_source": timing.get("time_source"),
        }
        record["billed_to_list"] = (
            record["billed_cost"] / record["list_cost"] if record["list_cost"] else math.nan
        )
        run_calls = calls[calls["run_name"] == run_name]
        for role, role_calls in run_calls.groupby("role"):
            record[f"median_call_s_{role}"] = float(role_calls["latency_s"].median())
        records.append(record)
    runs = pd.DataFrame.from_records(records)
    if runs.empty:
        return runs
    runs["sort_time"] = runs["started"].where(runs["started"].notna(), runs["finished"])
    runs = runs.sort_values(["question_set", "sort_time", "run"]).reset_index(drop=True)
    runs["order"] = runs.groupby("question_set").cumcount() + 1
    return runs.drop(columns="sort_time")


def _mean(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame.get(column), errors="coerce").dropna() if column in frame else pd.Series(dtype=float)
    return float(values.mean()) if not values.empty else math.nan


def _ratio(frame: pd.DataFrame, numerator: str, denominator: str) -> float:
    if frame.empty or numerator not in frame or denominator not in frame:
        return math.nan
    total = pd.to_numeric(frame[denominator], errors="coerce").sum()
    return float(pd.to_numeric(frame[numerator], errors="coerce").sum() / total) if total else math.nan


# ---------------------------------------------------------------------------------------
# Statistics and verdicts
# ---------------------------------------------------------------------------------------


def wilcoxon_p(differences: Iterable[float]) -> float:
    """Two-sided Wilcoxon signed-rank p over the non-zero paired differences.

    NaN when every difference is zero, when there are none, or without scipy. Differences
    are rounded first: per-question means such as 1/3 and (0 + 0.5 + 0.5) / 3 must tie
    exactly, or floating-point noise changes the ranks and the test's method.
    """

    nonzero = [round(float(value), 9) for value in differences if not pd.isna(value) and abs(float(value)) > 1e-9]
    if not nonzero:
        return math.nan
    try:
        from scipy.stats import wilcoxon
    except ImportError:  # pragma: no cover - depends on the environment
        return math.nan
    return float(wilcoxon(nonzero).pvalue)


def dominance(frame: pd.DataFrame, cost_column: str, quality_column: str = "quality") -> list[str]:
    """For each row, the configurations that match or beat it on both axes ('' if none).

    A configuration is dominated when another has quality at least as high and cost (or
    time) at least as low, and is strictly better on one of the two.
    """

    result: list[str] = []
    for _, row in frame.iterrows():
        cost, quality = row[cost_column], row[quality_column]
        if pd.isna(cost) or pd.isna(quality):
            result.append("")
            continue
        beaters = [
            other["configuration"]
            for _, other in frame.iterrows()
            if other["configuration"] != row["configuration"]
            and not pd.isna(other[cost_column])
            and other[quality_column] >= quality - 1e-12
            and other[cost_column] <= cost + 1e-12
            and (other[quality_column] > quality + 1e-12 or other[cost_column] < cost - 1e-12)
        ]
        result.append("; ".join(beaters))
    return result


def tradeoff_verdict(delta_quality: float, delta_cost: float) -> str:
    """How a configuration trades quality for cost against the baseline, in plain words."""

    if pd.isna(delta_quality) or pd.isna(delta_cost):
        return "n/a"
    same_quality = abs(delta_quality) < 1e-9
    same_cost = abs(delta_cost) < 5e-5
    if same_quality and same_cost:
        return "same quality, same cost"
    if delta_quality >= -1e-9 and delta_cost <= 5e-5:
        return "dominates the baseline: at least as good, no more expensive"
    if delta_quality <= 1e-9 and delta_cost >= -5e-5:
        return "dominated by the baseline: no better, no cheaper"
    if delta_quality > 0:
        return f"pays ${delta_cost / delta_quality * 0.1:.4f} per question for each +0.10 quality"
    return f"saves ${delta_cost / delta_quality * 0.1:.4f} per question for each -0.10 quality"


# ---------------------------------------------------------------------------------------
# Section builders: each returns plain DataFrames (written to CSV and rendered in the PDF)
# ---------------------------------------------------------------------------------------


@dataclass
class SetReport:
    """All tables for one question set."""

    name: str
    baseline: str
    baseline_note: str
    rows: pd.DataFrame
    runs: pd.DataFrame
    frontier: pd.DataFrame
    paired: pd.DataFrame
    paired_questions: pd.DataFrame
    roles: pd.DataFrame
    paths: pd.DataFrame
    tail: pd.DataFrame
    top_expensive: pd.DataFrame
    safeguards: pd.DataFrame
    flagged_spans: pd.DataFrame
    policies: pd.DataFrame
    policy_note: str
    routes: pd.DataFrame
    warnings: list[str] = field(default_factory=list)

    @property
    def configurations(self) -> list[str]:
        return self.frontier["configuration"].tolist()


def build_frontier(rows: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """§1: one row per configuration, ordered by its first run; dominance on cost and time."""

    records: list[dict[str, Any]] = []
    for label, group in rows.groupby("label", sort=False):
        config_runs = runs[runs["configuration"] == label]
        measured = group[group["cost_list_usd"].notna()]
        measured_runs = config_runs[config_runs["has_telemetry"]]
        recall = pd.to_numeric(group.get("article_recall_recomputed"), errors="coerce").dropna()
        records.append(
            {
                "configuration": label,
                "first_order": int(config_runs["order"].min()),
                "runs": int(group["run_name"].nunique()),
                "telemetry_runs": int(measured["run_name"].nunique()),
                "questions": int(group["question_id"].nunique()),
                "question_runs": len(group),
                "pass": int((group["score"] == "pass").sum()),
                "partial": int((group["score"] == "partial").sum()),
                "fail": int((group["score"] == "fail").sum()),
                "quality": float(group["quality"].mean()),
                "quality_with_telemetry": float(measured["quality"].mean()) if not measured.empty else math.nan,
                "quality_run_min": float(config_runs["quality"].min()),
                "quality_run_max": float(config_runs["quality"].max()),
                "article_recall": float(recall.mean()) if not recall.empty else math.nan,
                "list_cost": _mean(measured, "cost_list_usd"),
                "list_run_min": float(measured_runs["list_cost"].min()) if not measured_runs.empty else math.nan,
                "list_run_max": float(measured_runs["list_cost"].max()) if not measured_runs.empty else math.nan,
                "billed_cost": _mean(measured, "cost_billed_usd"),
                "cached_share": _ratio(measured, "telemetry_cached_tokens", "telemetry_input_tokens"),
                "seconds": _mean(measured, "agent_seconds"),
                "seconds_median": float(pd.to_numeric(measured["agent_seconds"], errors="coerce").median()) if not measured.empty else math.nan,
                "seconds_run_min": float(measured_runs["seconds"].min()) if not measured_runs.empty else math.nan,
                "seconds_run_max": float(measured_runs["seconds"].max()) if not measured_runs.empty else math.nan,
                "calls": _mean(measured, "telemetry_calls"),
                "input_tokens": _mean(measured, "telemetry_input_tokens"),
            }
        )
    frontier = pd.DataFrame.from_records(records).sort_values("first_order").reset_index(drop=True)
    frontier["list_per_quality_point"] = frontier["list_cost"] / frontier["quality_with_telemetry"]
    frontier["dominated_on_cost_by"] = dominance(frontier, "list_cost", "quality_with_telemetry")
    frontier["dominated_on_time_by"] = dominance(frontier, "seconds", "quality_with_telemetry")
    return frontier


def _per_question(rows: pd.DataFrame) -> pd.DataFrame:
    return (
        rows.groupby(["label", "question_id"], sort=False)
        .agg(
            category=("category", "first"),
            runs=("run_name", "nunique"),
            quality=("quality", "mean"),
            list_cost=("cost_list_usd", "mean"),
            seconds=("agent_seconds", "mean"),
        )
        .reset_index()
    )


def build_paired(rows: pd.DataFrame, baseline: str, configurations: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """§2: every configuration against the baseline, paired by question (means over runs)."""

    per_question = _per_question(rows)
    base_q = per_question[per_question["label"] == baseline].set_index("question_id")
    summary: list[dict[str, Any]] = []
    details: list[pd.DataFrame] = []
    for label in configurations:
        if label == baseline:
            continue
        other = per_question[per_question["label"] == label].set_index("question_id")
        common = base_q.index.intersection(other.index)
        if common.empty:
            continue
        joined = pd.DataFrame(
            {
                "configuration": label,
                "question_id": common,
                "category": base_q.loc[common, "category"].values,
                "runs_baseline": base_q.loc[common, "runs"].values,
                "runs_configuration": other.loc[common, "runs"].values,
                "quality_baseline": base_q.loc[common, "quality"].values,
                "quality_configuration": other.loc[common, "quality"].values,
                "list_baseline": base_q.loc[common, "list_cost"].values,
                "list_configuration": other.loc[common, "list_cost"].values,
                "seconds_baseline": base_q.loc[common, "seconds"].values,
                "seconds_configuration": other.loc[common, "seconds"].values,
            }
        )
        joined["delta_quality"] = joined["quality_configuration"] - joined["quality_baseline"]
        joined["delta_list"] = joined["list_configuration"] - joined["list_baseline"]
        joined["delta_seconds"] = joined["seconds_configuration"] - joined["seconds_baseline"]
        details.append(joined)
        delta_quality = float(joined["delta_quality"].mean())
        delta_list = float(joined["delta_list"].mean())
        base_list = float(joined["list_baseline"].mean())
        summary.append(
            {
                "configuration": label,
                "baseline": baseline,
                "questions_compared": len(joined),
                "quality_baseline": float(joined["quality_baseline"].mean()),
                "quality_configuration": float(joined["quality_configuration"].mean()),
                "delta_quality": delta_quality,
                "questions_better": int((joined["delta_quality"] > 1e-9).sum()),
                "questions_worse": int((joined["delta_quality"] < -1e-9).sum()),
                "questions_unchanged": int((joined["delta_quality"].abs() <= 1e-9).sum()),
                "p_quality": wilcoxon_p(joined["delta_quality"]),
                "list_baseline": base_list,
                "list_configuration": float(joined["list_configuration"].mean()),
                "delta_list": delta_list,
                "delta_list_pct": delta_list / base_list if base_list else math.nan,
                "p_list": wilcoxon_p(joined["delta_list"]),
                "seconds_baseline": float(joined["seconds_baseline"].mean()),
                "seconds_configuration": float(joined["seconds_configuration"].mean()),
                "delta_seconds": float(joined["delta_seconds"].mean()),
                "p_seconds": wilcoxon_p(joined["delta_seconds"]),
                "verdict": tradeoff_verdict(delta_quality, delta_list),
            }
        )
    detail_frame = pd.concat(details, ignore_index=True) if details else pd.DataFrame()
    return pd.DataFrame.from_records(summary), detail_frame


def build_roles(rows: pd.DataFrame, calls: pd.DataFrame, configurations: list[str]) -> pd.DataFrame:
    """§3: calls, tokens, cost, and model time per role, per question-run with telemetry."""

    records: list[dict[str, Any]] = []
    for label in configurations:
        measured = rows[(rows["label"] == label) & rows["cost_list_usd"].notna()]
        config_calls = calls[calls["label"] == label]
        if measured.empty or config_calls.empty:
            continue
        question_runs = len(measured)
        total_cost = config_calls["list_cost_usd"].sum()
        total_time = config_calls["latency_s"].sum()
        roles = sorted(config_calls["role"].dropna().unique(), key=_role_key)
        for role in roles:
            mine = config_calls[config_calls["role"] == role]
            records.append(
                {
                    "configuration": label,
                    "role": role,
                    "calls_per_question": len(mine) / question_runs,
                    "input_tokens_per_question": mine["input_tokens"].sum() / question_runs,
                    "output_tokens_per_question": mine["output_tokens"].sum() / question_runs,
                    "cached_share": _ratio(mine, "cached_input_tokens", "input_tokens"),
                    "list_per_question": mine["list_cost_usd"].sum() / question_runs,
                    "share_of_list": mine["list_cost_usd"].sum() / total_cost if total_cost else math.nan,
                    "model_seconds_per_question": mine["latency_s"].sum() / question_runs,
                    "share_of_model_time": mine["latency_s"].sum() / total_time if total_time else math.nan,
                    "median_call_seconds": float(mine["latency_s"].median()),
                }
            )
    return pd.DataFrame.from_records(records)


def _role_key(role: str) -> tuple[int, str]:
    return (ROLE_ORDER.index(role) if role in ROLE_ORDER else len(ROLE_ORDER), role)


def build_paths(rows: pd.DataFrame, configurations: list[str]) -> pd.DataFrame:
    """§4: question-runs, quality, cost, and time by path, with each path's share of spend."""

    records: list[dict[str, Any]] = []
    for label in configurations:
        group = rows[rows["label"] == label]
        spend = pd.to_numeric(group["cost_list_usd"], errors="coerce").sum()
        for path in PATH_ORDER:
            mine = group[group["path"] == path]
            if mine.empty:
                continue
            records.append(
                {
                    "configuration": label,
                    "path": path,
                    "question_runs": len(mine),
                    "share_of_question_runs": len(mine) / len(group),
                    "quality": float(mine["quality"].mean()),
                    "list_per_question": _mean(mine, "cost_list_usd"),
                    "billed_per_question": _mean(mine, "cost_billed_usd"),
                    "seconds": _mean(mine, "agent_seconds"),
                    "share_of_list_spend": (
                        pd.to_numeric(mine["cost_list_usd"], errors="coerce").sum() / spend if spend else math.nan
                    ),
                }
            )
    return pd.DataFrame.from_records(records)


def build_tail(rows: pd.DataFrame, configurations: list[str], top: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """§5: the distribution's tail per configuration, and the most expensive question-runs."""

    records: list[dict[str, Any]] = []
    for label in configurations:
        measured = rows[(rows["label"] == label) & rows["cost_list_usd"].notna()]
        if measured.empty:
            continue
        cost = pd.to_numeric(measured["cost_list_usd"], errors="coerce")
        seconds = pd.to_numeric(measured["agent_seconds"], errors="coerce")
        spend = cost.sum()
        passes = int((measured["score"] == "pass").sum())
        records.append(
            {
                "configuration": label,
                "list_p50": float(cost.quantile(0.5)),
                "list_p90": float(cost.quantile(0.9)),
                "list_max": float(cost.max()),
                "max_over_mean": float(cost.max() / cost.mean()) if cost.mean() else math.nan,
                "seconds_p50": float(seconds.quantile(0.5)),
                "seconds_p90": float(seconds.quantile(0.9)),
                "seconds_max": float(seconds.max()),
                "spend_on_fail_share": float(cost[measured["score"] == "fail"].sum() / spend) if spend else math.nan,
                "spend_on_partial_share": float(cost[measured["score"] == "partial"].sum() / spend) if spend else math.nan,
                "list_per_pass": float(spend / passes) if passes else math.nan,
            }
        )
    measured_rows = rows[rows["cost_list_usd"].notna()].copy()
    top_rows = measured_rows.sort_values("cost_list_usd", ascending=False).head(top)
    top_frame = pd.DataFrame(
        {
            "configuration": top_rows["label"],
            "run": top_rows["run_name"],
            "question_id": top_rows["question_id"],
            "path": top_rows["path"],
            "score": top_rows["score"],
            "list_cost": top_rows["cost_list_usd"],
            "seconds": top_rows["agent_seconds"],
            "calls": top_rows["telemetry_calls"],
        }
    ).reset_index(drop=True)
    return pd.DataFrame.from_records(records), top_frame


def build_comparability_warnings(frontier: pd.DataFrame, runs: pd.DataFrame, rows: pd.DataFrame) -> list[str]:
    """§6: differences more likely to come from the provider or the run order than the system."""

    warnings: list[str] = []
    single = frontier[frontier["runs"] == 1]["configuration"].tolist()
    if single:
        warnings.append(
            "Single run: " + ", ".join(single) + ". One run cannot show a difference smaller than the "
            "run-to-run spread of a repeated configuration."
        )
    spreads = frontier.dropna(subset=["list_run_min", "list_run_max"])
    for _, row in spreads[spreads["telemetry_runs"] > 1].iterrows():
        if row["list_run_min"] and row["list_run_max"] / row["list_run_min"] > 1.2:
            warnings.append(
                f"{row['configuration']}: list cost per question ranges from ${row['list_run_min']:.4f} to "
                f"${row['list_run_max']:.4f} across its own runs ({row['list_run_max'] / row['list_run_min'] - 1:.0%} apart)."
            )
    measured = runs[runs["has_telemetry"]]
    if len(measured) > 1:
        cached = measured["cached_share"].dropna()
        if not cached.empty and cached.max() - cached.min() > CACHE_SPREAD_WARNING:
            warnings.append(
                f"Cached share ranges from {cached.min():.0%} to {cached.max():.0%} across runs (it grows with "
                "repeats of the same questions). Billed cost depends on run order; compare list cost."
            )
        probe = f"median_call_s_{LATENCY_PROBE_ROLE}"
        if probe in measured.columns:
            values = measured[probe].dropna()
            if len(values) > 1 and values.min() > 0 and values.max() / values.min() > LATENCY_DRIFT_WARNING:
                warnings.append(
                    f"The {LATENCY_PROBE_ROLE}'s median call took {values.min():.2f}-{values.max():.2f} s across runs "
                    f"({values.max() / values.min() - 1:.0%} apart). Its prompt is the same in every configuration, "
                    "so time differences of this size are the provider's speed, not the system."
                )
    coverage = rows.groupby("label")["question_id"].nunique()
    if coverage.nunique() > 1:
        warnings.append(
            "Configurations cover different questions ("
            + ", ".join(f"{label}: {count}" for label, count in coverage.items())
            + "). Paired comparisons use the questions both cover; the frontier uses all."
        )
    no_telemetry = frontier[frontier["telemetry_runs"] < frontier["runs"]]["configuration"].tolist()
    if no_telemetry:
        warnings.append(
            "Runs without telemetry (quality only; cost and time from the remaining runs): " + ", ".join(no_telemetry) + "."
        )
    return warnings


def build_safeguards(rows: pd.DataFrame, configurations: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """§7: how often each safeguard fires, and how the judge graded the answers it touched."""

    records: list[dict[str, Any]] = []
    for label in configurations:
        group = rows[rows["label"] == label]
        noticed = group[group["evidence_notice_flag"]]
        checked = group[group["has_grounding"].astype(bool)]
        flagged = checked[checked["grounding_acted_flag"]]
        passed_check = checked[checked["grounding_ok_flag"]]
        records.append(
            {
                "configuration": label,
                "question_runs": len(group),
                "evidence_notice": len(noticed),
                "evidence_notice_rate": len(noticed) / len(group),
                "notice_pass": int((noticed["score"] == "pass").sum()),
                "notice_partial": int((noticed["score"] == "partial").sum()),
                "notice_fail": int((noticed["score"] == "fail").sum()),
                "grounding_checked": len(checked),
                "grounding_flagged": len(flagged),
                "grounding_flagged_rate": len(flagged) / len(checked) if len(checked) else math.nan,
                "flagged_pass": int((flagged["score"] == "pass").sum()),
                "flagged_partial": int((flagged["score"] == "partial").sum()),
                "flagged_fail": int((flagged["score"] == "fail").sum()),
                "check_passed_but_fail": int((passed_check["score"] == "fail").sum()),
                "input_sanitized": int(group["input_sanitized_flag"].sum()),
            }
        )
    spans: dict[tuple[str, str], dict[str, Any]] = {}
    for _, row in rows.iterrows():
        if not row.get("grounding_acted_flag"):
            continue
        for kind, column in (("name", "ungrounded_entities"), ("quotation", "ungrounded_quotations")):
            for span in base._as_text(row.get(column)).split("; "):
                span = span.strip()
                if not span:
                    continue
                entry = spans.setdefault(
                    (span, kind),
                    {"span": span, "kind": kind, "count": 0, "configurations": set(), "pass": 0, "partial": 0, "fail": 0},
                )
                entry["count"] += 1
                entry["configurations"].add(row["label"])
                entry[row["score"]] += 1
    span_frame = pd.DataFrame(
        [{**entry, "configurations": "; ".join(sorted(entry["configurations"]))} for entry in spans.values()]
    )
    if not span_frame.empty:
        span_frame = span_frame.sort_values(["count", "span"], ascending=[False, True]).reset_index(drop=True)
    return pd.DataFrame.from_records(records), span_frame


@dataclass
class Policy:
    name: str
    description: str
    decide: Callable[[pd.Series], str]  # "cheap", "strong", or "both" (cheap first, then strong)


def routing_policies(strong_table_flags: dict[str, bool], text_categories: Iterable[str]) -> list[Policy]:
    text = set(text_categories)
    return [
        Policy("All cheap", "every question on the cheap configuration", lambda row: "cheap"),
        Policy("All strong", "every question on the strong configuration", lambda row: "strong"),
        Policy(
            "Route on the cheap run's table flag",
            "strong when the cheap run's TOC review flagged a table",
            lambda row: "strong" if row["path"] == PATH_TABLE else "cheap",
        ),
        Policy(
            "Route on the strong runs' table flag",
            "strong when most strong runs flagged a table for the question",
            lambda row: "strong" if strong_table_flags.get(row["question_id"], False) else "cheap",
        ),
        Policy(
            "Route on the question's category",
            "strong unless the category is one of the text categories",
            lambda row: "cheap" if base._as_text(row.get("category")) in text else "strong",
        ),
        Policy(
            "Escalate on the evidence notice",
            "cheap first; rerun on strong when the evidence notice fired (both paid)",
            lambda row: "both" if row["evidence_notice_flag"] else "cheap",
        ),
    ]


def load_route_labels(path: Path) -> tuple[str, dict[str, str]]:
    """A router's decisions from a CSV with ``question_id`` and ``route`` (cheap or strong).

    The policy is named after the CSV's ``router`` column when present, else its file name.
    """

    table = pd.read_csv(path)
    name = base._as_text(table["router"].iloc[0]) if "router" in table.columns and not table.empty else path.stem
    routes = dict(zip(table["question_id"].astype(str), table["route"].astype(str).str.strip().str.lower()))
    unknown = sorted(set(routes.values()) - {"cheap", "strong"})
    if unknown:
        raise ValueError(f"{path}: routes must be 'cheap' or 'strong', found {unknown}")
    return name, routes


def simulate_policies(
    rows: pd.DataFrame,
    cheap: list[str],
    strong: str,
    text_categories: Iterable[str] = FINDING_3_TEXT_CATEGORIES,
    route_labels: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    """§8: replay routing policies over saved question-runs.

    Each question-run of the cheap configuration(s) keeps its own outcome, cost, and time,
    or, when a policy sends it to the strong configuration, takes that question's mean
    outcome, cost, and time over the strong runs. "Both" pays both and takes the strong
    outcome. The perfect router knows the outcomes: it sends a question-run to the strong
    configuration only when the strong mean scores higher, and pays only the path taken,
    which bounds what any router can save.
    """

    cheap_rows = rows[rows["label"].isin(cheap) & rows["cost_list_usd"].notna()]
    strong_rows = rows[(rows["label"] == strong) & rows["cost_list_usd"].notna()]
    if cheap_rows.empty or strong_rows.empty:
        return pd.DataFrame()
    strong_q = strong_rows.groupby("question_id").agg(
        quality=("quality", "mean"),
        list_cost=("cost_list_usd", "mean"),
        seconds=("agent_seconds", "mean"),
        table_share=("path", lambda paths: float((paths == PATH_TABLE).mean())),
    )
    cheap_rows = cheap_rows[cheap_rows["question_id"].isin(strong_q.index)]
    flags = {question: share > 0.5 for question, share in strong_q["table_share"].items()}
    policies = routing_policies(flags, text_categories)
    for router, routes in (route_labels or {}).items():
        policies.append(
            Policy(
                f"Route on {router}",
                "the router's own decision per question; a question it did not label goes to strong",
                lambda row, routes=routes: routes.get(row["question_id"], "strong"),
            )
        )
    policies.append(
        Policy(
            "Perfect router (hindsight)",
            "strong only where the strong mean scores higher; the lower bound for any router",
            lambda row: "strong" if strong_q.loc[row["question_id"], "quality"] > row["quality"] + 1e-9 else "cheap",
        )
    )
    records: list[dict[str, Any]] = []
    for policy in policies:
        quality = cost = seconds = 0.0
        routed = twice = 0
        for _, row in cheap_rows.iterrows():
            decision = policy.decide(row)
            target = strong_q.loc[row["question_id"]]
            if decision == "cheap":
                quality += row["quality"]
                cost += row["cost_list_usd"]
                seconds += row["agent_seconds"]
            elif decision == "strong":
                routed += 1
                quality += target["quality"]
                cost += target["list_cost"]
                seconds += target["seconds"]
            else:
                routed += 1
                twice += 1
                quality += target["quality"]
                cost += row["cost_list_usd"] + target["list_cost"]
                seconds += row["agent_seconds"] + target["seconds"]
        n = len(cheap_rows)
        records.append(
            {
                "policy": policy.name,
                "description": policy.description,
                "quality": quality / n,
                "list_per_question": cost / n,
                "seconds": seconds / n,
                "sent_to_strong": routed / n,
                "paid_twice": twice / n,
                "question_runs": n,
            }
        )
    frame = pd.DataFrame.from_records(records)
    all_strong = frame.loc[frame["policy"] == "All strong", "list_per_question"].iloc[0]
    frame["saving_vs_all_strong"] = 1 - frame["list_per_question"] / all_strong if all_strong else math.nan
    return frame


def build_routes(rows: pd.DataFrame, configurations: list[str]) -> pd.DataFrame:
    """§8: the route mix, once runs record the router's decision in a ``route`` column."""

    if "route" not in rows.columns:
        return pd.DataFrame()
    records: list[dict[str, Any]] = []
    for label in configurations:
        group = rows[(rows["label"] == label) & rows["route"].notna()]
        for route, mine in group.groupby("route"):
            records.append(
                {
                    "configuration": label,
                    "route": route,
                    "question_runs": len(mine),
                    "share": len(mine) / len(group),
                    "quality": float(mine["quality"].mean()),
                    "list_per_question": _mean(mine, "cost_list_usd"),
                    "seconds": _mean(mine, "agent_seconds"),
                }
            )
    return pd.DataFrame.from_records(records)


def _resolve(name: str | None, labels: list[str], aliases: dict[str, str]) -> str | None:
    if not name:
        return None
    if name in labels:
        return name
    alias = {**DEFAULT_ALIASES, **aliases}.get(name)
    return alias if alias in labels else None


def build_set_report(
    data: EfficiencyData,
    question_set: str,
    *,
    baseline: str | None = None,
    route_cheap: list[str] | None = None,
    route_strong: str | None = None,
    text_categories: Iterable[str] = FINDING_3_TEXT_CATEGORIES,
    aliases: dict[str, str] | None = None,
    route_labels: dict[str, dict[str, str]] | None = None,
) -> SetReport:
    aliases = aliases or {}
    rows = data.rows[data.rows["question_set"] == question_set].copy()
    runs = data.runs[data.runs["question_set"] == question_set].copy()
    calls = data.calls[data.calls["question_set"] == question_set]
    frontier = build_frontier(rows, runs)
    labels = frontier["configuration"].tolist()

    chosen = _resolve(baseline, labels, aliases)
    if chosen:
        note = f"Baseline: {chosen} (requested)."
    else:
        chosen = labels[0]
        note = (
            f"Baseline: {chosen}, the configuration whose first run came first"
            + (f" ('{baseline}' has no runs on this set)." if baseline else ".")
        )
    order = [chosen] + [label for label in labels if label != chosen]
    paired, paired_questions = build_paired(rows, chosen, order)
    tail, top_expensive = build_tail(rows, order)
    safeguards, spans = build_safeguards(rows, order)

    cheap = [resolved for resolved in (_resolve(name, labels, aliases) for name in route_cheap or []) if resolved]
    strong = _resolve(route_strong, labels, aliases)
    if route_cheap or route_strong:
        if cheap and strong:
            policies = simulate_policies(rows, cheap, strong, text_categories, route_labels)
            policy_note = (
                f"Cheap: {', '.join(cheap)}. Strong: {strong}. Text categories for the category policy: "
                + "; ".join(text_categories)
                + "."
            )
        else:
            policies = pd.DataFrame()
            missing = [name for name in [*(route_cheap or []), route_strong or ""] if name and not _resolve(name, labels, aliases)]
            policy_note = "Not simulated on this set: no runs for " + ", ".join(missing) + "."
    else:
        policies = pd.DataFrame()
        policy_note = "Not requested (--route-cheap and --route-strong)."

    return SetReport(
        name=question_set,
        baseline=chosen,
        baseline_note=note,
        rows=rows,
        runs=runs,
        frontier=frontier,
        paired=paired,
        paired_questions=paired_questions,
        roles=build_roles(rows, calls, order),
        paths=build_paths(rows, order),
        tail=tail,
        top_expensive=top_expensive,
        safeguards=safeguards,
        flagged_spans=spans,
        policies=policies,
        policy_note=policy_note,
        routes=build_routes(rows, order),
        warnings=build_comparability_warnings(frontier, runs, rows),
    )


# ---------------------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------------------


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def write_csv_tables(reports: list[SetReport], data: EfficiencyData, csv_dir: Path) -> list[Path]:
    csv_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for report in reports:
        tables = {
            "1_frontier": report.frontier,
            "2_paired": report.paired,
            "2_paired_questions": report.paired_questions,
            "3_roles": report.roles,
            "4_paths": report.paths,
            "5_tail": report.tail,
            "5_top_expensive": report.top_expensive,
            "6_runs": report.runs,
            "7_safeguards": report.safeguards,
            "7_flagged_spans": report.flagged_spans,
            "8_policies": report.policies,
            "8_routes": report.routes,
        }
        for name, table in tables.items():
            if table is None or table.empty:
                continue
            path = csv_dir / f"{_slug(report.name)}__{name}.csv"
            table.to_csv(path, index=False)
            written.append(path)
    keep = [
        "question_set", "label", "configuration", "run_name", "question_id", "category", "path", "score",
        "quality", "cost_list_usd", "cost_billed_usd", "agent_seconds", "telemetry_calls",
        "telemetry_input_tokens", "telemetry_cached_tokens", "evidence_notice_flag", "grounding_acted_flag",
        "grounding_ok_flag", "input_sanitized_flag", "route_trace",
    ]
    question_runs = data.rows[[column for column in keep if column in data.rows.columns]]
    path = csv_dir / "question_runs.csv"
    question_runs.to_csv(path, index=False)
    written.append(path)
    return written


# ---------------------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------------------


def _money(value: Any, digits: int = 4) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else f"${number:.{digits}f}"


def _signed_money(value: Any) -> str:
    number = base._as_float(value)
    if number is None:
        return "n/a"
    if abs(number) < 5e-5:
        return "$0.0000"
    return f"{'+' if number > 0 else '-'}${abs(number):.4f}"


def _num(value: Any, digits: int = 3) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else f"{number:.{digits}f}"


def _signed(value: Any, digits: int = 3) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else f"{number:+.{digits}f}"


def _pct(value: Any) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else f"{number:.0%}"


def _signed_pct(value: Any) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else f"{number:+.0%}"


def _p(value: Any) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else ("<0.001" if number < 0.001 else f"{number:.3f}")


def _thousands(value: Any) -> str:
    number = base._as_float(value)
    return "n/a" if number is None else f"{number / 1000:.1f}K"


def _range(low: Any, high: Any, formatter: Callable[[Any], str]) -> str:
    if base._as_float(low) is None or base._as_float(high) is None:
        return "n/a"
    return formatter(low) if abs(float(high) - float(low)) < 1e-12 else f"{formatter(low)}-{formatter(high)}"


def _color_map(labels: list[str]) -> dict[str, Color]:
    return {label: PALETTE[index % len(PALETTE)] for index, label in enumerate(labels)}


def _table(
    headers: list[str],
    body: list[list[Any]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[Any]] = [[base._paragraph(header, styles["table_header"]) for header in headers]]
    for row in body:
        data.append(
            [cell if isinstance(cell, Paragraph) else base._paragraph(cell, styles["table"] if index == 0 else styles["table_center"])
             for index, cell in enumerate(row)]
        )
    scale = min(1.0, CONTENT_WIDTH / sum(widths))
    return base._styled_table(data, [width * scale for width in widths], long=len(body) > 20)


# ---------------------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------------------


def nice_axis(max_value: float, target_ticks: int = 5) -> tuple[float, float]:
    """A round step (1, 2, 2.5, or 5 times a power of ten) and the axis top it reaches."""

    if not max_value or max_value <= 0 or math.isnan(max_value):
        return 1.0, 0.25
    raw = max_value / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(multiple * magnitude for multiple in (1, 2, 2.5, 5, 10) if raw <= multiple * magnitude + 1e-15)
    return math.ceil(max_value / step - 1e-9) * step, step


def _tick_text(value: float, step: float, money: bool) -> str:
    decimals = max(0, -math.floor(math.log10(step)) + (1 if round(step / 10 ** math.floor(math.log10(step)), 6) == 2.5 else 0))
    return f"${value:.{decimals}f}" if money else f"{value:.{decimals}f} s"


def _ticks(top: float, step: float) -> list[float]:
    return [index * step for index in range(int(round(top / step)) + 1)]


def _quality_ticks(q_min: float, y_of: Callable[[float], float]) -> list[tuple[float, str]]:
    step = 0.05 if 1.0 - q_min <= 0.3 else 0.1
    count = int(round((1.0 - q_min) / step))
    return [(y_of(q_min + index * step), f"{q_min + index * step:.2f}") for index in range(count + 1)]


def _axes(drawing: Drawing, left: float, bottom: float, width: float, height: float,
          x_ticks: list[tuple[float, str]], y_ticks: list[tuple[float, str]], x_label: str, y_label: str) -> None:
    drawing.add(Line(left, bottom, left + width, bottom, strokeColor=base.MID_GRAY, strokeWidth=0.6))
    drawing.add(Line(left, bottom, left, bottom + height, strokeColor=base.MID_GRAY, strokeWidth=0.6))
    for x, text in x_ticks:
        drawing.add(Line(x, bottom, x, bottom - 3, strokeColor=base.MID_GRAY, strokeWidth=0.5))
        drawing.add(String(x, bottom - 12, text, textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=base.GRAY))
    for y, text in y_ticks:
        drawing.add(Line(left, y, left + width, y, strokeColor=base.LIGHT_GRAY, strokeWidth=0.4))
        drawing.add(String(left - 5, y - 2.5, text, textAnchor="end", fontName="Helvetica", fontSize=7, fillColor=base.GRAY))
    drawing.add(String(left + width / 2, bottom - 26, x_label, textAnchor="middle", fontName="Helvetica", fontSize=8, fillColor=base.GRAY))
    drawing.add(String(left - 36, bottom + height + 8, y_label, textAnchor="start", fontName="Helvetica", fontSize=8, fillColor=base.GRAY))


def frontier_chart(report: SetReport, x_field: str, run_field: str, x_label: str, money: bool) -> Drawing | None:
    """Quality against cost (or seconds): run points, the mean with its run range, dominance."""

    frontier = report.frontier.dropna(subset=[x_field, "quality_with_telemetry"])
    runs = report.runs[report.runs["has_telemetry"]]
    if frontier.empty:
        return None
    width, height = 340, 230
    left, bottom, plot_w, plot_h = 52, 40, 270, 165
    x_max, x_step = nice_axis(max(float(frontier[x_field].max()), float(runs[run_field].max())) * 1.12)
    q_values = list(frontier["quality_with_telemetry"]) + list(runs["quality"])
    q_min = max(0.0, math.floor((min(q_values) - 0.05) * 10) / 10)
    drawing = Drawing(width, height)

    def x_of(value: float) -> float:
        return left + plot_w * value / x_max

    def y_of(value: float) -> float:
        return bottom + plot_h * (value - q_min) / (1.0 - q_min)

    x_ticks = [(x_of(value), _tick_text(value, x_step, money)) for value in _ticks(x_max, x_step)]
    y_ticks = _quality_ticks(q_min, y_of)
    _axes(drawing, left, bottom, plot_w, plot_h, x_ticks, y_ticks, x_label, "Quality")
    colors = _color_map(report.configurations)
    dominated_column = "dominated_on_cost_by" if money else "dominated_on_time_by"
    for _, run in runs.iterrows():
        color = colors.get(run["configuration"], base.GRAY)
        drawing.add(Circle(x_of(run[run_field]), y_of(run["quality"]), 2.4, fillColor=color, strokeColor=None, fillOpacity=0.45))
    for _, row in frontier.iterrows():
        dominated = bool(base._as_text(row[dominated_column]))
        color = DOMINATED_GRAY if dominated else colors[row["configuration"]]
        x, y = x_of(row[x_field]), y_of(row["quality_with_telemetry"])
        low, high = (row["list_run_min"], row["list_run_max"]) if money else (row["seconds_run_min"], row["seconds_run_max"])
        if base._as_float(low) is not None:
            drawing.add(Line(x_of(low), y, x_of(high), y, strokeColor=color, strokeWidth=1))
        drawing.add(Line(x, y_of(row["quality_run_min"]), x, y_of(row["quality_run_max"]), strokeColor=color, strokeWidth=1))
        drawing.add(Circle(x, y, 4.5, fillColor=color, strokeColor=base.BLACK, strokeWidth=0.6))
        label = row["configuration"] + (" (dominated)" if dominated else "")
        drawing.add(String(x + 7, y + 4, label, fontName="Helvetica", fontSize=6.5, fillColor=base.BLACK))
    return drawing


def delta_chart(report: SetReport, configuration: str) -> Drawing | None:
    """Per-question change in quality against the baseline, worst first."""

    detail = report.paired_questions
    if detail.empty:
        return None
    detail = detail[detail["configuration"] == configuration].sort_values(["delta_quality", "question_id"])
    if detail.empty:
        return None
    row_h = 11
    width, height = 690, 30 + row_h * len(detail)
    left, center, half = 60, 330, 220
    drawing = Drawing(width, height)
    top = height - 14
    drawing.add(String(center - half, top + 2, "-1", textAnchor="middle", fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    drawing.add(String(center, top + 2, "0", textAnchor="middle", fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    drawing.add(String(center + half, top + 2, "+1", textAnchor="middle", fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    drawing.add(String(center + half + 40, top + 2, "list $ change", textAnchor="start", fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    drawing.add(Line(center, 8, center, top - 2, strokeColor=base.MID_GRAY, strokeWidth=0.6))
    for index, (_, row) in enumerate(detail.iterrows()):
        y = top - 12 - index * row_h
        delta = float(row["delta_quality"])
        drawing.add(String(left - 4, y, row["question_id"], textAnchor="end", fontName="Helvetica", fontSize=6.5, fillColor=base.BLACK))
        if abs(delta) > 1e-9:
            color = base.GREEN if delta > 0 else base.RED
            x0 = center if delta > 0 else center + half * delta
            drawing.add(Rect(x0, y - 1, half * abs(delta), 7, fillColor=color, strokeColor=None))
            drawing.add(String(center + half * delta + (4 if delta > 0 else -4), y, f"{delta:+.2f}",
                               textAnchor="start" if delta > 0 else "end", fontName="Helvetica", fontSize=6, fillColor=base.BLACK))
        else:
            drawing.add(Circle(center, y + 2.5, 1.4, fillColor=base.GRAY, strokeColor=None))
        drawing.add(String(center + half + 40, y, _signed_money(row["delta_list"]), fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    return drawing


def stacked_share_chart(table: pd.DataFrame, category_field: str, share_field: str,
                        order: list[str], colors: dict[str, Color], title: str) -> Drawing | None:
    """One horizontal bar per configuration, split into shares (roles or paths)."""

    if table.empty:
        return None
    configurations = list(dict.fromkeys(table["configuration"]))
    bar_h, gap = 14, 8
    width = 690
    height = 40 + len(configurations) * (bar_h + gap)
    left, plot_w = 150, 500
    drawing = Drawing(width, height)
    drawing.add(String(left, height - 10, title, fontName="Helvetica", fontSize=7.5, fillColor=base.GRAY))
    for index, configuration in enumerate(configurations):
        y = height - 32 - index * (bar_h + gap)
        drawing.add(String(left - 6, y + 4, configuration, textAnchor="end", fontName="Helvetica", fontSize=7, fillColor=base.BLACK))
        x = left
        mine = table[table["configuration"] == configuration].set_index(category_field)
        for category in order:
            if category not in mine.index:
                continue
            share = base._as_float(mine.loc[category, share_field]) or 0.0
            segment = plot_w * share
            drawing.add(Rect(x, y, segment, bar_h, fillColor=colors.get(category, base.GRAY), strokeColor=base.WHITE, strokeWidth=0.5))
            if share >= 0.06:
                drawing.add(String(x + segment / 2, y + 4, f"{share:.0%}", textAnchor="middle", fontName="Helvetica-Bold", fontSize=6.5, fillColor=base.WHITE))
            x += segment
    legend_x = left
    for category in order:
        if category not in set(table[category_field]):
            continue
        drawing.add(Rect(legend_x, 4, 8, 8, fillColor=colors.get(category, base.GRAY), strokeColor=None))
        drawing.add(String(legend_x + 11, 5, category, fontName="Helvetica", fontSize=6.5, fillColor=base.BLACK))
        legend_x += 18 + 4.2 * len(category)
    return drawing


def strip_chart(report: SetReport) -> Drawing | None:
    """Every question-run's list cost, one row per configuration, colored by verdict."""

    measured = report.rows[report.rows["cost_list_usd"].notna()]
    if measured.empty:
        return None
    configurations = report.configurations
    row_h = 24
    width, height = 690, 50 + row_h * len(configurations)
    left, plot_w = 150, 500
    x_max, x_step = nice_axis(float(measured["cost_list_usd"].max()) * 1.02)
    drawing = Drawing(width, height)

    def x_of(value: float) -> float:
        return left + plot_w * value / x_max

    bottom = 30
    drawing.add(Line(left, bottom, left + plot_w, bottom, strokeColor=base.MID_GRAY, strokeWidth=0.6))
    for value in _ticks(x_max, x_step):
        drawing.add(String(x_of(value), bottom - 11, _tick_text(value, x_step, True), textAnchor="middle", fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    drawing.add(String(left + plot_w / 2, 4, "List cost per question-run (USD)", textAnchor="middle", fontName="Helvetica", fontSize=7.5, fillColor=base.GRAY))
    for index, configuration in enumerate(configurations):
        y = bottom + 14 + (len(configurations) - 1 - index) * row_h
        drawing.add(String(left - 6, y - 2, configuration, textAnchor="end", fontName="Helvetica", fontSize=7, fillColor=base.BLACK))
        mine = measured[measured["label"] == configuration]
        for position, (_, row) in enumerate(mine.iterrows()):
            jitter = ((position * 37) % 9 - 4) * 1.2
            drawing.add(Circle(x_of(row["cost_list_usd"]), y + jitter, 2.2, fillColor=VERDICT_COLORS[row["score"]], strokeColor=None, fillOpacity=0.75))
        cost = pd.to_numeric(mine["cost_list_usd"], errors="coerce")
        for quantile, dash in ((0.5, None), (0.9, (2, 2))):
            x = x_of(float(cost.quantile(quantile)))
            drawing.add(Line(x, y - 9, x, y + 9, strokeColor=base.NAVY, strokeWidth=0.9, strokeDashArray=dash))
    legend_x = left + plot_w - 230
    for name, color in VERDICT_COLORS.items():
        drawing.add(Circle(legend_x, height - 8, 3, fillColor=color, strokeColor=None))
        drawing.add(String(legend_x + 6, height - 10.5, name, fontName="Helvetica", fontSize=6.5, fillColor=base.BLACK))
        legend_x += 45
    drawing.add(String(legend_x, height - 10.5, "solid line p50, dashed p90", fontName="Helvetica", fontSize=6.5, fillColor=base.GRAY))
    return drawing


def run_order_chart(report: SetReport) -> Drawing | None:
    """Seconds per question in run order, with cached share and the probe role's latency.

    Each bar carries only its run number and figures; the configurations are named once,
    in a colour legend underneath, so the labels never collide however many runs there are.
    """

    runs = report.runs[report.runs["has_telemetry"]].sort_values("order")
    if runs.empty:
        return None
    configurations = list(dict.fromkeys(runs["configuration"]))
    legend_rows = (len(configurations) + 2) // 3
    width = 690
    left, plot_w, plot_h = 60, 600, 115
    bottom = 58 + 14 * legend_rows
    height = bottom + plot_h + 30
    s_max, s_step = nice_axis(float(runs["seconds"].max()) * 1.15, 4)
    drawing = Drawing(width, height)
    colors = _color_map(report.configurations)
    slot = plot_w / len(runs)
    bar_w = min(48, slot * 0.6)
    y_ticks = [(bottom + plot_h * value / s_max, _tick_text(value, s_step, False)) for value in _ticks(s_max, s_step)]
    _axes(drawing, left, bottom, plot_w, plot_h, [], y_ticks, "", "Seconds per question")
    probe = f"median_call_s_{LATENCY_PROBE_ROLE}"
    for index, (_, run) in enumerate(runs.iterrows()):
        x = left + slot * (index + 0.5)
        bar_h = plot_h * float(run["seconds"]) / s_max
        drawing.add(Rect(x - bar_w / 2, bottom, bar_w, bar_h, fillColor=colors.get(run["configuration"], base.GRAY), strokeColor=None))
        drawing.add(String(x, bottom + bar_h + 11, f"{run['seconds']:.1f} s", textAnchor="middle", fontName="Helvetica", fontSize=6, fillColor=base.BLACK))
        drawing.add(String(x, bottom + bar_h + 3, f"cached {run['cached_share']:.0%}", textAnchor="middle", fontName="Helvetica", fontSize=5.5, fillColor=base.GRAY))
        drawing.add(String(x, bottom - 11, str(int(run["order"])), textAnchor="middle", fontName="Helvetica-Bold", fontSize=7, fillColor=base.BLACK))
        if probe in run and base._as_float(run[probe]) is not None:
            drawing.add(String(x, bottom - 21, f"{run[probe]:.2f} s", textAnchor="middle", fontName="Helvetica", fontSize=5.5, fillColor=base.GRAY))
    drawing.add(String(left - 6, bottom - 11, "Run", textAnchor="end", fontName="Helvetica", fontSize=6, fillColor=base.GRAY))
    drawing.add(String(left - 6, bottom - 21, f"{LATENCY_PROBE_ROLE} s/call", textAnchor="end", fontName="Helvetica", fontSize=5.5, fillColor=base.GRAY))
    for index, configuration in enumerate(configurations):
        column, row = index % 3, index // 3
        x, y = left + column * 205, bottom - 40 - row * 14
        orders = [str(int(order)) for order in runs[runs["configuration"] == configuration]["order"]]
        drawing.add(Rect(x, y, 8, 8, fillColor=colors.get(configuration, base.GRAY), strokeColor=None))
        drawing.add(String(x + 12, y + 1, f"{configuration} (run{'s' if len(orders) > 1 else ''} {', '.join(orders)})",
                           fontName="Helvetica", fontSize=6.5, fillColor=base.BLACK))
    return drawing


def policy_chart(policies: pd.DataFrame) -> Drawing | None:
    if policies.empty:
        return None
    width, height = 690, 230
    left, bottom, plot_w, plot_h = 60, 40, 420, 165
    x_max, x_step = nice_axis(float(policies["list_per_question"].max()) * 1.1)
    q_min = max(0.0, math.floor((float(policies["quality"].min()) - 0.05) * 10) / 10)
    drawing = Drawing(width, height)

    def x_of(value: float) -> float:
        return left + plot_w * value / x_max

    def y_of(value: float) -> float:
        return bottom + plot_h * (value - q_min) / (1.0 - q_min)

    x_ticks = [(x_of(value), _tick_text(value, x_step, True)) for value in _ticks(x_max, x_step)]
    y_ticks = _quality_ticks(q_min, y_of)
    _axes(drawing, left, bottom, plot_w, plot_h, x_ticks, y_ticks, "List cost per question (USD)", "Quality")
    for index, (_, row) in enumerate(policies.iterrows()):
        color = PALETTE[index % len(PALETTE)]
        x, y = x_of(row["list_per_question"]), y_of(row["quality"])
        drawing.add(Circle(x, y, 4, fillColor=color, strokeColor=base.BLACK, strokeWidth=0.5))
        drawing.add(String(x + 6, y + 3, str(index + 1), fontName="Helvetica-Bold", fontSize=7, fillColor=base.BLACK))
        drawing.add(Rect(left + plot_w + 25, height - 30 - index * 15, 7, 7, fillColor=color, strokeColor=None))
        drawing.add(String(left + plot_w + 36, height - 29 - index * 15, f"{index + 1}. {row['policy']}", fontName="Helvetica", fontSize=6.5, fillColor=base.BLACK))
    return drawing


# ---------------------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------------------

READING_GUIDE = [
    ("Quality", "pass = 1, partial = 0.5, fail = 0, averaged over question-runs (RAGAS judge)."),
    ("List cost", "every input token at the full price: the comparison of record. Billed cost charges cached input at the cached rate, so it falls when runs repeat the same questions."),
    ("Seconds", "agent graph plus answer per question, judge excluded. Provider speed varies by hour; §6 shows how much."),
    ("Dominated", "another configuration is at least as good and no more expensive (or slower), and better on one of the two."),
    ("Paired", "each question's mean over its runs, configuration minus baseline; p from the Wilcoxon signed-rank test over the questions that changed."),
    ("Paths", "Table: the TOC review flagged a table. Text, escalated: an assessment asked for more evidence. Text, ready: neither."),
]


def _footer(canvas: Any, document: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setStrokeColor(base.MID_GRAY)
    canvas.setLineWidth(0.4)
    canvas.line(0.55 * inch, 0.42 * inch, base.PAGE_WIDTH - 0.55 * inch, 0.42 * inch)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(base.GRAY)
    canvas.drawString(0.55 * inch, 0.22 * inch, "Accuracy, cost, and latency")
    canvas.drawRightString(base.PAGE_WIDTH - 0.55 * inch, 0.22 * inch, f"Page {document.page}")
    canvas.restoreState()


def _chart(drawing: Drawing | None, max_height: float = 330) -> list[Any]:
    if drawing is None:
        return []
    return [base._fit_drawing(drawing, CONTENT_WIDTH, max_height), Spacer(1, 4)]


def _set_story(report: SetReport, styles: dict[str, ParagraphStyle]) -> list[Any]:
    story: list[Any] = [Paragraph(html.escape(report.name), styles["h1"])]
    configs = len(report.frontier)
    story.append(base._paragraph(
        f"{configs} configuration(s), {report.runs['run'].nunique()} run(s), {len(report.rows)} question-runs. {report.baseline_note}",
        styles["body"],
    ))

    # §1 Frontier
    story.append(Paragraph("1. Frontier: quality against cost and time", styles["h2"]))
    body = []
    for _, row in report.frontier.iterrows():
        body.append([
            row["configuration"],
            f"{row['runs']} ({row['telemetry_runs']})",
            f"{_num(row['quality'])} ({_range(row['quality_run_min'], row['quality_run_max'], _num)})",
            f"{row['pass']}/{row['partial']}/{row['fail']}",
            f"{_money(row['list_cost'])} ({_range(row['list_run_min'], row['list_run_max'], _money)})",
            _money(row["billed_cost"]),
            _pct(row["cached_share"]),
            f"{_num(row['seconds'], 1)} / {_num(row['seconds_median'], 1)}",
            _num(row["calls"], 2),
            _thousands(row["input_tokens"]),
            _money(row["list_per_quality_point"]),
            base._as_text(row["dominated_on_cost_by"]) or "-",
            base._as_text(row["dominated_on_time_by"]) or "-",
        ])
    story.append(_table(
        ["Configuration", "Runs (with telemetry)", "Quality (run range)", "Pass / partial / fail", "List $/q (run range)",
         "Billed $/q", "Cached", "Seconds mean / median", "Calls/q", "Input tokens/q", "List $ per quality point",
         "Dominated on cost by", "Dominated on time by"],
        body, [96, 46, 70, 48, 88, 46, 44, 50, 38, 44, 50, 66, 66], styles,
    ))
    cost_chart = frontier_chart(report, "list_cost", "list_cost", "List cost per question (USD)", money=True)
    time_chart = frontier_chart(report, "seconds", "seconds", "Seconds per question", money=False)
    if cost_chart is not None and time_chart is not None:
        pair = Table([[cost_chart, time_chart]], colWidths=[CONTENT_WIDTH / 2] * 2, hAlign="LEFT")
        story.extend([Spacer(1, 6), pair])
    story.append(base._paragraph(
        "Small dots are runs; a large dot is the configuration mean, with lines across its run range. Gray: dominated.",
        styles["note"],
    ))

    # §2 Paired
    story.append(PageBreak())
    story.append(Paragraph(f"2. Paired against the baseline ({html.escape(report.baseline)})", styles["h2"]))
    if report.paired.empty:
        story.append(base._paragraph("Only one configuration on this set: nothing to pair.", styles["body"]))
    else:
        body = []
        for _, row in report.paired.iterrows():
            body.append([
                row["configuration"],
                row["questions_compared"],
                f"{_num(row['quality_baseline'])} -> {_num(row['quality_configuration'])}",
                _signed(row["delta_quality"]),
                f"{row['questions_better']} / {row['questions_worse']} / {row['questions_unchanged']}",
                _p(row["p_quality"]),
                f"{_signed_money(row['delta_list'])} ({_signed_pct(row['delta_list_pct'])})",
                _p(row["p_list"]),
                _signed(row["delta_seconds"], 1),
                _p(row["p_seconds"]),
                row["verdict"],
            ])
        story.append(_table(
            ["Configuration", "Questions", "Quality", "Δ quality", "Better / worse / same", "p (quality)",
             "Δ list $/q", "p (cost)", "Δ seconds", "p (time)", "Trade-off"],
            body, [96, 52, 70, 44, 66, 44, 82, 40, 46, 40, 164], styles,
        ))
        story.append(base._paragraph(
            "Per-question change in quality, worst first (right column: change in list cost):", styles["note"]))
        for configuration in report.paired["configuration"]:
            story.append(base._paragraph(f"{configuration} against {report.baseline}", styles["body"]))
            story.extend(_chart(delta_chart(report, configuration), max_height=420))

    # §3 Roles
    story.append(PageBreak())
    story.append(Paragraph("3. Where the cost goes: by role", styles["h2"]))
    if report.roles.empty:
        story.append(base._paragraph("No per-call telemetry on this set.", styles["body"]))
    else:
        role_order = sorted(report.roles["role"].unique(), key=_role_key)
        role_colors = {role: PALETTE[index % len(PALETTE)] for index, role in enumerate(role_order)}
        story.extend(_chart(stacked_share_chart(report.roles, "role", "share_of_list", role_order, role_colors, "Share of list cost")))
        story.extend(_chart(stacked_share_chart(report.roles, "role", "share_of_model_time", role_order, role_colors, "Share of model time")))
        body = [[row["configuration"], row["role"], _num(row["calls_per_question"], 2), _thousands(row["input_tokens_per_question"]),
                 _num(row["output_tokens_per_question"], 0), _pct(row["cached_share"]), _money(row["list_per_question"]),
                 _pct(row["share_of_list"]), _num(row["model_seconds_per_question"], 1), _pct(row["share_of_model_time"]),
                 _num(row["median_call_seconds"], 2)] for _, row in report.roles.iterrows()]
        story.append(_table(
            ["Configuration", "Role", "Calls/q", "Input tokens/q", "Output tokens/q", "Cached", "List $/q",
             "Share of list", "Model s/q", "Share of time", "Median s/call"],
            body, [110, 70, 46, 60, 60, 46, 60, 56, 52, 56, 56], styles,
        ))

    # §4 Paths
    story.append(PageBreak())
    story.append(Paragraph("4. By path: text ready, text escalated, table", styles["h2"]))
    story.extend(_chart(stacked_share_chart(report.paths, "path", "share_of_list_spend", list(PATH_ORDER), PATH_COLORS, "Share of list spend by path")))
    body = [[row["configuration"], row["path"], f"{row['question_runs']} ({_pct(row['share_of_question_runs'])})",
             _num(row["quality"]), _money(row["list_per_question"]), _money(row["billed_per_question"]),
             _num(row["seconds"], 1), _pct(row["share_of_list_spend"])] for _, row in report.paths.iterrows()]
    story.append(_table(
        ["Configuration", "Path", "Question-runs (share)", "Quality", "List $/q", "Billed $/q", "Seconds/q", "Share of list spend"],
        body, [120, 150, 80, 56, 66, 66, 56, 76], styles,
    ))

    # §5 Tail
    story.append(PageBreak())
    story.append(Paragraph("5. Tail and waste", styles["h2"]))
    story.extend(_chart(strip_chart(report)))
    body = [[row["configuration"], _money(row["list_p50"]), _money(row["list_p90"]), _money(row["list_max"]),
             f"{_num(row['max_over_mean'], 1)}x", _num(row["seconds_p50"], 1), _num(row["seconds_p90"], 1),
             _num(row["seconds_max"], 1), _pct(row["spend_on_fail_share"]), _pct(row["spend_on_partial_share"]),
             _money(row["list_per_pass"])] for _, row in report.tail.iterrows()]
    story.append(_table(
        ["Configuration", "List p50", "List p90", "List max", "Max / mean", "Seconds p50", "Seconds p90", "Seconds max",
         "Spend on fails", "Spend on partials", "List $ per pass"],
        body, [120, 56, 56, 56, 50, 54, 54, 54, 56, 60, 64], styles,
    ))
    story.append(Spacer(1, 6))
    story.append(base._paragraph("Most expensive question-runs:", styles["body"]))
    body = [[row["configuration"], row["run"], row["question_id"], row["path"], row["score"], _money(row["list_cost"]),
             _num(row["seconds"], 1), _num(row["calls"], 0)] for _, row in report.top_expensive.iterrows()]
    story.append(_table(["Configuration", "Run", "Question", "Path", "Verdict", "List $", "Seconds", "Calls"],
                        body, [120, 110, 56, 150, 50, 60, 50, 40], styles))

    # §6 Comparability
    story.append(PageBreak())
    story.append(Paragraph("6. Comparability: run order, caching, and provider speed", styles["h2"]))
    story.extend(_chart(run_order_chart(report)))
    roles_seen = sorted({column.removeprefix("median_call_s_") for column in report.runs.columns if column.startswith("median_call_s_")}, key=_role_key)
    body = []
    for _, run in report.runs.sort_values("order").iterrows():
        finished = run["finished"]
        body.append([
            f"{int(run['order'])}. {run['configuration']}", run["run"],
            finished.strftime("%Y-%m-%d %H:%M") if not pd.isna(finished) else "n/a",
            _num(run["quality"]), _money(run["list_cost"]), _money(run["billed_cost"]), _num(run["billed_to_list"], 2),
            _pct(run["cached_share"]), _num(run["seconds"], 1),
            *[_num(run.get(f"median_call_s_{role}"), 2) for role in roles_seen],
        ])
    story.append(_table(
        ["Run (order)", "Results CSV", "Finished", "Quality", "List $/q", "Billed $/q", "Billed / list", "Cached", "Seconds per q",
         *[f"{ROLE_SHORT.get(role, role)} s/call" for role in roles_seen]],
        body, [92, 104, 62, 40, 52, 52, 42, 44, 46, *[46] * len(roles_seen)], styles,
    ))
    sources = sorted(set(report.runs["time_source"].dropna()))
    story.append(base._paragraph("Run times from: " + ", ".join(sources) + ".", styles["note"]))
    if report.warnings:
        story.append(Paragraph("Warnings", styles["h2"]))
        for warning in report.warnings:
            story.append(base._paragraph("- " + warning, styles["body"]))
    else:
        story.append(base._paragraph("No comparability warnings.", styles["body"]))

    # §7 Safeguards
    story.append(PageBreak())
    story.append(Paragraph("7. Safeguard markers", styles["h2"]))
    body = [[row["configuration"], row["question_runs"],
             f"{row['evidence_notice']} ({_pct(row['evidence_notice_rate'])})",
             f"{row['notice_pass']}/{row['notice_partial']}/{row['notice_fail']}",
             row["grounding_checked"] or "not checked",
             f"{row['grounding_flagged']} ({_pct(row['grounding_flagged_rate'])})" if row["grounding_checked"] else "-",
             f"{row['flagged_pass']}/{row['flagged_partial']}/{row['flagged_fail']}" if row["grounding_checked"] else "-",
             row["check_passed_but_fail"] if row["grounding_checked"] else "-",
             row["input_sanitized"]] for _, row in report.safeguards.iterrows()]
    story.append(_table(
        ["Configuration", "Question-runs", "Evidence notice", "Noticed: pass / partial / fail", "Grounding checked",
         "Flagged", "Flagged: pass / partial / fail", "Check passed, judge failed", "Input sanitized"],
        body, [116, 64, 66, 84, 60, 60, 84, 70, 56], styles,
    ))
    story.append(base._paragraph(
        "A flagged answer the judge passed is a false alarm the user still sees (policy 'surface' labels it). "
        "'Check passed, judge failed' counts wrong answers the deterministic check cannot see.", styles["note"]))
    if not report.flagged_spans.empty:
        story.append(base._paragraph("Spans the grounding check could not find in the evidence:", styles["body"]))
        body = [[row["span"], row["kind"], row["count"], f"{row['pass']}/{row['partial']}/{row['fail']}", row["configurations"]]
                for _, row in report.flagged_spans.iterrows()]
        story.append(_table(["Span", "Kind", "Times", "Judge: pass / partial / fail", "Configurations"],
                            body, [220, 60, 40, 100, 200], styles))

    # §8 Routing
    story.append(PageBreak())
    story.append(Paragraph("8. Routing", styles["h2"]))
    story.append(base._paragraph(report.policy_note, styles["body"]))
    if not report.policies.empty:
        story.extend(_chart(policy_chart(report.policies)))
        body = [[f"{index + 1}. {row['policy']}", row["description"], _num(row["quality"]), _money(row["list_per_question"]),
                 _num(row["seconds"], 1), _pct(row["sent_to_strong"]), _pct(row["paid_twice"]), _pct(row["saving_vs_all_strong"])]
                for index, (_, row) in enumerate(report.policies.iterrows())]
        story.append(_table(
            ["Policy", "Rule", "Quality", "List $/q", "Seconds/q", "Sent to strong", "Paid twice", "Saving vs all strong"],
            body, [150, 220, 46, 56, 50, 50, 46, 60], styles,
        ))
        story.append(base._paragraph(
            "Simulated on saved runs: a routed question takes the strong configuration's mean outcome, cost, and time for "
            "that question. A routed system is a different run, so the simulation predicts and a live run confirms.",
            styles["note"]))
    if report.routes.empty:
        story.append(base._paragraph("Route mix: no run on this set records a router decision (column 'route').", styles["note"]))
    else:
        body = [[row["configuration"], row["route"], f"{row['question_runs']} ({_pct(row['share'])})", _num(row["quality"]),
                 _money(row["list_per_question"]), _num(row["seconds"], 1)] for _, row in report.routes.iterrows()]
        story.append(_table(["Configuration", "Route", "Question-runs (share)", "Quality", "List $/q", "Seconds/q"],
                            body, [140, 120, 90, 56, 66, 56], styles))
    return story


def create_pdf(reports: list[SetReport], data: EfficiencyData, output: Path, *, title: str, sources: list[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = base._styles()
    document = BaseDocTemplate(
        str(output),
        pagesize=base.PAGE_SIZE,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.55 * inch,
        title=title,
        author="Wikipedia Retrieval Engine capstone",
        subject="Accuracy against cost and latency",
    )
    frame = Frame(document.leftMargin, document.bottomMargin, document.width, document.height, id="frame")
    document.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_footer)])
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    story: list[Any] = [
        Paragraph(html.escape(title), styles["title"]),
        base._paragraph(f"Generated {generated}. Sources: " + "; ".join(str(path) for path in sources), styles["subtitle"]),
    ]
    body = []
    for report in reports:
        best = report.frontier.sort_values("quality", ascending=False).iloc[0]
        priced = report.frontier.dropna(subset=["list_cost"])
        cheapest = priced.sort_values("list_cost").iloc[0] if not priced.empty else None
        fastest = report.frontier.dropna(subset=["seconds"]).sort_values("seconds")
        body.append([
            report.name, len(report.frontier), report.runs["run"].nunique(), len(report.rows), report.baseline,
            f"{best['configuration']} ({_num(best['quality'])})",
            f"{cheapest['configuration']} ({_money(cheapest['list_cost'])})" if cheapest is not None else "n/a",
            f"{fastest.iloc[0]['configuration']} ({_num(fastest.iloc[0]['seconds'], 1)} s)" if not fastest.empty else "n/a",
        ])
    story.append(_table(["Question set", "Configurations", "Runs", "Question-runs", "Baseline", "Highest quality",
                         "Lowest list cost", "Fastest"], body, [90, 60, 40, 60, 100, 130, 130, 100], styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph("How to read this report", styles["h2"]))
    for term, text in READING_GUIDE:
        story.append(Paragraph(f"<b>{html.escape(term)}.</b> {html.escape(text)}", styles["body"]))
    if data.warnings:
        story.append(Paragraph("Loader warnings", styles["h2"]))
        for warning in data.warnings:
            story.append(base._paragraph("- " + warning, styles["note"]))
    for report in reports:
        story.append(PageBreak())
        story.extend(_set_story(report, styles))
    document.build(story)


# ---------------------------------------------------------------------------------------
# Console and CLI
# ---------------------------------------------------------------------------------------


def print_console_summary(reports: list[SetReport], output: Path, written: list[Path], warnings: list[str] = ()) -> None:
    for warning in warnings:
        print(f"! {warning}")
    for report in reports:
        print(f"\n== {report.name} ({report.baseline_note})")
        print(f"  {'configuration':<34}{'runs':>5}{'quality':>9}{'list $/q':>10}{'billed $/q':>11}{'s/q':>7}{'calls/q':>8}")
        for _, row in report.frontier.iterrows():
            print(f"  {row['configuration']:<34}{row['runs']:>5}{row['quality']:>9.3f}{_money(row['list_cost']):>10}"
                  f"{_money(row['billed_cost']):>11}{_num(row['seconds'], 1):>7}{_num(row['calls'], 2):>8}")
        for _, row in report.paired.iterrows():
            print(f"  vs {report.baseline}: {row['configuration']}: quality {_signed(row['delta_quality'])} "
                  f"(better {row['questions_better']}, worse {row['questions_worse']}, p {_p(row['p_quality'])}); "
                  f"list {_signed_money(row['delta_list'])}; seconds {_signed(row['delta_seconds'], 1)} -> {row['verdict']}")
        for warning in report.warnings:
            print(f"  ! {warning}")
    print(f"\nPDF: {output}")
    print(f"CSV tables: {written[0].parent if written else 'none'} ({len(written)} files)")


def _parse_alias(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=LABEL")
    name, label = text.split("=", 1)
    return name.strip(), label.strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Accuracy against cost and latency, from RAGAS runs with telemetry.")
    parser.add_argument("--experiments-dir", type=Path, nargs="+", default=[DEFAULT_EXPERIMENTS_DIR],
                        help=f"Directories searched recursively for runs (default: {DEFAULT_EXPERIMENTS_DIR}).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"PDF destination (default: {DEFAULT_OUTPUT}).")
    parser.add_argument("--csv-dir", type=Path, default=None, help="CSV tables (default: <output stem>_tables next to the PDF).")
    parser.add_argument("--baseline", default=None,
                        help="Configuration to pair against: a display label or an experiment name (default: the "
                             "configuration whose first run came first, per question set).")
    parser.add_argument("--alias", type=_parse_alias, action="append", default=[], metavar="NAME=LABEL",
                        help="Display label for an experiment name (repeatable).")
    parser.add_argument("--route-cheap", action="append", default=[], metavar="CONFIGURATION",
                        help="§8: the cheap configuration(s) of a routing simulation (repeatable; runs are pooled).")
    parser.add_argument("--route-strong", default=None, metavar="CONFIGURATION",
                        help="§8: the strong configuration of a routing simulation.")
    parser.add_argument("--text-categories", default=None,
                        help="§8: semicolon-separated categories treated as text by the category policy "
                             "(default: the README 7.1 Finding 3 set).")
    parser.add_argument("--route-labels", type=Path, action="append", default=[], metavar="CSV",
                        help="§8: a router's decisions (question_id, route = cheap or strong) to simulate; repeatable.")
    parser.add_argument("--title", default="Accuracy, cost, and latency")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    aliases = dict(args.alias)
    data = load_efficiency_data(args.experiments_dir, aliases=aliases)
    text_categories = (
        [category.strip() for category in args.text_categories.split(";") if category.strip()]
        if args.text_categories else list(FINDING_3_TEXT_CATEGORIES)
    )
    reports = [
        build_set_report(
            data, question_set,
            baseline=args.baseline,
            route_cheap=args.route_cheap,
            route_strong=args.route_strong,
            text_categories=text_categories,
            aliases=aliases,
            route_labels=dict(load_route_labels(path) for path in args.route_labels),
        )
        for question_set in data.question_sets()
    ]
    output = args.output.expanduser().resolve()
    csv_dir = (args.csv_dir or output.parent / f"{output.stem}_tables").expanduser().resolve()
    written = write_csv_tables(reports, data, csv_dir)
    create_pdf(reports, data, output, title=args.title, sources=[Path(path) for path in args.experiments_dir])
    print_console_summary(reports, output, written, data.warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main())

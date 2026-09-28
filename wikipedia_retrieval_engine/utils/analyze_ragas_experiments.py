#!/usr/bin/env python3
"""Analyze RAGAS experiment CSVs and create a comparison PDF.

The script recursively discovers experiment CSVs and groups repeated runs by an
explicit ``experiment_name`` / ``config_name`` when present, otherwise by the
configuration metadata stored in each file. The primary comparison excludes files
inside directories named ``pass_fail_only`` because those runs used an incompatible
binary scoring framework.

Examples
--------
Use the project defaults::

    python utils/analyze_ragas_experiments.py

Choose explicit locations::

    python utils/analyze_ragas_experiments.py \
        --experiments-dir "Capstone Checkpoint 3.1/ragas_experiments/experiments" \
        --output "/path/to/output/ragas_evaluation_report.pdf"

The report requires pandas and reportlab. It does not call an LLM or make network
requests.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - dependency error is user-facing
    raise SystemExit(
        "pandas is required. Install the Checkpoint 3.1 requirements first."
    ) from exc

try:
    from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.colors import Color, HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        KeepTogether,
        LongTable,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:  # pragma: no cover - dependency error is user-facing
    raise SystemExit(
        "reportlab is required to create the PDF. Install it with "
        "'python -m pip install reportlab==4.4.9'."
    ) from exc


SCRIPT_PATH = Path(__file__).resolve()
ENGINE_DIR = SCRIPT_PATH.parents[1]

# Checkpoint 6.1 cost telemetry, written next to a run as
# <output>/telemetry/<run>__*.csv by the cost starters. These files are merged into
# their run, never read as runs themselves.
TELEMETRY_SUFFIXES = ("__llm_calls.csv", "__node_timings.csv", "__question_telemetry.csv")
COST_COLUMNS = (
    "telemetry_calls",
    "telemetry_input_tokens",
    "telemetry_output_tokens",
    "telemetry_cached_tokens",
    "cost_list_usd",
    "cost_billed_usd",
    "agent_seconds",
)
DEFAULT_EXPERIMENTS_DIR = (
    ENGINE_DIR
    / "Capstone Checkpoint 3.1"
    / "ragas_experiments"
    / "experiments"
)
# This resolves to RAGandContextEng/output/pdf, outside the capstone repository.
DEFAULT_OUTPUT = (
    SCRIPT_PATH.parents[4]
    / "output"
    / "pdf"
    / "ragas_evaluation_report.pdf"
)

PAGE_SIZE = landscape(letter)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

NAVY = HexColor("#19324A")
BLUE = HexColor("#3B6EA5")
LIGHT_BLUE = HexColor("#DCE8F3")
GREEN = HexColor("#3C8D6B")
LIGHT_GREEN = HexColor("#DDEFE7")
AMBER = HexColor("#D89C36")
LIGHT_AMBER = HexColor("#F8EBCF")
RED = HexColor("#C65B55")
LIGHT_RED = HexColor("#F3DDDB")
GRAY = HexColor("#68737D")
LIGHT_GRAY = HexColor("#EEF1F3")
MID_GRAY = HexColor("#C8CED3")
WHITE = colors.white
BLACK = HexColor("#20262B")

SCORE_VALUE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
SCORE_COLORS = {"pass": GREEN, "partial": AMBER, "fail": RED}

# The original 19-case dataset uses intentionally specific category names. Most
# categories contain only one question, which makes category-level percentages look
# more certain than they are. These broader families preserve the task distinction
# while providing two to six questions per group.
TASK_FAMILY_BY_CATEGORY = {
    "direct fact and quotation": "Direct fact or table lookup",
    "direct fact": "Direct fact or table lookup",
    "table lookup": "Direct fact or table lookup",
    "open-list question and quotations": "Evidence selection or explanation",
    "process explanation": "Evidence selection or explanation",
    "uncertainty and conflicting estimates": "Evidence selection or explanation",
    "cross-article exhaustive intersection and winner classification": (
        "Exhaustive list or time filter"
    ),
    "temporal aggregation": "Exhaustive list or time filter",
    "program-history filter": "Exhaustive list or time filter",
    "historical identity timeline": "Exhaustive list or time filter",
    "historical entity resolution": "Entity relationship or historical synthesis",
    "people connection: shared work and awards": (
        "Entity relationship or historical synthesis"
    ),
    "people connection: repeated collaboration": (
        "Entity relationship or historical synthesis"
    ),
    "people connection: intermediary person": (
        "Entity relationship or historical synthesis"
    ),
    "geopolitical state-formation timeline": (
        "Entity relationship or historical synthesis"
    ),
    "geopolitical entity relationships": (
        "Entity relationship or historical synthesis"
    ),
    "cross-table comparison": "Cross-table quantitative reasoning",
    "geopolitical cross-table calculation": "Cross-table quantitative reasoning",
}
TASK_FAMILY_ORDER = {
    "Direct fact or table lookup": 10,
    "Evidence selection or explanation": 20,
    "Exhaustive list or time filter": 30,
    "Entity relationship or historical synthesis": 40,
    "Cross-table quantitative reasoning": 50,
    "Other or unclassified": 90,
}
SOURCE_SCOPE_ORDER = {"1 article": 10, "2 articles": 20, "3+ articles": 30}


@dataclass
class AnalysisData:
    rows: pd.DataFrame
    run_summary: pd.DataFrame
    config_summary: pd.DataFrame
    task_summary: pd.DataFrame
    scope_summary: pd.DataFrame
    included_files: list[Path]
    excluded_files: list[tuple[Path, str]]
    warnings: list[str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze RAGAS experiment CSVs and create a comparison PDF."
    )
    parser.add_argument(
        "--experiments-dir",
        type=Path,
        nargs="+",
        default=[DEFAULT_EXPERIMENTS_DIR],
        help=(
            "One or more directories searched recursively for CSVs "
            f"(default: {DEFAULT_EXPERIMENTS_DIR})"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"PDF destination (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--include-binary-oracle",
        action="store_true",
        help="Include legacy oracle runs stored under pass_fail_only directories.",
    )
    parser.add_argument(
        "--title",
        default="RAGAS evaluation results",
        help="Title printed on the report.",
    )
    return parser.parse_args(argv)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _as_float(value: Any) -> float | None:
    text = _as_text(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _format_number(value: Any) -> str:
    number = _as_float(value)
    if number is None:
        return "?"
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _split_articles(value: Any) -> list[str]:
    return [part.strip() for part in _as_text(value).split(";") if part.strip()]


def _canonical_article_name(name: str) -> str:
    """Normalize only known final suffixes, preserving periods inside the title."""
    normalized = name.strip()
    normalized = normalized.removesuffix(".txt")
    normalized = normalized.removesuffix(".html")
    return normalized.casefold()


def _recomputed_article_recall(row: pd.Series) -> float | None:
    if _as_text(row.get("evaluation_mode")) == "oracle_ground_truth_context":
        return None

    required_value = row.get("required_articles", row.get("source_articles", ""))
    required = _split_articles(required_value)
    retrieved = _split_articles(row.get("retrieved_articles", ""))
    if not required:
        return None

    retrieved_set = {_canonical_article_name(name) for name in retrieved}
    matches = sum(
        _canonical_article_name(name) in retrieved_set
        for name in required
    )
    return matches / len(required)


def _configuration_metadata(first: pd.Series) -> tuple[str, str, int]:
    mode = _as_text(first.get("evaluation_mode"))
    answer_model = _as_text(first.get("answer_model")) or "unknown-answer-model"
    judge_model = _as_text(first.get("judge_model")) or "unknown-judge-model"
    # Context representation sent to the LLM (e.g. plain_text vs markdown). Runs made
    # before this column existed report as "unspecified": they keep grouping together
    # as before and get no label suffix, so legacy reports are unchanged. New runs that
    # differ only by context become distinct configurations, shown side by side.
    context = _as_text(first.get("context_source")) or "unspecified"
    ctx_tag = "" if context == "unspecified" else f" [{context}]"

    if mode == "oracle_ground_truth_context":
        config_id = f"oracle|answer={answer_model}|judge={judge_model}|context={context}"
        return config_id, f"Oracle context{ctx_tag}", 0

    kind = _as_text(first.get("retriever_kind")).lower() or "retriever"
    label = _as_text(first.get("retriever_label")) or kind
    top_k = _format_number(first.get("retrieval_top_k"))

    if kind == "hybrid":
        bm25 = _as_float(first.get("weight_bm25"))
        vector = _as_float(first.get("weight_vector"))
        bm25_text = f"{bm25 * 100:.0f}" if bm25 is not None else "?"
        vector_text = f"{vector * 100:.0f}" if vector is not None else "?"
        display = f"Hybrid k={top_k} ({bm25_text}/{vector_text}){ctx_tag}"
        order = 30
    elif kind == "vector":
        display = f"Vector k={top_k}{ctx_tag}"
        order = 20
    elif kind == "bm25":
        display = f"BM25 k={top_k}{ctx_tag}"
        order = 10
    else:
        display = f"{label} k={top_k}{ctx_tag}"
        order = 40

    config_id = (
        f"{kind}|label={label}|k={top_k}|"
        f"bm25={_as_text(first.get('weight_bm25'))}|"
        f"vector={_as_text(first.get('weight_vector'))}|"
        f"context={context}|"
        f"answer={answer_model}|judge={judge_model}"
    )
    return config_id, display, order


def _explicit_experiment_name(first: pd.Series) -> str:
    """Read a user-provided comparison label from current or future CSV schemas."""
    for column in ("experiment_name", "config_name"):
        name = _as_text(first.get(column))
        if name:
            return name
    return ""


def _comparison_metadata(first: pd.Series) -> tuple[str, str, int, str, str, bool]:
    """Resolve the grouping label, preserving the existing derived-label fallback."""
    derived_id, derived_label, order = _configuration_metadata(first)
    experiment_name = _explicit_experiment_name(first)
    if experiment_name:
        return (
            f"experiment_name={experiment_name}",
            experiment_name,
            order,
            derived_id,
            derived_label,
            True,
        )
    return derived_id, derived_label, order, derived_id, derived_label, False


def _min_configuration_order(group: pd.DataFrame) -> int:
    orders = pd.to_numeric(group["configuration_order"], errors="coerce").dropna()
    return int(orders.min()) if not orders.empty else 90


def _append_experiment_name_warnings(
    rows: pd.DataFrame,
    warnings: list[str],
) -> None:
    if "experiment_name_source" not in rows.columns:
        return

    provided = rows[rows["experiment_name_source"] == "provided"]
    if provided.empty:
        return

    for name, group in provided.groupby("configuration", sort=True, dropna=False):
        derived_ids = {
            _as_text(value)
            for value in group["derived_configuration_id"]
            if _as_text(value)
        }
        if len(derived_ids) <= 1:
            continue

        derived_labels = sorted(
            {
                _as_text(value)
                for value in group["derived_configuration"]
                if _as_text(value)
            }
        )
        shown_labels = ", ".join(derived_labels[:4])
        if len(derived_labels) > 4:
            shown_labels += ", ..."
        warnings.append(
            f"Experiment name {name!r} combines {len(derived_ids)} auto-derived "
            f"configurations ({shown_labels}). Use distinct --experiment-name "
            "values if these should be compared separately."
        )


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _contains_legacy_binary_folder(path: Path) -> bool:
    return any("pass_fail_only" in part.casefold() for part in path.parts)


def _task_family(category: Any) -> str:
    return TASK_FAMILY_BY_CATEGORY.get(
        _as_text(category).casefold(),
        "Other or unclassified",
    )


def _source_scope(row: pd.Series) -> str:
    source_count = _as_float(row.get("source_count"))
    if source_count is None:
        articles = _split_articles(row.get("source_articles", ""))
        source_count = float(len(articles)) if articles else None
    if source_count is None or source_count <= 1:
        return "1 article"
    if source_count <= 2:
        return "2 articles"
    return "3+ articles"


def _telemetry_path(run_path: Path) -> Path:
    """Where the cost starters write a run's per-question telemetry."""

    return run_path.parent.parent / "telemetry" / f"{run_path.stem}__question_telemetry.csv"


def _attach_telemetry(frame: pd.DataFrame, run_path: Path) -> pd.DataFrame:
    """Add the run's per-question calls, tokens, cost, and time when telemetry exists.

    Runs without a telemetry file are returned unchanged, so reports on earlier
    checkpoints are not affected.
    """

    telemetry_path = _telemetry_path(run_path)
    if not telemetry_path.is_file():
        return frame
    telemetry = pd.read_csv(telemetry_path)
    if "question_id" not in telemetry.columns:
        return frame

    def column(name: str) -> pd.Series:
        return pd.to_numeric(telemetry.get(name), errors="coerce")

    billed = column("provider_cost_usd")
    if billed.isna().all():
        billed = column("billed_est_usd")
    per_question = pd.DataFrame(
        {
            "question_id": telemetry["question_id"],
            "telemetry_calls": column("llm_calls"),
            "telemetry_input_tokens": column("input_tokens"),
            "telemetry_output_tokens": column("output_tokens"),
            "telemetry_cached_tokens": column("cached_input_tokens"),
            "cost_list_usd": column("list_cost_usd"),
            "cost_billed_usd": billed,
            "agent_seconds": column("graph_wall_s") + column("answer_wall_s"),
        }
    ).drop_duplicates("question_id")
    return frame.merge(per_question, on="question_id", how="left")


def load_experiments(
    experiments_dir: Path | Iterable[Path],
    *,
    include_binary_oracle: bool = False,
) -> AnalysisData:
    roots = (
        [Path(experiments_dir)]
        if isinstance(experiments_dir, (str, Path))
        else [Path(root) for root in experiments_dir]
    )
    roots = [root.expanduser().resolve() for root in roots]
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f"Experiments directory not found: {root}")

    csv_paths = [(root, path) for root in roots for path in sorted(root.rglob("*.csv"))]
    if not csv_paths:
        raise ValueError(f"No CSV files found under: {', '.join(str(root) for root in roots)}")

    frames: list[pd.DataFrame] = []
    included_files: list[Path] = []
    excluded_files: list[tuple[Path, str]] = []
    warnings: list[str] = []
    seen_digests: dict[str, Path] = {}

    for root, path in csv_paths:
        relative_path = (
            path.relative_to(root)
            if len(roots) == 1
            else Path(root.name) / path.relative_to(root)
        )
        if path.name.endswith(TELEMETRY_SUFFIXES):
            excluded_files.append((relative_path, "telemetry, merged into its run"))
            continue
        if _contains_legacy_binary_folder(relative_path) and not include_binary_oracle:
            excluded_files.append((relative_path, "legacy pass/fail-only scoring"))
            continue

        digest = _file_digest(path)
        if digest in seen_digests:
            excluded_files.append(
                (relative_path, f"duplicate of {seen_digests[digest]}")
            )
            continue
        seen_digests[digest] = relative_path

        try:
            frame = pd.read_csv(path)
        except Exception as exc:
            excluded_files.append((relative_path, f"could not read: {exc}"))
            continue

        required_columns = {"question_id", "score"}
        missing_columns = required_columns - set(frame.columns)
        if missing_columns:
            excluded_files.append(
                (relative_path, f"missing columns: {sorted(missing_columns)}")
            )
            continue
        if frame.empty:
            excluded_files.append((relative_path, "empty CSV"))
            continue

        frame = frame.copy()
        frame["score"] = frame["score"].astype(str).str.strip().str.lower()
        invalid_scores = sorted(set(frame["score"]) - set(SCORE_VALUE))
        if invalid_scores:
            warnings.append(
                f"{relative_path}: dropped unsupported scores {invalid_scores}"
            )
            frame = frame[frame["score"].isin(SCORE_VALUE)].copy()
        if frame.empty:
            excluded_files.append((relative_path, "no supported score rows"))
            continue

        if "evaluation_mode" not in frame.columns:
            frame["evaluation_mode"] = ""

        (
            config_id,
            config_label,
            config_order,
            derived_config_id,
            derived_config_label,
            has_explicit_name,
        ) = _comparison_metadata(
            frame.iloc[0]
        )
        frame["configuration_id"] = config_id
        frame["configuration"] = config_label
        frame["configuration_order"] = config_order
        frame["experiment_name"] = config_label
        frame["experiment_name_source"] = "provided" if has_explicit_name else "derived"
        frame["derived_configuration_id"] = derived_config_id
        frame["derived_configuration"] = derived_config_label
        frame["run_file"] = str(relative_path)
        frame["run_name"] = path.stem
        frame["run_mtime"] = path.stat().st_mtime
        frame["quality"] = frame["score"].map(SCORE_VALUE)
        if "category" not in frame.columns:
            frame["category"] = ""
        frame["task_family"] = frame["category"].map(_task_family)
        frame["source_scope"] = frame.apply(_source_scope, axis=1)
        frame["article_recall_recomputed"] = frame.apply(
            _recomputed_article_recall,
            axis=1,
        )
        frame["full_source_coverage"] = frame[
            "article_recall_recomputed"
        ].apply(
            lambda value: (
                None if pd.isna(value) else bool(abs(float(value) - 1.0) < 1e-9)
            )
        )
        frame["context_characters_numeric"] = pd.to_numeric(
            frame.get("context_characters"),
            errors="coerce",
        )
        frame = _attach_telemetry(frame, path)

        frames.append(frame)
        included_files.append(relative_path)

    if not frames:
        reasons = "; ".join(f"{path}: {reason}" for path, reason in excluded_files)
        raise ValueError(f"No usable experiment CSVs. {reasons}")

    # Drop columns that are entirely empty within an individual run before unioning
    # oracle and retriever schemas. This also avoids pandas' all-NA concat warning.
    frames = [frame.dropna(axis=1, how="all") for frame in frames]
    rows = pd.concat(frames, ignore_index=True, sort=False)
    for column in ("article_recall_recomputed", "context_characters_numeric", *COST_COLUMNS):
        if column not in rows.columns:
            rows[column] = math.nan
    _append_experiment_name_warnings(rows, warnings)
    unclassified = sorted(
        {
            _as_text(value)
            for value in rows.loc[
                rows["task_family"] == "Other or unclassified",
                "category",
            ]
            if _as_text(value)
        }
    )
    if unclassified:
        warnings.append(
            "Task-family analysis left these categories unclassified: "
            + ", ".join(unclassified)
        )
    run_summary = _build_run_summary(rows)
    config_summary = _build_config_summary(rows, run_summary)
    task_summary = _build_dimension_summary(
        rows,
        "task_family",
        TASK_FAMILY_ORDER,
    )
    scope_summary = _build_dimension_summary(
        rows,
        "source_scope",
        SOURCE_SCOPE_ORDER,
    )

    return AnalysisData(
        rows=rows,
        run_summary=run_summary,
        config_summary=config_summary,
        task_summary=task_summary,
        scope_summary=scope_summary,
        included_files=included_files,
        excluded_files=excluded_files,
        warnings=warnings,
    )


def _build_run_summary(rows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    group_columns = [
        "run_file",
        "run_name",
        "run_mtime",
        "configuration_id",
        "configuration",
    ]
    for keys, group in rows.groupby(group_columns, sort=False, dropna=False):
        (
            run_file,
            run_name,
            run_mtime,
            config_id,
            configuration,
        ) = keys
        config_order = _min_configuration_order(group)
        recall = pd.to_numeric(
            group["article_recall_recomputed"], errors="coerce"
        ).dropna()
        records.append(
            {
                "run_file": run_file,
                "run_name": run_name,
                "run_mtime": run_mtime,
                "configuration_id": config_id,
                "configuration": configuration,
                "configuration_order": config_order,
                "cases": len(group),
                "pass": int((group["score"] == "pass").sum()),
                "partial": int((group["score"] == "partial").sum()),
                "fail": int((group["score"] == "fail").sum()),
                "quality": float(group["quality"].mean()),
                "article_recall": float(recall.mean()) if not recall.empty else math.nan,
                "full_source_coverage": (
                    float((recall >= 1.0 - 1e-9).mean())
                    if not recall.empty
                    else math.nan
                ),
                "context_characters": float(
                    group["context_characters_numeric"].mean()
                ),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(
        ["configuration_order", "configuration", "run_mtime", "run_name"]
    )


def _build_config_summary(
    rows: pd.DataFrame,
    run_summary: pd.DataFrame,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    group_columns = [
        "configuration_id",
        "configuration",
    ]
    for keys, group in rows.groupby(group_columns, sort=False, dropna=False):
        config_id, configuration = keys
        config_order = _min_configuration_order(group)
        run_group = run_summary[
            run_summary["configuration_id"] == config_id
        ]
        cases = len(group)
        recall = pd.to_numeric(
            group["article_recall_recomputed"], errors="coerce"
        ).dropna()
        records.append(
            {
                "configuration_id": config_id,
                "configuration": configuration,
                "configuration_order": config_order,
                "runs": int(group["run_file"].nunique()),
                "questions": int(group["question_id"].nunique()),
                "cases": cases,
                "pass": int((group["score"] == "pass").sum()),
                "partial": int((group["score"] == "partial").sum()),
                "fail": int((group["score"] == "fail").sum()),
                "pass_rate": float((group["score"] == "pass").mean()),
                "partial_rate": float((group["score"] == "partial").mean()),
                "fail_rate": float((group["score"] == "fail").mean()),
                "quality": float(group["quality"].mean()),
                "run_quality_std": float(run_group["quality"].std(ddof=0)),
                "run_quality_min": float(run_group["quality"].min()),
                "run_quality_max": float(run_group["quality"].max()),
                "article_recall": float(recall.mean()) if not recall.empty else math.nan,
                "full_source_coverage": (
                    float((recall >= 1.0 - 1e-9).mean())
                    if not recall.empty
                    else math.nan
                ),
                "context_characters": float(
                    group["context_characters_numeric"].mean()
                ),
                **_cost_summary(group),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(
        ["configuration_order", "configuration"]
    ).reset_index(drop=True)


def _cost_summary(group: pd.DataFrame) -> dict[str, Any]:
    """Per-question cost and latency over the question-runs that have telemetry."""

    measured = group[group["cost_list_usd"].notna()]

    def mean(column: str) -> float:
        values = pd.to_numeric(measured[column], errors="coerce").dropna()
        return float(values.mean()) if not values.empty else math.nan

    return {
        "telemetry_runs": int(measured["run_file"].nunique()),
        "telemetry_quality": float(measured["quality"].mean()) if not measured.empty else math.nan,
        "calls_per_question": mean("telemetry_calls"),
        "input_tokens_per_question": mean("telemetry_input_tokens"),
        "cached_share": (
            float(measured["telemetry_cached_tokens"].sum() / measured["telemetry_input_tokens"].sum())
            if not measured.empty and measured["telemetry_input_tokens"].sum()
            else math.nan
        ),
        "list_cost_per_question": mean("cost_list_usd"),
        "billed_cost_per_question": mean("cost_billed_usd"),
        "seconds_per_question": mean("agent_seconds"),
    }


def _build_dimension_summary(
    rows: pd.DataFrame,
    dimension: str,
    dimension_order: dict[str, int],
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    group_columns = [
        "configuration_id",
        "configuration",
        dimension,
    ]
    for keys, group in rows.groupby(group_columns, sort=False, dropna=False):
        config_id, configuration, group_value = keys
        config_order = _min_configuration_order(group)
        recall = pd.to_numeric(
            group["article_recall_recomputed"], errors="coerce"
        ).dropna()
        quality = float(group["quality"].mean())
        records.append(
            {
                "configuration_id": config_id,
                "configuration": configuration,
                "configuration_order": config_order,
                dimension: group_value,
                "dimension_order": dimension_order.get(_as_text(group_value), 90),
                "questions": int(group["question_id"].nunique()),
                "question_runs": len(group),
                "pass_rate": float((group["score"] == "pass").mean()),
                "partial_rate": float((group["score"] == "partial").mean()),
                "fail_rate": float((group["score"] == "fail").mean()),
                "quality": quality,
                "attention_score": 100.0 * (1.0 - quality),
                "article_recall": (
                    float(recall.mean()) if not recall.empty else math.nan
                ),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(
        ["configuration_order", "configuration", "dimension_order"]
    ).reset_index(drop=True)


def _primary_retrieval_configuration(data: AnalysisData) -> pd.Series | None:
    retrieval = data.config_summary[
        data.config_summary["article_recall"].notna()
    ].copy()
    if retrieval.empty:
        return None
    return retrieval.sort_values(
        ["quality", "configuration_order", "configuration"],
        ascending=[False, True, True],
    ).iloc[0]


def _task_priority_summary(data: AnalysisData) -> tuple[str, pd.DataFrame] | None:
    primary = _primary_retrieval_configuration(data)
    if primary is None:
        return None

    primary_id = primary["configuration_id"]
    baseline = data.task_summary[
        data.task_summary["configuration_id"] == primary_id
    ].copy()
    if baseline.empty:
        return None

    baseline = baseline.rename(
        columns={
            "quality": "baseline_quality",
            "fail_rate": "baseline_fail_rate",
            "article_recall": "baseline_article_recall",
        }
    )

    oracle_config_ids = data.rows.loc[
        data.rows["evaluation_mode"] == "oracle_ground_truth_context",
        "configuration_id",
    ].dropna().unique()
    oracle_configs = data.config_summary[
        data.config_summary["configuration_id"].isin(oracle_config_ids)
    ].sort_values(["cases", "configuration_id"], ascending=[False, True])
    if oracle_configs.empty:
        baseline["oracle_quality"] = math.nan
    else:
        oracle_id = oracle_configs.iloc[0]["configuration_id"]
        oracle = data.task_summary[
            data.task_summary["configuration_id"] == oracle_id
        ][["task_family", "quality"]].rename(
            columns={"quality": "oracle_quality"}
        )
        baseline = baseline.merge(oracle, on="task_family", how="left")

    baseline["oracle_gap"] = (
        baseline["oracle_quality"] - baseline["baseline_quality"]
    )
    baseline = baseline.sort_values(
        ["attention_score", "baseline_fail_rate", "task_family"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    return _as_text(primary["configuration"]), baseline


def _percent(value: Any) -> str:
    number = _as_float(value)
    return "n/a" if number is None else f"{number * 100:.1f}%"


def _decimal(value: Any, digits: int = 3) -> str:
    number = _as_float(value)
    return "n/a" if number is None else f"{number:.{digits}f}"


def _thousands(value: Any) -> str:
    number = _as_float(value)
    return "n/a" if number is None else f"{number / 1000:,.1f}k"


def _question_sort_key(value: Any) -> tuple[str, int, str]:
    text = _as_text(value)
    prefix = "".join(char for char in text if not char.isdigit())
    digits = "".join(char for char in text if char.isdigit())
    return prefix, int(digits) if digits else 10**9, text


def _interpolate_color(start: Color, end: Color, fraction: float) -> Color:
    fraction = min(1.0, max(0.0, fraction))
    return Color(
        start.red + (end.red - start.red) * fraction,
        start.green + (end.green - start.green) * fraction,
        start.blue + (end.blue - start.blue) * fraction,
    )


def _quality_color(value: float) -> Color:
    if value <= 0.5:
        return _interpolate_color(LIGHT_RED, LIGHT_AMBER, value / 0.5)
    return _interpolate_color(LIGHT_AMBER, LIGHT_GREEN, (value - 0.5) / 0.5)


def _stacked_outcome_chart(summary: pd.DataFrame) -> Drawing:
    width = 690
    row_height = 34
    top = 38
    bottom = 35
    left = 155
    bar_width = width - left - 25
    height = top + bottom + row_height * len(summary)
    drawing = Drawing(width, height)

    legend_x = left
    for index, score in enumerate(("pass", "partial", "fail")):
        x = legend_x + index * 115
        drawing.add(Rect(x, height - 16, 10, 10, fillColor=SCORE_COLORS[score], strokeColor=None))
        drawing.add(String(x + 15, height - 14, score.title(), fontName="Helvetica", fontSize=8, fillColor=BLACK))

    for row_index, (_, row) in enumerate(summary.iterrows()):
        y = height - top - (row_index + 1) * row_height + 10
        drawing.add(String(0, y + 4, _as_text(row["configuration"]), fontName="Helvetica", fontSize=8, fillColor=BLACK))
        x = left
        for score in ("pass", "partial", "fail"):
            fraction = float(row[f"{score}_rate"])
            segment_width = bar_width * fraction
            if segment_width > 0:
                drawing.add(Rect(x, y, segment_width, 18, fillColor=SCORE_COLORS[score], strokeColor=WHITE, strokeWidth=0.5))
                if segment_width >= 35:
                    drawing.add(String(x + segment_width / 2, y + 5, f"{fraction * 100:.0f}%", textAnchor="middle", fontName="Helvetica-Bold", fontSize=7, fillColor=WHITE))
            x += segment_width
        drawing.add(Rect(left, y, bar_width, 18, fillColor=None, strokeColor=MID_GRAY, strokeWidth=0.5))

    for tick in range(0, 101, 20):
        x = left + bar_width * tick / 100
        drawing.add(Line(x, 19, x, 24, strokeColor=GRAY, strokeWidth=0.5))
        drawing.add(String(x, 7, str(tick), textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    drawing.add(String(left + bar_width / 2, 0, "Share of evaluated question-runs (%)", textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    return drawing


def _recall_chart(summary: pd.DataFrame) -> Drawing | None:
    retrieval = summary[summary["article_recall"].notna()].copy()
    if retrieval.empty:
        return None

    width = 690
    row_height = 42
    top = 40
    bottom = 35
    left = 155
    bar_width = width - left - 25
    height = top + bottom + row_height * len(retrieval)
    drawing = Drawing(width, height)

    legend = ((BLUE, "Mean designated-source recall"), (GREEN, "Full designated-source coverage"))
    for index, (color, label) in enumerate(legend):
        x = left + index * 210
        drawing.add(Rect(x, height - 16, 10, 10, fillColor=color, strokeColor=None))
        drawing.add(String(x + 15, height - 14, label, fontName="Helvetica", fontSize=8, fillColor=BLACK))

    for row_index, (_, row) in enumerate(retrieval.iterrows()):
        base_y = height - top - (row_index + 1) * row_height + 14
        drawing.add(String(0, base_y + 5, _as_text(row["configuration"]), fontName="Helvetica", fontSize=8, fillColor=BLACK))
        for offset, column, color in ((12, "article_recall", BLUE), (-1, "full_source_coverage", GREEN)):
            value = float(row[column])
            y = base_y + offset
            drawing.add(Rect(left, y, bar_width * value, 9, fillColor=color, strokeColor=None))
            drawing.add(Rect(left, y, bar_width, 9, fillColor=None, strokeColor=MID_GRAY, strokeWidth=0.4))
            drawing.add(String(left + bar_width * value + 4, y + 1, f"{value * 100:.1f}%", fontName="Helvetica", fontSize=7, fillColor=BLACK))

    for tick in range(0, 101, 20):
        x = left + bar_width * tick / 100
        drawing.add(String(x, 7, str(tick), textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    drawing.add(String(left + bar_width / 2, 0, "Percent", textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    return drawing


def _variability_chart(run_summary: pd.DataFrame, config_summary: pd.DataFrame) -> Drawing:
    width = 690
    row_height = 38
    top = 35
    bottom = 35
    left = 155
    plot_width = width - left - 25
    height = top + bottom + row_height * len(config_summary)
    drawing = Drawing(width, height)

    drawing.add(String(left, height - 15, "Each dot is one run; the larger dot is the configuration mean.", fontName="Helvetica", fontSize=8, fillColor=GRAY))
    for row_index, (_, row) in enumerate(config_summary.iterrows()):
        y = height - top - (row_index + 1) * row_height + 16
        drawing.add(String(0, y - 2, _as_text(row["configuration"]), fontName="Helvetica", fontSize=8, fillColor=BLACK))
        run_values = run_summary.loc[
            run_summary["configuration_id"] == row["configuration_id"],
            "quality",
        ].astype(float)
        minimum = float(run_values.min())
        maximum = float(run_values.max())
        mean = float(run_values.mean())
        drawing.add(Line(left + plot_width * minimum, y, left + plot_width * maximum, y, strokeColor=MID_GRAY, strokeWidth=2))
        for value in run_values:
            drawing.add(Circle(left + plot_width * float(value), y, 3, fillColor=BLUE, strokeColor=WHITE, strokeWidth=0.5))
        drawing.add(Circle(left + plot_width * mean, y, 5, fillColor=NAVY, strokeColor=WHITE, strokeWidth=0.8))
        drawing.add(String(left + plot_width * mean, y + 8, f"{mean:.3f}", textAnchor="middle", fontName="Helvetica-Bold", fontSize=7, fillColor=NAVY))

    for tick in range(0, 11, 2):
        value = tick / 10
        x = left + plot_width * value
        drawing.add(Line(x, 19, x, 24, strokeColor=GRAY, strokeWidth=0.5))
        drawing.add(String(x, 7, f"{value:.1f}", textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    drawing.add(String(left + plot_width / 2, 0, "Quality score (pass=1, partial=0.5, fail=0)", textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    return drawing


def _question_heatmap(rows: pd.DataFrame, config_summary: pd.DataFrame) -> Drawing:
    configurations = list(config_summary["configuration"])
    question_ids = sorted(rows["question_id"].dropna().unique(), key=_question_sort_key)
    matrix = rows.pivot_table(
        index="question_id",
        columns="configuration",
        values="quality",
        aggfunc="mean",
    )

    width = 690
    left = 58
    top = 62
    bottom = 24
    right = 8
    cell_width = (width - left - right) / max(1, len(configurations))
    cell_height = min(20, 350 / max(1, len(question_ids)))
    height = top + bottom + cell_height * len(question_ids)
    drawing = Drawing(width, height)

    for column_index, configuration in enumerate(configurations):
        x = left + column_index * cell_width + cell_width / 2
        label = configuration if len(configuration) <= 29 else configuration[:27] + ".."
        drawing.add(String(x, height - 18, label, angle=25, textAnchor="start", fontName="Helvetica", fontSize=7, fillColor=BLACK))

    for row_index, question_id in enumerate(question_ids):
        y = height - top - (row_index + 1) * cell_height
        drawing.add(String(left - 6, y + cell_height / 2 - 2, str(question_id), textAnchor="end", fontName="Helvetica", fontSize=7, fillColor=BLACK))
        for column_index, configuration in enumerate(configurations):
            x = left + column_index * cell_width
            value = matrix.at[question_id, configuration] if configuration in matrix.columns and question_id in matrix.index else math.nan
            if pd.isna(value):
                fill = LIGHT_GRAY
                label = "n/a"
            else:
                value = float(value)
                fill = _quality_color(value)
                label = f"{value:.2f}"
            drawing.add(Rect(x, y, cell_width, cell_height, fillColor=fill, strokeColor=WHITE, strokeWidth=1))
            drawing.add(String(x + cell_width / 2, y + cell_height / 2 - 2, label, textAnchor="middle", fontName="Helvetica-Bold", fontSize=7, fillColor=BLACK))

    legend_y = 4
    legend_values = ((0.0, "Fail"), (0.5, "Partial"), (1.0, "Pass"))
    for index, (value, label) in enumerate(legend_values):
        x = left + index * 90
        drawing.add(Rect(x, legend_y, 12, 8, fillColor=_quality_color(value), strokeColor=MID_GRAY, strokeWidth=0.3))
        drawing.add(String(x + 17, legend_y, f"{label} ({value:g})", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    return drawing


def _attention_chart(data: AnalysisData) -> Drawing | None:
    priority_result = _task_priority_summary(data)
    if priority_result is None:
        return None
    baseline_label, priority = priority_result

    width = 690
    row_height = 34
    top = 40
    bottom = 35
    left = 270
    bar_width = width - left - 35
    height = top + bottom + row_height * len(priority)
    drawing = Drawing(width, height)
    drawing.add(
        String(
            left,
            height - 15,
            f"Baseline: {baseline_label}. Higher attention means more lost quality.",
            fontName="Helvetica",
            fontSize=8,
            fillColor=GRAY,
        )
    )

    for row_index, (_, row) in enumerate(priority.iterrows()):
        y = height - top - (row_index + 1) * row_height + 10
        label = _as_text(row["task_family"])
        drawing.add(
            String(
                left - 8,
                y + 4,
                label,
                textAnchor="end",
                fontName="Helvetica",
                fontSize=8,
                fillColor=BLACK,
            )
        )
        attention = float(row["attention_score"])
        quality = float(row["baseline_quality"])
        segment_width = bar_width * attention / 100.0
        drawing.add(
            Rect(
                left,
                y,
                segment_width,
                18,
                fillColor=_quality_color(quality),
                strokeColor=None,
            )
        )
        drawing.add(
            Rect(
                left,
                y,
                bar_width,
                18,
                fillColor=None,
                strokeColor=MID_GRAY,
                strokeWidth=0.5,
            )
        )
        drawing.add(
            String(
                left + segment_width + 5,
                y + 5,
                f"{attention:.1f}",
                fontName="Helvetica-Bold",
                fontSize=7,
                fillColor=BLACK,
            )
        )

    for tick in range(0, 101, 20):
        x = left + bar_width * tick / 100
        drawing.add(Line(x, 19, x, 24, strokeColor=GRAY, strokeWidth=0.5))
        drawing.add(
            String(
                x,
                7,
                str(tick),
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=7,
                fillColor=GRAY,
            )
        )
    drawing.add(
        String(
            left + bar_width / 2,
            0,
            "Attention score = 100 x (1 - grouped quality)",
            textAnchor="middle",
            fontName="Helvetica",
            fontSize=7,
            fillColor=GRAY,
        )
    )
    return drawing


def _dimension_quality_heatmap(
    summary: pd.DataFrame,
    config_summary: pd.DataFrame,
    dimension: str,
    dimension_order: dict[str, int],
) -> Drawing:
    configurations = list(config_summary["configuration"])
    labels = sorted(
        summary[dimension].dropna().unique(),
        key=lambda value: dimension_order.get(_as_text(value), 90),
    )
    matrix = summary.pivot_table(
        index=dimension,
        columns="configuration",
        values="quality",
        aggfunc="mean",
    )

    width = 690
    left = 245
    top = 62
    bottom = 24
    right = 8
    cell_width = (width - left - right) / max(1, len(configurations))
    cell_height = 28
    height = top + bottom + cell_height * len(labels)
    drawing = Drawing(width, height)

    for column_index, configuration in enumerate(configurations):
        x = left + column_index * cell_width + cell_width / 2
        drawing.add(
            String(
                x,
                height - 18,
                configuration,
                angle=22,
                textAnchor="start",
                fontName="Helvetica",
                fontSize=7,
                fillColor=BLACK,
            )
        )

    for row_index, label in enumerate(labels):
        y = height - top - (row_index + 1) * cell_height
        drawing.add(
            String(
                left - 8,
                y + cell_height / 2 - 2,
                _as_text(label),
                textAnchor="end",
                fontName="Helvetica",
                fontSize=8,
                fillColor=BLACK,
            )
        )
        for column_index, configuration in enumerate(configurations):
            x = left + column_index * cell_width
            value = (
                matrix.at[label, configuration]
                if configuration in matrix.columns and label in matrix.index
                else math.nan
            )
            if pd.isna(value):
                fill = LIGHT_GRAY
                text_value = "n/a"
            else:
                value = float(value)
                fill = _quality_color(value)
                text_value = f"{value:.3f}"
            drawing.add(
                Rect(
                    x,
                    y,
                    cell_width,
                    cell_height,
                    fillColor=fill,
                    strokeColor=WHITE,
                    strokeWidth=1,
                )
            )
            drawing.add(
                String(
                    x + cell_width / 2,
                    y + cell_height / 2 - 2,
                    text_value,
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                    fontSize=8,
                    fillColor=BLACK,
                )
            )
    return drawing


def _failure_diagnostics(rows: pd.DataFrame) -> pd.DataFrame:
    retrieval = rows[
        rows["evaluation_mode"].astype(str) != "oracle_ground_truth_context"
    ].copy()
    if retrieval.empty:
        return pd.DataFrame()

    def classify(row: pd.Series) -> str:
        recall = _as_float(row.get("article_recall_recomputed"))
        full = recall is not None and recall >= 1.0 - 1e-9
        if row["score"] == "pass":
            return (
                "Pass with full designated-source recall"
                if full
                else "Pass without full designated-source recall"
            )
        return (
            "Non-pass despite full designated-source recall"
            if full
            else "Non-pass with a missing designated source"
        )

    retrieval["diagnostic"] = retrieval.apply(classify, axis=1)
    return (
        retrieval.groupby(["configuration", "diagnostic"], dropna=False)
        .size()
        .rename("cases")
        .reset_index()
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=GRAY,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "ReportH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ReportH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=BLUE,
            spaceBefore=6,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=BLACK,
            spaceAfter=6,
        ),
        "note": ParagraphStyle(
            "ReportNote",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=GRAY,
            spaceAfter=5,
        ),
        "table": ParagraphStyle(
            "TableText",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=8.5,
            textColor=BLACK,
            spaceAfter=0,
        ),
        "table_center": ParagraphStyle(
            "TableTextCenter",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=8.5,
            textColor=BLACK,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.5,
            leading=7.5,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "small": ParagraphStyle(
            "SmallText",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            textColor=BLACK,
            spaceAfter=0,
        ),
    }


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    text = html.escape(_as_text(value)).replace("\n", "<br/>")
    return Paragraph(text or "-", style)


def _styled_table(
    data: list[list[Any]],
    column_widths: list[float],
    *,
    repeat_rows: int = 1,
    long: bool = False,
) -> Table:
    table_class = LongTable if long else Table
    table = table_class(
        data,
        colWidths=column_widths,
        repeatRows=repeat_rows,
        hAlign="LEFT",
    )
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, MID_GRAY),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GRAY))
    table.setStyle(TableStyle(commands))
    return table


def _configuration_table(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> Table:
    headers = [
        "Configuration",
        "Runs",
        "Cases",
        "Pass",
        "Partial",
        "Fail",
        "Quality",
        "Run SD",
        "Article recall",
        "Full source coverage",
        "Mean context",
    ]
    table_data: list[list[Any]] = [
        [_paragraph(header, styles["table_header"]) for header in headers]
    ]
    for _, row in data.config_summary.iterrows():
        table_data.append(
            [
                _paragraph(row["configuration"], styles["table"]),
                int(row["runs"]),
                int(row["cases"]),
                _percent(row["pass_rate"]),
                _percent(row["partial_rate"]),
                _percent(row["fail_rate"]),
                _decimal(row["quality"]),
                _decimal(row["run_quality_std"]),
                _percent(row["article_recall"]),
                _percent(row["full_source_coverage"]),
                _thousands(row["context_characters"]),
            ]
        )
    return _styled_table(
        table_data,
        [112, 32, 36, 43, 43, 43, 47, 43, 62, 70, 58],
    )


def _measured_configurations(data: AnalysisData) -> pd.DataFrame:
    """Configurations with at least one telemetry run (Checkpoint 6.1 cost starters)."""

    summary = data.config_summary
    if "telemetry_runs" not in summary.columns:
        return summary.iloc[0:0]
    return summary[summary["telemetry_runs"] > 0]


def _cost_table(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> Table:
    headers = [
        "Configuration",
        "Runs",
        "Quality",
        "Calls / question",
        "Input tokens / question",
        "Cached",
        "List $ / question",
        "Billed $ / question",
        "Seconds / question",
        "List $ per quality point",
    ]
    table_data: list[list[Any]] = [[_paragraph(header, styles["table_header"]) for header in headers]]
    for _, row in _measured_configurations(data).iterrows():
        quality = _as_float(row["telemetry_quality"])
        list_cost = _as_float(row["list_cost_per_question"])
        table_data.append(
            [
                _paragraph(row["configuration"], styles["table"]),
                int(row["telemetry_runs"]),
                _decimal(row["telemetry_quality"]),
                _decimal(row["calls_per_question"], 2),
                _thousands(row["input_tokens_per_question"]),
                _percent(row["cached_share"]),
                _format_money(row["list_cost_per_question"]),
                _format_money(row["billed_cost_per_question"]),
                _decimal(row["seconds_per_question"], 1),
                _format_money(list_cost / quality if list_cost is not None and quality else None),
            ]
        )
    return _styled_table(table_data, [128, 32, 44, 52, 62, 44, 58, 58, 56, 66])


def _format_money(value: Any) -> str:
    number = _as_float(value)
    return "n/a" if number is None else f"${number:.4f}"


def _cost_quality_chart(data: AnalysisData) -> Drawing | None:
    """Quality against list cost per question, one point per measured configuration."""

    measured = _measured_configurations(data).dropna(subset=["list_cost_per_question", "telemetry_quality"])
    if measured.empty:
        return None
    width, height = 690, 250
    left, right, bottom, top = 60, 30, 40, 20
    plot_width, plot_height = width - left - right, height - bottom - top
    max_cost = float(measured["list_cost_per_question"].max()) * 1.15 or 1.0
    min_quality = min(0.5, float(measured["telemetry_quality"].min()) - 0.05)
    drawing = Drawing(width, height)

    def x_of(cost: float) -> float:
        return left + plot_width * cost / max_cost

    def y_of(quality: float) -> float:
        return bottom + plot_height * (quality - min_quality) / (1.0 - min_quality)

    drawing.add(Line(left, bottom, left + plot_width, bottom, strokeColor=MID_GRAY, strokeWidth=0.6))
    drawing.add(Line(left, bottom, left, bottom + plot_height, strokeColor=MID_GRAY, strokeWidth=0.6))
    for step in range(5):
        cost = max_cost * step / 4
        drawing.add(String(x_of(cost), bottom - 12, f"${cost:.3f}", textAnchor="middle", fontName="Helvetica", fontSize=7, fillColor=GRAY))
        quality = min_quality + (1.0 - min_quality) * step / 4
        drawing.add(String(left - 6, y_of(quality) - 2, f"{quality:.2f}", textAnchor="end", fontName="Helvetica", fontSize=7, fillColor=GRAY))
    drawing.add(String(left + plot_width / 2, 4, "List cost per question (USD, no caching)", textAnchor="middle", fontName="Helvetica", fontSize=8, fillColor=GRAY))
    drawing.add(String(12, bottom + plot_height / 2, "Quality", textAnchor="middle", fontName="Helvetica", fontSize=8, fillColor=GRAY))
    for _, row in measured.iterrows():
        x, y = x_of(float(row["list_cost_per_question"])), y_of(float(row["telemetry_quality"]))
        drawing.add(Circle(x, y, 4, fillColor=BLUE, strokeColor=None))
        drawing.add(String(x + 7, y + 3, _as_text(row["configuration"]), fontName="Helvetica", fontSize=7, fillColor=BLACK))
    return drawing


def _run_table(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> LongTable:
    headers = [
        "Run",
        "Configuration",
        "Cases",
        "Pass",
        "Partial",
        "Fail",
        "Quality",
        "Article recall",
        "Full source coverage",
    ]
    table_data: list[list[Any]] = [headers]
    for _, row in data.run_summary.iterrows():
        table_data.append(
            [
                _paragraph(row["run_name"], styles["table"]),
                _paragraph(row["configuration"], styles["table"]),
                int(row["cases"]),
                int(row["pass"]),
                int(row["partial"]),
                int(row["fail"]),
                _decimal(row["quality"]),
                _percent(row["article_recall"]),
                _percent(row["full_source_coverage"]),
            ]
        )
    return _styled_table(
        table_data,
        [92, 120, 38, 38, 42, 38, 48, 65, 78],
        long=True,
    )


def _diagnostic_table(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> Table | None:
    diagnostics = _failure_diagnostics(data.rows)
    if diagnostics.empty:
        return None
    pivot = diagnostics.pivot_table(
        index="configuration",
        columns="diagnostic",
        values="cases",
        aggfunc="sum",
        fill_value=0,
    )
    columns = [
        "Pass with full designated-source recall",
        "Pass without full designated-source recall",
        "Non-pass despite full designated-source recall",
        "Non-pass with a missing designated source",
    ]
    headers = [
        "Configuration",
        "Pass, full",
        "Pass, incomplete",
        "Non-pass, full",
        "Non-pass, missing",
    ]
    table_data: list[list[Any]] = [headers]
    for configuration in pivot.index:
        table_data.append(
            [
                _paragraph(configuration, styles["table"]),
                *[int(pivot.at[configuration, column]) if column in pivot.columns else 0 for column in columns],
            ]
        )
    return _styled_table(table_data, [135, 75, 85, 85, 90])


def _question_table(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> LongTable:
    configurations = list(data.config_summary["configuration"])
    pivot = data.rows.pivot_table(
        index="question_id",
        columns="configuration",
        values="quality",
        aggfunc="mean",
    )
    question_ids = sorted(pivot.index, key=_question_sort_key)
    headers = ["Question"] + configurations
    table_data: list[list[Any]] = [headers]
    for question_id in question_ids:
        row: list[Any] = [question_id]
        for configuration in configurations:
            value = (
                pivot.at[question_id, configuration]
                if configuration in pivot.columns
                else math.nan
            )
            row.append("n/a" if pd.isna(value) else f"{float(value):.3f}")
        table_data.append(row)
    total_width = 640
    first_width = 58
    other_width = (total_width - first_width) / max(1, len(configurations))
    return _styled_table(
        table_data,
        [first_width] + [other_width] * len(configurations),
        long=True,
    )


def _question_recall_table(
    data: AnalysisData, styles: dict[str, ParagraphStyle]
) -> LongTable | None:
    """Per-question article recall (retriever configurations only).

    Mirrors _question_table, but each cell is the fraction of that question's
    designated source articles that were retrieved — so retrieval misses are visible
    per question, not just in the overall/per-configuration averages. Oracle
    configurations have no retrieval and are omitted; returns None when no retrieval
    rows carry a recall value.
    """
    retrieval = data.rows[
        data.rows["evaluation_mode"].astype(str) != "oracle_ground_truth_context"
    ]
    if retrieval.empty or retrieval["article_recall_recomputed"].dropna().empty:
        return None
    pivot = retrieval.pivot_table(
        index="question_id",
        columns="configuration",
        values="article_recall_recomputed",
        aggfunc="mean",
    )
    configurations = [
        c for c in data.config_summary["configuration"] if c in pivot.columns
    ]
    if not configurations:
        return None
    question_ids = sorted(pivot.index, key=_question_sort_key)
    headers = ["Question"] + configurations
    table_data: list[list[Any]] = [headers]
    for question_id in question_ids:
        row: list[Any] = [question_id]
        for configuration in configurations:
            value = (
                pivot.at[question_id, configuration]
                if configuration in pivot.columns
                else math.nan
            )
            row.append("n/a" if pd.isna(value) else _percent(value))
        table_data.append(row)
    total_width = 640
    first_width = 58
    other_width = (total_width - first_width) / max(1, len(configurations))
    return _styled_table(
        table_data,
        [first_width] + [other_width] * len(configurations),
        long=True,
    )


def _task_priority_table(
    data: AnalysisData,
    styles: dict[str, ParagraphStyle],
) -> tuple[str, Table] | None:
    priority_result = _task_priority_summary(data)
    if priority_result is None:
        return None
    baseline_label, priority = priority_result
    headers = [
        "Task family",
        "Questions",
        "Baseline quality",
        "Attention",
        "Fail",
        "Oracle quality",
        "Oracle gap",
        "Article recall",
    ]
    table_data: list[list[Any]] = [headers]
    for _, row in priority.iterrows():
        oracle_gap = _as_float(row.get("oracle_gap"))
        table_data.append(
            [
                _paragraph(row["task_family"], styles["table"]),
                int(row["questions"]),
                _decimal(row["baseline_quality"]),
                f"{float(row['attention_score']):.1f}",
                _percent(row["baseline_fail_rate"]),
                _decimal(row.get("oracle_quality")),
                "n/a" if oracle_gap is None else f"{oracle_gap:+.3f}",
                _percent(row["baseline_article_recall"]),
            ]
        )
    return baseline_label, _styled_table(
        table_data,
        [205, 48, 67, 55, 47, 65, 55, 65],
    )


def _scope_table(
    data: AnalysisData,
    styles: dict[str, ParagraphStyle],
) -> LongTable:
    headers = [
        "Source scope",
        "Configuration",
        "Questions",
        "Question-runs",
        "Pass",
        "Partial",
        "Fail",
        "Quality",
        "Article recall",
    ]
    table_data: list[list[Any]] = [headers]
    for _, row in data.scope_summary.iterrows():
        table_data.append(
            [
                _paragraph(row["source_scope"], styles["table"]),
                _paragraph(row["configuration"], styles["table"]),
                int(row["questions"]),
                int(row["question_runs"]),
                _percent(row["pass_rate"]),
                _percent(row["partial_rate"]),
                _percent(row["fail_rate"]),
                _decimal(row["quality"]),
                _percent(row["article_recall"]),
            ]
        )
    return _styled_table(
        table_data,
        [70, 118, 47, 57, 48, 48, 48, 50, 66],
        long=True,
    )


def _kpi_table(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> Table:
    rows = data.rows
    cards = [
        ("Included runs", str(rows["run_file"].nunique())),
        ("Configurations", str(rows["configuration_id"].nunique())),
        ("Question-runs", f"{len(rows):,}"),
        ("Questions", str(rows["question_id"].nunique())),
        ("Legacy runs excluded", str(sum("pass/fail-only" in reason for _, reason in data.excluded_files))),
    ]
    card_cells = []
    for label, value in cards:
        card_cells.append(
            [
                Paragraph(f"<b><font size='16' color='#19324A'>{html.escape(value)}</font></b><br/><font size='7' color='#68737D'>{html.escape(label)}</font>", styles["table_center"])
            ]
        )
    table = Table([card_cells], colWidths=[130] * len(cards), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                ("BOX", (0, 0), (-1, -1), 0.4, MID_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 2, WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _summary_paragraphs(data: AnalysisData, styles: dict[str, ParagraphStyle]) -> list[Paragraph]:
    summary = data.config_summary
    highest = summary.loc[summary["quality"].idxmax()]
    retrieval = summary[summary["article_recall"].notna()]
    paragraphs = [
        _paragraph(
            f"The highest observed mean quality score was {highest['quality']:.3f} for "
            f"{highest['configuration']} across {int(highest['runs'])} run(s). "
            "Quality assigns 1 to pass, 0.5 to partial, and 0 to fail.",
            styles["body"],
        )
    ]
    if not retrieval.empty:
        highest_recall = retrieval.loc[retrieval["article_recall"].idxmax()]
        paragraphs.append(
            _paragraph(
                f"The highest observed mean designated-source recall was "
                f"{highest_recall['article_recall'] * 100:.1f}% for "
                f"{highest_recall['configuration']}. Article recall is recomputed "
                "from the required and retrieved article names in every CSV.",
                styles["body"],
            )
        )
    priority_result = _task_priority_summary(data)
    if priority_result is not None:
        baseline_label, priority = priority_result
        highest_attention = priority.iloc[0]
        paragraphs.append(
            _paragraph(
                f"The highest task-family attention score was "
                f"{highest_attention['attention_score']:.1f} for "
                f"{highest_attention['task_family']} under {baseline_label}. "
                "Attention is 100 x (1 - grouped quality), so higher values "
                "identify larger observed improvement opportunities.",
                styles["body"],
            )
        )
    return paragraphs


def _page_header_footer(canvas: Any, document: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setStrokeColor(MID_GRAY)
    canvas.setLineWidth(0.4)
    canvas.line(0.55 * inch, 0.42 * inch, PAGE_WIDTH - 0.55 * inch, 0.42 * inch)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY)
    canvas.drawString(0.55 * inch, 0.22 * inch, "RAGAS evaluation results")
    canvas.drawRightString(PAGE_WIDTH - 0.55 * inch, 0.22 * inch, f"Page {document.page}")
    canvas.restoreState()


def create_pdf_report(
    data: AnalysisData,
    output_path: Path,
    *,
    title: str,
) -> None:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    document = BaseDocTemplate(
        str(output_path),
        pagesize=PAGE_SIZE,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.55 * inch,
        title=title,
        author="Wikipedia Retrieval Engine capstone",
        subject="Comparison of RAGAS oracle and retriever experiments",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="report_frame",
    )
    document.addPageTemplates(
        [PageTemplate(id="report", frames=[frame], onPage=_page_header_footer)]
    )

    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    story: list[Any] = [
        Paragraph(html.escape(title), styles["title"]),
        Paragraph(
            f"Oracle, vector, and hybrid experiment comparison. Generated {html.escape(generated)}.",
            styles["subtitle"],
        ),
        _kpi_table(data, styles),
        Spacer(1, 12),
        Paragraph("Summary", styles["h1"]),
        *_summary_paragraphs(data, styles),
        Paragraph("Answer outcomes", styles["h2"]),
        _stacked_outcome_chart(data.config_summary),
        Spacer(1, 6),
        _configuration_table(data, styles),
        Spacer(1, 5),
        Paragraph(
            "Percentages aggregate all question-runs within a configuration. Run SD is the standard deviation of mean quality across repeated runs.",
            styles["note"],
        ),
    ]

    if not _measured_configurations(data).empty:
        chart = _cost_quality_chart(data)
        story.extend(
            [
                PageBreak(),
                Paragraph("Cost and latency", styles["h1"]),
                _paragraph(
                    "Configurations whose runs carry per-question telemetry (the Checkpoint 6.1 cost starters). Every figure, quality included, is computed over those runs only, so cost and quality come from the same question-runs.",
                    styles["body"],
                ),
                Spacer(1, 6),
                _cost_table(data, styles),
                Spacer(1, 6),
                *([chart] if chart is not None else []),
                Spacer(1, 5),
                _paragraph(
                    "List cost charges every input token at the full rate; billed cost is what OpenRouter reported, with cached input at the cached rate. The judge is not included. Seconds cover the agent graph and the answer call, not the judge.",
                    styles["note"],
                ),
            ]
        )

    story.extend([PageBreak(), Paragraph("Retrieval diagnostics", styles["h1"])])

    recall_chart = _recall_chart(data.config_summary)
    if recall_chart is not None:
        story.extend(
            [
                Paragraph("Designated-source coverage", styles["h2"]),
                recall_chart,
                Paragraph(
                    "The analyzer recomputes recall after removing only final .txt and .html suffixes. This corrects historical .html.txt versus .html mismatches. Designated-source recall is diagnostic: alternative retrieved articles may still contain sufficient evidence.",
                    styles["note"],
                ),
            ]
        )

    diagnostics = _diagnostic_table(data, styles)
    if diagnostics is not None:
        story.extend(
            [
                Paragraph("Outcome and source-coverage combinations", styles["h2"]),
                diagnostics,
                Spacer(1, 8),
                Paragraph(
                    "A non-pass result with full designated-source recall points toward answer synthesis, context noise, table interpretation, or judge behavior. A non-pass result with a missing designated source is consistent with a retrieval recall problem, but manual review is still required.",
                    styles["body"],
                ),
            ]
        )

    story.extend(
        [
            PageBreak(),
            Paragraph("Per-question comparison", styles["h1"]),
            Paragraph(
                "Cells show the mean quality score for each question and configuration across repeated runs.",
                styles["body"],
            ),
            _question_heatmap(data.rows, data.config_summary),
            Spacer(1, 7),
            _question_table(data, styles),
        ]
    )

    recall_table = _question_recall_table(data, styles)
    if recall_table is not None:
        story.extend(
            [
                Spacer(1, 10),
                Paragraph("Per-question article recall", styles["h2"]),
                Paragraph(
                    "Fraction of each question's designated source articles that "
                    "appeared in the retrieved set (retriever configurations only). "
                    "1.00 = every gold article retrieved; lower values mark a retrieval "
                    "miss — usually a multi-source question.",
                    styles["body"],
                ),
                Spacer(1, 6),
                recall_table,
            ]
        )

    attention_chart = _attention_chart(data)
    priority_table_result = _task_priority_table(data, styles)
    if attention_chart is not None and priority_table_result is not None:
        baseline_label, priority_table = priority_table_result
        story.extend(
            [
                PageBreak(),
                Paragraph("Performance by task type", styles["h1"]),
                _paragraph(
                    "The 18 original category labels are consolidated into five task families so each group contains multiple questions. The attention score ranks observed improvement opportunities for the strongest retrieval configuration; it is not a statistical significance test.",
                    styles["body"],
                ),
                attention_chart,
                Spacer(1, 7),
                priority_table,
                Spacer(1, 6),
                _paragraph(
                    f"Baseline quality and failure rate use {baseline_label}. Oracle gap equals oracle quality minus baseline quality: a large positive gap is consistent with a retrieval or context-selection opportunity, while low oracle quality indicates that the difficulty persists even when the designated articles are supplied.",
                    styles["note"],
                ),
            ]
        )

    story.extend(
        [
            PageBreak(),
            Paragraph("Performance by source scope", styles["h1"]),
            _paragraph(
                "Source scope groups questions by the number of designated articles. It tests whether the number of sources, rather than the reasoning operation, explains performance.",
                styles["body"],
            ),
            _dimension_quality_heatmap(
                data.scope_summary,
                data.config_summary,
                "source_scope",
                SOURCE_SCOPE_ORDER,
            ),
            Spacer(1, 8),
            _scope_table(data, styles),
            Spacer(1, 6),
            _paragraph(
                "Question-runs are repeated measurements of the listed unique questions. Source-scope groups remain small and mix different task families, so this view should be used as a diagnostic rather than a general performance estimate.",
                styles["note"],
            ),
            PageBreak(),
            Paragraph("Run-to-run variability", styles["h1"]),
            _variability_chart(data.run_summary, data.config_summary),
            Spacer(1, 8),
            _run_table(data, styles),
            PageBreak(),
            Paragraph("Methodology and limitations", styles["h1"]),
            Paragraph("Scoring", styles["h2"]),
            _paragraph(
                "Pass is assigned 1, partial is assigned 0.5, and fail is assigned 0. The quality score is the arithmetic mean across the applicable question-runs. Pass, partial, and fail percentages are also reported separately so the weighted score does not hide the underlying verdicts.",
                styles["body"],
            ),
            Paragraph("Task-family attention", styles["h2"]),
            _paragraph(
                "The attention score is 100 multiplied by one minus grouped quality. A score of 66 means that the group lost 66% of the available quality points under the selected retrieval baseline. It is a prioritization aid, not an estimate of population-wide failure risk. Task-family and source-scope results must be read with their unique-question counts because the evaluation set contains only 19 questions.",
                styles["body"],
            ),
            Paragraph("Configuration grouping", styles["h2"]),
            _paragraph(
                "Runs are grouped by a CSV experiment_name or config_name when one is present. If no explicit name is present, grouping falls back to evaluation mode, context source, retriever kind and label, Top K, hybrid weights, answer model, and judge model. RAGAS-generated filenames identify individual runs but do not define configurations.",
                styles["body"],
            ),
            Paragraph("Framework compatibility", styles["h2"]),
            _paragraph(
                "Legacy oracle runs stored under pass_fail_only directories are excluded by default because they could not produce partial verdicts. Use --include-binary-oracle only for a labeled historical appendix, not for a direct three-level score comparison.",
                styles["body"],
            ),
            Paragraph("Interpretation limits", styles["h2"]),
            _paragraph(
                "An LLM produced the answers and another LLM applied the rubric, so repeated runs can vary. Article recall measures coverage of designated ground-truth sources, not every possible supporting source. Full article recall does not prove that the model used the evidence correctly, and missing a designated source does not prove the context was insufficient when another article contains equivalent evidence. Differences between configurations should be interpreted together with run counts and per-question behavior.",
                styles["body"],
            ),
            Paragraph("Included experiment files", styles["h2"]),
        ]
    )

    included_data: list[list[Any]] = [["Run file"]]
    included_data.extend(
        [[_paragraph(str(path), styles["small"])]]
        for path in data.included_files
    )
    story.append(_styled_table(included_data, [650], long=True))

    if data.excluded_files:
        story.extend([Spacer(1, 8), Paragraph("Excluded files", styles["h2"])])
        excluded_data: list[list[Any]] = [["Run file", "Reason"]]
        excluded_data.extend(
            [
                _paragraph(str(path), styles["small"]),
                _paragraph(reason, styles["small"]),
            ]
            for path, reason in data.excluded_files
        )
        story.append(_styled_table(excluded_data, [430, 220], long=True))

    if data.warnings:
        story.extend([Spacer(1, 8), Paragraph("Warnings", styles["h2"])])
        for warning in data.warnings:
            story.append(_paragraph(warning, styles["note"]))

    # Charts grow with the number of configurations; one taller than the page frame
    # made reportlab raise LayoutError. Only such charts are scaled down.
    story = [
        _fit_drawing(item, document.width, document.height - 12) if isinstance(item, Drawing) else item
        for item in story
    ]
    document.build(story)


def _fit_drawing(drawing: Drawing, max_width: float, max_height: float) -> Drawing:
    """Scale a chart down to fit the page frame; a chart that fits is left unchanged."""

    factor = min(1.0, max_width / drawing.width, max_height / drawing.height)
    if factor < 1.0:
        drawing.scale(factor, factor)
        drawing.width *= factor
        drawing.height *= factor
    return drawing


def print_console_summary(data: AnalysisData, output_path: Path) -> None:
    columns = [
        "configuration",
        "runs",
        "cases",
        "pass_rate",
        "partial_rate",
        "fail_rate",
        "quality",
        "article_recall",
    ]
    summary = data.config_summary[columns].copy()
    for column in ("pass_rate", "partial_rate", "fail_rate", "article_recall"):
        summary[column] = summary[column].map(_percent)
    summary["quality"] = summary["quality"].map(_decimal)
    print(summary.to_string(index=False))

    priority_result = _task_priority_summary(data)
    if priority_result is not None:
        baseline_label, priority = priority_result
        focus = priority[
            [
                "task_family",
                "questions",
                "baseline_quality",
                "attention_score",
                "baseline_fail_rate",
                "oracle_quality",
                "oracle_gap",
                "baseline_article_recall",
            ]
        ].copy()
        focus["baseline_quality"] = focus["baseline_quality"].map(_decimal)
        focus["attention_score"] = focus["attention_score"].map(
            lambda value: f"{float(value):.1f}"
        )
        focus["baseline_fail_rate"] = focus["baseline_fail_rate"].map(_percent)
        focus["oracle_quality"] = focus["oracle_quality"].map(_decimal)
        focus["oracle_gap"] = focus["oracle_gap"].map(
            lambda value: (
                "n/a" if _as_float(value) is None else f"{float(value):+.3f}"
            )
        )
        focus["baseline_article_recall"] = focus[
            "baseline_article_recall"
        ].map(_percent)
        print(f"\nTask-family attention ({baseline_label}):")
        print(focus.to_string(index=False))

    measured = _measured_configurations(data)
    if not measured.empty:
        cost = measured[
            [
                "configuration",
                "telemetry_runs",
                "telemetry_quality",
                "calls_per_question",
                "input_tokens_per_question",
                "list_cost_per_question",
                "billed_cost_per_question",
                "seconds_per_question",
            ]
        ].copy()
        cost["telemetry_quality"] = cost["telemetry_quality"].map(_decimal)
        cost["calls_per_question"] = cost["calls_per_question"].map(lambda value: _decimal(value, 2))
        cost["input_tokens_per_question"] = cost["input_tokens_per_question"].map(_thousands)
        for column in ("list_cost_per_question", "billed_cost_per_question"):
            cost[column] = cost[column].map(_format_money)
        cost["seconds_per_question"] = cost["seconds_per_question"].map(lambda value: _decimal(value, 1))
        print("\nCost and latency (runs with telemetry; judge excluded):")
        print(cost.to_string(index=False))

    print(f"\nIncluded CSVs: {len(data.included_files)}")
    print(f"Excluded CSVs: {len(data.excluded_files)}")
    print(f"PDF report: {output_path.expanduser().resolve()}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = load_experiments(
            args.experiments_dir,
            include_binary_oracle=args.include_binary_oracle,
        )
        create_pdf_report(data, args.output, title=args.title)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_console_summary(data, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

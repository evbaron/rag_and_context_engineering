"""Helpers shared by the reports. (Checkpoint 1)"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ragkit import config
from ragkit.runlog import list_logs


def resolve_logs(paths: Sequence[str], last: int) -> list[Path]:
    """The log files named on the command line, or the ``last`` most recent ones."""
    if paths:
        resolved = [Path(path).expanduser() for path in paths]
        missing = [str(path) for path in resolved if not path.is_file()]
        if missing:
            raise SystemExit(f"Log file not found: {', '.join(missing)}")
        return resolved
    logs = list_logs()
    if not logs:
        raise SystemExit(f"No logs yet in {config.logs_dir()}. Run a sample first.")
    return logs[-last:]


def group_runs(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Log lines grouped by run, in the order they were read."""
    runs: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        runs.setdefault(record.get("run_id", "?"), []).append(record)
    return runs


def run_label(run_id: str, records: Sequence[dict[str, Any]]) -> str:
    """'experiment (time)', for example 'history_on (10:01:12)'."""
    experiment = records[0].get("experiment") if records else run_id
    clock = run_id[11:19].replace("-", ":") if len(run_id) >= 19 else run_id
    return f"{experiment} ({clock})"


def describe_pipeline(settings: dict[str, Any]) -> str:
    """A short one-line description of a pipeline's settings."""
    parts = [str(settings.get("name", "?"))]
    for key, value in settings.items():
        if key == "name" or isinstance(value, (dict, list)):
            continue
        if key == "model" and isinstance(value, str):
            value = value.split("/")[-1]
        parts.append(f"{key}={value}")
    return " · ".join(parts)


def question_key(record: dict[str, Any]) -> str:
    """How a question is matched across runs: its id if it has one, else its text."""
    return record.get("question_id") or " ".join((record.get("question") or "").split())


def cell(value: Any, limit: int | None = None) -> str:
    """Text made safe for one Markdown table cell."""
    text = " ".join(str(value).split()).replace("|", "\\|")
    if limit and len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def md_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return "\n".join(lines)


def usd(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.4f}" if value < 1 else f"${value:,.2f}"


def number(value: float | int | None, digits: int = 0) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.{digits}f}"


def write_report(text: str, name: str) -> Path:
    """Save a report under RAG_WORK_DIR/reports/ and return its path."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = config.reports_dir() / f"{stamp}_{name}.md"
    path.write_text(text, encoding="utf-8")
    return path

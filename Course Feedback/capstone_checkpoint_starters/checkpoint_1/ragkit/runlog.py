"""Logging every answered question to a file. (Checkpoint 1)

Each run writes one JSON Lines file under RAG_WORK_DIR/logs/: one JSON object per
line, one line per answered question. A line holds the question, the answer, the
passages retrieved, every model call with its tokens and time, and any scores.

Later checkpoints read these files: Checkpoint 3 compares the quality of runs, and the
log analysis works out cost and latency across every run since Checkpoint 1. The shape
of a line never changes; fields a pipeline does not use simply stay empty.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ragkit import config
from ragkit.pipelines.base import Answer, LLMCall, Pipeline


class RunLog:
    """One run's log file. Create one per experiment run, then ``record`` each answer."""

    def __init__(
        self,
        experiment: str,
        *,
        checkpoint: str = "",
        pipeline: Pipeline | None = None,
        settings: dict[str, Any] | None = None,
        folder: Path | None = None,
    ):
        self.experiment = experiment
        self.checkpoint = checkpoint
        if settings is None:
            settings = pipeline.settings() if pipeline is not None else {}
        self.settings = settings
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_id = f"{stamp}_{_slug(experiment)}"
        self.path = (folder or config.logs_dir()) / f"{self.run_id}.jsonl"
        self.count = 0

    def record(
        self,
        answer: Answer,
        *,
        question: str | None = None,
        question_id: str | None = None,
        dataset: str | None = None,
        category: str | None = None,
        scores: dict[str, Any] | None = None,
        history_turns: int = 0,
        latency_s: float | None = None,
        extra_calls: Sequence[LLMCall] = (),
    ) -> dict[str, Any]:
        """Write one line for ``answer``. ``extra_calls`` adds calls made outside the
        pipeline, such as the evaluation judge's, so their cost is logged too."""
        if latency_s is None:
            latency_s = sum(call.latency_s for call in answer.calls)
        details = {key: value for key, value in answer.metadata.items() if key != "context_chars"}
        record = self._base(question if question is not None else answer.question, question_id, dataset)
        record["category"] = category
        record.update(
            {
                "question_used": answer.question,
                "history_turns": history_turns,
                "retrieved": [hit_summary(hit) for hit in answer.hits],
                "context_chars": int(answer.metadata.get("context_chars", 0)),
                "answer": answer.text,
                "calls": [asdict(call) for call in [*answer.calls, *extra_calls]],
                "latency_s": round(latency_s, 3),
                "scores": scores or {},
                "details": details,
            }
        )
        self._write(record)
        return record

    def record_error(
        self,
        question: str,
        error: BaseException,
        *,
        question_id: str | None = None,
        dataset: str | None = None,
        history_turns: int = 0,
    ) -> dict[str, Any]:
        """Write one line for a question that failed, so failures show up in reports."""
        record = self._base(question, question_id, dataset)
        record.update({"history_turns": history_turns, "error": f"{type(error).__name__}: {error}"})
        self._write(record)
        return record

    def _base(self, question: str, question_id: str | None, dataset: str | None) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment": self.experiment,
            "checkpoint": self.checkpoint,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "pipeline": self.settings,
            "question_id": question_id,
            "dataset": dataset,
            "category": None,
            "question": question,
            "question_used": question,
            "history_turns": 0,
            "retrieved": [],
            "context_chars": 0,
            "answer": "",
            "calls": [],
            "latency_s": 0.0,
            "scores": {},
            "details": {},
            "error": None,
        }

    def _write(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.count += 1


def hit_summary(hit: Any) -> dict[str, Any]:
    """The part of a retrieved passage worth logging: its id, source, score, and route."""
    doc = getattr(hit, "doc", None)
    metadata = getattr(doc, "metadata", {}) or {}
    return {
        "id": getattr(doc, "id", None),
        "source": metadata.get("source"),
        "score": round(float(getattr(hit, "score", 0.0)), 4),
        "via": getattr(hit, "via", "retrieval"),
    }


def list_logs(folder: Path | None = None) -> list[Path]:
    """Every log file, oldest first (file names start with the run's date and time)."""
    return sorted((folder or config.logs_dir()).glob("*.jsonl"))


def read_records(paths: Iterable[Path | str]) -> list[dict[str, Any]]:
    """Read the lines of one or more log files. Unreadable lines are skipped."""
    records: list[dict[str, Any]] = []
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:60] or "run"

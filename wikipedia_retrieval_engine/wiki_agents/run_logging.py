"""Per-run, per-question evidence logs for the Checkpoint 5.1 graph."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel

from wikipedia_retrieval_engine.wiki_agents.agentic_models import AgentState

DEFAULT_AGENT_LOG_ROOT = (
    Path(__file__).resolve().parents[1]
    / "Capstone Checkpoint 5.1"
    / "logs"
)


def _question_slug(question: str, max_characters: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return (slug or "question")[:max_characters].rstrip("-")


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): _json_ready(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


class AgentRunLogger:
    """Write one complete terminal-state file per question in one run folder."""

    def __init__(
        self,
        log_root: str | Path = DEFAULT_AGENT_LOG_ROOT,
        *,
        started_at: datetime | None = None,
    ) -> None:
        self.started_at = started_at or datetime.now().astimezone()
        self.run_id = self.started_at.strftime("%Y_%m_%d_%H_%M_%S")
        self.run_directory = self._create_run_directory(Path(log_root))
        self._question_number = 0
        self._lock = Lock()

    def _create_run_directory(self, log_root: Path) -> Path:
        log_root.mkdir(parents=True, exist_ok=True)
        candidate = log_root / self.run_id
        collision_number = 2
        while candidate.exists():
            candidate = log_root / f"{self.run_id}__{collision_number:02d}"
            collision_number += 1
        candidate.mkdir()
        return candidate

    def write_question_state(self, state: AgentState) -> Path:
        """Atomically write the complete state and return the evidence-log path."""

        question = state.get("question", "").strip()
        if not question:
            raise ValueError("Cannot log agent state without a question.")

        with self._lock:
            self._question_number += 1
            number = self._question_number
            filename = (
                f"{number:03d}__{_question_slug(question)}.evidence.json"
            )
            path = self.run_directory / filename
            temporary_path = path.with_suffix(path.suffix + ".tmp")
            payload = {
                "run_id": self.run_id,
                "question_number": number,
                "logged_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "question": question,
                "final_state": _json_ready(state),
            }
            temporary_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(path)
            return path


def write_question_log(
    state: AgentState,
    logger: AgentRunLogger,
) -> AgentState:
    """Terminal graph node that persists state without adding paths to state."""

    logger.write_question_state(state)
    return {}

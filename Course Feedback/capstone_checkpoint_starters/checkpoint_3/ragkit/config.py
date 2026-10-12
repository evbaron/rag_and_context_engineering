"""Project settings, read from the .env file in the project folder. (Checkpoint 1)

Every setting has one name, one place it comes from, and a clear message when it is
missing or wrong. Other modules call these functions instead of reading environment
variables themselves.

Settings (see .env.example):
    OPENROUTER_API_KEY   the course API key
    RAG_SCENARIO         wikipedia, papers, or emails
    RAG_CORPUS_DIR       the folder holding that scenario's documents
    RAG_WORK_DIR         where logs, reports, indexes, and question sets are kept
    RAG_MODEL            chat model (optional)
    RAG_EMBEDDING_MODEL  embedding model (optional)
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-5.4-mini"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
SCENARIOS = ("wikipedia", "papers", "emails")

# Values already set in the shell win over the .env file.
load_dotenv(ENV_FILE, override=False)


class SetupError(RuntimeError):
    """A setting is missing or wrong. The message says how to fix it."""


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def api_key() -> str:
    key = _env("OPENROUTER_API_KEY")
    if not key or key == "sk-or-your-key-here":
        raise SetupError(
            f"OPENROUTER_API_KEY is not set. Copy .env.example to {ENV_FILE} "
            "and put the course key on the OPENROUTER_API_KEY line."
        )
    return key


def model() -> str:
    return _env("RAG_MODEL") or DEFAULT_MODEL


def embedding_model() -> str:
    return _env("RAG_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL


def scenario() -> str:
    value = (_env("RAG_SCENARIO") or "wikipedia").lower()
    if value not in SCENARIOS:
        raise SetupError(f"RAG_SCENARIO is '{value}'; use one of: {', '.join(SCENARIOS)}.")
    return value


def corpus_dir() -> Path:
    value = _env("RAG_CORPUS_DIR")
    if not value:
        raise SetupError(
            f"RAG_CORPUS_DIR is not set in {ENV_FILE}. Set it to the folder that holds "
            f"the {scenario()} documents."
        )
    path = Path(value).expanduser()
    if not path.is_dir():
        raise SetupError(f"RAG_CORPUS_DIR points to {path}, which is not a folder.")
    return path


def work_dir() -> Path:
    value = _env("RAG_WORK_DIR")
    path = Path(value).expanduser() if value else Path.home() / "rag_course_work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    return _subfolder("logs")


def reports_dir() -> Path:
    return _subfolder("reports")


def indexes_dir() -> Path:
    return _subfolder("indexes")


def cache_dir() -> Path:
    return _subfolder("cache")


def _subfolder(name: str) -> Path:
    path = work_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path

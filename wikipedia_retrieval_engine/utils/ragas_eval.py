"""Shared RAGAS evaluation harness for the Checkpoint 4.1 scripts.

Common plumbing extracted from the oracle / retriever / advanced-retrieval scripts so
each script keeps only its own technique (its build_*_experiment + a thin main()).
Edit shared behavior HERE, not in the individual checkpoint scripts.
"""
from __future__ import annotations

import argparse
import os
import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

import pandas as pd
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI
from ragas import Dataset
from ragas.llms import llm_factory
from ragas.metrics import DiscreteMetric

from retrievers import build_or_load_article_text_store, format_full_articles_context
from retrievers.corpus import build_or_load_markdown_store
from retrievers.llm import openrouter_headers

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "openai/gpt-5.4-mini"   # answer LLM (OpenRouter); covered by course credits
JUDGE_MODEL = "openai/gpt-5.4-mini"  # RAGAS DiscreteMetric judge (OpenRouter)
TEMPERATURE = 0.2

# Context sent to the answer LLM for the source articles: "plain_text" (flattened) or
# "markdown" (structure-preserving). Shared so oracle/retriever/advanced stay consistent
# within a comparison; flip it in ONE place.
CONTEXT_SOURCE = "markdown"
ARTICLE_TEXT_STORE_NAME = "wikipedia_plain_text"
ARTICLE_MARKDOWN_STORE_NAME = "wikipedia_markdown"

REQUIRED_GT_COLUMNS = {
    "ID",
    "Category",
    "Question",
    "Reference answer",
    "Grading notes",
    "Source articles",
}

T = TypeVar("T")


@dataclass(frozen=True)
class RateLimitBackoff:
    """Retry settings for OpenRouter 429/rate-limit errors."""

    retries: int = 3
    initial_seconds: float = 20.0
    multiplier: float = 2.0
    max_seconds: float = 120.0
    jitter: float = 0.15

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "RateLimitBackoff":
        return cls(
            retries=max(0, args.rate_limit_retries),
            initial_seconds=max(0.0, args.rate_limit_backoff_initial),
            multiplier=max(1.0, args.rate_limit_backoff_multiplier),
            max_seconds=max(0.0, args.rate_limit_backoff_max),
            jitter=max(0.0, args.rate_limit_backoff_jitter),
        )


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True for OpenRouter/OpenAI 429 errors and similar rate-limit text."""
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True

    text = str(exc).lower()
    return "rate limit" in text or "code': 429" in text or '"code": 429' in text


def _retry_after_from_error(exc: Exception) -> float | None:
    """Best-effort extraction of server-provided retry delay, in seconds."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None

    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            return None

    reset = headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset")
    if reset:
        try:
            reset_value = float(reset)
        except ValueError:
            return None
        if reset_value > 10_000_000_000:
            reset_value = reset_value / 1000.0
        return max(0.0, reset_value - time.time())

    return None


def call_with_rate_limit_backoff(
    func: Callable[[], T],
    backoff: RateLimitBackoff,
    *,
    label: str = "OpenRouter call",
) -> T:
    """Run a sync LLM/Judge call with configurable incremental backoff for 429s."""
    attempt = 0
    while True:
        try:
            return func()
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= backoff.retries:
                raise

            retry_number = attempt + 1
            server_delay = _retry_after_from_error(exc)
            delay = (
                server_delay
                if server_delay is not None
                else backoff.initial_seconds * (backoff.multiplier ** attempt)
            )
            if backoff.max_seconds:
                delay = min(delay, backoff.max_seconds)
            if backoff.jitter:
                low = max(0.0, 1.0 - backoff.jitter)
                high = 1.0 + backoff.jitter
                delay *= random.uniform(low, high)

            print(
                f"{label} hit a rate limit; retry "
                f"{retry_number}/{backoff.retries} in {delay:.1f}s..."
            )
            time.sleep(delay)
            attempt += 1


def check_api_key() -> str:
    """Load OPENROUTER_API_KEY from .env; raise a clear error if it is missing."""
    load_dotenv()
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Use the OpenRouter API key "
            "provided for this program, put it in a .env file next to this "
            "script, and rerun."
        )
    return key

def make_llm() -> ChatOpenAI:
    """Answer LLM for this script (shadows retrievers.llm.make_llm so LLM_MODEL applies)."""
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        api_key=check_api_key(),
        base_url=OPENROUTER_BASE_URL,
        default_headers=openrouter_headers("WRE retriever"),
    )

def make_judge():
    """Build the RAGAS judge LLM via OpenRouter.

    Loads OPENROUTER_API_KEY first so a missing key raises a clear error
    instead of failing later inside llm_factory.
    """
    api_key = check_api_key()
    return llm_factory(
        JUDGE_MODEL,
        client=OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers=openrouter_headers("WRE judge"),
        ),
    )

def parse_source_articles(source_cell: str) -> list[str]:
    """Convert the semicolon-separated spreadsheet cell into filenames."""
    return [
        filename.strip()
        for filename in source_cell.split(";")
        if filename.strip()
    ]

def source_key_from_gt_filename(filename: str) -> str:
    """Map a GT `Source articles` filename to the article-store key.

    Spreadsheet cells use Checkpoint 2.1 names such as `100_metres.html.txt`.
    Both stores are keyed by the HTML source (`100_metres.html`).
    """
    return filename.removesuffix(".txt")

def load_ground_truth_context(source_cell: str, article_text_store) -> str:
    """Load the complete text of every gold source article from CONTEXT_SOURCE.

    Used by the oracle experiment (and the optional validate_framework helper).
    """
    articles = []
    for filename in parse_source_articles(source_cell):
        source = source_key_from_gt_filename(filename)
        if not article_text_store.has_article(source):
            raise FileNotFoundError(
                f"Ground-truth article was not found in the "
                f"{CONTEXT_SOURCE} store: {source} ({article_text_store.root})"
            )
        articles.append(article_text_store.load(source))
    return format_full_articles_context(articles)

def my_eval_set(gt_path: Path) -> list[dict]:
    """Load and validate a selected ground-truth CSV."""
    gt_path = gt_path.expanduser().resolve()
    if not gt_path.is_file():
        raise FileNotFoundError(f"Ground-truth CSV does not exist: {gt_path}")

    df = pd.read_csv(gt_path)
    missing_columns = sorted(REQUIRED_GT_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(
            f"Ground-truth CSV is missing required columns: {missing_columns}"
        )
    if df.empty:
        raise ValueError(f"Ground-truth CSV contains no evaluation rows: {gt_path}")
    if df["ID"].isna().any() or df["ID"].duplicated().any():
        raise ValueError("Ground-truth IDs must be populated and unique.")

    df = df.rename(columns={"Question": "question", "Grading notes": "grading_notes"})
    return df.to_dict(orient="records")

correctness_metric = DiscreteMetric(
    name="answer_correctness",
    prompt=(
        "Evaluate the response using the question-specific grading notes. "
        "The grading notes are authoritative and define PASS, PARTIAL, and FAIL.\n\n"
        "Return exactly one label:\n"
        "- 'pass' when all PASS requirements are satisfied.\n"
        "- 'partial' when the answer is correct and supported but incomplete, "
        "as defined by the PARTIAL requirements, with no material false claims.\n"
        "- 'fail' when the answer contains a material error, unsupported claim, "
        "invalid addition, or contradiction described by the FAIL requirements.\n\n"
        "If both incompleteness and a material error are present, return 'fail'.\n\n"
        "Response: {response}\n\n"
        "Grading notes: {grading_notes}"
    ),
    allowed_values=["pass", "partial", "fail"],
)

def parse_args() -> argparse.Namespace:
    """Parse the required ground-truth and output paths."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a RAGAS evaluation against a selected Wikipedia "
            "ground-truth CSV."
        )
    )
    parser.add_argument(
        "--gt-set",
        type=Path,
        required=True,
        help="Path to a ground-truth CSV using the wikipedia_GT.csv schema.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory in which RAGAS will save datasets and experiments.",
    )
    parser.add_argument(
        "--experiment-name",
        "--config-name",
        dest="experiment_name",
        default="",
        help=(
            "Optional friendly comparison label saved with each result row, "
            "for example oracle_markdown. If omitted, the analyzer derives "
            "the configuration name from run metadata."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optional number of ground-truth rows to run. Omit for the full set."
        ),
    )
    parser.add_argument(
        "--question-id",
        dest="question_ids",
        action="append",
        default=None,
        help=(
            "Run one ground-truth question ID. Repeat this option to select "
            "multiple IDs in the supplied order."
        ),
    )
    parser.add_argument(
        "--rate-limit-retries",
        type=int,
        default=3,
        help=(
            "How many times to retry an OpenRouter 429/rate-limit error. "
            "Use 0 to disable retry backoff."
        ),
    )
    parser.add_argument(
        "--rate-limit-backoff-initial",
        type=float,
        default=20.0,
        help="Initial wait, in seconds, before the first 429 retry.",
    )
    parser.add_argument(
        "--rate-limit-backoff-multiplier",
        type=float,
        default=2.0,
        help="Multiplier applied after each 429 retry delay.",
    )
    parser.add_argument(
        "--rate-limit-backoff-max",
        type=float,
        default=120.0,
        help="Maximum wait, in seconds, before any single 429 retry.",
    )
    parser.add_argument(
        "--rate-limit-backoff-jitter",
        type=float,
        default=0.15,
        help=(
            "Random jitter fraction added/subtracted from each 429 retry delay. "
            "Use 0 for deterministic waits."
        ),
    )
    return parser.parse_args()

def build_ragas_dataset(
    gt_path: Path,
    output_dir: Path,
    dataset_suffix: str = "inputs",
    limit: int | None = 2,
    question_ids: list[str] | None = None,
) -> Dataset:
    """Copy ground-truth rows into a RAGAS Dataset saved under output_dir.

    If question_ids is set, those IDs are used (order preserved). Otherwise
    the first `limit` spreadsheet rows are used; limit=None means the full set.
    """
    rows = my_eval_set(gt_path)

    if question_ids is not None:
        rows_by_id = {
            row["ID"]: row
            for row in rows
        }

        missing_ids = [
            question_id
            for question_id in question_ids
            if question_id not in rows_by_id
        ]

        if missing_ids:
            raise ValueError(
                f"Unknown question IDs: {missing_ids}"
            )

        selected_rows = [
            rows_by_id[question_id]
            for question_id in question_ids
        ]
    else:
        selected_rows = rows[:limit]

    dataset = Dataset(
        name=f"{re.sub(r'[^A-Za-z0-9_-]+', '_', gt_path.stem)}_{dataset_suffix}",
        backend="local/csv",
        root_dir=str(output_dir),
    )

    for row in selected_rows:
        dataset.append(
            {
                "question_id": row["ID"],
                "category": row["Category"],
                "question": row["question"],
                "reference_answer": row["Reference answer"],
                "grading_notes": row["grading_notes"],
                "source_articles": row["Source articles"],
            }
        )
    dataset.save()
    return dataset

def load_context_store(context_source: str = CONTEXT_SOURCE):
    """Load the full-article store used for answer context (markdown or plain_text)."""
    if context_source == "markdown":
        print("Context source: markdown (structure-preserving)")
        return build_or_load_markdown_store(store_name=ARTICLE_MARKDOWN_STORE_NAME)
    if context_source == "plain_text":
        print("Context source: plain_text (baseline)")
        return build_or_load_article_text_store(text_store_name=ARTICLE_TEXT_STORE_NAME)
    raise ValueError(
        f"context_source must be 'markdown' or 'plain_text', got {context_source!r}"
    )


def print_score_summary(results) -> Counter:
    """Print the pass/partial/fail tally for a completed experiment and return it."""
    counts = Counter(row["score"] for row in results)
    print(
        "\nExperiment complete: "
        f"Pass: {counts['pass']} | Partial: {counts['partial']} | "
        f"Fail: {counts['fail']} | Total: {len(results)}"
    )
    return counts


def save_results(results, output_dir: Path) -> Path:
    """Persist RAGAS results and print the CSV path."""
    results.save()
    results_path = output_dir / "experiments" / f"{results.name}.csv"
    print(f"\nResults saved to: {results_path.resolve()}")
    return results_path

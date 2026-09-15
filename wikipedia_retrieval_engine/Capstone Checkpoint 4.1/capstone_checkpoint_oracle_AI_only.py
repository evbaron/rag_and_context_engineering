r"""Capstone Checkpoint 4.1 — Oracle evaluation (ground-truth Wikipedia context).

Jupytext-style cell markers (# %% / # %% [markdown]) — runnable as a
plain script and openable as cells in VS Code / PyCharm / Jupytext.

This script does not retrieve. For each question in the CSV supplied with
``--gt-set`` it
loads the labeled source articles in full, asks the answer LLM to respond
from that context only, and scores the response with a RAGAS DiscreteMetric
(pass / partial / fail) against the grading notes. The required
``--output-dir`` argument selects the RAGAS dataset and experiment directory.
"""

# %% [markdown]
# # Capstone Checkpoint 4.1 — Oracle evaluation (no retriever)
# **Wikipedia Retrieval Engine / Module 4**
#
# This script measures answer quality when retrieval is replaced by the
# ground-truth source articles. It is an upper-bound / framework-check run:
# the same questions, grading notes, answer model, and RAGAS judge as
# `capstone_checkpoint_3_1_with_retriever.py`, but with gold context instead
# of hybrid retrieval.
#
# **Pipeline**
# 1. Load the ground-truth CSV selected by `--gt-set`.
# 2. For each question, concatenate the full text of every labeled source article
#    from the store selected by `CONTEXT_SOURCE` (`plain_text` or `markdown`).
# 3. Generate an answer from that context only (`answer_from_context`).
# 4. Score the answer with a RAGAS `DiscreteMetric`: `pass`, `partial`, or `fail`.
# 5. Save the experiment CSV under `<output-dir>/experiments/`.
#
# Compare these scores with the retriever script to separate generation/judge
# issues from retrieval misses.
#
# **Learning outcomes (Module 3):**
# 1. Define evaluation metrics that reflect the real-world performance requirements of an LLM-powered retrieval system.
# 2. Identify key variables that influence system performance during evaluation and development.
# 3. Use language models to support evaluation tasks while avoiding common pitfalls.
# 4. Evaluate the performance of a retrieval-augmented system during development using a structured evaluation framework.

# %% [markdown]
# ## Step 1 — Wikipedia scenario and ground truth
#
# This run uses the **Wikipedia Retrieval Engine** from Checkpoints 1.1 and 2.1.
# Oracle mode never calls a retriever: the `Source articles` column *is* the context.
#
# | Resource | Location / setting |
# |---|---|
# | Questions, reference answers, grading notes, source articles | CSV selected by `--gt-set` |
# | Full article text store | `CONTEXT_SOURCE`: `"plain_text"` → `wikipedia_plain_text/`; `"markdown"` → `wikipedia_markdown/` |

# %% [markdown]
# ## Setup
#
# 1. **Python 3.11 or 3.12.**
# 2. From the repo venv: `pip install -r "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/requirements.txt"`
#    (includes RAGAS, LangChain, OpenAI, pandas — not only `langchain-openai`).
# 3. Put the course OpenRouter key in a `.env` file as `OPENROUTER_API_KEY=sk-or-v1-...`
#    (next to this script, or in `rag_and_context_engineering/.env`).
# 4. The Wikipedia article-text store selected by `CONTEXT_SOURCE` must already exist.
#
# This is not the Lab 3.1 toy corpus. Both the answer LLM and the RAGAS judge
# call OpenRouter.

# %%
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

# %%

try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    _HERE = Path.cwd()
_ENGINE = _HERE.parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from retrievers import (
    EvidenceLogger,
    RetrieverSpec,
    build_or_load_article_text_store,
    build_or_load_db,
    format_articles,
    format_chunks,
    format_full_articles_context,
    load_wikipedia_chunks,
    load_retrieved_article_texts,
    make_retriever,
)
from retrievers.corpus import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_WIKI_DIR,
    build_or_load_markdown_store,
)
from retrievers.llm import answer as answer_from_context
from retrievers.llm import make_llm

from openai import OpenAI
from ragas import Dataset, experiment
from ragas.llms import llm_factory
from ragas.metrics import DiscreteMetric

import asyncio


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "openai/gpt-5.4-mini"  # answer LLM (OpenRouter); covered by course credits
JUDGE_MODEL = "openai/gpt-5.4-mini"  # RAGAS DiscreteMetric judge (OpenRouter)
TEMPERATURE = 0.2
TOP_K = 3  # unused leftover from the Lab 3.1 demo retriever

ARTICLE_TEXT_STORE_NAME = "wikipedia_plain_text"
ARTICLE_MARKDOWN_STORE_NAME = "wikipedia_markdown"
# Context sent to the answer LLM for the gold source articles:
#   "plain_text" — Checkpoint 2.1/3.1 baseline (flattened text; tables collapsed)
#   "markdown"   — structure-preserving markdown store (tables/infobox preserved)
# Retrieval is not involved either way; only the gold-article representation
# differs, so a plain_text→markdown comparison isolates that effect.
CONTEXT_SOURCE = "markdown"

ARTICLE_TEXT_DIR = (
    _ENGINE
    / "retrievers"
    / "db"
    / "article_text"
    / (
        ARTICLE_MARKDOWN_STORE_NAME
        if CONTEXT_SOURCE == "markdown"
        else ARTICLE_TEXT_STORE_NAME
    )
)
LOG_PATH = _HERE / f"checkpoint_3.1_evaluation_{datetime.now().strftime('%Y-%m-%d-%H-%M')}.log"  # unused by the RAGAS experiment; see log()
SCENARIO = "wikipedia"  # Wikipedia Retrieval Engine (not used as a runtime switch)

# Used only by the leftover Lab 3.1 helpers below. Live answers use
# retrievers.llm.answer (SYSTEM_PROMPT); live judging uses correctness_metric.
ANSWER_SYSTEM = (
    "You are a helpful assistant. Answer the question using ONLY the provided "
    "documents, and quote from them where you can. If the documents do not contain "
    "the answer, say so rather than guessing."
)
JUDGE_SYSTEM = (
    "You are a strict evaluator. You are given an ANSWER and GRADING NOTES describing "
    "what a correct answer must contain. Reply with exactly one word: 'pass' if the "
    "answer satisfies the grading notes, or 'fail' if it does not."
)


# %%
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
    )

# ─── RAGAS evaluation harness ────────────────────────────────────────
def make_judge():
    """Build the RAGAS judge LLM via OpenRouter.

    Loads OPENROUTER_API_KEY first so a missing key raises a clear error
    instead of failing later inside llm_factory.
    """
    api_key = check_api_key()
    return llm_factory(
        JUDGE_MODEL,
        client=OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL),
    )

def log(label: str, text: str) -> None:
    """Append a timestamped block to LOG_PATH. Not used by the RAGAS experiment."""
    ts = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {label}\n{text}\n{'-' * 72}\n")

def _tokens(text: str) -> set[str]:
    """Tokenize for overlap checks. Not used by the RAGAS experiment."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def answer(llm: ChatOpenAI, query: str, doc_ids: list[str]) -> str:
    """Unused Lab 3.1 leftover (depends on DOC_BY_ID). Live path: answer_from_context."""
    context = "\n\n".join(f"[{i}] {DOC_BY_ID[i]['text']}" for i in doc_ids if i in DOC_BY_ID)
    messages = [
        SystemMessage(content=ANSWER_SYSTEM),
        HumanMessage(content=f"Documents:\n{context}\n\nQuestion: {query}"),
    ]
    return llm.invoke(messages).content

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
# %% [markdown]
# ## Step 2 — RAGAS evaluation metric
#
# The live judge is a RAGAS `DiscreteMetric` named `answer_correctness`.
# It reads the generated response and the question's grading notes and
# returns exactly one of `pass`, `partial`, or `fail`.
#
# The binary `judge()` helper in the next cell is leftover from the Lab 3.1
# starter (pass/fail only) and is **not** used by `main()`.

# %%
def judge(llm: ChatOpenAI, answer_text: str, grading_notes: str) -> str:
    """Unused Lab 3.1 leftover: binary pass/fail. The experiment uses correctness_metric."""
    messages = [
        SystemMessage(content=JUDGE_SYSTEM),
        HumanMessage(content=f"ANSWER:\n{answer_text}\n\nGRADING NOTES:\n{grading_notes}\n\nVerdict (pass/fail):"),
    ]
    verdict = llm.invoke(messages).content.strip().lower()
    return "pass" if "pass" in verdict else "fail"


REQUIRED_GT_COLUMNS = {
    "ID",
    "Category",
    "Question",
    "Reference answer",
    "Grading notes",
    "Source articles",
}


def parse_args() -> argparse.Namespace:
    """Parse the required ground-truth and output paths."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the oracle-context RAGAS evaluation against a selected "
            "Wikipedia ground-truth CSV."
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
    return parser.parse_args()


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

# Optional smoke test (disabled): score a gold-context answer vs a known-wrong
# answer to check that the judge can distinguish them. Uncomment to run once.
#
# def validate_framework() -> None:
#     evaluation_set = my_eval_set(Path("path/to/ground_truth.csv"))
#     first = evaluation_set[0]
#
#     context = load_ground_truth_context(first["Source articles"], article_text_store)
#
#     answer_llm = make_llm()
#     correct_response = answer_from_context(
#         query=first["question"],
#         context=context,
#         llm=answer_llm,
#     )
#
#     manipulated_response = (
#         "The current men's world record is 10.20 seconds, "
#         "held by Carl Lewis of the United States. It was set "
#         "in Paris in 1995."
#     )
#
#     ragas_judge = make_judge()
#
#     correct_score = correctness_metric.score(
#         llm=ragas_judge,
#         response=correct_response,
#         grading_notes=first["grading_notes"],
#     )
#
#     manipulated_score = correctness_metric.score(
#         llm=ragas_judge,
#         response=manipulated_response,
#         grading_notes=first["grading_notes"],
#     )
#
#     print(f"ID: {first['ID']}")
#     print(f"Question: {first['question']}")
#
#     print(f"\nCorrect answer:\n{correct_response}")
#     print(f"Correct-answer verdict: {correct_score.value.upper()}")
#
#     print(f"\nManipulated answer:\n{manipulated_response}")
#     print(f"Manipulated-answer verdict: {manipulated_score.value.upper()}")
#
# validate_framework()


# %% [markdown]
# ## Step 3 — RAGAS dataset from the selected ground-truth CSV
#
# `build_ragas_dataset()` copies ground-truth rows into a RAGAS `Dataset`
# named `wikipedia_oracle_inputs`. Pass `question_ids=` for specific IDs,
# or `limit=` for a prefix of the spreadsheet. `main()` uses `limit=None`
# (the full set). The default `limit=2` is only a smoke-test subset.

# %%
def build_ragas_dataset(
    gt_path: Path,
    output_dir: Path,
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
        name=f"{re.sub(r'[^A-Za-z0-9_-]+', '_', gt_path.stem)}_oracle_inputs",
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

# %% [markdown]
# ## Step 4 — Oracle experiment
#
# For each dataset row this run:
# 1. Loads the full text of every gold source article (`load_ground_truth_context`)
#    from the store selected by `CONTEXT_SOURCE` (`plain_text` or `markdown`).
# 2. Generates an answer from that context (`answer_from_context`).
# 3. Scores the answer with `correctness_metric` (`pass` / `partial` / `fail`).
# 4. Records `context_source` and any optional `experiment_name` on each result row
#    so runs can be compared.
#
# `asyncio.run(main())` evaluates the full ground-truth set and writes
# `<output-dir>/experiments/<run_name>.csv`.

# %%
def build_oracle_experiment(
    article_text_store,
    answer_llm: ChatOpenAI,
    ragas_judge,
    experiment_name: str = "",
):
    """Return a RAGAS experiment that answers from gold articles, then judges."""
    @experiment()
    async def run_oracle_case(row: dict) -> dict:
        context = load_ground_truth_context(
            row["source_articles"],
            article_text_store,
        )

        response = answer_from_context(
            query=row["question"],
            context=context,
            llm=answer_llm,
        )

        score = correctness_metric.score(
            llm=ragas_judge,
            response=response,
            grading_notes=row["grading_notes"],
        )

        return {
            **row,
            "experiment_name": experiment_name,
            "evaluation_mode": "oracle_ground_truth_context",
            "context_source": CONTEXT_SOURCE,
            "answer_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL,
            "response": response,
            "score": score.value,
            "source_count": len(
                parse_source_articles(row["source_articles"])
            ),
            "context_characters": len(context),
        }

    return run_oracle_case


async def main() -> None:
    """Run the oracle RAGAS experiment on the selected ground-truth set."""
    args = parse_args()
    gt_path = args.gt_set.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    experiment_name = args.experiment_name.strip()
    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(f"Output path is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_ragas_dataset(
        gt_path=gt_path,
        output_dir=output_dir,
        limit=None,
    )

    print("Loading Wikipedia article-text store...")
    if CONTEXT_SOURCE == "markdown":
        print("Context source: markdown (structure-preserving)")
        article_text_store = build_or_load_markdown_store(
            store_name=ARTICLE_MARKDOWN_STORE_NAME,
        )
    elif CONTEXT_SOURCE == "plain_text":
        print("Context source: plain_text (baseline)")
        article_text_store = build_or_load_article_text_store(
            text_store_name=ARTICLE_TEXT_STORE_NAME,
        )
    else:
        raise ValueError(
            "CONTEXT_SOURCE must be 'markdown' or 'plain_text', "
            f"got {CONTEXT_SOURCE!r}"
        )

    answer_llm = make_llm()
    ragas_judge = make_judge()

    oracle_experiment = build_oracle_experiment(
        article_text_store=article_text_store,
        answer_llm=answer_llm,
        ragas_judge=ragas_judge,
        experiment_name=experiment_name,
    )

    experiment_label = experiment_name or "auto-derived"
    print(
        f"Running oracle evaluation on {len(dataset)} questions "
        f"from {gt_path} "
        f"(context_source={CONTEXT_SOURCE}, experiment_name={experiment_label})..."
    )

    results = await oracle_experiment.arun(dataset)
    score_counts = Counter(
        row["score"]
        for row in results
    )

    print(
        "\nExperiment complete: "
        f"Pass: {score_counts['pass']} | "
        f"Partial: {score_counts['partial']} | "
        f"Fail: {score_counts['fail']} | "
        f"Total: {len(results)}"
    )

    results.save()

    results_path = (
        output_dir
        / "experiments"
        / f"{results.name}.csv"
    )

    print(f"\nResults saved to: {results_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())

r"""Capstone Checkpoint 3.1 — Evaluation Infrastructure and Baseline Diagnosis (starter).
Jupytext-style cell markers (# %% / # %% [markdown]) — runnable as a
plain script AND openable as cells in VS Code / PyCharm / Jupytext.

This demonstration system is not your capstone system and 
does not use the Research Paper Navigator or Wikipedia corpus.
"""

# %% [markdown]
# # Capstone Checkpoint 3.1 — Evaluation Infrastructure and Baseline Diagnosis
# **MO-LLM Module 3 / Required Capstone Checkpoint (120 minutes)**
#
# ## What this checkpoint is
#
# #
# This mirrors **Lab 3.1** (an LLM-judge that scores answers pass/fail against grading
# notes), applied to your capstone system. 
# You have a baseline retrieval system from Checkpoint 2.1. In this checkpoint, 
# you will use a structured evaluation approach to measure baseline performance, diagnose strengths 
# and weaknesses, and examine whether the evaluation framework detects problematic outputs.
# The starter script includes a small demonstration corpus and retriever to illustrate the 
# evaluation workflow. Apply the same evaluation approach to your selected capstone scenario and 
# baseline retrieval system. The graded deliverable is the completed Capstone Checkpoint 3.1 worksheet.
#
# **Learning outcomes (Module 3):**
# 1. Define evaluation metrics that reflect the real-world performance requirements of an LLM-powered retrieval system.
# 2. Identify key variables that influence system performance during evaluation and development.
# 3. Use language models to support evaluation tasks while avoiding common pitfalls.
# 4. Evaluate the performance of a retrieval-augmented system during development using a structured evaluation framework.

# %% [markdown]
# ## Step 1 — Keep your capstone scenario
#
# Use the **same scenario and baseline retriever** from Checkpoints 1.1 and 2.1.
#
# | Scenario | Corpus |
# |---|---|
# | **Research Paper Navigator** | ~150 research-paper PDFs (`Labs/CapstoneDatasets/ResearchPapers/`) |
# | **Wikipedia Retrieval Engine** | ~2,400 Wikipedia HTML articles (`Labs/CapstoneDatasets/Wikipedia/`) |

# %% [markdown]
# ## Setup (~5 min)
#
# 1. **Python 3.11 or 3.12.**
# 2. `pip install langchain-openai langchain-core python-dotenv`
# 3. Use the OpenRouter API key provided for this program.
# 4. Create a `.env` file next to this script: `OPENROUTER_API_KEY=sk-or-v1-...`
#
# Runs on a tiny built-in sample corpus, so you do not need to prepare your own dataset.
# It still requires an OpenRouter API key to run the LLM (it is not offline or free of API
# calls). You apply the same evaluation approach to your real system for the report.

# %%
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

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
from retrievers.corpus import CHUNK_OVERLAP, CHUNK_SIZE, DEFAULT_WIKI_DIR
from retrievers.llm import answer as answer_from_context
from retrievers.llm import make_llm

from openai import OpenAI
from ragas import Dataset, experiment
from ragas.llms import llm_factory
from ragas.metrics import DiscreteMetric

import asyncio


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "openai/gpt-5.4-mini"  # latest small OpenAI model, fast; covered by course credits
JUDGE_MODEL = "openai/gpt-5.4-mini"  # judge model; try a different one in Step 2
TEMPERATURE = 0.2
RETRIEVAL_TOP_K = 7
HYBRID_CANDIDATE_POOL = max(10, RETRIEVAL_TOP_K)

CHROMA_DB_NAME = "wikipedia_chars1600_overlap200"
ARTICLE_TEXT_STORE_NAME = "wikipedia_plain_text"

BASELINE_RETRIEVER_SPEC = RetrieverSpec(
    kind="hybrid",
    label="hybrid_vector_heavy_k7",
    top_k=RETRIEVAL_TOP_K,
    candidate_pool=HYBRID_CANDIDATE_POOL,
    weight_bm25=0.35,
    weight_vector=0.65,
)

ARTICLE_TEXT_DIR = (
    _ENGINE
    / "retrievers"
    / "db"
    / "article_text"
    / "wikipedia_plain_text"
)
LOG_PATH = _HERE / f"checkpoint_3.1_evaluation_{datetime.now().strftime('%Y-%m-%d-%H-%M')}.log"
RAGAS_OUTPUT_DIR = _HERE / "ragas_experiments"

SCENARIO ="wikipedia"

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
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        api_key=check_api_key(),
        base_url=OPENROUTER_BASE_URL,
    )

# ─── RAGAS evaluation harness ────────────────────────────────────────
def make_judge():
    """Build the judge LLM. Called from main() AFTER require_api_key(), so a missing
    key gives a friendly message instead of a KeyError at import time."""

    api_key = check_api_key()
    return llm_factory(
        JUDGE_MODEL,
        client=OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL),
    )

def log(label: str, text: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {label}\n{text}\n{'-' * 72}\n")

def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def answer(llm: ChatOpenAI, query: str, doc_ids: list[str]) -> str:
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

def load_ground_truth_context(source_cell: str) -> str:
    """Load the complete text of every ground-truth source article."""
    context_parts = []

    for filename in parse_source_articles(source_cell):
        article_path = ARTICLE_TEXT_DIR / filename

        if not article_path.is_file():
            raise FileNotFoundError(
                f"Ground-truth article was not found: {article_path}"
            )

        article_text = article_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        context_parts.append(
            f"[SOURCE: {filename}]\n{article_text}"
        )

    separator = "\n\n" + "=" * 80 + "\n\n"
    return separator.join(context_parts)
# %% [markdown]
# ## Step 2 — The evaluation metric (provided)
#
# A simple **LLM-judge** that returns pass/fail by checking an answer against grading
# notes — the same idea as Lab 3.1's DiscreteMetric, written directly here so the
# checkpoint needs no extra packages. Tuning this metric (stricter notes, a 'partial'
# level, a stronger judge model) is part of the diagnosis.

# %%
def judge(llm: ChatOpenAI, answer_text: str, grading_notes: str) -> str:
    messages = [
        SystemMessage(content=JUDGE_SYSTEM),
        HumanMessage(content=f"ANSWER:\n{answer_text}\n\nGRADING NOTES:\n{grading_notes}\n\nVerdict (pass/fail):"),
    ]
    verdict = llm.invoke(messages).content.strip().lower()
    return "pass" if "pass" in verdict else "fail"


def my_eval_set() -> list[dict]:
    gt_path = _ENGINE / "GT" / "wikipedia_GT.csv"
    df = pd.read_csv(gt_path)
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
# ---------  VALIDATION OF THE FRAMEWORK ---------

# def validate_framework() -> None:
#     evaluation_set = my_eval_set()
#     first = evaluation_set[0]

#     context = load_ground_truth_context(first["Source articles"])

#     answer_llm = make_llm()
#     correct_response = answer_from_context(
#         query=first["question"],
#         context=context,
#         llm=answer_llm,
#     )

#     manipulated_response = (
#         "The current men's world record is 10.20 seconds, "
#         "held by Carl Lewis of the United States. It was set "
#         "in Paris in 1995."
#     )

#     ragas_judge = make_judge()

#     correct_score = correctness_metric.score(
#         llm=ragas_judge,
#         response=correct_response,
#         grading_notes=first["grading_notes"],
#     )

#     manipulated_score = correctness_metric.score(
#         llm=ragas_judge,
#         response=manipulated_response,
#         grading_notes=first["grading_notes"],
#     )

#     print(f"ID: {first['ID']}")
#     print(f"Question: {first['question']}")

#     print(f"\nCorrect answer:\n{correct_response}")
#     print(f"Correct-answer verdict: {correct_score.value.upper()}")

#     print(f"\nManipulated answer:\n{manipulated_response}")
#     print(f"Manipulated-answer verdict: {manipulated_score.value.upper()}")

# validate_framework() # this is the validation of the framework
# ------------------------END OF VALIDATION OF THE FRAMEWORK----------------------------


# Ragas required dataset for evalution
# convert my_eval_set() to a Ragas dataset
def build_ragas_dataset(
    limit: int | None = 2,
    question_ids: list[str] | None = None,
) -> Dataset:
    rows = my_eval_set()

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
        name="wikipedia_retrieval_inputs",
        backend="local/csv",
        root_dir=str(RAGAS_OUTPUT_DIR),
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

def build_retrieval_experiment(
    retriever,
    article_text_store,
    answer_llm: ChatOpenAI,
    ragas_judge,
):
    @experiment()
    async def run_retrieval_case(row: dict) -> dict:
        # The question—not the ground-truth filenames—selects the evidence.
        hits = retriever.getTopK(row["question"])
        retrieved_article_texts = load_retrieved_article_texts(
            hits,
            article_text_store,
        )
        context = format_full_articles_context(retrieved_article_texts)

        required_articles = [
            article.removesuffix(".txt")
            for article in parse_source_articles(row["source_articles"])
        ]
        retrieved_articles = [
            article.source
            for article in retrieved_article_texts
        ]
        retrieved_article_set = set(retrieved_articles)
        matched_articles = [
            article
            for article in required_articles
            if article in retrieved_article_set
        ]
        missing_articles = [
            article
            for article in required_articles
            if article not in retrieved_article_set
        ]
        article_recall = (
            len(matched_articles) / len(required_articles)
            if required_articles
            else 1.0
        )

        if context.strip():
            response = answer_from_context(
                query=row["question"],
                context=context,
                llm=answer_llm,
            )
        else:
            response = (
                "I cannot answer because no Wikipedia articles were retrieved."
            )

        score = correctness_metric.score(
            llm=ragas_judge,
            response=response,
            grading_notes=row["grading_notes"],
        )

        return {
            **row,
            "evaluation_mode": "retrieved_full_article_context",
            "answer_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL,
            "retriever_kind": BASELINE_RETRIEVER_SPEC.kind,
            "retriever_label": BASELINE_RETRIEVER_SPEC.label,
            "retrieval_top_k": BASELINE_RETRIEVER_SPEC.top_k,
            "hybrid_candidate_pool": BASELINE_RETRIEVER_SPEC.candidate_pool,
            "weight_bm25": BASELINE_RETRIEVER_SPEC.weight_bm25,
            "weight_vector": BASELINE_RETRIEVER_SPEC.weight_vector,
            "required_articles": "; ".join(required_articles),
            "retrieved_articles": "; ".join(retrieved_articles),
            "matched_articles": "; ".join(matched_articles),
            "missing_articles": "; ".join(missing_articles),
            "article_recall": article_recall,
            "retrieved_chunk_ids": "; ".join(hit[0] for hit in hits),
            "retrieved_chunk_count": len(hits),
            "retrieved_article_count": len(retrieved_articles),
            "response": response,
            "score": score.value,
            "source_count": len(required_articles),
            "context_characters": len(context),
        }

    return run_retrieval_case


async def main() -> None:
    dataset = build_ragas_dataset(limit=None)

    print("Loading Wikipedia retrieval resources...")
    chunks = load_wikipedia_chunks()
    article_text_store = build_or_load_article_text_store(
        text_store_name=ARTICLE_TEXT_STORE_NAME,
    )
    db = build_or_load_db(
        chroma_db_name=CHROMA_DB_NAME,
        chunks=chunks,
    )
    retriever = make_retriever(
        BASELINE_RETRIEVER_SPEC,
        chunks=chunks,
        db=db,
        chroma_db_name=CHROMA_DB_NAME,
    )

    answer_llm = make_llm()
    ragas_judge = make_judge()

    retrieval_experiment = build_retrieval_experiment(
        retriever=retriever,
        article_text_store=article_text_store,
        answer_llm=answer_llm,
        ragas_judge=ragas_judge,
    )

    print(
        f"Running retrieval evaluation on {len(dataset)} questions "
        f"with {retriever.settings()}..."
    )

    results = await retrieval_experiment.arun(dataset)

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

    for row in results:
        print("=" * 72)
        print(f"ID: {row['question_id']}")
        print(f"Required articles: {row['required_articles']}")
        print(f"Retrieved articles: {row['retrieved_articles']}")
        print(f"Missing articles: {row['missing_articles'] or '(none)'}")
        print(f"Article recall: {row['article_recall']:.2f}")
        print(f"Verdict: {row['score'].upper()}")

    results.save()

    results_path = (
        RAGAS_OUTPUT_DIR
        / "experiments"
        / f"{results.name}.csv"
    )

    print(f"\nResults saved to: {results_path.resolve()}")


asyncio.run(main())

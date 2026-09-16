r"""Capstone Checkpoint 4.1 — Advanced Retrieval (query decomposition).

Runs the ADVANCED retriever — multistep query decomposition (Lab 4.1) — on the real
Wikipedia system and scores it with the SAME RAGAS harness as the baseline, so the two
are directly comparable. Shared plumbing lives in ``utils/ragas_eval.py``; the
decomposition retriever is ``retrievers/multistep.py`` (``MultiStepRetriever``).

Jupytext cell markers (# %% / # %% [markdown]) — runnable as a script and as cells.

Run (from ``wikipedia_retrieval_engine/``):
    python "Capstone Checkpoint 4.1/capstone_checkpoint_4_1_advanced_retrieval_starter.py" \
        --gt-set "GT/wikipedia_GT.csv" \
        --output-dir "Capstone Checkpoint 4.1/ragas_advanced" \
        --experiment-name vs_k7_markdown_decomposed

For the comparison, run the baseline (capstone_checkpoint_with_retriever.py with
DECOMPOSE=False) into the SAME --output-dir, then build the report with
utils/analyze_ragas_experiments.py.
"""

# %% [markdown]
# # Capstone Checkpoint 4.1 — Advanced Retrieval (query decomposition)
#
# **Technique:** multistep query decomposition — split the question into focused
# sub-queries, run vector search for each in parallel, and merge (a chunk found by
# several sub-queries ranks higher). Targets multi-source questions where single-pass
# retrieval misses one of the required articles.
#
# **Only the retriever changes** vs the baseline: same Chroma index, same markdown
# context, same GT set, same judge — so the comparison isolates decomposition.

# %%
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import asyncio
import sys
from pathlib import Path

try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    _HERE = Path.cwd()
_ENGINE = _HERE.parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from ragas import experiment

from retrievers import (
    build_or_load_db,
    format_full_articles_context,
    load_retrieved_article_texts,
    load_wikipedia_chunks,
)
from retrievers.llm import answer as answer_from_context
from retrievers.multistep import MultiStepRetriever
from utils.ragas_eval import (
    CONTEXT_SOURCE,
    JUDGE_MODEL,
    LLM_MODEL,
    RateLimitBackoff,
    build_ragas_dataset,
    call_with_rate_limit_backoff,
    correctness_metric,
    load_context_store,
    make_judge,
    make_llm,
    parse_args,
    parse_source_articles,
    print_score_summary,
    save_results,
)

# %%
# Retrieval config — held identical to the baseline so decomposition is the ONLY change.
CHROMA_DB_NAME = "wikipedia_chars1600_overlap200"
RETRIEVAL_TOP_K = 7
# Reasoning is applied per-question: the decomposition emits reasoning instructions only
# for multi-step questions (else NONE, see _SYSTEM_PROMPT), so simple lookups run the
# plain answer path — no toggle needed.


# %% [markdown]
# ## The advanced experiment
# Retrieve with the decomposition retriever, expand hits to full markdown articles,
# answer, judge, and record article-level recall — so the per-question recall table in
# the report shows whether multi-source questions (e.g. GT03/GT09/GT14/GT16) improve.

# %%
def build_advanced_experiment(
    retriever,
    article_text_store,
    answer_llm,
    ragas_judge,
    rate_limit_backoff: RateLimitBackoff,
    experiment_name: str = "",
):
    """RAGAS experiment: decomposition retrieval -> full markdown context -> answer -> judge."""

    @experiment()
    async def run_advanced_case(row: dict) -> dict:
        # The question — not the gold filenames — selects the evidence.
        hits, reasoning = retriever.retrieve_with_reasoning(row["question"])
        retrieved_article_texts = load_retrieved_article_texts(hits, article_text_store)
        context = format_full_articles_context(retrieved_article_texts)

        required_articles = [
            article.removesuffix(".txt")
            for article in parse_source_articles(row["source_articles"])
        ]
        retrieved_articles = [article.source for article in retrieved_article_texts]
        retrieved_set = set(retrieved_articles)
        matched = [a for a in required_articles if a in retrieved_set]
        missing = [a for a in required_articles if a not in retrieved_set]
        article_recall = len(matched) / len(required_articles) if required_articles else 1.0

        answer_query = row["question"]
        if reasoning:
            answer_query = (
                f"{row['question']}\n\nSteps to follow when answering:\n{reasoning}"
            )
        if context.strip():
            response = call_with_rate_limit_backoff(
                lambda: answer_from_context(
                    query=answer_query, context=context, llm=answer_llm
                ),
                rate_limit_backoff,
                label=f"answer LLM for {row['question_id']}",
            )
        else:
            response = "I cannot answer because no Wikipedia articles were retrieved."
        score = call_with_rate_limit_backoff(
            lambda: correctness_metric.score(
                llm=ragas_judge,
                response=response,
                grading_notes=row["grading_notes"],
            ),
            rate_limit_backoff,
            label=f"RAGAS judge for {row['question_id']}",
        )
        return {
            **row,
            "experiment_name": experiment_name,
            "evaluation_mode": "retrieved_full_article_context",
            "context_source": CONTEXT_SOURCE,
            "decompose": True,
            "reasoning_used": bool(reasoning),
            "answer_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL,
            "retriever_kind": "vector_multistep",
            "retriever_label": retriever.label,
            "retrieval_top_k": RETRIEVAL_TOP_K,
            "required_articles": "; ".join(required_articles),
            "retrieved_articles": "; ".join(retrieved_articles),
            "matched_articles": "; ".join(matched),
            "missing_articles": "; ".join(missing),
            "article_recall": article_recall,
            "retrieved_chunk_ids": "; ".join(hit[0] for hit in hits),
            "retrieved_chunk_count": len(hits),
            "retrieved_article_count": len(retrieved_articles),
            "response": response,
            "score": score.value,
            "source_count": len(required_articles),
            "context_characters": len(context),
        }

    return run_advanced_case


# %%
async def main() -> None:
    args = parse_args()
    gt_path = args.gt_set.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    experiment_name = args.experiment_name.strip()
    rate_limit_backoff = RateLimitBackoff.from_args(args)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_ragas_dataset(
        gt_path=gt_path,
        output_dir=output_dir,
        dataset_suffix="advanced_inputs",
        limit=None,
    )

    print("Loading retrieval resources...")
    chunks = load_wikipedia_chunks()
    db = build_or_load_db(chroma_db_name=CHROMA_DB_NAME, chunks=chunks)
    article_text_store = load_context_store(CONTEXT_SOURCE)
    retriever = MultiStepRetriever(
        db=db,  # reuse the already-loaded Chroma index (no reload)
        chroma_db_name=CHROMA_DB_NAME,
        top_k=RETRIEVAL_TOP_K,
        label=f"vector_k{RETRIEVAL_TOP_K}_decomposed",
    )

    answer_llm = make_llm()
    ragas_judge = make_judge()
    advanced_experiment = build_advanced_experiment(
        retriever,
        article_text_store,
        answer_llm,
        ragas_judge,
        rate_limit_backoff,
        experiment_name,
    )

    print(
        f"Running ADVANCED (query decomposition) on {len(dataset)} questions from "
        f"{gt_path} (context_source={CONTEXT_SOURCE}, "
        f"experiment_name={experiment_name or 'auto-derived'}, "
        f"rate_limit_retries={rate_limit_backoff.retries})..."
    )
    results = await advanced_experiment.arun(dataset)

    print_score_summary(results)
    for row in results:
        print(
            f"  {row['question_id']}: recall={row['article_recall']:.2f} "
            f"verdict={row['score'].upper()} missing={row['missing_articles'] or '(none)'}"
        )
    save_results(results, output_dir)


if __name__ == "__main__":
    asyncio.run(main())


# %% [markdown]
# ## Deliverable reminder (the worksheet, not this code)
# Fill the Checkpoint 4.1 worksheet using evidence from this run vs the baseline:
# 1. **Failure diagnosis** (from your 3.1 eval) — why single-pass under-recalls
#    multi-source questions.
# 2. **Data redesign** — the markdown + JSON-sidecar schema (articles, categories, links).
# 3. **Advanced retrieval implemented** — this decomposition retriever (code + log evidence).
# 4. **Comparative evaluation** — baseline vs advanced on the SAME GT set and a similar
#    number of retrieved documents.
# 5. **Analysis & reflection** — where it helped (multi-source recall), the cost/latency
#    of the extra decomposition LLM call, and remaining limitations.

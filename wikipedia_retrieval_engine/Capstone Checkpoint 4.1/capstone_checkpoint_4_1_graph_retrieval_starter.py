r"""Capstone Checkpoint 4.1 — Advanced Retrieval (graph augmentation).

Runs the GRAPH retriever (Lab 4.2 pattern) on the real Wikipedia system and scores it
with the SAME RAGAS harness as the baseline and the decomposition run, so all three are
directly comparable. Vector search finds seed articles; we then follow graph edges
(direct link / shared entity / shared category over the sidecars) to pull in adjacent
articles single-pass retrieval missed. Shared plumbing lives in ``utils/ragas_eval.py``;
the graph + retriever are ``retrievers/graph.py``.

Only the RETRIEVER changes vs the baseline: same Chroma index, same markdown context,
same GT set, same judge — so the comparison isolates graph augmentation.

Run (from ``wikipedia_retrieval_engine/``):
    python "Capstone Checkpoint 4.1/capstone_checkpoint_4_1_graph_retrieval_starter.py" \
        --gt-set "GT/wikipedia_GT.csv" \
        --output-dir "Capstone Checkpoint 4.1/ragas_advanced" \
        --experiment-name vs_k7_markdown_graph
"""

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

from langchain_openai import ChatOpenAI
from ragas import experiment

from retrievers import (
    build_or_load_db,
    load_retrieved_article_texts,
    load_wikipedia_chunks,
)
from retrievers.graph import GraphParams, GraphRetriever, build_or_load_graph
from retrievers.llm import answer as answer_from_context
from utils.ragas_eval import (
    CONTEXT_SOURCE,
    JUDGE_MODEL,
    LLM_MODEL,
    OPENROUTER_BASE_URL,
    RateLimitBackoff,
    TEMPERATURE,
    build_ragas_dataset,
    call_with_rate_limit_backoff,
    check_api_key,
    correctness_metric,
    load_context_store,
    make_judge,
    parse_args,
    parse_source_articles,
    print_score_summary,
    save_results,
)

# %%
# Retrieval config — held identical to the baseline so the graph is the ONLY change.
CHROMA_DB_NAME = "wikipedia_chars1600_overlap200"
SEED_TOP_K = 7  # vector seeds (same k as the baseline); graph adds neighbors on top
# Query-time graph knobs (tunable with no rebuild). max_neighbors is the recall/noise dial.
GRAPH_PARAMS = GraphParams(
    max_bucket_size=50,   # drop giant/boilerplate buckets (ISBN, "Living people", ...)
    min_shared=1,         # min shared attributes for a co-occurrence edge
    max_neighbors=5,      # total graph-neighbors added per query
    max_neighbors_per_seed=3,
)

# Context strategy — keep the base-vs-graph comparison clean AND fit the budget.
# SEED articles are always included IN FULL (identical to the baseline's context). How each
# GRAPH NEIGHBOR contributes is chosen by the knobs below (first match wins):
#   1. NEIGHBOR_SECTIONS_K (int)  -> two-stage retrieval: add the neighbor's top-k SECTIONS
#      ranked by vector similarity to the QUESTION (graph finds the article; vector search
#      finds the relevant section). Targeted + small — the smart default.
#   2. NEIGHBOR_SNIPPET_CHARS (int) -> add a fixed lead slice of the neighbor (arbitrary
#      chars; may miss the answer-bearing section, e.g. GT16 scored PARTIAL this way).
#   3. both None -> add the whole neighbor article (only fits when seeds are small).
# Whole Wikipedia articles are large (India/US/lists are 25-100k tokens; seeds alone can be
# ~116k), so option 3 overflows the model window and the key's per-request credit budget.
# Sections keep the added text tiny (k chunks x ~1600 chars) while being MORE relevant.
# ANSWER_MAX_TOKENS caps answer output (a synthesized answer needs nowhere near the model's
# ~65k default) to fix the 402 credit error; None omits max_tokens (provider default).
NEIGHBOR_SECTIONS_K = None
NEIGHBOR_SNIPPET_CHARS = 12000
ANSWER_MAX_TOKENS = None

_CONTEXT_SEP = "\n\n" + "=" * 80 + "\n\n"


def _lead_snippet(text: str, max_chars: int) -> str:
    """A lead slice of `text` (first max_chars, on a word boundary)."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"


def neighbor_body(article, retriever, query: str) -> str:
    """Text one graph neighbor contributes, per the active mode (see knobs above):
    top-k query-relevant sections, a lead slice, or the full article."""
    if NEIGHBOR_SECTIONS_K is not None:
        sections = retriever.article_sections(query, article.source, NEIGHBOR_SECTIONS_K)
        body = "\n\n".join(f"[{label}]\n{text}" if label else text for label, text in sections)
        return body or _lead_snippet(article.text, 3000)  # fallback if no chunk matched
    if NEIGHBOR_SNIPPET_CHARS is not None:
        return _lead_snippet(article.text, NEIGHBOR_SNIPPET_CHARS)
    return article.text.strip()


def _neighbor_heading() -> str:
    if NEIGHBOR_SECTIONS_K is not None:
        return "Related articles surfaced via the graph (top matching sections):\n\n"
    if NEIGHBOR_SNIPPET_CHARS is None:
        return "Related articles surfaced via the graph (full text):\n\n"
    return "Related articles surfaced via the graph (lead extracts):\n\n"


def assemble_graph_context(seed_articles, neighbor_blocks) -> str:
    """Full seed articles + a labeled block per graph neighbor.

    ``neighbor_blocks`` is a list of ``(source, body_text)`` so the body can be sections,
    a lead slice, or full text — assembly is mode-agnostic."""
    seed_block = _CONTEXT_SEP.join(a.text.strip() for a in seed_articles)
    if not neighbor_blocks:
        return seed_block
    block = "\n\n".join(f"[graph neighbor: {src}]\n{body}" for src, body in neighbor_blocks)
    return seed_block + _CONTEXT_SEP + _neighbor_heading() + block


# %%
def build_graph_experiment(
    retriever,
    article_text_store,
    answer_llm,
    ragas_judge,
    rate_limit_backoff: RateLimitBackoff,
    experiment_name: str = "",
):
    """RAGAS experiment: vector seeds + graph neighbors -> full markdown context -> answer -> judge."""

    @experiment()
    async def run_graph_case(row: dict) -> dict:
        # Seed with vector search, then expand along graph edges.
        verbose = retriever.retrieve_verbose(row["question"])
        neighbors = verbose["neighbors"]  # (article, score, reasons)

        # Seed articles IN FULL (identical to the baseline); neighbors as snippets or full text.
        seed_texts = load_retrieved_article_texts(
            list(verbose["seed_hits"]), article_text_store
        )
        seed_sources = {a.source for a in seed_texts}
        neighbor_texts = [
            article_text_store.load(article)
            for article, _score, _reasons in neighbors
            if article not in seed_sources and article_text_store.has_article(article)
        ]
        neighbor_blocks = [
            (a.source, neighbor_body(a, retriever, row["question"])) for a in neighbor_texts
        ]
        context = assemble_graph_context(seed_texts, neighbor_blocks)

        required_articles = [
            article.removesuffix(".txt")
            for article in parse_source_articles(row["source_articles"])
        ]
        retrieved_article_texts = seed_texts + neighbor_texts
        retrieved_articles = [article.source for article in retrieved_article_texts]
        retrieved_set = set(retrieved_articles)
        matched = [a for a in required_articles if a in retrieved_set]
        missing = [a for a in required_articles if a not in retrieved_set]
        article_recall = len(matched) / len(required_articles) if required_articles else 1.0

        if context.strip():
            response = call_with_rate_limit_backoff(
                lambda: answer_from_context(
                    query=row["question"], context=context, llm=answer_llm
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

        neighbor_labels = [
            f"{article}({'|'.join(reasons[:2])})" for article, _s, reasons in neighbors
        ]
        return {
            **row,
            "experiment_name": experiment_name,
            "evaluation_mode": "retrieved_full_article_context",
            "context_source": CONTEXT_SOURCE,
            "decompose": False,
            "reasoning_used": False,
            "answer_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL,
            "retriever_kind": "vector_graph",
            "retriever_label": retriever.label,
            "retrieval_top_k": SEED_TOP_K,
            "graph_max_neighbors": GRAPH_PARAMS.max_neighbors,
            "graph_min_shared": GRAPH_PARAMS.min_shared,
            "graph_max_bucket_size": GRAPH_PARAMS.max_bucket_size,
            "seed_article_count": len(seed_texts),
            "graph_neighbors_added": len(neighbor_texts),
            "graph_neighbor_labels": "; ".join(neighbor_labels),
            "neighbor_sections_k": NEIGHBOR_SECTIONS_K,
            "neighbor_snippet_chars": NEIGHBOR_SNIPPET_CHARS,
            "required_articles": "; ".join(required_articles),
            "retrieved_articles": "; ".join(retrieved_articles),
            "matched_articles": "; ".join(matched),
            "missing_articles": "; ".join(missing),
            "article_recall": article_recall,
            "retrieved_chunk_ids": "; ".join(
                [h[0] for h in verbose["seed_hits"]] + [a.source for a in neighbor_texts]
            ),
            "retrieved_chunk_count": len(seed_texts) + len(neighbor_texts),
            "retrieved_article_count": len(retrieved_articles),
            "response": response,
            "score": score.value,
            "source_count": len(required_articles),
            "context_characters": len(context),
        }

    return run_graph_case


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
        dataset_suffix="graph_inputs",
        limit=None,
    )

    print("Loading retrieval resources...")
    chunks = load_wikipedia_chunks()
    db = build_or_load_db(chroma_db_name=CHROMA_DB_NAME, chunks=chunks)
    article_text_store = load_context_store(CONTEXT_SOURCE)
    graph = build_or_load_graph(article_text_store)  # cached; rebuilds only if corpus changed
    retriever = GraphRetriever(
        db=db,
        graph=graph,
        params=GRAPH_PARAMS,
        top_k=SEED_TOP_K,
        label=f"vector_k{SEED_TOP_K}_graph_n{GRAPH_PARAMS.max_neighbors}",
    )

    # Answer LLM. Same model/temperature as the baseline. Pass max_tokens only when
    # ANSWER_MAX_TOKENS is an int (caps output / 402 credit reservation); None omits it.
    answer_kwargs = {}
    if ANSWER_MAX_TOKENS is not None:
        answer_kwargs["max_tokens"] = ANSWER_MAX_TOKENS
    answer_llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        api_key=check_api_key(),
        base_url=OPENROUTER_BASE_URL,
        **answer_kwargs,
    )
    ragas_judge = make_judge()
    graph_experiment = build_graph_experiment(
        retriever,
        article_text_store,
        answer_llm,
        ragas_judge,
        rate_limit_backoff,
        experiment_name,
    )

    print(
        f"Running GRAPH augmentation on {len(dataset)} questions from {gt_path} "
        f"(context_source={CONTEXT_SOURCE}, seed_k={SEED_TOP_K}, "
        f"max_neighbors={GRAPH_PARAMS.max_neighbors}, "
        f"experiment_name={experiment_name or 'auto-derived'}, "
        f"rate_limit_retries={rate_limit_backoff.retries})..."
    )
    results = await graph_experiment.arun(dataset)

    print_score_summary(results)
    for row in results:
        print(
            f"  {row['question_id']}: recall={row['article_recall']:.2f} "
            f"verdict={row['score'].upper()} +nbrs={row['graph_neighbors_added']} "
            f"missing={row['missing_articles'] or '(none)'}"
        )
    save_results(results, output_dir)


if __name__ == "__main__":
    asyncio.run(main())

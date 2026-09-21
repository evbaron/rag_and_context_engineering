r"""Checkpoint 5.1 retrieval-only agent benchmark over the Wikipedia GT set.

This remains the course-facing harness. Production state, nodes, routing, retrieval,
and logging live in ``wiki_agents`` and ``retrievers``.

The benchmark intentionally disables table requests. Its bounded workflow is:

    section-aware vector search
        -> evidence assessment
        -> graph expansion from selected VS articles
        -> section retrieval inside graph-neighbor articles
        -> evidence assessment
        -> targeted multi-step section retrieval
        -> final evidence assessment

Article names are routing handles only. The answer model receives accumulated section
``EvidenceItem`` content—never full articles and never fixed leading-character slices.

Run from ``wikipedia_retrieval_engine/``:

    python "Capstone Checkpoint 5.1/capstone_checkpoint_5_1_agent_rag_starter.py" \
        --gt-set "GT/wikipedia_GT.csv" \
        --output-dir "Capstone Checkpoint 5.1/ragas_retrieval_only" \
        --experiment-name agentic_sections_no_tables

Use ``--limit 2`` for a smoke test or repeat ``--question-id GT01`` to select IDs.
"""

# %%
from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    _HERE = Path.cwd()
_ENGINE = _HERE.parent
_PACKAGE_ROOT = _ENGINE.parent
for path in (_PACKAGE_ROOT, _ENGINE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ragas import experiment

from wikipedia_retrieval_engine.retrievers import DEFAULT_SECTION_CHROMA_DB_NAME
from wikipedia_retrieval_engine.retrievers.corpus import build_or_load_markdown_store
from wikipedia_retrieval_engine.retrievers.graph import GraphParams, build_or_load_graph
from wikipedia_retrieval_engine.retrievers.llm import answer as answer_from_context
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.utils.ragas_eval import (
    JUDGE_MODEL,
    LLM_MODEL,
    RateLimitBackoff,
    build_ragas_dataset,
    call_with_rate_limit_backoff,
    correctness_metric,
    make_judge,
    make_llm,
    parse_args,
    parse_source_articles,
    print_score_summary,
    save_results,
)
from wikipedia_retrieval_engine.wiki_agents.agent_graph import (
    build_retrieval_benchmark_graph,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    EvidenceItem,
    initial_agent_state,
)
from wikipedia_retrieval_engine.wiki_agents.run_logging import AgentRunLogger


# %%
# These controls define the benchmark described in the Checkpoint 5.1 report.
# Retriever strategy per stage. "multistep_entity" decomposes the question into one
# clean full-name query per named/implied entity at the initial stage, so entities a
# blunt query buries (e.g. GT16's Barack Obama) are retrieved at rank 1; graph
# expansion is the repeated escalation. Set INITIAL_RETRIEVER = "vector" to reproduce
# the plain-vector baseline for A/B, or "multistep" for sub-topic decomposition.
INITIAL_RETRIEVER = "multistep_entity"  # "vector" | "multistep" | "multistep_entity"
REPEATED_RETRIEVERS = ("graph_seeded",)  # escalation stages after the initial one
INITIAL_SUBQUERY_TOP_K = 2
INITIAL_MAX_CANDIDATES = 8
# GT questions designate up to 4 articles (e.g. GT14: Chazelle + Emma Stone +
# La La Land + 89th Academy Awards). A cap of 3 makes full initial-stage recall
# impossible on those, so seed with 4 unique articles.
INITIAL_ARTICLE_TOP_K = 4
# Each selected article is deepened with this many focused sections on the initial
# pass. Keeping only the single top-ranked chunk per article tends to grab the
# prose preamble of a table article rather than the row-bearing section, so the
# answer content can be absent even at article-recall = 1.0.
SECTIONS_PER_SELECTED_ARTICLE = 3
SECTIONS_PER_GRAPH_NEIGHBOR = 2
# Global cap on graph-neighbor sections kept per expansion, ranked by match
# distance across all neighbors. Prevents adjacent-but-wrong neighbors (sibling
# award pages, medalist lists) from each contributing distractor chunks.
MAX_GRAPH_SECTIONS = 4
MULTISTEP_HITS_PER_REQUEST = 6
GRAPH_PARAMS = GraphParams(
    max_bucket_size=50,
    min_shared=1,
    max_neighbors=5,
    max_neighbors_per_seed=3,
)
RECURSION_LIMIT = 12

_CONTEXT_SEPARATOR = "\n\n" + "=" * 80 + "\n\n"


def format_section_evidence(evidence: list[EvidenceItem]) -> str:
    """Format exactly the accumulated section evidence sent to the answer model."""

    blocks: list[str] = []
    for item in evidence:
        section = " > ".join(item.section_path) or item.title or "(section unknown)"
        stage = item.metadata.get("retrieval_stage", "unknown")
        blocks.append(
            f"[Evidence ID: {item.evidence_id}]\n"
            f"Source article: {item.source_article}\n"
            f"Section: {section}\n"
            f"Retrieval stage: {stage}\n"
            f"{item.content.strip()}"
        )
    return _CONTEXT_SEPARATOR.join(blocks)


def _required_articles(source_cell: str) -> list[str]:
    return [
        article.removesuffix(".txt")
        for article in parse_source_articles(source_cell)
    ]


def _stage_name(retrieval_attempts: int) -> str:
    if retrieval_attempts == 1:
        return f"{INITIAL_RETRIEVER}_initial"
    return {
        2: "graph_seeded_sections",
        3: "targeted_multistep_sections",
    }.get(retrieval_attempts, f"retrieval_attempt_{retrieval_attempts}")


def build_agentic_experiment(
    agent_graph,
    answer_llm,
    ragas_judge,
    rate_limit_backoff: RateLimitBackoff,
    experiment_name: str,
):
    """Create the RAGAS case function for the retrieval-only LangGraph."""

    @experiment()
    async def run_agentic_case(row: dict) -> dict:
        state: AgentState = call_with_rate_limit_backoff(
            lambda: agent_graph.invoke(
                initial_agent_state(row["question"]),
                config={"recursion_limit": RECURSION_LIMIT},
            ),
            rate_limit_backoff,
            label=f"agent graph for {row['question_id']}",
        )

        evidence = state.get("evidence", [])
        context = format_section_evidence(evidence)
        if context.strip():
            response = call_with_rate_limit_backoff(
                lambda: answer_from_context(
                    query=row["question"],
                    context=context,
                    llm=answer_llm,
                ),
                rate_limit_backoff,
                label=f"answer LLM for {row['question_id']}",
            )
        else:
            response = "I cannot answer because no relevant Wikipedia sections were retrieved."

        score = call_with_rate_limit_backoff(
            lambda: correctness_metric.score(
                llm=ragas_judge,
                response=response,
                grading_notes=row["grading_notes"],
            ),
            rate_limit_backoff,
            label=f"RAGAS judge for {row['question_id']}",
        )

        required_articles = _required_articles(row["source_articles"])
        retrieved_articles = list(
            dict.fromkeys(item.source_article for item in evidence)
        )
        retrieved_set = set(retrieved_articles)
        matched = [article for article in required_articles if article in retrieved_set]
        missing = [article for article in required_articles if article not in retrieved_set]
        article_recall = (
            len(matched) / len(required_articles)
            if required_articles
            else 1.0
        )

        attempts = state.get("retrieval_attempts", 0)
        assessment = state["assessment"]
        history = state.get("assessment_history", [])
        route_trace = [
            "ready_to_answer" if item.ready_to_answer else "need_more_evidence"
            for item in history
        ]
        stage_counts: dict[str, int] = {}
        for item in evidence:
            stage = str(item.metadata.get("retrieval_stage", "unknown"))
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        # Phase 2 signal: which kept articles flagged that answering needs a table.
        reviews = state.get("article_reviews", [])
        tables_flagged = any(r.needs_table_reader for r in reviews if r.relevant)
        flagged_tables = sorted(
            {t for r in reviews if r.relevant for t in (r.relevant_table_names or [])}
        )

        return {
            **row,
            "experiment_name": experiment_name,
            "evaluation_mode": "agentic_section_evidence_no_tables",
            "answer_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL,
            "retriever_kind": "vs_graph_multistep_sections",
            "initial_retriever": INITIAL_RETRIEVER,
            "repeated_retrievers": "->".join(REPEATED_RETRIEVERS),
            "initial_article_top_k": INITIAL_ARTICLE_TOP_K,
            "sections_per_selected_article": SECTIONS_PER_SELECTED_ARTICLE,
            "graph_max_neighbors": GRAPH_PARAMS.max_neighbors,
            "sections_per_graph_neighbor": SECTIONS_PER_GRAPH_NEIGHBOR,
            "max_graph_sections": MAX_GRAPH_SECTIONS,
            "multistep_hits_per_request": MULTISTEP_HITS_PER_REQUEST,
            "retrieval_attempts": attempts,
            "terminal_stage": _stage_name(attempts),
            "evidence_ready": assessment.ready_to_answer,
            "route_trace": " -> ".join(route_trace),
            "assessment_explanation": assessment.explanation,
            "evidence_stage_counts": "; ".join(
                f"{stage}={count}" for stage, count in sorted(stage_counts.items())
            ),
            "tables_flagged": tables_flagged,
            "flagged_tables": "; ".join(flagged_tables),
            "required_articles": "; ".join(required_articles),
            "retrieved_articles": "; ".join(retrieved_articles),
            "retrieved_article_count": len(retrieved_articles),
            "matched_articles": "; ".join(matched),
            "missing_articles": "; ".join(missing),
            "article_recall": article_recall,
            "evidence_ids": "; ".join(item.evidence_id for item in evidence),
            "evidence_count": len(evidence),
            "context_characters": len(context),
            "response": response,
            "score": score.value,
            "source_count": len(required_articles),
        }

    return run_agentic_case


# %%
async def main() -> None:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1.")

    gt_path = args.gt_set.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    experiment_name = args.experiment_name.strip() or "agentic_sections_no_tables"
    rate_limit_backoff = RateLimitBackoff.from_args(args)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_ragas_dataset(
        gt_path=gt_path,
        output_dir=output_dir,
        dataset_suffix="agentic_section_inputs",
        limit=args.limit,
        question_ids=args.question_ids,
    )

    print("Loading section-aware retrieval resources...")
    retriever = VectorRetriever.for_section_index(
        top_k=INITIAL_ARTICLE_TOP_K,
        label=f"section_vector_articles_k{INITIAL_ARTICLE_TOP_K}",
    )
    agent_llm = make_llm()
    multistep_retriever = MultiStepRetriever(
        llm=agent_llm,
        chroma_db_name=DEFAULT_SECTION_CHROMA_DB_NAME,
        top_k=MULTISTEP_HITS_PER_REQUEST,
        label="targeted_multistep_sections",
    )

    # Markdown sidecars load the article relationship graph only. Full article
    # markdown is never assembled into answer context.
    relationship_store = build_or_load_markdown_store()
    wiki_graph = build_or_load_graph(relationship_store)
    run_logger = AgentRunLogger()
    agent_graph = build_retrieval_benchmark_graph(
        retriever,
        multistep_retriever,
        wiki_graph,
        agent_llm,
        run_logger,
        markdown_store=relationship_store,
        initial_retriever=INITIAL_RETRIEVER,
        repeated_retrievers=REPEATED_RETRIEVERS,
        initial_article_top_k=INITIAL_ARTICLE_TOP_K,
        initial_subquery_top_k=INITIAL_SUBQUERY_TOP_K,
        initial_max_candidates=INITIAL_MAX_CANDIDATES,
        sections_per_selected_article=SECTIONS_PER_SELECTED_ARTICLE,
        graph_params=GRAPH_PARAMS,
        sections_per_neighbor=SECTIONS_PER_GRAPH_NEIGHBOR,
        max_graph_sections=MAX_GRAPH_SECTIONS,
        multistep_hits_per_request=MULTISTEP_HITS_PER_REQUEST,
    )

    ragas_judge = make_judge()
    agentic_experiment = build_agentic_experiment(
        agent_graph,
        agent_llm,
        ragas_judge,
        rate_limit_backoff,
        experiment_name,
    )

    print(
        f"Running retrieval-only agent on {len(dataset)} questions from {gt_path}\n"
        f"  initial retriever={INITIAL_RETRIEVER}\n"
        f"  repeated retrievers={' -> '.join(REPEATED_RETRIEVERS)}\n"
        f"  initial article k={INITIAL_ARTICLE_TOP_K}\n"
        f"  sections per selected article={SECTIONS_PER_SELECTED_ARTICLE}\n"
        f"  graph neighbors={GRAPH_PARAMS.max_neighbors}\n"
        f"  sections per graph neighbor={SECTIONS_PER_GRAPH_NEIGHBOR}\n"
        f"  max graph sections kept={MAX_GRAPH_SECTIONS}\n"
        f"  multistep hits per request={MULTISTEP_HITS_PER_REQUEST}\n"
        f"  table requests=disabled\n"
        f"  evidence logs={run_logger.run_directory}"
    )
    results = await agentic_experiment.arun(dataset)

    print_score_summary(results)
    for row in results:
        print(
            f"  {row['question_id']}: stage={row['terminal_stage']} "
            f"ready={row['evidence_ready']} recall={row['article_recall']:.2f} "
            f"verdict={row['score'].upper()} "
            f"missing={row['missing_articles'] or '(none)'}"
        )
    save_results(results, output_dir)


if __name__ == "__main__":
    asyncio.run(main())

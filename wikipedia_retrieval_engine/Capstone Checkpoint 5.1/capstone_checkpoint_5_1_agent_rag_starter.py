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
INITIAL_ARTICLE_TOP_K = 3
SECTIONS_PER_GRAPH_NEIGHBOR = 2
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
    return {
        1: "vector_sections",
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

        return {
            **row,
            "experiment_name": experiment_name,
            "evaluation_mode": "agentic_section_evidence_no_tables",
            "answer_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL,
            "retriever_kind": "vs_graph_multistep_sections",
            "initial_article_top_k": INITIAL_ARTICLE_TOP_K,
            "graph_max_neighbors": GRAPH_PARAMS.max_neighbors,
            "sections_per_graph_neighbor": SECTIONS_PER_GRAPH_NEIGHBOR,
            "multistep_hits_per_request": MULTISTEP_HITS_PER_REQUEST,
            "retrieval_attempts": attempts,
            "terminal_stage": _stage_name(attempts),
            "evidence_ready": assessment.ready_to_answer,
            "route_trace": " -> ".join(route_trace),
            "assessment_explanation": assessment.explanation,
            "evidence_stage_counts": "; ".join(
                f"{stage}={count}" for stage, count in sorted(stage_counts.items())
            ),
            "required_articles": "; ".join(required_articles),
            "retrieved_articles": "; ".join(retrieved_articles),
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
        graph_params=GRAPH_PARAMS,
        sections_per_neighbor=SECTIONS_PER_GRAPH_NEIGHBOR,
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
        f"  initial article k={INITIAL_ARTICLE_TOP_K}\n"
        f"  graph neighbors={GRAPH_PARAMS.max_neighbors}\n"
        f"  sections per graph neighbor={SECTIONS_PER_GRAPH_NEIGHBOR}\n"
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

"""Run the currently implemented Checkpoint 5.1 graph milestone."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from wikipedia_retrieval_engine.retrievers.llm import make_llm
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agent_graph import (
    build_evidence_intake_graph,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    initial_agent_state,
)
from wikipedia_retrieval_engine.wiki_agents.retrieval_nodes import (
    route_after_evidence_assessment,
)
from wikipedia_retrieval_engine.wiki_agents.run_logging import AgentRunLogger


def run_current_milestone(question: str) -> tuple[AgentState, AgentRunLogger]:
    """Run retrieval through assessment and return state plus its run logger."""

    retriever = VectorRetriever.for_section_index()
    llm = make_llm()
    logger = AgentRunLogger()
    graph = build_evidence_intake_graph(retriever, llm, logger)
    result = graph.invoke(initial_agent_state(question))
    return result, logger


def print_milestone_summary(state: AgentState, logger: AgentRunLogger) -> None:
    """Print a compact summary; the complete state remains in the evidence log."""

    assessment = state["assessment"]
    route = route_after_evidence_assessment(state)

    print("\nCURRENT CHECKPOINT 5.1 MILESTONE")
    print("=" * 72)
    print(f"Question: {state['question']}")
    print(f"Retrieval attempts: {state.get('retrieval_attempts', 0)}")

    print("\nArticle candidates:")
    for candidate in state.get("article_candidates", []):
        section = " > ".join(candidate.section_path) or "(section unavailable)"
        print(
            f"  {candidate.rank}. {candidate.source_article}"
            f" | section={section} | distance={candidate.raw_score:.6f}"
        )

    print("\nArticle review:")
    print(f"  selected={state.get('selected_articles', [])}")
    print(f"  rejected={state.get('rejected_articles', [])}")

    print("\nInitial evidence:")
    for item in state.get("evidence", []):
        section = " > ".join(item.section_path) or item.title or "(unknown)"
        print(f"  - {item.evidence_id} | {section}")

    print("\nEvidence assessment:")
    print(f"  route={route}")
    print(f"  explanation={assessment.explanation}")
    print(f"  supported={assessment.supported_requirements}")
    print(f"  missing={assessment.missing_requirements}")
    print(f"  retrieval_requests={len(assessment.retrieval_requests)}")
    print(f"  table_requests={len(assessment.table_requests)}")

    log_files = sorted(logger.run_directory.glob("*.evidence.json"))
    print(f"\nRun log directory: {logger.run_directory}")
    if log_files:
        print(f"Evidence file: {log_files[-1]}")
    print("=" * 72)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Checkpoint 5.1 graph through evidence assessment. "
            "Answer generation and conditional branches are not implemented yet."
        )
    )
    parser.add_argument("question", help="Wikipedia question to evaluate")
    args = parser.parse_args(argv)

    state, logger = run_current_milestone(args.question)
    print_milestone_summary(state, logger)


if __name__ == "__main__":
    main()

"""LangGraph assembly for the Checkpoint 5.1 agent."""

from __future__ import annotations

from functools import partial

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agentic_models import AgentState
from wikipedia_retrieval_engine.wiki_agents.retrieval_nodes import (
    assess_evidence,
    collect_initial_evidence,
    retrieve_initial_articles,
    review_article_candidates,
)
from wikipedia_retrieval_engine.wiki_agents.run_logging import (
    AgentRunLogger,
    write_question_log,
)


def build_evidence_intake_graph(
    retriever: VectorRetriever,
    llm: BaseChatModel,
    run_logger: AgentRunLogger | None = None,
) -> CompiledStateGraph:
    """Compile the implemented retrieval, review, and assessment prefix.

    The graph ends after evidence assessment until the three real branch nodes
    (answering, table reading, and follow-up retrieval) are implemented. It does
    not use placeholder branch behavior that could be mistaken for working logic.
    """

    graph = StateGraph(AgentState)
    logger = run_logger or AgentRunLogger()

    graph.add_node(
        "retrieve_initial_articles",
        partial(retrieve_initial_articles, retriever=retriever),
    )
    graph.add_node(
        "review_article_candidates",
        partial(review_article_candidates, llm=llm),
    )
    graph.add_node("collect_initial_evidence", collect_initial_evidence)
    graph.add_node(
        "assess_evidence",
        partial(assess_evidence, llm=llm),
    )
    graph.add_node(
        "write_question_log",
        partial(write_question_log, logger=logger),
    )

    graph.add_edge(START, "retrieve_initial_articles")
    graph.add_edge("retrieve_initial_articles", "review_article_candidates")
    graph.add_edge("review_article_candidates", "collect_initial_evidence")
    graph.add_edge("collect_initial_evidence", "assess_evidence")
    graph.add_edge("assess_evidence", "write_question_log")
    graph.add_edge("write_question_log", END)

    return graph.compile(name="checkpoint_5_1_evidence_intake")

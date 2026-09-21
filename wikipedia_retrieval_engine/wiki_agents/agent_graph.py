"""LangGraph assembly for the Checkpoint 5.1 agent."""

from __future__ import annotations

from functools import partial

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from wikipedia_retrieval_engine.retrievers.graph import GraphParams, WikiGraph
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    retrieval_attempt_count,
)
from wikipedia_retrieval_engine.wiki_agents.retrieval_nodes import (
    assess_evidence,
    collect_initial_evidence,
    retrieve_graph_seeded_evidence,
    retrieve_initial_articles,
    retrieve_multistep_evidence,
    retrieve_selected_article_sections,
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


def route_retrieval_benchmark(state: AgentState) -> str:
    """Choose the next bounded retrieval stage, or finish with current evidence."""

    assessment = state.get("assessment")
    if assessment is None:
        raise ValueError("Agent state does not contain an evidence assessment.")
    if assessment.ready_to_answer:
        return "finish"

    attempts = retrieval_attempt_count(state)
    if attempts == 1:
        return "graph_seeded_sections"
    if attempts == 2:
        return "multistep_sections"
    return "finish"


def build_retrieval_benchmark_graph(
    retriever: VectorRetriever,
    multistep_retriever: MultiStepRetriever,
    wiki_graph: WikiGraph,
    llm: BaseChatModel,
    run_logger: AgentRunLogger | None = None,
    *,
    initial_article_top_k: int = 3,
    sections_per_selected_article: int = 3,
    graph_params: GraphParams | None = None,
    sections_per_neighbor: int = 2,
    max_graph_sections: int = 6,
    multistep_hits_per_request: int = 6,
) -> CompiledStateGraph:
    """Compile the retrieval-only VS → graph → multistep benchmark graph.

    Article names route retrieval. Only section chunks are added to evidence and
    therefore only section evidence reaches assessment and answering.

    The initial stage seeds ``initial_article_top_k`` unique articles and then
    deepens each selected article with ``sections_per_selected_article`` focused
    sections, so the chunk that actually carries the answer (not just the highest
    ranked prose chunk) is present before the first assessment.
    """

    workflow = StateGraph(AgentState)
    logger = run_logger or AgentRunLogger()
    params = graph_params or GraphParams()

    workflow.add_node(
        "retrieve_initial_articles",
        partial(
            retrieve_initial_articles,
            retriever=retriever,
            top_k=initial_article_top_k,
        ),
    )
    workflow.add_node(
        "review_article_candidates",
        partial(review_article_candidates, llm=llm),
    )
    workflow.add_node("collect_initial_evidence", collect_initial_evidence)
    workflow.add_node(
        "deepen_selected_article_sections",
        partial(
            retrieve_selected_article_sections,
            retriever=retriever,
            sections_per_article=sections_per_selected_article,
        ),
    )
    workflow.add_node(
        "assess_evidence",
        partial(
            assess_evidence,
            llm=llm,
            allow_table_requests=False,
        ),
    )
    workflow.add_node(
        "retrieve_graph_seeded_sections",
        partial(
            retrieve_graph_seeded_evidence,
            retriever=retriever,
            graph=wiki_graph,
            graph_params=params,
            sections_per_neighbor=sections_per_neighbor,
            max_graph_sections=max_graph_sections,
        ),
    )
    workflow.add_node(
        "retrieve_multistep_sections",
        partial(
            retrieve_multistep_evidence,
            retriever=multistep_retriever,
            hits_per_request=multistep_hits_per_request,
        ),
    )
    workflow.add_node(
        "write_question_log",
        partial(write_question_log, logger=logger),
    )

    workflow.add_edge(START, "retrieve_initial_articles")
    workflow.add_edge("retrieve_initial_articles", "review_article_candidates")
    workflow.add_edge("review_article_candidates", "collect_initial_evidence")
    workflow.add_edge(
        "collect_initial_evidence", "deepen_selected_article_sections"
    )
    workflow.add_edge("deepen_selected_article_sections", "assess_evidence")
    workflow.add_conditional_edges(
        "assess_evidence",
        route_retrieval_benchmark,
        {
            "graph_seeded_sections": "retrieve_graph_seeded_sections",
            "multistep_sections": "retrieve_multistep_sections",
            "finish": "write_question_log",
        },
    )
    workflow.add_edge("retrieve_graph_seeded_sections", "assess_evidence")
    workflow.add_edge("retrieve_multistep_sections", "assess_evidence")
    workflow.add_edge("write_question_log", END)

    return workflow.compile(name="checkpoint_5_1_retrieval_benchmark")

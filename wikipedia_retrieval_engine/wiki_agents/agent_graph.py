"""LangGraph assembly for the Checkpoint 5.1 agent."""

from __future__ import annotations

from functools import partial
from typing import Callable, Literal, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from wikipedia_retrieval_engine.retrievers.corpus import MarkdownArticleStore
from wikipedia_retrieval_engine.retrievers.graph import GraphParams, WikiGraph
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.utils.wiki_table_store import TableArtifactStore
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    retrieval_attempt_count,
    table_attempt_count,
)
from wikipedia_retrieval_engine.wiki_agents.retrieval_nodes import (
    assess_evidence,
    collect_initial_evidence,
    load_selected_sections,
    load_selected_tables,
    retrieve_broadened_article_sections,
    retrieve_graph_seeded_evidence,
    retrieve_initial_articles,
    retrieve_initial_articles_decomposed,
    retrieve_multistep_evidence,
    retrieve_whole_article_evidence,
    review_and_select_from_toc,
    review_article_candidates,
)
from wikipedia_retrieval_engine.wiki_agents.answer_context import ContextRule, markdown_text_loader
from wikipedia_retrieval_engine.wiki_agents.answer_guard import GroundingPolicy
from wikipedia_retrieval_engine.wiki_agents.answer_nodes import (
    answer_question,
    guard_answer_node,
    sanitize_question,
)
from wikipedia_retrieval_engine.wiki_agents.table_nodes import (
    compute_requested_tables,
)

# Retriever strategy names used by the configurable benchmark graph.
InitialRetriever = Literal["vector", "multistep", "multistep_entity"]
RepeatedRetriever = Literal["graph_seeded", "multistep", "article_broaden", "whole_article"]
_REPEATED_EDGE = {
    "graph_seeded": "retrieve_graph_seeded_sections",
    "multistep": "retrieve_multistep_sections",
    "article_broaden": "retrieve_broadened_sections",
    "whole_article": "retrieve_whole_article_evidence",
}
_RETRIEVAL_STAGE_LABEL = {
    "graph_seeded": "graph_seeded_sections",
    "multistep": "targeted_multistep_sections",
    "article_broaden": "broadened_article_sections",
    "whole_article": "whole_article_evidence",
}
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


def make_retrieval_benchmark_router(
    repeated_retrievers: Sequence[RepeatedRetriever],
    *,
    max_table_rounds: int = 0,
):
    """Build the conditional-edge router for a configured repeated-stage sequence.

    ``repeated_retrievers`` is the ordered list of retrieval stages to try after
    the initial stage, one per unsatisfied assessment. The initial stage sets
    ``retrieval_attempts`` to 1, so the stage index is ``attempts - 1``. When the
    sequence is exhausted the graph finishes with whatever evidence it has.
    Table requests take priority while their independent round budget remains.
    """

    if max_table_rounds < 0:
        raise ValueError("max_table_rounds must be non-negative.")

    def route_retrieval_benchmark(state: AgentState) -> str:
        assessment = state.get("assessment")
        if assessment is None:
            raise ValueError("Agent state does not contain an evidence assessment.")
        if assessment.ready_to_answer:
            return "finish"

        if assessment.table_requests:
            if table_attempt_count(state) < max_table_rounds:
                return "compute_requested_tables"
            if not assessment.retrieval_requests:
                return "finish"

        index = retrieval_attempt_count(state) - 1
        if 0 <= index < len(repeated_retrievers):
            return _REPEATED_EDGE[repeated_retrievers[index]]
        return "finish"

    return route_retrieval_benchmark


def retrieval_stage_name(
    retrieval_attempts: int,
    *,
    initial_retriever: InitialRetriever,
    repeated_retrievers: Sequence[RepeatedRetriever],
) -> str:
    """Describe the actual terminal retrieval stage for experiment metadata."""

    if retrieval_attempts < 1:
        return "retrieval_not_started"
    if retrieval_attempts == 1:
        return f"{initial_retriever}_initial"

    repeated_index = retrieval_attempts - 2
    if 0 <= repeated_index < len(repeated_retrievers):
        return _RETRIEVAL_STAGE_LABEL[repeated_retrievers[repeated_index]]
    return f"retrieval_attempt_{retrieval_attempts}"


def build_retrieval_benchmark_graph(
    retriever: VectorRetriever,
    multistep_retriever: MultiStepRetriever,
    wiki_graph: WikiGraph,
    llm: BaseChatModel,
    run_logger: AgentRunLogger | None = None,
    *,
    markdown_store: MarkdownArticleStore,
    table_store: TableArtifactStore,
    initial_retriever: InitialRetriever = "vector",
    repeated_retrievers: Sequence[RepeatedRetriever] = ("graph_seeded", "multistep"),
    initial_article_top_k: int = 3,
    initial_subquery_top_k: int = 2,
    initial_max_candidates: int = 8,
    sections_per_selected_article: int = 3,
    graph_params: GraphParams | None = None,
    sections_per_neighbor: int = 2,
    max_graph_sections: int = 6,
    multistep_hits_per_request: int = 6,
    broaden_sections_k: int = 8,
    max_table_rounds: int = 2,
    max_table_requests_per_round: int = 6,
    review_llm: BaseChatModel | None = None,
    assess_llm: BaseChatModel | None = None,
    table_llm: BaseChatModel | None = None,
    repair_invalid_table_plan: bool = False,
    label_incomplete_tables: bool = False,
    answer_llm: BaseChatModel | None = None,
    route_after_review: Callable[[AgentState], AgentState] | None = None,
    answer_context_rule: ContextRule = "sections",
    answer_system_prompt: str | None = None,
    grounding_policy: GroundingPolicy | None = None,
    sanitize_input: bool = False,
    input_filter_llm: BaseChatModel | None = None,
    call_with_backoff: Callable[[Callable[[], object], str], object] | None = None,
) -> CompiledStateGraph:
    """Compile the configurable TOC, section, and table-evidence graph.

    Checkpoint 6.1 options, all defaulting to the 5.1 behavior:

    - ``"whole_article"`` in ``repeated_retrievers`` widens a question without
      tables to its whole articles (``retrieve_whole_article_evidence``). The breadth
      nudge stays tied to ``"article_broaden"``, so a sequence without it has no nudge.
    - ``review_llm``, ``assess_llm``, and ``table_llm`` give the TOC reviewer, the
      assessor, and the table planner their own model; each defaults to ``llm``.
    - ``repair_invalid_table_plan`` and ``label_incomplete_tables`` are passed to
      ``compute_requested_tables``.

    The initial and repeated retrieval stages are pluggable:

    - ``initial_retriever="vector"`` seeds articles from one blunt vector search
      over the question; ``"multistep"`` decomposes into broader sub-topic
      sub-queries; ``"multistep_entity"`` decomposes into one clean full-name
      query per named/implied entity, so explicitly-named articles a blunt query
      buries are retrieved at rank 1.
    - ``repeated_retrievers`` is the ordered escalation tried after the initial
      stage, one stage per unsatisfied assessment, drawn from ``"graph_seeded"``
      and ``"multistep"``.

    After the initial stage, one fused call judges each candidate by its table of
    contents (not a snippet) and selects exact sections and stable table artifact
    IDs. Section chunks and the explicitly selected normalized table artifacts are
    then loaded into evidence before assessment.
    """

    workflow = StateGraph(AgentState)
    logger = run_logger or AgentRunLogger()
    params = graph_params or GraphParams()

    if initial_retriever in ("multistep", "multistep_entity"):
        initial_node = partial(
            retrieve_initial_articles_decomposed,
            retriever=retriever,
            multistep=multistep_retriever,
            top_k=initial_article_top_k,
            per_subquery_k=initial_subquery_top_k,
            max_candidates=initial_max_candidates,
            decompose_mode=(
                "entity" if initial_retriever == "multistep_entity" else "subtopic"
            ),
        )
    elif initial_retriever == "vector":
        initial_node = partial(
            retrieve_initial_articles,
            retriever=retriever,
            top_k=initial_article_top_k,
        )
    else:
        raise ValueError(f"Unknown initial_retriever: {initial_retriever!r}")

    unknown_repeated = [r for r in repeated_retrievers if r not in _REPEATED_EDGE]
    if unknown_repeated:
        raise ValueError(f"Unknown repeated_retrievers: {unknown_repeated}")
    if max_table_rounds < 0:
        raise ValueError("max_table_rounds must be non-negative.")
    if max_table_requests_per_round < 1:
        raise ValueError("max_table_requests_per_round must be at least 1.")

    workflow.add_node("retrieve_initial_articles", initial_node)
    workflow.add_node(
        "review_and_select_from_toc",
        partial(
            review_and_select_from_toc,
            llm=review_llm or llm,
            markdown_store=markdown_store,
            table_store=table_store,
        ),
    )
    workflow.add_node(
        "load_selected_sections",
        partial(
            load_selected_sections,
            retriever=retriever,
            fallback_sections=sections_per_selected_article,
        ),
    )
    workflow.add_node(
        "load_selected_tables",
        partial(load_selected_tables, table_store=table_store),
    )
    workflow.add_node(
        "assess_evidence",
        partial(
            assess_evidence,
            llm=assess_llm or llm,
            allow_table_requests=max_table_rounds > 0,
            # Only nudge non-table questions off a first-pass "ready" when the
            # breadth escalation actually exists in the sequence to catch them.
            breadth_nudge="article_broaden" in repeated_retrievers,
        ),
    )
    workflow.add_node(
        "compute_requested_tables",
        partial(
            compute_requested_tables,
            table_store=table_store,
            llm=table_llm or llm,
            max_requests_per_round=max_table_requests_per_round,
            repair_invalid_plan=repair_invalid_table_plan,
            label_incomplete=label_incomplete_tables,
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
        "retrieve_broadened_sections",
        partial(
            retrieve_broadened_article_sections,
            retriever=retriever,
            broaden_k=broaden_sections_k,
        ),
    )
    # 6.1 whole-article widening; added only when the sequence uses it, so a 5.1
    # graph compiles exactly as before.
    uses_whole_article = "whole_article" in repeated_retrievers
    if uses_whole_article:
        workflow.add_node(
            "retrieve_whole_article_evidence",
            partial(
                retrieve_whole_article_evidence,
                retriever=retriever,
                load_text=markdown_text_loader(markdown_store),
                broaden_k=broaden_sections_k,
            ),
        )
    workflow.add_node(
        "write_question_log",
        partial(write_question_log, logger=logger),
    )

    # Checkpoint 7.1: the safeguards and the answer step become nodes. Each is added only
    # when the builder was given what it needs, so a 5.1 or 6.1 call produces the exact
    # topology it always did and its recorded runs stay reproducible.
    if sanitize_input:
        workflow.add_node(
            "sanitize_question",
            partial(sanitize_question, model_filter=input_filter_llm),
        )
    if answer_llm is not None:
        workflow.add_node(
            "answer_question",
            partial(
                answer_question,
                answer_llm=answer_llm,
                context_rule=answer_context_rule,
                load_text=markdown_text_loader(markdown_store),
                system_prompt=answer_system_prompt,
                call_with_backoff=call_with_backoff,
            ),
        )
        if grounding_policy is not None:
            workflow.add_node(
                "guard_answer",
                partial(guard_answer_node, policy=grounding_policy),
            )

    if sanitize_input:
        workflow.add_edge(START, "sanitize_question")
        workflow.add_edge("sanitize_question", "retrieve_initial_articles")
    else:
        workflow.add_edge(START, "retrieve_initial_articles")
    workflow.add_edge("retrieve_initial_articles", "review_and_select_from_toc")
    if route_after_review is not None:
        # Checkpoint 7.1 model routing: decide the model for the remaining roles from the
        # review (``wiki_agents/model_routing.py``). Without it the edge is unchanged.
        workflow.add_node("route_model", route_after_review)
        workflow.add_edge("review_and_select_from_toc", "route_model")
        workflow.add_edge("route_model", "load_selected_sections")
    else:
        workflow.add_edge("review_and_select_from_toc", "load_selected_sections")
    workflow.add_edge("load_selected_sections", "load_selected_tables")
    workflow.add_edge("load_selected_tables", "assess_evidence")
    routes = {
        "compute_requested_tables": "compute_requested_tables",
        "retrieve_graph_seeded_sections": "retrieve_graph_seeded_sections",
        "retrieve_multistep_sections": "retrieve_multistep_sections",
        "retrieve_broadened_sections": "retrieve_broadened_sections",
        "finish": "write_question_log",
    }
    if uses_whole_article:
        routes["retrieve_whole_article_evidence"] = "retrieve_whole_article_evidence"
    workflow.add_conditional_edges(
        "assess_evidence",
        make_retrieval_benchmark_router(
            tuple(repeated_retrievers),
            max_table_rounds=max_table_rounds,
        ),
        routes,
    )
    workflow.add_edge("compute_requested_tables", "assess_evidence")
    workflow.add_edge("retrieve_graph_seeded_sections", "assess_evidence")
    workflow.add_edge("retrieve_multistep_sections", "assess_evidence")
    workflow.add_edge("retrieve_broadened_sections", "assess_evidence")
    if uses_whole_article:
        workflow.add_edge("retrieve_whole_article_evidence", "assess_evidence")

    # The log is written before the answer, so a run that fails while answering still
    # records the evidence it had reached.
    if answer_llm is None:
        workflow.add_edge("write_question_log", END)
    elif grounding_policy is None:
        workflow.add_edge("write_question_log", "answer_question")
        workflow.add_edge("answer_question", END)
    else:
        workflow.add_edge("write_question_log", "answer_question")
        workflow.add_edge("answer_question", "guard_answer")
        workflow.add_edge("guard_answer", END)

    name = "checkpoint_5_1_retrieval_benchmark"
    if answer_llm is not None:
        name = "checkpoint_7_1_guarded_answer" if grounding_policy else "checkpoint_7_1_answer"
    return workflow.compile(name=name)

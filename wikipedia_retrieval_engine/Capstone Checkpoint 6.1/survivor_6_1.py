"""The Checkpoint 6.1 survivor: the 5.1 survivor with whole articles for text questions
and incomplete evidence surfaced to the user instead of passed along.

Changes against 5.1 (README 6.1 - performance and cost, Experiment 3):

1. **Whole articles replace the breadth step.**
   - No breadth nudge: a text-only question's first "ready" is accepted.
   - The first escalation widens a question without tables to its whole articles
     (``whole_article``) instead of 8 more sections; graph neighbors follow.
   - The answer reads the whole kept articles of a question without tables
     (rule ``whole_per_question``, Experiment 1).
   - Table questions keep the 5.1 sections, table gateway, and broadening.
2. **Incomplete evidence is surfaced** (the synthesis fix recorded on 2026-09-26,
   parts 2 and 3):
   - the table planner's most common schema slip is repaired, and a plan that still
     fails validation gets one corrected retry;
   - a computation that failed or returned no usable rows is labeled incomplete
     instead of "use the computed rows";
   - when the evidence ends incomplete, the answer receives a notice and has to say
     what could not be found or computed. It still answers what the evidence supports.
3. **Models are arguments:** one model for every agent role and the answer, and
   optionally another model for the table planner. The judge stays the 5.1 judge.

Everything else (initial retrieval, TOC review, table gateway, budgets, answer
prompt) is the 5.1 configuration, read from the 5.1 harness as in ``survivor_agent``.
The result rows keep the 5.1 schema plus the 6.1 columns, so the analyzer reads them
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from survivor_agent import LOG_ROOT, load_harness_5_1

from ragas import experiment

from wikipedia_retrieval_engine.retrievers.corpus import build_or_load_markdown_store
from wikipedia_retrieval_engine.retrievers.llm import answer as answer_from_context
from wikipedia_retrieval_engine.retrievers.llm import make_llm
from wikipedia_retrieval_engine.wiki_agents.agentic_models import initial_agent_state
from wikipedia_retrieval_engine.wiki_agents.answer_context import (
    WHOLE_ARTICLE_STAGE,
    build_answer_evidence,
    evidence_status_notice,
    markdown_text_loader,
)

REPEATED_RETRIEVERS_6_1 = ("whole_article", "graph_seeded")
ANSWER_CONTEXT_RULE = "whole_per_question"
NO_EVIDENCE_RESPONSE = "I cannot answer because no relevant Wikipedia sections were retrieved."


@dataclass
class Survivor61:
    """The compiled 6.1 graph plus the objects its case function needs."""

    harness: Any  # the 5.1 harness module (configuration, formatting, judge)
    graph: Any
    agent_llm: Any  # every agent role and the answer
    run_logger: Any
    load_text: Callable[[str], str | None]
    model: str
    table_model: str


def build_survivor_6_1(
    log_subdir: str,
    *,
    model: str | None = None,
    table_model: str | None = None,
    answer_in_graph: bool = False,
    answer_system_prompt: str | None = None,
    grounding_policy: str | None = None,
    sanitize_input: bool = False,
    input_filter_llm: Any | None = None,
    log_root: Any | None = None,
    assess_llm: Any | None = None,
    planner_llm: Any | None = None,
    answer_llm: Any | None = None,
    make_route_node: Callable[[Callable[[str], str | None]], Callable[[dict], dict]] | None = None,
) -> Survivor61:
    """Build the 6.1 graph: the 5.1 survivor's configuration with the 6.1 changes.

    The arguments after ``table_model`` are the Checkpoint 7.1 extension and all default
    to off, so a call without them builds the 6.1 survivor exactly as the recorded runs
    used it. They live here rather than in the 7.1 module because the answer model is the
    agent model, built in this function: ``answer_in_graph`` wires it into the graph's
    answer node instead of leaving the answering to the harness.

    ``assess_llm``, ``planner_llm``, ``answer_llm``, and ``make_route_node`` are the 7.1
    model routing (``wiki_agents/model_routing.py``): per-role model objects, and a factory
    that receives the markdown loader and returns the routing node placed after the TOC
    review.
    """

    h = load_harness_5_1()
    model = model or h.LLM_MODEL
    table_model = table_model or model
    agent_llm = make_llm(model=model)
    table_llm = planner_llm or (agent_llm if table_model == model else make_llm(model=table_model))
    retriever = h.VectorRetriever.for_section_index(
        top_k=h.INITIAL_ARTICLE_TOP_K,
        label=f"section_vector_articles_k{h.INITIAL_ARTICLE_TOP_K}",
    )
    multistep_retriever = h.MultiStepRetriever(
        llm=agent_llm,
        chroma_db_name=h.DEFAULT_SECTION_CHROMA_DB_NAME,
        top_k=h.MULTISTEP_HITS_PER_REQUEST,
        label="targeted_multistep_sections",
    )
    markdown_store = build_or_load_markdown_store()
    load_text = markdown_text_loader(markdown_store)
    wiki_graph = h.build_or_load_graph(markdown_store)
    table_store = h.TableArtifactStore.open()
    run_logger = h.AgentRunLogger(log_root=(log_root or LOG_ROOT) / log_subdir)
    graph = h.build_retrieval_benchmark_graph(
        retriever,
        multistep_retriever,
        wiki_graph,
        agent_llm,
        run_logger,
        markdown_store=markdown_store,
        table_store=table_store,
        initial_retriever=h.INITIAL_RETRIEVER,
        repeated_retrievers=REPEATED_RETRIEVERS_6_1,
        initial_article_top_k=h.INITIAL_ARTICLE_TOP_K,
        initial_subquery_top_k=h.INITIAL_SUBQUERY_TOP_K,
        initial_max_candidates=h.INITIAL_MAX_CANDIDATES,
        sections_per_selected_article=h.SECTIONS_PER_SELECTED_ARTICLE,
        graph_params=h.GRAPH_PARAMS,
        sections_per_neighbor=h.SECTIONS_PER_GRAPH_NEIGHBOR,
        max_graph_sections=h.MAX_GRAPH_SECTIONS,
        multistep_hits_per_request=h.MULTISTEP_HITS_PER_REQUEST,
        max_table_rounds=h.MAX_TABLE_ROUNDS,
        max_table_requests_per_round=h.MAX_TABLE_REQUESTS_PER_ROUND,
        assess_llm=assess_llm,
        table_llm=table_llm,
        repair_invalid_table_plan=True,
        label_incomplete_tables=True,
        answer_llm=(answer_llm or agent_llm) if answer_in_graph else None,
        route_after_review=make_route_node(load_text) if make_route_node else None,
        answer_context_rule=ANSWER_CONTEXT_RULE,
        answer_system_prompt=answer_system_prompt,
        grounding_policy=grounding_policy,
        sanitize_input=sanitize_input,
        input_filter_llm=input_filter_llm,
    )
    return Survivor61(
        harness=h,
        graph=graph,
        agent_llm=agent_llm,
        run_logger=run_logger,
        load_text=load_text,
        model=model,
        table_model=table_model,
    )


def describe_survivor_6_1(agent: Survivor61) -> str:
    """One-block summary of the 6.1 configuration for run headers."""

    h = agent.harness
    return (
        f"  survivor=6.1 (5.1 configuration with the 6.1 changes)\n"
        f"  initial retriever={h.INITIAL_RETRIEVER}\n"
        f"  repeated retrievers={' -> '.join(REPEATED_RETRIEVERS_6_1)} (no breadth nudge)\n"
        f"  answer context={ANSWER_CONTEXT_RULE}; table plan repair and retry on; "
        f"incomplete computations labeled; evidence notice on\n"
        f"  model={agent.model} (every agent role and the answer), table planner={agent.table_model}, "
        f"judge={h.JUDGE_MODEL}"
    )


def _required_articles(h: Any, source_cell: str) -> list[str]:
    return [article.removesuffix(".txt") for article in h.parse_source_articles(source_cell)]


def build_experiment_6_1(
    agent_graph: Any,
    answer_llm: Any,
    ragas_judge: Any,
    rate_limit_backoff: Any,
    experiment_name: str,
    agent: Survivor61,
    survivor_label: str = "6.1",
):
    """The RAGAS case function for the 6.1 survivor.

    It follows the 5.1 case function (``build_agentic_experiment`` in the 5.1
    harness) and changes only the answer context: whole articles by
    ``ANSWER_CONTEXT_RULE``, plus the evidence notice when the evidence ended
    incomplete. Retrieval metrics are computed from the agent's own evidence, as in 5.1.

    Checkpoint 7.1 moved answering and the grounding guardrail into the graph. When the
    graph was built that way it returns ``state["answer"]`` already guarded, and this
    function uses it instead of answering again; the judge therefore scores what a reader
    would receive rather than a draft the system decided to withhold. A graph without
    those nodes leaves no ``answer`` in the state, so the 2.1-6.1 path below is unchanged.
    """

    h = agent.harness

    @experiment()
    async def run_survivor_6_1_case(row: dict) -> dict:
        state = h.call_with_rate_limit_backoff(
            lambda: agent_graph.invoke(
                initial_agent_state(row["question"]),
                config={"recursion_limit": h.RECURSION_LIMIT},
            ),
            rate_limit_backoff,
            label=f"agent graph for {row['question_id']}",
        )

        evidence = state.get("evidence", [])
        answer_evidence = build_answer_evidence(state, ANSWER_CONTEXT_RULE, agent.load_text)
        notice = evidence_status_notice(state)
        context = h.format_section_evidence(answer_evidence)
        if context.strip() and notice:
            context = f"{context}{h._CONTEXT_SEPARATOR}[Evidence status]\n{notice}"
        graph_answer = state.get("answer")
        if graph_answer:
            # 7.1: the graph answered and the guardrail has already acted on it.
            response = graph_answer
            context = state.get("answer_context", context)
        elif context.strip():
            response = h.call_with_rate_limit_backoff(
                lambda: answer_from_context(query=row["question"], context=context, llm=answer_llm),
                rate_limit_backoff,
                label=f"answer LLM for {row['question_id']}",
            )
        else:
            response = NO_EVIDENCE_RESPONSE

        guard_columns: dict[str, Any] = {
            **state.get("input_sanitization", {}),
            **state.get("grounding", {}),
            **state.get("routing", {}),
        }

        score = h.call_with_rate_limit_backoff(
            lambda: h.correctness_metric.score(
                llm=ragas_judge,
                response=response,
                grading_notes=row["grading_notes"],
            ),
            rate_limit_backoff,
            label=f"RAGAS judge for {row['question_id']}",
        )

        required_articles = _required_articles(h, row["source_articles"])
        retrieved_articles = list(dict.fromkeys(item.source_article for item in evidence))
        retrieved_set = set(retrieved_articles)
        matched = [article for article in required_articles if article in retrieved_set]
        missing = [article for article in required_articles if article not in retrieved_set]
        article_recall = len(matched) / len(required_articles) if required_articles else 1.0

        attempts = state.get("retrieval_attempts", 0)
        assessment = state["assessment"]
        history = state.get("assessment_history", [])
        route_trace = [
            (
                "ready_to_answer"
                if item.ready_to_answer
                else "need_table_reader"
                if item.table_requests
                else "need_more_evidence"
            )
            for item in history
        ]
        stage_counts: dict[str, int] = {}
        for item in evidence:
            stage = str(item.metadata.get("retrieval_stage", "unknown"))
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        reviews = state.get("article_reviews", [])
        tables_flagged = any(
            r.needs_table_reader or r.relevant_table_ids or r.relevant_table_names
            for r in reviews
            if r.relevant
        )
        flagged_tables = sorted({t for r in reviews if r.relevant for t in (r.relevant_table_names or [])})
        flagged_table_ids = sorted({t for r in reviews if r.relevant for t in (r.relevant_table_ids or [])})
        table_attempts = state.get("table_attempts", 0)
        computed_table_evidence = [
            item for item in evidence if item.metadata.get("retrieval_stage") == "table_computation"
        ]
        incomplete_computations = [
            item for item in computed_table_evidence if item.metadata.get("table_computation_sufficient") is False
        ]
        retrieval_terminal_stage = h.retrieval_stage_name(
            attempts,
            initial_retriever=h.INITIAL_RETRIEVER,
            repeated_retrievers=REPEATED_RETRIEVERS_6_1,
        )
        terminal_stage = (
            f"{retrieval_terminal_stage}+table_compute_{table_attempts}" if table_attempts else retrieval_terminal_stage
        )
        whole_articles = [
            item.source_article
            for item in answer_evidence
            if item.metadata.get("retrieval_stage") == WHOLE_ARTICLE_STAGE
        ]

        return {
            **row,
            "experiment_name": experiment_name,
            "evaluation_mode": "agentic_survivor_6_1",
            "answer_model": agent.model,
            "judge_model": h.JUDGE_MODEL,
            "retriever_kind": "survivor_6_1",
            "initial_retriever": h.INITIAL_RETRIEVER,
            "repeated_retrievers": "->".join(REPEATED_RETRIEVERS_6_1),
            "initial_article_top_k": h.INITIAL_ARTICLE_TOP_K,
            "sections_per_selected_article": h.SECTIONS_PER_SELECTED_ARTICLE,
            "graph_max_neighbors": h.GRAPH_PARAMS.max_neighbors,
            "sections_per_graph_neighbor": h.SECTIONS_PER_GRAPH_NEIGHBOR,
            "max_graph_sections": h.MAX_GRAPH_SECTIONS,
            "multistep_hits_per_request": h.MULTISTEP_HITS_PER_REQUEST,
            "retrieval_attempts": attempts,
            "terminal_stage": terminal_stage,
            "evidence_ready": assessment.ready_to_answer,
            "route_trace": " -> ".join(route_trace),
            "assessment_explanation": assessment.explanation,
            "evidence_stage_counts": "; ".join(f"{stage}={count}" for stage, count in sorted(stage_counts.items())),
            "tables_flagged": tables_flagged,
            "flagged_tables": "; ".join(flagged_tables),
            "flagged_table_ids": "; ".join(flagged_table_ids),
            "table_attempts": table_attempts,
            "table_computation_evidence_count": len(computed_table_evidence),
            "computed_table_artifact_ids": "; ".join(item.table_id or "" for item in computed_table_evidence),
            "required_articles": "; ".join(required_articles),
            "retrieved_articles": "; ".join(retrieved_articles),
            "retrieved_article_count": len(retrieved_articles),
            "matched_articles": "; ".join(matched),
            "missing_articles": "; ".join(missing),
            "article_recall": article_recall,
            "evidence_ids": "; ".join(item.evidence_id for item in answer_evidence),
            "evidence_count": len(answer_evidence),
            "context_characters": len(context),
            "response": response,
            "score": score.value,
            "source_count": len(required_articles),
            # 6.1 columns
            "survivor": survivor_label,
            "table_model": agent.table_model,
            "answer_context_rule": ANSWER_CONTEXT_RULE,
            "whole_articles_sent": "; ".join(whole_articles),
            "evidence_notice": bool(notice),
            "incomplete_table_computations": len(incomplete_computations),
            # 7.1 columns, empty unless an answer_guard was supplied
            **guard_columns,
        }

    return run_survivor_6_1_case

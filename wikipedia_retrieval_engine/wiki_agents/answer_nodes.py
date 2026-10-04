"""Graph nodes for the steps that used to sit outside the graph: sanitise, answer, guard.

Until Checkpoint 7.1 the graph ended at ``write_question_log`` and every checkpoint called
``retrievers.llm.answer`` itself afterwards. That was fine while answering was the last
thing to happen, but a guardrail has to run *between* the answer and the reader, and a
safeguard that lives in a benchmark harness is not part of the system being benchmarked.

So the three steps become nodes:

``sanitize_question``  cleans the user's text before retrieval sees it (Lab 7.1's input
                       middleware). Placed first, so no later node can be reached by text
                       the filters would have removed.
``answer_question``    builds the answer context under the configured context rule and
                       calls the answer model.
``guard_answer``       checks the drafted answer against the evidence and applies the
                       failure policy.

All three are optional and off unless the graph builder is given what they need, so the
2.1-6.1 graphs keep their exact topology and their recorded runs stay reproducible.
"""

from __future__ import annotations

from typing import Any, Callable

from wikipedia_retrieval_engine.retrievers.llm import build_answer_messages
from wikipedia_retrieval_engine.wiki_agents.agentic_models import AgentState
from wikipedia_retrieval_engine.wiki_agents.answer_guard import GroundingPolicy, guard_answer
from wikipedia_retrieval_engine.wiki_agents.answer_context import (
    ContextRule,
    build_answer_evidence,
    evidence_status_notice,
)
from wikipedia_retrieval_engine.wiki_agents.sanitize import sanitize_user_text

NO_EVIDENCE_RESPONSE = "I cannot answer because no relevant Wikipedia sections were retrieved."

# Mirrors the 5.1 harness separator so the assembled context is byte-identical to the one
# the recorded runs used. Imported lazily to keep this module free of harness imports.
_CONTEXT_SEPARATOR = "\n\n" + "=" * 80 + "\n\n"


def format_section_evidence(evidence: list[Any]) -> str:
    """The 5.1 evidence format, duplicated here so the graph does not import a harness.

    Kept byte-identical to ``capstone_checkpoint_5_1_agent_rag_starter.format_section_evidence``;
    ``tests/test_answer_nodes.py`` pins the two against each other.
    """

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


def sanitize_question(
    state: AgentState,
    *,
    model_filter: Any | None = None,
    escape: bool = True,
    strip_blocks: bool = True,
) -> dict[str, Any]:
    """Clean the question before retrieval, and record which layers fired.

    ``escape`` defaults to True for parity with Lab 7.1, but note the cost: the escaped
    question is what retrieval then searches for, so a question containing "<" is searched
    in its escaped form. A deployment that structures its prompt with XML compartments
    wants this; one that does not can pass ``escape=False``.
    """

    result = sanitize_user_text(
        state["question"],
        escape=escape,
        strip_blocks=strip_blocks,
        model_filter=model_filter,
    )
    return {"question": result.text, "input_sanitization": result.columns}


def answer_question(
    state: AgentState,
    *,
    answer_llm: Any,
    context_rule: ContextRule,
    load_text: Callable[[str], str | None],
    system_prompt: str | None = None,
    call_with_backoff: Callable[[Callable[[], Any], str], Any] | None = None,
) -> dict[str, Any]:
    """Build the answer context under ``context_rule`` and draft the answer.

    This is the 6.1 answer step moved verbatim: the same evidence rule, the same
    ``[Evidence status]`` notice, the same no-evidence reply.
    """

    answer_evidence = build_answer_evidence(state, context_rule, load_text)
    notice = evidence_status_notice(state)
    context = format_section_evidence(answer_evidence)
    if context.strip() and notice:
        context = f"{context}{_CONTEXT_SEPARATOR}[Evidence status]\n{notice}"

    if not context.strip():
        return {
            "answer": NO_EVIDENCE_RESPONSE,
            "answer_drafted": NO_EVIDENCE_RESPONSE,
            "answer_usage": {},
            "answer_context": "",
            "answer_evidence": answer_evidence,
        }

    kwargs: dict[str, Any] = {}
    if system_prompt is not None:
        kwargs["system_prompt"] = system_prompt

    # ``build_answer_messages`` is what ``retrievers.llm.answer`` calls internally, so with
    # no history this produces the identical message list the recorded runs used.
    # ``tests/test_answer_nodes.py`` pins the two against each other.
    messages = build_answer_messages(
        state["question"],
        context,
        history=state.get("history"),
        max_history_turns=state.get("max_history_turns"),
        **kwargs,
    )

    usage: dict[str, Any] = {}

    def call() -> Any:
        response = answer_llm.invoke(messages)
        usage.update(dict(getattr(response, "usage_metadata", None) or {}))
        content = getattr(response, "content", response)
        return content if isinstance(content, str) else str(content)

    drafted = call_with_backoff(call, "answer LLM") if call_with_backoff else call()
    return {
        "answer": drafted,
        "answer_drafted": drafted,
        "answer_usage": usage,
        "answer_context": context,
        "answer_evidence": answer_evidence,
    }


def guard_answer_node(
    state: AgentState,
    *,
    policy: GroundingPolicy = "surface",
) -> dict[str, Any]:
    """Check the drafted answer against its evidence and apply ``policy``.

    The haystack is built from ``answer_evidence``, never from ``answer_context``: the
    context also carries the ``[Evidence status]`` notice and the echoed user text inside
    table-computation items, and neither may certify an answer.
    """

    drafted = state.get("answer", "")
    guarded = guard_answer(drafted, state.get("answer_evidence", []), policy=policy)
    return {"answer": guarded.answer, "answer_drafted": drafted, "grounding": guarded.columns}

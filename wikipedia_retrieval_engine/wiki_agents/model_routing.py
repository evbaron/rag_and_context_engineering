"""Checkpoint 7.1 model routing: ``gpt-5.4-mini`` by default, ``gpt-5.4`` when a rule says so.

Three strategies share one mechanism (README 7.1, "Options for the live runs"):

``type``   after the TOC review, a question the reviewer flagged for a table runs its
           remaining roles (assessor, table planner, answer) on the strong model.
``b``      the same trigger; only the assessor and the answer switch, the planner stays
           on the cheap model.
``check``  after the TOC review, a text question whose kept articles are too large for
           Jev to read switches the remaining roles to the strong model; every other
           question is answered on the cheap model, then Jev asks "does the answer fully
           answer every part of the question?" and, below the threshold, the whole
           question is answered again on the strong model.
``b_check`` the answer check with Router B's models: on large evidence and on a rerun only
           the assessor and the answer use the strong model; the table planner stays on
           the cheap one (on the strong model it requested far more table data in the GT
           runs, the bulk of the routers' cost).

The decomposer and the TOC reviewer always run on the cheap model: the route is decided
from their output.

**Mechanism.** The graph's nodes build their model call at call time
(``llm.with_structured_output(...)`` inside the node; ``answer_llm.invoke`` in the answer
node), so a ``TierSwitchModel`` standing in for a chat model can forward each call to the
cheap or the strong model at that moment. A routing node after the TOC review sets the
tier in a ``RouteHolder`` and records the decision in the state (``routing``), which the
cost harness writes to the results CSV. The RAGAS harness answers one question at a time,
so one mutable holder per graph is enough; the wrappers reset it before every question.

**Jev** (``typesafe/jev-1.13``, pinned) is called over plain HTTP on OpenRouter's
decisions endpoint. LangChain telemetry does not see it, so its cost and latency go into
``routing`` as ``router_cost_usd`` and ``router_latency_s``. A failed or oversized check
escalates: the strategy is accuracy first.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

CHEAP, STRONG = "cheap", "strong"
STRATEGIES = ("type", "b", "check", "b_check")

JEV_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"
# Evidence Jev can read: its window is 32,000 of its own tokens, which count higher than
# o200k (the offline check had GT19 rejected at 23,602 o200k tokens). About 3.7 characters
# per token puts 22,000 o200k tokens at roughly 80,000 characters.
JEV_MAX_EVIDENCE_CHARS = 80_000
COMPLETE_CHECK = {
    "type": "noul",
    "instructions": "Does the answer fully answer every part of the question?",
    "criteria": {
        "true": "The answer gives a definite answer to every part of the question.",
        "false": "The answer leaves a part of the question unanswered, gives only part of a list or count, or "
                 "says it cannot answer.",
    },
}


# Every routing record carries the same fields, filled with None where a step did not
# apply. The results CSV is written in one go at the end of a run with the first row's
# columns; a later row with an extra field fails the whole write. The first live answer-
# check run lost its answers and verdicts that way (a question routed after the review had
# no check fields; a checked one had them).
ROUTING_FIELDS = (
    "route", "route_reason", "route_point", "kept_article_chars", "check_status", "check_p_complete",
    "check_threshold", "escalated", "router_cost_usd", "router_latency_s", "first_answer_chars",
)


def routing_record(**values: Any) -> dict[str, Any]:
    """A routing record with every field, in a fixed order."""

    unknown = set(values) - set(ROUTING_FIELDS)
    if unknown:
        raise ValueError(f"Unknown routing fields: {sorted(unknown)}")
    return {field_name: values.get(field_name) for field_name in ROUTING_FIELDS}


@dataclass
class RouteHolder:
    """The current question's tier, set by the routing node and read by every switch."""

    tier: str = CHEAP

    def reset(self) -> None:
        self.tier = CHEAP


class TierSwitchModel:
    """Stands in for a chat model and forwards each call to the cheap or the strong one."""

    def __init__(self, cheap: Any, strong: Any, holder: RouteHolder):
        self.cheap, self.strong, self.holder = cheap, strong, holder

    def current(self) -> Any:
        return self.strong if self.holder.tier == STRONG else self.cheap

    def with_structured_output(self, *args: Any, **kwargs: Any) -> Any:
        return self.current().with_structured_output(*args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return self.current().invoke(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.current(), name)


def tables_flagged(state: dict) -> bool:
    """The TOC review's table decision, as the results CSV's ``tables_flagged`` column defines it."""

    return any(
        review.needs_table_reader or review.relevant_table_ids or review.relevant_table_names
        for review in state.get("article_reviews", [])
        if review.relevant
    )


def make_type_route(holder: RouteHolder) -> Callable[[dict], dict]:
    """Routing node for ``type`` and ``b``: strong when the TOC review flagged a table."""

    def route_model(state: dict) -> dict:
        table = tables_flagged(state)
        holder.tier = STRONG if table else CHEAP
        return {"routing": routing_record(route=holder.tier, route_reason="table flagged" if table else "text question",
                                          route_point="after TOC review")}

    return route_model


def make_size_route(
    holder: RouteHolder,
    load_text: Callable[[str], str | None],
    max_chars: int = JEV_MAX_EVIDENCE_CHARS,
) -> Callable[[dict], dict]:
    """Routing node for ``check``: strong for a text question whose kept articles Jev cannot read.

    A text question's answer context is its kept articles, whole (rule
    ``whole_per_question``), so their size is known after the review. A table question's
    context is known only when it is answered; the check handles it then.
    """

    def route_model(state: dict) -> dict:
        if tables_flagged(state):
            holder.tier = CHEAP
            return {"routing": routing_record(route=CHEAP, route_reason="table question: checked after the answer",
                                              route_point="after TOC review")}
        chars = sum(len(load_text(article) or "") for article in state.get("selected_articles", []))
        holder.tier = STRONG if chars > max_chars else CHEAP
        return {"routing": routing_record(route=holder.tier, kept_article_chars=chars,
                                          route_reason="large evidence" if holder.tier == STRONG else "text question",
                                          route_point="after TOC review")}

    return route_model


def jev_complete_check(question: str, answer: str, evidence: str, headers: dict[str, str],
                       session: requests.Session | None = None, timeout: float = 60) -> dict[str, Any]:
    """Jev's probability that ``answer`` fully answers ``question`` from ``evidence``."""

    body = {"model": JEV_MODEL, "state": {"question": question, "answer": answer, "evidence": evidence},
            "questions": {"complete": COMPLETE_CHECK}}
    started = time.perf_counter()
    try:
        response = (session or requests).post(JEV_DECISIONS_URL, headers=headers, json=body, timeout=timeout)
        latency = time.perf_counter() - started
        payload = response.json() if response.content else {}
    except Exception as error:
        return {"check_status": f"error:{type(error).__name__}", "router_latency_s": time.perf_counter() - started,
                "router_cost_usd": 0.0}
    if response.status_code != 200 or "answers" not in payload:
        return {"check_status": f"http_{response.status_code}", "router_latency_s": latency, "router_cost_usd": 0.0}
    return {"check_status": "ok", "check_p_complete": payload["answers"]["complete"].get("noul"),
            "router_latency_s": latency, "router_cost_usd": float(payload.get("usage", {}).get("cost") or 0.0)}


class RoutedGraph:
    """A compiled graph with a routing node; resets the tier before every question."""

    def __init__(self, graph: Any, holder: RouteHolder):
        self.graph, self.holder = graph, holder

    def invoke(self, state: dict, config: dict | None = None, **kwargs: Any) -> Any:
        self.holder.reset()
        return self.graph.invoke(state, config=config, **kwargs)


class EscalatingGraph:
    """``check``: answer on the routed graph; when Jev says incomplete, answer again on the strong graph."""

    def __init__(self, first: Any, strong: Any, holder: RouteHolder,
                 checker: Callable[[str, str, str], dict[str, Any]], threshold: float = 0.5,
                 max_chars: int = JEV_MAX_EVIDENCE_CHARS):
        self.first, self.strong, self.holder = first, strong, holder
        self.checker, self.threshold, self.max_chars = checker, threshold, max_chars

    def invoke(self, state: dict, config: dict | None = None, **kwargs: Any) -> Any:
        self.holder.reset()
        first = self.first.invoke(state, config=config, **kwargs)
        routing = routing_record(**first.get("routing", {}))
        if routing.get("route") == STRONG:  # already on the strong model after the review
            return {**first, "routing": routing}
        answer = first.get("answer_drafted") or first.get("answer") or ""
        context = first.get("answer_context") or ""
        if not answer.strip() or not context.strip():
            check = {"check_status": "no answer or no evidence", "router_cost_usd": 0.0, "router_latency_s": 0.0}
        elif len(context) > self.max_chars:
            check = {"check_status": "evidence too large for Jev", "router_cost_usd": 0.0, "router_latency_s": 0.0}
        else:
            check = self.checker(state["question"], answer, context)
        probability = check.get("check_p_complete")
        escalate = check.get("check_status") != "ok" or probability is None or probability < self.threshold
        routing = routing_record(**{**routing, **check, "check_threshold": self.threshold, "escalated": escalate})
        if not escalate:
            return {**first, "routing": routing}
        self.holder.tier = STRONG
        second = self.strong.invoke(state, config=config, **kwargs)
        routing = routing_record(**{**routing, "route": "escalated", "first_answer_chars": len(answer)})
        return {**second, "routing": routing}

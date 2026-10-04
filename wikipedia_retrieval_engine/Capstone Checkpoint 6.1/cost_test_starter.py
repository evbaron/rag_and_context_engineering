r"""Checkpoint 6.1 cost test starter — the 5.1 survivor with per-question, per-tool telemetry.

Run from the repository root (rag_and_context_engineering/):

    # zero cost: verify the telemetry on a fake model, no API calls
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/cost_test_starter.py" --self-check

    # live: smoke test, then the full validation set
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/cost_test_starter.py" --question-id VAL04
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/cost_test_starter.py" \
        --gt-set "wikipedia_retrieval_engine/GT/wikipedia_GT_validation_set.csv"

History is OFF: every question is a fresh single-turn run, exactly as in 5.1.
The questions go through the unchanged 5.1 RAGAS case function
(``build_agentic_experiment``), so the RAGAS CSV has the 5.1 schema and
``utils/analyze_ragas_experiments.py`` reads it as-is. Telemetry is observed from
the outside:

    TelemetryGraph      wraps the compiled graph; attaches one callback handler per
                        question through ``config["callbacks"]``
    TelemetryAnswerLLM  wraps the answer model; tags its call as node "answer"
    QuestionUsage       the callback handler: one record per chat-model call
                        (node, role, tokens, cached tokens, latency) and one per
                        graph-node execution (wall time)

Outputs next to the RAGAS CSV ``<output-dir>/experiments/<run>.csv``:

    <output-dir>/telemetry/<run>__llm_calls.csv          one row per chat call
    <output-dir>/telemetry/<run>__node_timings.csv       one row per node execution
    <output-dir>/telemetry/<run>__question_telemetry.csv one row per question

The RAGAS judge is not a LangChain model, so judge calls are not in the tally
(evaluation overhead; OpenRouter analytics app "WRE judge"). Embedding calls are
not chat calls either; their time is inside the retrieval nodes' wall time.
"""

# %%
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    _HERE = Path.cwd()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from survivor_agent import (  # noqa: E402  (sys.path set above)
    VALIDATION_PATH,
    build_survivor_agent,
    describe_survivor,
    load_harness_5_1,
)
from usage_accounting import (  # noqa: E402
    PRICES_PATH,
    call_cost,
    load_prices,
    price_for,
    usage_from_message,
)
from survivor_6_1 import build_experiment_6_1, build_survivor_6_1, describe_survivor_6_1  # noqa: E402

from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402

OUTPUT_ROOT = _HERE / "cost_tests"

# Graph node (or the harness answer call) -> the role it plays in the 5.1 agent.
ROLE_BY_NODE = {
    "retrieve_initial_articles": "decomposer",
    "review_and_select_from_toc": "toc_reviewer",
    "assess_evidence": "assessor",
    "compute_requested_tables": "table_planner",
    "answer": "answer",
    # Checkpoint 7.1: answering moved into the graph, so it is attributed by node name
    # like the other roles rather than by the answer wrapper's run_name.
    "answer_question": "answer",
    "sanitize_question": "input_filter",
}


# %% [markdown]
# ## Telemetry records

# %%
@dataclass
class CallRecord:
    """One chat-model call."""

    question_id: str
    graph_attempt: int
    node: str
    role: str
    step: int | None  # LangGraph superstep; two assessor calls in one step = a retry
    model: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    latency_s: float = 0.0
    provider_cost_usd: float | None = None
    status: str = "ok"


@dataclass(eq=False)  # handlers compare by identity, as LangChain expects
class QuestionUsage(BaseCallbackHandler):
    """Callback handler that collects every chat call and node timing for ONE question."""

    question_id: str
    question: str
    graph_attempts: int = 0
    graph_wall_s: float = 0.0
    answer_wall_s: float = 0.0
    calls: list[CallRecord] = field(default_factory=list)
    node_timings: list[dict[str, Any]] = field(default_factory=list)
    _pending: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    _chains: dict[UUID, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__()

    # -- chat-model calls --------------------------------------------------------
    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
        """Remember where this call happens (graph node or the answer call) and when."""

        metadata = metadata or {}
        node = metadata.get("langgraph_node") or kwargs.get("name") or "unknown"
        self._pending[run_id] = {
            "node": node,
            "step": metadata.get("langgraph_step"),
            "start": time.perf_counter(),
        }

    def on_llm_end(self, response, *, run_id, **kwargs):
        """Record one finished chat-model call as a ``CallRecord`` in ``self.calls``.

        The Lab 6.2 ``_track_usage`` step, per call instead of per model.
        ``response`` is an ``LLMResult``; the model's reply is
        ``response.generations[0][0].message`` (an ``AIMessage``), whose token
        counts, model name, and reported cost ``usage_from_message`` reads. What
        ``on_chat_model_start`` stored for this ``run_id`` (node, step, start time)
        supplies where the call happened and how long it took.
        """

        pending = self._pending.pop(run_id, None) or {"node": "unknown", "step": None, "start": time.perf_counter()}
        try:
            message = response.generations[0][0].message
        except (AttributeError, IndexError):
            message = None
        usage = usage_from_message(message)
        self.calls.append(
            CallRecord(
                question_id=self.question_id,
                graph_attempt=self.graph_attempts,
                node=pending["node"],
                role=ROLE_BY_NODE.get(pending["node"], "other"),
                step=pending["step"],
                model=usage["model"],
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["total_tokens"],
                cached_input_tokens=usage["cached_input_tokens"],
                reasoning_tokens=usage["reasoning_tokens"],
                latency_s=time.perf_counter() - pending["start"],
                provider_cost_usd=usage["provider_cost_usd"],
            )
        )

    def on_llm_error(self, error, *, run_id, **kwargs):
        pending = self._pending.pop(run_id, None) or {"node": "unknown", "step": None, "start": time.perf_counter()}
        self.calls.append(
            CallRecord(
                question_id=self.question_id,
                graph_attempt=self.graph_attempts,
                node=pending["node"],
                role=ROLE_BY_NODE.get(pending["node"], "other"),
                step=pending["step"],
                model=None,
                latency_s=time.perf_counter() - pending["start"],
                status=f"error:{type(error).__name__}",
            )
        )

    # -- graph-node timing -------------------------------------------------------
    def on_chain_start(self, serialized, inputs, *, run_id, metadata=None, **kwargs):
        metadata = metadata or {}
        name = kwargs.get("name")
        # Node runs carry their own name as langgraph_node; routers and the graph do not.
        if name and name == metadata.get("langgraph_node"):
            self._chains[run_id] = {"node": name, "step": metadata.get("langgraph_step"), "start": time.perf_counter()}

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self._finish_chain(run_id, "ok")

    def on_chain_error(self, error, *, run_id, **kwargs):
        self._finish_chain(run_id, f"error:{type(error).__name__}")

    def _finish_chain(self, run_id: UUID, status: str) -> None:
        chain = self._chains.pop(run_id, None)
        if chain:
            self.node_timings.append(
                {
                    "question_id": self.question_id,
                    "graph_attempt": self.graph_attempts,
                    "node": chain["node"],
                    "step": chain["step"],
                    "wall_s": round(time.perf_counter() - chain["start"], 3),
                    "status": status,
                }
            )


class UsageRecorder:
    """Hands out one ``QuestionUsage`` per question and keeps them for the report."""

    def __init__(self, question_ids_by_text: dict[str, str]):
        self._ids = question_ids_by_text
        self.questions: dict[str, QuestionUsage] = {}
        self._current: QuestionUsage | None = None

    def for_graph(self, question: str) -> QuestionUsage:
        usage = self.questions.get(question)
        if usage is None:
            usage = QuestionUsage(question_id=self._ids.get(question, "?"), question=question)
            self.questions[question] = usage
        usage.graph_attempts += 1  # >1 means the 429 wrapper re-ran the whole graph
        self._current = usage
        return usage

    def for_answer(self, messages: list[Any]) -> QuestionUsage | None:
        # The 5.1 answer message ends with "\n\nQuestion: {question}".
        text = str(getattr(messages[-1], "content", "")) if messages else ""
        question = text.rsplit("\n\nQuestion: ", 1)[-1] if "\n\nQuestion: " in text else None
        return self.questions.get(question or "") or self._current


class TelemetryGraph:
    """The compiled 5.1 graph, unchanged, plus one callback handler per question."""

    def __init__(self, graph: Any, recorder: UsageRecorder):
        self._graph, self._recorder = graph, recorder

    def invoke(self, state: dict, config: dict | None = None, **kwargs: Any) -> Any:
        usage = self._recorder.for_graph(state["question"])
        merged = dict(config or {})
        merged["callbacks"] = [*(merged.get("callbacks") or []), usage]
        start = time.perf_counter()
        try:
            return self._graph.invoke(state, config=merged, **kwargs)
        finally:
            usage.graph_wall_s += time.perf_counter() - start


class TelemetryAnswerLLM:
    """The answer model, unchanged, with its call tagged as node "answer"."""

    def __init__(self, llm: Any, recorder: UsageRecorder):
        self._llm, self._recorder = llm, recorder

    def invoke(self, messages: list[Any], config: dict | None = None, **kwargs: Any) -> Any:
        usage = self._recorder.for_answer(messages)
        merged = dict(config or {})
        merged.setdefault("run_name", "answer")
        if usage is not None:
            merged["callbacks"] = [*(merged.get("callbacks") or []), usage]
        start = time.perf_counter()
        try:
            return self._llm.invoke(messages, config=merged, **kwargs)
        finally:
            if usage is not None:
                usage.answer_wall_s += time.perf_counter() - start


# %% [markdown]
# ## Cost estimate and summaries

# %%
def call_costs(record: CallRecord, prices: dict[str, dict[str, float | None]]) -> dict[str, float | None]:
    """List and billed cost of one recorded call (see ``usage_accounting.call_cost``)."""

    return call_cost(
        record.input_tokens,
        record.cached_input_tokens,
        record.output_tokens,
        price_for(record.model, prices),
    )


def _total(values: list[float | None]) -> float | None:
    return round(sum(values), 6) if values and None not in values else None


def question_summary(usage: QuestionUsage, prices: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    calls = usage.calls
    costs = [call_costs(call, prices) for call in calls]
    provider = [call.provider_cost_usd for call in calls if call.provider_cost_usd is not None]
    tokens_by_role: dict[str, int] = defaultdict(int)
    for call in calls:
        tokens_by_role[call.role] += call.input_tokens + call.output_tokens
    input_tokens = sum(call.input_tokens for call in calls)
    cached = sum(call.cached_input_tokens for call in calls)
    return {
        "question_id": usage.question_id,
        "graph_attempts": usage.graph_attempts,
        "llm_calls": len(calls),
        "llm_calls_by_role": "; ".join(f"{r}={n}" for r, n in sorted(Counter(c.role for c in calls).items())),
        "input_tokens": input_tokens,
        "output_tokens": sum(call.output_tokens for call in calls),
        "cached_input_tokens": cached,
        "reasoning_tokens": sum(call.reasoning_tokens for call in calls),
        "cache_share": round(cached / input_tokens, 3) if input_tokens else 0.0,
        "tokens_by_role": "; ".join(f"{r}={n}" for r, n in sorted(tokens_by_role.items())),
        "graph_wall_s": round(usage.graph_wall_s, 2),
        "answer_wall_s": round(usage.answer_wall_s, 2),
        "list_cost_usd": _total([cost["list"] for cost in costs]),
        "billed_est_usd": _total([cost["billed"] for cost in costs]),
        "provider_cost_usd": round(sum(provider), 6) if provider else None,
        "question": usage.question,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_telemetry(recorder: UsageRecorder, out_dir: Path, run_name: str, prices: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    calls = []
    for usage in recorder.questions.values():
        for call in usage.calls:
            cost = call_costs(call, prices)
            calls.append(
                {"run": run_name, **asdict(call), "list_cost_usd": cost["list"], "billed_est_usd": cost["billed"]}
            )
    nodes = [{"run": run_name, **row} for usage in recorder.questions.values() for row in usage.node_timings]
    questions = [{"run": run_name, **question_summary(u, prices)} for u in recorder.questions.values()]
    _write_csv(out_dir / f"{run_name}__llm_calls.csv", calls)
    _write_csv(out_dir / f"{run_name}__node_timings.csv", nodes)
    _write_csv(out_dir / f"{run_name}__question_telemetry.csv", questions)
    print(f"Telemetry saved to: {out_dir.resolve()}/{run_name}__*.csv")


def print_role_summary(recorder: UsageRecorder) -> None:
    usages = list(recorder.questions.values())
    calls = [call for usage in usages for call in usage.calls]
    if not calls:
        print("No chat-model calls were recorded.")
        return
    n_questions = len(usages)
    total_tokens = sum(c.input_tokens + c.output_tokens for c in calls) or 1
    print(f"\nPER ROLE (tool) over {n_questions} question(s)")
    print(f"  {'role':<14}{'calls/q':>8}{'in tok/q':>10}{'out tok/q':>10}{'cached':>8}{'token share':>13}")
    for role in sorted({c.role for c in calls}):
        mine = [c for c in calls if c.role == role]
        tokens_in = sum(c.input_tokens for c in mine)
        cached = sum(c.cached_input_tokens for c in mine)
        share = sum(c.input_tokens + c.output_tokens for c in mine) / total_tokens
        print(
            f"  {role:<14}{len(mine) / n_questions:>8.1f}{tokens_in / n_questions:>10.0f}"
            f"{sum(c.output_tokens for c in mine) / n_questions:>10.0f}"
            f"{(cached / tokens_in if tokens_in else 0):>8.0%}{share:>13.0%}"
        )
    walls = [(u.question_id, u.graph_wall_s + u.answer_wall_s, len(u.calls)) for u in usages]
    walls.sort(key=lambda item: item[1], reverse=True)
    print("  slowest questions: " + ", ".join(f"{q} {s:.0f}s/{n} calls" for q, s, n in walls[:5]))


# %% [markdown]
# ## Self-check (zero cost)

# %%
def self_check(verbose: bool = True) -> bool:
    """Run the telemetry on a fake two-node graph and a fake answer model — no API calls."""

    from typing import TypedDict

    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, LLMResult
    from langgraph.graph import END, START, StateGraph

    def say(*lines: str) -> None:
        if verbose:
            for line in lines:
                print(f"[self-check] {line}")

    class UsageFake(GenericFakeChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            result.generations[0].message = AIMessage(
                content=result.generations[0].message.content,
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "total_tokens": 110,
                    "input_token_details": {"cache_read": 40},
                    "output_token_details": {"reasoning": 4},
                },
                response_metadata={"model_name": "fake/model", "token_usage": {"cost": 0.001}},
            )
            return result

    # 1) on_llm_end called directly, outside LangChain, so an exception is visible
    #    here instead of being swallowed by the callback manager.
    probe = QuestionUsage(question_id="probe", question="probe")
    run_id = uuid4()
    probe.on_chat_model_start({}, [[HumanMessage("x")]], run_id=run_id, metadata={"langgraph_node": "assess_evidence", "langgraph_step": 1})
    fake_reply = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        response_metadata={"model_name": "fake/model"},
    )
    probe.on_llm_end(LLMResult(generations=[[ChatGeneration(message=fake_reply)]]), run_id=run_id)

    # 2) End to end through the wrappers, the way the 5.1 case function calls them.
    llm = UsageFake(messages=iter(["a", "b", "c", "d"]))

    class State(TypedDict, total=False):
        question: str

    def retrieve_initial_articles(state):  # decomposer: 1 call
        llm.invoke("decompose")
        return {}

    def assess_evidence(state):  # assessor: 1 call + 1 retry in the same step
        llm.invoke("assess")
        llm.invoke("assess again")
        return {}

    builder = StateGraph(State)
    builder.add_node("retrieve_initial_articles", retrieve_initial_articles)
    builder.add_node("assess_evidence", assess_evidence)
    builder.add_edge(START, "retrieve_initial_articles")
    builder.add_edge("retrieve_initial_articles", "assess_evidence")
    builder.add_edge("assess_evidence", END)

    recorder = UsageRecorder({"Q?": "Q1"})
    TelemetryGraph(builder.compile(), recorder).invoke({"question": "Q?"}, config={"recursion_limit": 5})
    TelemetryAnswerLLM(llm, recorder).invoke([HumanMessage("Context (Wikipedia articles):\nctx\n\nQuestion: Q?")])

    usage = recorder.questions["Q?"]
    summary = question_summary(usage, {"fake/model": {"input": 1.0, "cached_input": 0.5, "output": 2.0}})
    steps = [c.step for c in usage.calls if c.role == "assessor"]
    real_prices = load_prices()
    checks = {
        "direct call produced one record": len(probe.calls) == 1 and probe.calls[0].input_tokens == 7,
        "4 calls attributed to decomposer, assessor x2, answer": summary["llm_calls_by_role"]
        == "answer=1; assessor=2; decomposer=1",
        "assessor retry shares one step": len(steps) == 2 and steps[0] == steps[1] is not None,
        "tokens summed (400 in / 40 out / 160 cached)": (
            summary["input_tokens"], summary["output_tokens"], summary["cached_input_tokens"]
        ) == (400, 40, 160),
        "reasoning tokens and provider cost read": summary["reasoning_tokens"] == 16
        and summary["provider_cost_usd"] == 0.004,
        "billed estimate uses the cached rate": summary["billed_est_usd"]
        == round(4 * (60 * 1.0 + 40 * 0.5 + 10 * 2.0) / 1e6, 6),
        "list price ignores caching": summary["list_cost_usd"] == round(4 * (100 * 1.0 + 10 * 2.0) / 1e6, 6),
        "price file: dated gpt-5.4-mini id priced as mini, not gpt-5.4": price_for(
            "openai/gpt-5.4-mini-20260317", real_prices
        )
        == real_prices.get("openai/gpt-5.4-mini")
        is not None,
        "node timings for both nodes": {row["node"] for row in usage.node_timings}
        == {"retrieve_initial_articles", "assess_evidence"},
    }
    for name, ok in checks.items():
        say(f"{'PASS' if ok else 'FAIL'}  {name}")
    return all(checks.values())


# %%
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Checkpoint 6.1 cost tests (history off, telemetry on).")
    parser.add_argument("--gt-set", type=Path, default=VALIDATION_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: Capstone Checkpoint 6.1/cost_tests/<gt-set file stem>.",
    )
    parser.add_argument(
        "--survivor",
        choices=["5.1", "6.1", "final"],
        default="5.1",
        help="5.1: the unchanged 5.1 survivor. 6.1: the Checkpoint 6.1 survivor "
             "(survivor_6_1.py). final: the Checkpoint 7.1 agent (survivor_agent_final.py) "
             "-- the 6.1 configuration with input sanitising, answering and the grounding "
             "guardrail inside the graph.",
    )
    parser.add_argument(
        "--grounding",
        choices=["off", "surface", "withhold"],
        default="surface",
        help="final only: the grounding policy. 'off' delivers the answer unchanged and "
             "still records the verdict, so one run gives both the 6.1-comparable quality "
             "and the guardrail's trigger rate.",
    )
    parser.add_argument("--no-sanitize", action="store_true",
                        help="final only: turn the input layers off.")
    parser.add_argument("--legacy-prompt", action="store_true",
                        help="final only: keep the 2.1-6.1 answer prompt, to separate the "
                             "prompt's effect from the guardrail's.")
    parser.add_argument(
        "--model",
        default=None,
        help="6.1 and final only: OpenRouter model for every agent role and the answer "
             "(default: the 5.1 model).",
    )
    parser.add_argument(
        "--table-model",
        default=None,
        help="6.1 and final only: a separate OpenRouter model for the table planner "
             "(default: --model).",
    )
    parser.add_argument(
        "--experiment-name",
        default=None,
        help="Default: survivor_cost_6_1 for 5.1; survivor_6_1 (plus the models when given) "
             "for 6.1; survivor_final__grounding_<policy> for final.",
    )
    parser.add_argument("--limit", type=int, default=None, help="First N questions only.")
    parser.add_argument("--question-id", dest="question_ids", action="append", default=None)
    parser.add_argument("--prices", type=Path, default=PRICES_PATH)
    parser.add_argument("--self-check", action="store_true", help="Run the offline checks and exit.")
    args = parser.parse_args(argv)
    if args.survivor == "5.1" and (args.model or args.table_model):
        parser.error("--model and --table-model apply to --survivor 6.1 or final only.")
    if args.survivor != "final" and (args.grounding != "surface" or args.no_sanitize or args.legacy_prompt):
        parser.error("--grounding, --no-sanitize and --legacy-prompt apply to --survivor final only.")
    if args.experiment_name is None:
        if args.survivor == "5.1":
            args.experiment_name = "survivor_cost_6_1"
        elif args.survivor == "final":
            short = lambda model: model.split("/")[-1].removesuffix(":free")
            args.experiment_name = (
                f"survivor_final__grounding_{args.grounding}"
                + ("__no_sanitize" if args.no_sanitize else "")
                + ("__legacy_prompt" if args.legacy_prompt else "")
                + (f"__{short(args.model)}" if args.model else "")
            )
        else:
            short = lambda model: model.split("/")[-1].removesuffix(":free")
            args.experiment_name = "survivor_6_1" + (f"__{short(args.model)}" if args.model else "") + (
                f"__planner_{short(args.table_model)}" if args.table_model else ""
            )
    return args


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.self_check:
        sys.exit(0 if self_check() else 1)
    if not self_check(verbose=False):
        sys.exit("Telemetry self-check failed — run --self-check for details.")

    gt_path = args.gt_set.expanduser().resolve()
    output_dir = (args.output_dir or OUTPUT_ROOT / gt_path.stem).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    h = load_harness_5_1()

    dataset = h.build_ragas_dataset(
        gt_path=gt_path,
        output_dir=output_dir,
        dataset_suffix="cost_inputs",
        limit=args.limit,
        question_ids=args.question_ids,
    )
    rows = [row if isinstance(row, dict) else row.model_dump() for row in dataset]
    recorder = UsageRecorder({row["question"]: row["question_id"] for row in rows})

    if args.survivor == "final":
        print("Loading the Checkpoint 7.1 survivor agent...")
        sys.path.insert(0, str(_HERE.parent / "Capstone Checkpoint 7.1"))
        from survivor_agent_final import (
            build_experiment_final,
            build_survivor_final,
            describe_survivor_final,
        )
        from wikipedia_retrieval_engine.wiki_agents.prompts import (
            GUARDED_ANSWER_SYSTEM_PROMPT,
            LEGACY_ANSWER_SYSTEM_PROMPT,
        )

        survivor = build_survivor_final(
            "cost_tests",  # log_root defaults to Checkpoint 7.1/logs
            model=args.model,
            table_model=args.table_model,
            policy=args.grounding,
            sanitize_input=not args.no_sanitize,
            answer_system_prompt=(
                LEGACY_ANSWER_SYSTEM_PROMPT if args.legacy_prompt else GUARDED_ANSWER_SYSTEM_PROMPT
            ),
        )
        experiment = build_experiment_final(
            TelemetryGraph(survivor.graph, recorder),
            TelemetryAnswerLLM(survivor.agent_llm, recorder),
            h.make_judge(),
            h.RateLimitBackoff(),
            args.experiment_name,
            survivor,
        )
        description = describe_survivor_final(survivor)
    elif args.survivor == "6.1":
        print("Loading the 6.1 survivor agent...")
        survivor = build_survivor_6_1("cost_tests", model=args.model, table_model=args.table_model)
        experiment = build_experiment_6_1(
            TelemetryGraph(survivor.graph, recorder),
            TelemetryAnswerLLM(survivor.agent_llm, recorder),
            h.make_judge(),
            h.RateLimitBackoff(),
            args.experiment_name,
            survivor,
        )
        description = describe_survivor_6_1(survivor)
    else:
        print("Loading the 5.1 survivor agent...")
        survivor = build_survivor_agent("cost_tests")
        experiment = h.build_agentic_experiment(
            TelemetryGraph(survivor.graph, recorder),
            TelemetryAnswerLLM(survivor.agent_llm, recorder),
            h.make_judge(),
            h.RateLimitBackoff(),
            args.experiment_name,
        )
        description = describe_survivor(h)
    print(
        f"Cost test — history OFF, {len(rows)} question(s) from {gt_path.name}, "
        f"experiment {args.experiment_name}\n"
        f"{description}\n"
        f"  AgentState logs={survivor.run_logger.run_directory}"
    )
    results = await experiment.arun(dataset)
    h.print_score_summary(results)
    h.save_results(results, output_dir)
    write_telemetry(recorder, output_dir / "telemetry", results.name, load_prices(args.prices))
    print_role_summary(recorder)


if __name__ == "__main__":
    asyncio.run(main())

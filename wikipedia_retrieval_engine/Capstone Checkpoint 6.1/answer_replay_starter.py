r"""Checkpoint 6.1 answer replay — re-answer saved 5.1 runs with another context or answer model.

Run from the repository root (rag_and_context_engineering/):

    # zero cost: rebuild every context, check it against the 5.1 results, and
    # estimate what a replay would change and cost
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/answer_replay_starter.py" --dry-run

    # Experiment 1: 5.1 sections (control) against whole articles, both rules
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/answer_replay_starter.py" \
        --rules sections whole_per_question whole_per_article

    # smoke test: one question in one saved run
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/answer_replay_starter.py" \
        --question-id VAL11 --runs validation --limit-runs 1

    # summarize a finished replay again (no API calls)
    python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/answer_replay_starter.py" \
        --summarize "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/replay_tests/<run stamp>"

Why a replay
------------
The 5.1 AgentState logs hold each question's final state: the kept articles, their
table flags, and every evidence item. Rebuilt from a log, the answer context is the
one the 5.1 answer model read, character for character; every replay checks this
against ``context_characters`` in the 5.1 results before it spends anything. A
change to what the answer model reads (the context rule, or the answer model
itself) is therefore tested on the agent's saved selections: only answer and judge
calls are paid, and a quality difference is attributable to the change alone.

Arms and sharing
----------------
Each (context rule, answer model) pair is an arm. A question-run (one question in
one saved 5.1 run) is replayed when the requested rules give it different contexts,
or always with ``--all``. Within a question-run, arms with the same context and
model share one answer and one verdict: their paired difference is exactly 0 and
no call is paid twice. Every arm is graded by the 5.1 judge.

Outputs in ``replay_tests/<run stamp>/``
----------------------------------------
    answer_calls.csv   one row per (question-run, arm): context size, tokens (input,
                       cached, output, reasoning), latency, list / billed / provider
                       cost, verdict, response
    run_config.json    arguments, selected source runs, judge, prices used
    summary.md         quality per arm (replayed question-runs and projected full
                       sets), paired differences, cost and latency per arm
"""

# %%
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    _HERE = Path.cwd()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from survivor_agent import ENGINE, load_harness_5_1  # noqa: E402  (also puts the package on sys.path)
from usage_accounting import PRICES_PATH, call_cost, load_prices, price_for, usage_from_message  # noqa: E402

from wikipedia_retrieval_engine.retrievers.corpus import build_or_load_markdown_store  # noqa: E402
from wikipedia_retrieval_engine.retrievers.llm import build_answer_messages, make_llm  # noqa: E402
from wikipedia_retrieval_engine.wiki_agents.agentic_models import ArticleReview, EvidenceItem  # noqa: E402
from wikipedia_retrieval_engine.wiki_agents.answer_context import (  # noqa: E402
    CONTEXT_RULES,
    WHOLE_ARTICLE_STAGE,
    build_answer_evidence,
    kept_reviews,
    needs_table,
)

OUTPUT_ROOT = _HERE / "replay_tests"
LOG_ROOT_5_1 = ENGINE / "Capstone Checkpoint 5.1" / "logs"
RESULTS_5_1 = {
    "validation": ENGINE / "Capstone Checkpoint 5.1" / "ragas_validation_GT_5.1" / "experiments",
    "gt": ENGINE / "Capstone Checkpoint 5.1" / "ragas_test_GT_5.1" / "experiments",
}
DEFAULT_MODEL = "openai/gpt-5.4-mini"  # the 5.1 answer model
NO_EVIDENCE_RESPONSE = "I cannot answer because no relevant Wikipedia sections were retrieved."
SCORE_VALUE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

# All calls of one 5.1 survivor question-run, judge included, measured in OpenRouter
# analytics (README 6.1 - performance and cost, Finding 1). Answer-cost changes are
# expressed as a share of these totals.
SURVIVOR_LIST_COST_PER_QUESTION = 0.0415
SURVIVOR_BILLED_COST_PER_QUESTION = 0.0313

# Assumptions used by --dry-run only, from the first smoke test (2026-09-27): answers
# returned 209-233 output tokens; two judge calls used 1,218 input and 133 output tokens.
# Input tokens need no assumption: tiktoken's count matched OpenRouter's within 1 token.
EST_ANSWER_OUTPUT_TOKENS = 250
EST_JUDGE_INPUT_TOKENS = 610
EST_JUDGE_OUTPUT_TOKENS = 70


@dataclass(frozen=True)
class SourceRun:
    """One saved 5.1 survivor run: its results CSV and its AgentState log folder."""

    set_name: str
    results_csv: str  # file stem in RESULTS_5_1[set_name]
    log_folder: str  # folder in LOG_ROOT_5_1


# The seven survivor runs of record (README 5.1). The CSV-to-log mapping is the one
# verified in README 6.1 - performance and cost, Finding 3.
SURVIVOR_RUNS = (
    SourceRun("validation", "distracted_dorsey", "2026_09_23_11_28_19"),
    SourceRun("validation", "cranky_stallman", "2026_09_23_11_44_15"),
    SourceRun("validation", "eager_rossum", "2026_09_23_11_55_11"),
    SourceRun("validation", "objective_hopper", "2026_09_23_12_05_45"),
    SourceRun("gt", "zealous_liskov", "2026_09_23_10_29_40"),
    SourceRun("gt", "happy_hopper", "2026_09_23_11_03_04"),
    SourceRun("gt", "stoic_postel", "2026_09_23_11_13_11"),
)


@dataclass(frozen=True)
class Arm:
    """One experimental condition: a context rule read by an answer model."""

    rule: str
    model: str

    @property
    def name(self) -> str:
        return f"{self.rule}|{self.model}"


@dataclass
class QuestionRun:
    """One question in one saved 5.1 run, with its final agent state."""

    source: SourceRun
    row: dict[str, str]  # the 5.1 results row
    state: dict[str, Any]  # AgentState holding ArticleReview / EvidenceItem objects

    @property
    def question_id(self) -> str:
        return self.row["question_id"]

    @property
    def question(self) -> str:
        return self.row["question"]


# %% [markdown]
# ## Loading the saved runs and rebuilding contexts

# %%
def state_from_log(final_state: dict[str, Any]) -> dict[str, Any]:
    """Turn a logged final state (JSON) back into the objects the context rules read."""

    state = dict(final_state)
    state["article_reviews"] = [ArticleReview.model_validate(r) for r in final_state.get("article_reviews", [])]
    state["evidence"] = [EvidenceItem.model_validate(e) for e in final_state.get("evidence", [])]
    return state


def load_question_runs(sources: list[SourceRun], question_ids: list[str] | None = None) -> list[QuestionRun]:
    """Pair every AgentState log of the selected runs with its 5.1 results row."""

    runs: list[QuestionRun] = []
    for source in sources:
        csv_path = RESULTS_5_1[source.set_name] / f"{source.results_csv}.csv"
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = {row["question"].strip(): row for row in csv.DictReader(handle)}
        logs = sorted((LOG_ROOT_5_1 / source.log_folder).glob("*.evidence.json"))
        if len(logs) != len(rows):
            raise ValueError(f"{source.log_folder}: {len(logs)} logs but {len(rows)} rows in {csv_path.name}")
        for path in logs:
            payload = json.loads(path.read_text(encoding="utf-8"))
            row = rows.get(payload["question"].strip())
            if row is None:
                raise ValueError(f"{path.name}: its question is not in {csv_path.name}")
            if question_ids and row["question_id"] not in question_ids:
                continue
            runs.append(QuestionRun(source, row, state_from_log(payload["final_state"])))
    return runs


class ContextBuilder:
    """Answer contexts per rule, formatted exactly as the 5.1 harness formats them."""

    def __init__(self, format_evidence: Callable[[list[EvidenceItem]], str], store: Any):
        self._format = format_evidence
        self._store = store
        self._texts: dict[str, str | None] = {}

    def load_text(self, source: str) -> str | None:
        if source not in self._texts:
            self._texts[source] = self._store.load(source).markdown if self._store.has_article(source) else None
        return self._texts[source]

    def build(self, qrun: QuestionRun, rule: str) -> tuple[str, list[str]]:
        """The context under ``rule`` and the articles it sends whole."""

        evidence = build_answer_evidence(qrun.state, rule, self.load_text)
        whole = [item.source_article for item in evidence if item.metadata.get("retrieval_stage") == WHOLE_ARTICLE_STAGE]
        return self._format(evidence), whole


def table_pattern(qrun: QuestionRun) -> str:
    """How the kept articles' table flags combine: the per-question / per-article split."""

    flags = [needs_table(review) for review in kept_reviews(qrun.state)]
    if not flags:
        return "no kept article"
    if not any(flags):
        return "no table"
    return "all table" if all(flags) else "mixed"


def make_token_counter() -> Callable[[str], int]:
    """Token count for estimates: tiktoken's o200k_base (GPT-5 family), else chars / 3.3."""

    try:
        import tiktoken

        encoding = tiktoken.get_encoding("o200k_base")
        return lambda text: len(encoding.encode(text, disallowed_special=()))
    except Exception:  # tiktoken missing or its encoding file unavailable offline
        return lambda text: round(len(text) / 3.3)


def estimate_input_tokens(count: Callable[[str], int], question: str, context: str) -> int:
    """Estimated prompt tokens of the answer call (system prompt + context + question)."""

    return sum(count(str(message.content)) + 4 for message in build_answer_messages(question, context)) + 3


@dataclass
class PlannedRun:
    """A question-run with its context and whole-article list per requested rule."""

    qrun: QuestionRun
    contexts: dict[str, tuple[str, list[str]]]

    @property
    def changed(self) -> bool:
        return len({context for context, _ in self.contexts.values()}) > 1


def plan_replay(qruns: list[QuestionRun], rules: list[str], builder: ContextBuilder) -> list[PlannedRun]:
    """Build every context and check the rebuilt 5.1 context against the results CSV."""

    planned, mismatches = [], []
    for qrun in qruns:
        sections, _ = builder.build(qrun, "sections")
        if len(sections) != int(qrun.row["context_characters"]):
            mismatches.append(f"{qrun.source.log_folder}/{qrun.question_id}")
        contexts = {rule: builder.build(qrun, rule) if rule != "sections" else (sections, []) for rule in rules}
        planned.append(PlannedRun(qrun, contexts))
    if mismatches:
        raise RuntimeError(
            "Rebuilt 5.1 contexts do not match context_characters for "
            f"{len(mismatches)} question-run(s), so a replay would not be faithful: {mismatches[:5]}"
        )
    return planned


# %% [markdown]
# ## Answering and judging

# %%
CALL_FIELDS = [
    "set", "source_run", "log_folder", "question_id", "table_pattern", "rule", "model", "arm",
    "shared_answer", "context_chars", "whole_articles", "est_input_tokens", "input_tokens",
    "cached_input_tokens", "output_tokens", "reasoning_tokens", "latency_s", "list_cost_usd",
    "billed_est_usd", "provider_cost_usd", "status", "verdict", "original_verdict",
    "original_context_chars", "served_model", "response",
]


def answer_and_judge(llm: Any, judge: Any, h: Any, qrun: QuestionRun, context: str, backoff: Any) -> dict[str, Any]:
    """One answer call on ``context`` and one 5.1 judge call on its response."""

    result: dict[str, Any] = {"status": "ok", "latency_s": 0.0, **usage_from_message(None)}
    if not context.strip():
        result.update(status="no_evidence", response=NO_EVIDENCE_RESPONSE)
    else:
        messages = build_answer_messages(qrun.question, context)
        started: dict[str, float] = {}

        def call() -> Any:
            started["at"] = time.perf_counter()  # restarted per attempt: rate-limit waits are not latency
            return llm.invoke(messages)

        try:
            reply = h.call_with_rate_limit_backoff(call, backoff, label=f"answer for {qrun.question_id}")
        except Exception as error:  # a failed model keeps the replay going; the row records why
            return {**result, "status": f"error:{type(error).__name__}", "response": str(error)[:500], "verdict": ""}
        result.update(usage_from_message(reply), latency_s=time.perf_counter() - started["at"])
        result["response"] = reply.content if isinstance(reply.content, str) else str(reply.content)

    try:
        score = h.call_with_rate_limit_backoff(
            lambda: h.correctness_metric.score(llm=judge, response=result["response"], grading_notes=qrun.row["grading_notes"]),
            backoff,
            label=f"judge for {qrun.question_id}",
        )
        result["verdict"] = score.value
    except Exception as error:
        result.update(status=f"judge_error:{type(error).__name__}", verdict="")
    return result


def run_replay(
    planned: list[PlannedRun],
    arms: list[Arm],
    h: Any,
    prices: dict,
    out_dir: Path,
    count_tokens: Callable[[str], int],
) -> Path:
    """Answer and judge every planned question-run in every arm; one CSV row per arm."""

    judge = h.make_judge()
    backoff = h.RateLimitBackoff()
    llms = {model: make_llm(model=model, app_title="WRE replay answer") for model in dict.fromkeys(a.model for a in arms)}
    calls_path = out_dir / "answer_calls.csv"
    with calls_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALL_FIELDS)
        writer.writeheader()
        for number, plan in enumerate(planned, 1):
            qrun = plan.qrun
            answered: dict[tuple[str, str], dict[str, Any]] = {}
            for arm in arms:
                context, whole = plan.contexts[arm.rule]
                key = (arm.model, hashlib.sha1(context.encode("utf-8")).hexdigest())
                shared = key in answered
                if not shared:
                    answered[key] = answer_and_judge(llms[arm.model], judge, h, qrun, context, backoff)
                result = answered[key]
                # Priced by the requested model id: OpenRouter bills it, and a served
                # name can differ (a dated snapshot, or a free model without ":free").
                cost = call_cost(
                    result["input_tokens"], result["cached_input_tokens"], result["output_tokens"],
                    price_for(arm.model, prices),
                )
                writer.writerow(
                    {
                        "set": qrun.source.set_name,
                        "source_run": qrun.source.results_csv,
                        "log_folder": qrun.source.log_folder,
                        "question_id": qrun.question_id,
                        "table_pattern": table_pattern(qrun),
                        "rule": arm.rule,
                        "model": arm.model,
                        "arm": arm.name,
                        "shared_answer": shared,
                        "context_chars": len(context),
                        "whole_articles": "; ".join(whole),
                        "est_input_tokens": estimate_input_tokens(count_tokens, qrun.question, context),
                        "input_tokens": result["input_tokens"],
                        "cached_input_tokens": result["cached_input_tokens"],
                        "output_tokens": result["output_tokens"],
                        "reasoning_tokens": result["reasoning_tokens"],
                        "latency_s": round(result["latency_s"], 3),
                        "list_cost_usd": cost["list"],
                        "billed_est_usd": cost["billed"],
                        "provider_cost_usd": result["provider_cost_usd"],
                        "status": result["status"],
                        "verdict": result.get("verdict", ""),
                        "original_verdict": qrun.row["score"],
                        "original_context_chars": qrun.row["context_characters"],
                        "served_model": result["model"],
                        "response": result.get("response", ""),
                    }
                )
                handle.flush()  # a crash keeps every paid result
                print(
                    f"[{number}/{len(planned)}] {qrun.question_id} ({qrun.source.results_csv}) {arm.name}: "
                    f"{len(context):,} chars, {result['input_tokens']:,} in / {result['output_tokens']:,} out, "
                    f"{result['latency_s']:.1f}s, {result.get('verdict') or result['status']}"
                    + (" (shared)" if shared else "")
                )
    return calls_path


# %% [markdown]
# ## Summary (also runs on a finished replay with --summarize)

# %%
def _number(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _fmt(value: float | None, pattern: str = "{:.3f}") -> str:
    return "n/a" if value is None else pattern.format(value)


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]


def _wilcoxon_p(differences: list[float]) -> float | None:
    nonzero = [d for d in differences if d]
    if len(nonzero) < 2:
        return None
    try:
        from scipy.stats import wilcoxon

        return float(wilcoxon(nonzero).pvalue)
    except Exception:
        return None


def summarize(run_dir: Path) -> str:
    """Quality, paired differences, cost, and latency per arm, as Markdown."""

    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    with (run_dir / "answer_calls.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    arms = [Arm(**arm) for arm in config["arms"]]
    for row in rows:
        row["quality"] = SCORE_VALUE.get(row["verdict"])
        for field in ("list_cost_usd", "billed_est_usd", "provider_cost_usd", "latency_s"):
            row[field] = _number(row[field])
        for field in ("context_chars", "input_tokens", "cached_input_tokens", "output_tokens", "est_input_tokens"):
            row[field] = int(_number(row[field]) or 0)
        row["shared_answer"] = row["shared_answer"] == "True"
    by_arm: dict[str, dict[tuple[str, str], dict]] = defaultdict(dict)
    for row in rows:
        by_arm[row["arm"]][(row["log_folder"], row["question_id"])] = row

    lines = [f"# Answer replay summary: {run_dir.name}", ""]
    n_runs = len({key for arm_rows in by_arm.values() for key in arm_rows})
    lines += [
        f"Replayed question-runs: {n_runs}. Judge: {config['judge_model']}. "
        f"Unchanged question-runs keep their 5.1 verdicts in the projections.",
        "",
        "## Quality on the replayed question-runs",
        "",
        "| Arm | n | Quality | Pass | Partial | Fail | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in arms:
        arm_rows = list(by_arm[arm.name].values())
        verdicts = Counter(r["verdict"] for r in arm_rows)
        scored = [r["quality"] for r in arm_rows if r["quality"] is not None]
        lines.append(
            f"| {arm.name} | {len(arm_rows)} | {_fmt(_mean(scored))} | {verdicts['pass']} | "
            f"{verdicts['partial']} | {verdicts['fail']} | {len(arm_rows) - len(scored)} |"
        )

    # Paired comparisons: one factor at a time.
    pairs: list[tuple[Arm, Arm]] = []
    for arm in arms:
        control_rule = Arm("sections", arm.model)
        if arm.rule != "sections" and control_rule in arms:
            pairs.append((arm, control_rule))
        control_model = Arm(arm.rule, arms[0].model)
        if arm.model != arms[0].model and control_model in arms:
            pairs.append((arm, control_model))
    if pairs:
        lines += [
            "",
            "## Paired differences (same question-run, one factor changed)",
            "",
            "| Arm | Against | Pairs | Mean difference | Better | Worse | Same | Wilcoxon p |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for arm, control in pairs:
            diffs = [
                row["quality"] - by_arm[control.name][key]["quality"]
                for key, row in by_arm[arm.name].items()
                if key in by_arm[control.name]
                and row["quality"] is not None
                and by_arm[control.name][key]["quality"] is not None
            ]
            lines.append(
                f"| {arm.name} | {control.name} | {len(diffs)} | {_fmt(_mean(diffs), '{:+.3f}')} | "
                f"{sum(d > 0 for d in diffs)} | {sum(d < 0 for d in diffs)} | {sum(d == 0 for d in diffs)} | "
                f"{_fmt(_wilcoxon_p(diffs), '{:.3f}')} |"
            )

    control = Arm("sections", DEFAULT_MODEL)
    if control in arms:
        replayed = [r for r in by_arm[control.name].values() if r["quality"] is not None]
        drift = [r["quality"] - SCORE_VALUE[r["original_verdict"]] for r in replayed if r["original_verdict"] in SCORE_VALUE]
        lines += [
            "",
            "## Noise floor",
            "",
            f"The control ({control.name}) re-answers the exact 5.1 contexts. Its verdict differs from the "
            f"original 5.1 verdict on {sum(d != 0 for d in drift)} of {len(drift)} question-runs "
            f"(mean difference {_fmt(_mean(drift), '{:+.3f}')}): the run-to-run variation of the answer model "
            f"and the judge on identical input.",
        ]

    # Projection onto the full selected runs: replayed verdicts where replayed, 5.1 verdicts elsewhere.
    originals: dict[str, list[dict[str, str]]] = {}
    for source in config["sources"]:
        with (RESULTS_5_1[source["set_name"]] / f"{source['results_csv']}.csv").open(newline="", encoding="utf-8") as handle:
            originals[source["log_folder"]] = list(csv.DictReader(handle))
    sets = sorted({s["set_name"] for s in config["sources"]}, key=lambda s: (s != "validation", s))
    lines += [
        "",
        "## Projected quality on the selected runs",
        "",
        "Replayed verdicts on the replayed question-runs, 5.1 verdicts on the rest. Only arms that use "
        f"the 5.1 answer model ({DEFAULT_MODEL}) or replayed every question-run are projected.",
        "",
        "| Arm | " + " | ".join(f"{s} ({sum(x['set_name'] == s for x in config['sources'])} runs)" for s in sets) + " |",
        "| --- | " + " | ".join("---:" for _ in sets) + " |",
    ]
    n_total = sum(len(v) for v in originals.values())
    for label, arm in [("5.1 as recorded", None), *[(a.name, a) for a in arms]]:
        if arm is not None and arm.model != DEFAULT_MODEL and len(by_arm[arm.name]) < n_total:
            continue
        cells = []
        for set_name in sets:
            run_scores = []
            for source in (s for s in config["sources"] if s["set_name"] == set_name):
                values = []
                for original in originals[source["log_folder"]]:
                    replayed_row = by_arm[arm.name].get((source["log_folder"], original["question_id"])) if arm else None
                    if replayed_row is not None and replayed_row["quality"] is not None:
                        values.append(replayed_row["quality"])
                    else:
                        values.append(SCORE_VALUE[original["score"]])
                run_scores.append(statistics.fmean(values))
            cells.append(_fmt(_mean(run_scores)))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Cost and latency per answer call (replayed question-runs)",
        "",
        "List price charges every input token at the full rate (no caching): the fair comparison, because "
        "repeated runs of the same prompt get cache hits that distinct user questions would not.",
        "",
        "| Arm | Context chars | Input tokens | Cached share | Output tokens | List $ | Billed $ | "
        "Provider $ | Latency median | Latency p90 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in arms:
        arm_rows = [r for r in by_arm[arm.name].values() if r["status"] in ("ok", "no_evidence")]
        tokens_in = sum(r["input_tokens"] for r in arm_rows)
        cached = sum(r["cached_input_tokens"] for r in arm_rows)
        latencies = [r["latency_s"] for r in arm_rows if r["latency_s"]]
        provider = [r["provider_cost_usd"] for r in arm_rows if r["provider_cost_usd"] is not None]
        lines.append(
            f"| {arm.name} | {_fmt(_mean([r['context_chars'] for r in arm_rows]), '{:,.0f}')} | "
            f"{_fmt(_mean([r['input_tokens'] for r in arm_rows]), '{:,.0f}')} | "
            f"{_fmt(cached / tokens_in if tokens_in else None, '{:.0%}')} | "
            f"{_fmt(_mean([r['output_tokens'] for r in arm_rows]), '{:,.0f}')} | "
            f"{_fmt(_mean([r['list_cost_usd'] for r in arm_rows if r['list_cost_usd'] is not None]), '{:.5f}')} | "
            f"{_fmt(_mean([r['billed_est_usd'] for r in arm_rows if r['billed_est_usd'] is not None]), '{:.5f}')} | "
            f"{_fmt(_mean(provider), '{:.5f}')} | "
            f"{_fmt(statistics.median(latencies) if latencies else None, '{:.1f}s')} | {_fmt(_p90(latencies), '{:.1f}s')} |"
        )

    if control in arms:
        lines += [
            "",
            "## Answer cost per question-run over the selected runs",
            "",
            f"Change against the control, spread over all {n_total} question-runs of the selected runs "
            "(unchanged question-runs add 0), and as a share of a whole 5.1 question-run "
            f"(${SURVIVOR_LIST_COST_PER_QUESTION} at list price, ${SURVIVOR_BILLED_COST_PER_QUESTION} billed, "
            "from OpenRouter analytics).",
            "",
            "| Arm | Change, list | Share of question, list | Change, billed | Share of question, billed |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for arm in arms:
            if arm.model != control.model or arm == control:
                continue
            deltas = {"list_cost_usd": 0.0, "billed_est_usd": 0.0}
            for key, row in by_arm[arm.name].items():
                base = by_arm[control.name].get(key)
                for field in deltas:
                    if base and row[field] is not None and base[field] is not None:
                        deltas[field] += row[field] - base[field]
            per_list, per_billed = deltas["list_cost_usd"] / n_total, deltas["billed_est_usd"] / n_total
            lines.append(
                f"| {arm.name} | {per_list:+.5f} | {per_list / SURVIVOR_LIST_COST_PER_QUESTION:+.1%} | "
                f"{per_billed:+.5f} | {per_billed / SURVIVOR_BILLED_COST_PER_QUESTION:+.1%} |"
            )

    paid = [r for r in rows if not r["shared_answer"] and r["status"] == "ok"]
    provider_paid = [r["provider_cost_usd"] for r in paid if r["provider_cost_usd"] is not None]
    lines += [
        "",
        f"**Spend of this replay:** {len(paid)} answer calls, ${sum(r['list_cost_usd'] or 0 for r in paid):.4f} at "
        f"list price, ${sum(r['billed_est_usd'] or 0 for r in paid):.4f} billed estimate"
        + (f", ${sum(provider_paid):.4f} reported by OpenRouter" if provider_paid else "")
        + f"; plus {len({(r['log_folder'], r['question_id'], r['arm']) for r in paid})} judge calls "
        "(not metered here; OpenRouter origin .../judge).",
    ]
    return "\n".join(lines) + "\n"


# %% [markdown]
# ## Dry run (zero cost)

# %%
def dry_run(
    planned: list[PlannedRun],
    rules: list[str],
    models: list[str],
    prices: dict,
    count_tokens,
    replay_all: bool = False,
) -> None:
    """Print what a replay would change and an estimate of what it would cost."""

    print(f"\nControl check passed: {len(planned)}/{len(planned)} rebuilt 5.1 contexts match context_characters.")

    patterns: dict[str, Counter] = defaultdict(Counter)
    mixed: dict[str, list[str]] = defaultdict(list)
    for plan in planned:
        pattern = table_pattern(plan.qrun)
        patterns[plan.qrun.source.set_name][pattern] += 1
        if pattern == "mixed":
            whole = [r.source_article for r in kept_reviews(plan.qrun.state) if not needs_table(r)]
            tables = [r.source_article for r in kept_reviews(plan.qrun.state) if needs_table(r)]
            mixed[plan.qrun.question_id].append(f"whole {', '.join(whole)} | table {', '.join(tables)}")
    print("\nQuestion-runs by the table flags of their kept articles:")
    print(f"  {'set':12}{'no table':>10}{'mixed':>8}{'all table':>11}{'no kept':>9}")
    for set_name, counts in patterns.items():
        print(
            f"  {set_name:12}{counts['no table']:>10}{counts['mixed']:>8}{counts['all table']:>11}"
            f"{counts['no kept article']:>9}"
        )
    if mixed:
        print("\nMixed question-runs (whole_per_article sends the non-table articles whole):")
        for question_id, variants in sorted(mixed.items()):
            for variant, times in Counter(variants).items():
                print(f"  {question_id} x{times}: {variant.replace('.html', '')}")

    selected = planned if replay_all else [plan for plan in planned if plan.changed]
    print(
        f"\nQuestion-runs to replay: {len(selected)} of {len(planned)} "
        + ("(--all)" if replay_all else "(those whose context differs between the requested rules)")
    )
    print(f"  {'rule':22}{'differs from sections':>22}{'mean chars':>12}{'est. input tokens':>19}")
    for rule in rules:
        differs = sum(1 for p in selected if p.contexts[rule][0] != p.contexts.get("sections", ("",))[0])
        sizes = [len(p.contexts[rule][0]) for p in selected]
        tokens = [estimate_input_tokens(count_tokens, p.qrun.question, p.contexts[rule][0]) for p in selected]
        print(f"  {rule:22}{differs:>22}{_fmt(_mean(sizes), '{:,.0f}'):>12}{_fmt(_mean(tokens), '{:,.0f}'):>19}")

    judge_price = price_for(DEFAULT_MODEL, prices)
    for model in models:
        calls, input_tokens = 0, 0
        for plan in selected:
            for context in {plan.contexts[rule][0] for rule in rules}:
                calls += 1
                input_tokens += estimate_input_tokens(count_tokens, plan.qrun.question, context)
        answers = call_cost(input_tokens, 0, calls * EST_ANSWER_OUTPUT_TOKENS, price_for(model, prices))
        judging = call_cost(calls * EST_JUDGE_INPUT_TOKENS, 0, calls * EST_JUDGE_OUTPUT_TOKENS, judge_price)
        total = None if answers["list"] is None else answers["list"] + (judging["list"] or 0)
        print(
            f"\n{model}: {calls} answer calls after sharing identical contexts, {input_tokens:,} input tokens.\n"
            f"  Estimated list-price cost: answers {_fmt(answers['list'], '${:.2f}')} "
            f"(assuming ~{EST_ANSWER_OUTPUT_TOKENS} output tokens each) + judge {_fmt(judging['list'], '${:.2f}')} "
            f"= {_fmt(total, '${:.2f}')}"
        )


# %%
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Checkpoint 6.1 answer replay over saved 5.1 runs.")
    parser.add_argument("--runs", choices=["validation", "gt", "all"], default="all")
    parser.add_argument("--limit-runs", type=int, default=None, help="First N saved runs per set only.")
    parser.add_argument("--question-id", dest="question_ids", action="append", default=None)
    parser.add_argument("--rules", nargs="+", choices=CONTEXT_RULES, default=list(CONTEXT_RULES))
    parser.add_argument("--models", nargs="+", default=[DEFAULT_MODEL], help="Answer models (OpenRouter ids).")
    parser.add_argument("--all", dest="replay_all", action="store_true", help="Replay unchanged question-runs too.")
    parser.add_argument("--dry-run", action="store_true", help="Build contexts and estimate cost; no API calls.")
    parser.add_argument("--summarize", type=Path, default=None, help="Summarize a finished replay folder and exit.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--prices", type=Path, default=PRICES_PATH)
    return parser.parse_args()


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True, cwd=_HERE
        ).stdout.strip()
    except Exception:
        return None


def main() -> None:
    args = parse_args()
    if args.summarize:
        summary = summarize(args.summarize.expanduser().resolve())
        print(summary)
        (args.summarize / "summary.md").write_text(summary, encoding="utf-8")
        return

    sources = [s for s in SURVIVOR_RUNS if args.runs in ("all", s.set_name)]
    if args.limit_runs:
        sources = [s for s in sources if [x for x in sources if x.set_name == s.set_name].index(s) < args.limit_runs]
    qruns = load_question_runs(sources, args.question_ids)
    if not qruns:
        sys.exit("No question-runs selected.")

    h = load_harness_5_1()
    builder = ContextBuilder(h.format_section_evidence, build_or_load_markdown_store())
    prices = load_prices(args.prices)
    count_tokens = make_token_counter()
    planned = plan_replay(qruns, args.rules, builder)
    print(f"Loaded {len(qruns)} question-runs from {len(sources)} saved 5.1 run(s).")

    if args.dry_run:
        dry_run(planned, args.rules, args.models, prices, count_tokens, replay_all=args.replay_all)
        return

    selected = planned if args.replay_all else [plan for plan in planned if plan.changed]
    if not selected:
        sys.exit("The requested rules give every selected question-run the same context; use --all to replay anyway.")
    arms = [Arm(rule, model) for model in args.models for rule in args.rules]
    missing_prices = [m for m in args.models if price_for(m, prices) is None]
    if missing_prices:
        print(f"NOTE: no price for {missing_prices}; their costs will be blank (provider cost is still recorded).")

    out_dir = args.output_dir.expanduser().resolve() / datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "run_config.json").write_text(
        json.dumps(
            {
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "git_commit": _git_commit(),
                "arguments": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
                "arms": [{"rule": a.rule, "model": a.model} for a in arms],
                "judge_model": h.JUDGE_MODEL,
                "sources": [s.__dict__ for s in sources],
                "question_runs_selected": len(planned),
                "question_runs_replayed": len(selected),
                "prices": {m: price_for(m, prices) for m in args.models},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Replaying {len(selected)} of {len(planned)} question-runs in {len(arms)} arm(s) -> {out_dir}")
    run_replay(selected, arms, h, prices, out_dir, count_tokens)
    summary = summarize(out_dir)
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    print("\n" + summary)


if __name__ == "__main__":
    main()

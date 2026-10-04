r"""Checkpoint 7.1 prompt replay: re-answer saved GT evidence with the old and the guarded prompt.

The GT baseline (README 7.1) found the 7.1 final 0.08 below the 6.1 survivor, with the
losses in the answer step on identical contexts (GT16 Joe Biden, GT05 the "Totals" row,
GT15 hedging). The two systems differ in three things at once: the answer prompt, the
grounding check, and whatever the agent happened to collect in each run. This replay
holds the evidence fixed and changes only the system prompt.

Run from ``rag_and_context_engineering/``::

    # zero cost: rebuild every saved context, verify it, and estimate the cost
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/prompt_replay.py" --dry-run

    # the replay: the questions whose verdicts differed between the systems
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/prompt_replay.py"

    # every GT question instead
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/prompt_replay.py" --all-questions

    # summarize a finished replay again (no API calls)
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/prompt_replay.py" --summarize <folder>

Design
------
- **Inputs:** the six GT baseline runs listed in ``cost_efficiency/run_manifest.csv``
  (three of each system) and their AgentState logs in ``cost_efficiency/logs/``.
- **Contexts:** rebuilt with ``analyzers/rebuild_answer_context.rebuild_row``, the same
  reconstruction the 7.1 grounding work verified. Before anything is paid, every rebuilt
  context must have exactly the length recorded in its run (``context_characters``).
- **Arms:** each saved context is answered twice, with ``LEGACY_ANSWER_SYSTEM_PROMPT``
  (2.1-6.1) and with ``GUARDED_ANSWER_SYSTEM_PROMPT`` (7.1), through the same
  ``build_answer_messages`` both systems use, on ``gpt-5.4-mini`` at the system's
  temperature. Contexts from both systems' runs are used, so the result separates the
  prompt (same context, two prompts) from the evidence (same prompt, two systems' runs).
- **Judging:** the RAGAS judge of every cost run grades the raw answer in both arms. The
  grounding label is not applied, so the judge sees only the prompt's effect; the check's
  verdict on each answer is still recorded (offline, deterministic).
- **Controls:** the arm that matches a context's own run (old prompt on a 6.1 context,
  guarded prompt on a 7.1 context) re-answers the recorded condition, which measures how
  much answers and verdicts move on identical input.

Outputs in ``cost_efficiency/replay_tests/<stamp>/``: ``answer_calls.csv`` (one row per
answer), ``run_config.json``, ``summary.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
REPO = ENGINE.parent
CHECKPOINT_6_1 = ENGINE / "Capstone Checkpoint 6.1"
COST_EFFICIENCY = HERE / "cost_efficiency"
for path in (str(REPO.parent), str(CHECKPOINT_6_1), str(HERE / "analyzers")):
    if path not in sys.path:
        sys.path.insert(0, path)

from rebuild_answer_context import _log_records, rebuild_row  # noqa: E402
from survivor_agent import load_harness_5_1  # noqa: E402
from usage_accounting import call_cost, load_prices, price_for, usage_from_message  # noqa: E402

from wikipedia_retrieval_engine.retrievers.llm import build_answer_messages, make_llm  # noqa: E402
from wikipedia_retrieval_engine.utils.analyze_ragas_experiments_efficiency import wilcoxon_p  # noqa: E402
from wikipedia_retrieval_engine.wiki_agents.grounding_check import check_grounding, evidence_haystack  # noqa: E402
from wikipedia_retrieval_engine.wiki_agents.prompts import (  # noqa: E402
    GUARDED_ANSWER_SYSTEM_PROMPT,
    LEGACY_ANSWER_SYSTEM_PROMPT,
)

MODEL = "openai/gpt-5.4-mini"
PROMPTS = {"legacy": LEGACY_ANSWER_SYSTEM_PROMPT, "guarded": GUARDED_ANSWER_SYSTEM_PROMPT}
SYSTEM_LABEL = {"6.1": "6.1 survivor", "final": "7.1 final"}
OWN_PROMPT = {"6.1": "legacy", "final": "guarded"}
SCORE_VALUE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
JUDGE_COST_ESTIMATE = 0.0008  # USD per judge call, measured in 6.1

# Answer patterns seen in the GT baseline, counted per arm.
HEDGE_RE = re.compile(
    r"\b(?:do|does|did)\s+not\s+(?:contain|support|include|state|identify|mention|show|provide)"
    r"|\bnot\s+(?:contained|supported|stated|included)\s+in\b",
    re.IGNORECASE,
)

CALL_FIELDS = [
    "question_id", "category", "source_system", "source_run", "log_folder", "arm", "own_arm",
    "context_chars", "input_tokens", "cached_input_tokens", "output_tokens", "latency_s",
    "list_cost_usd", "billed_est_usd", "provider_cost_usd", "status", "verdict", "recorded_verdict",
    "recorded_grounding_acted", "grounded", "ungrounded_spans", "hedge", "mentions_totals_row",
    "mentions_biden", "mentions_hillary", "response",
]


@dataclass
class SavedRun:
    system: str  # "6.1" or "final"
    results_csv: str
    log_folder: str


@dataclass
class Planned:
    run: SavedRun
    row: dict[str, str]
    rebuilt: Any  # rebuild_answer_context.RebuiltAnswer


def load_manifest(root: Path = COST_EFFICIENCY) -> list[SavedRun]:
    with (root / "run_manifest.csv").open(encoding="utf-8") as handle:
        return [
            SavedRun(system=row["arm"], results_csv=row["results_csv"], log_folder=row["log_folder"])
            for row in csv.DictReader(handle)
            # The replay compares the two gpt-5.4-mini baselines; later runs in the same
            # manifest (other models, routers) are not part of it.
            if row.get("exit_code") == "0" and row.get("arm") in SYSTEM_LABEL
        ]


def changed_questions(runs: list[SavedRun], root: Path = COST_EFFICIENCY) -> list[str]:
    """Questions whose mean verdict differs between the two systems' runs."""

    scores: dict[tuple[str, str], list[float]] = {}
    for run in runs:
        for row in _rows(run, root):
            scores.setdefault((run.system, row["question_id"]), []).append(SCORE_VALUE[row["score"]])
    questions = sorted({question for _, question in scores})
    return [
        question for question in questions
        if abs(statistics.mean(scores.get(("6.1", question), [0])) - statistics.mean(scores.get(("final", question), [0]))) > 1e-9
    ]


def _rows(run: SavedRun, root: Path) -> list[dict[str, str]]:
    path = root / "wikipedia_GT" / "experiments" / run.results_csv
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plan_replay(question_ids: list[str] | None, root: Path = COST_EFFICIENCY) -> list[Planned]:
    """Rebuild every selected question-run's context and verify it against its run."""

    runs = load_manifest(root)
    wanted = set(question_ids) if question_ids else None
    planned: list[Planned] = []
    mismatches: list[str] = []
    for run in runs:
        rows = _rows(run, root)
        records = _log_records(root / run.log_folder)
        for number, row in enumerate(rows, start=1):
            if wanted is not None and row["question_id"] not in wanted:
                continue
            record = records[number]
            if record["question"].strip() != row["question"].strip():
                raise RuntimeError(f"{run.results_csv} row {number}: log question does not match")
            rebuilt = rebuild_row(row, record, run=run.results_csv.removesuffix(".csv"))
            if not rebuilt.matches_recording or rebuilt.unresolved_evidence_ids:
                mismatches.append(
                    f"{run.results_csv}/{row['question_id']}: rebuilt {len(rebuilt.context)} "
                    f"recorded {rebuilt.recorded_characters} unresolved {rebuilt.unresolved_evidence_ids}"
                )
            planned.append(Planned(run, row, rebuilt))
    if mismatches:
        raise RuntimeError("Rebuilt contexts do not match their runs; a replay would not be faithful:\n" + "\n".join(mismatches))
    return planned


def estimate(planned: list[Planned], prices: dict) -> dict[str, float]:
    import tiktoken

    encoding = tiktoken.get_encoding("o200k_base")
    price = price_for(MODEL, prices)
    tokens = 0
    cost = 0.0
    for item in planned:
        for prompt in PROMPTS.values():
            messages = build_answer_messages(item.row["question"], item.rebuilt.context, system_prompt=prompt)
            count = sum(len(encoding.encode(message.content)) for message in messages) + 8
            tokens += count
            cost += call_cost(count, 0, 200, price)["list"] or 0.0
    calls = len(planned) * len(PROMPTS)
    return {
        "question_runs": len(planned),
        "answer_calls": calls,
        "input_tokens": tokens,
        "answer_list_usd": cost,
        "judge_usd": calls * JUDGE_COST_ESTIMATE,
        "total_usd": cost + calls * JUDGE_COST_ESTIMATE,
    }


def answer_and_judge(llm: Any, judge: Any, h: Any, item: Planned, arm: str, backoff: Any, prices: dict) -> dict[str, Any]:
    question_id = item.row["question_id"]
    messages = build_answer_messages(item.row["question"], item.rebuilt.context, system_prompt=PROMPTS[arm])
    started: dict[str, float] = {}

    def call() -> Any:
        started["at"] = time.perf_counter()  # restarted per attempt: rate-limit waits are not latency
        return llm.invoke(messages)

    result: dict[str, Any] = {"status": "ok"}
    try:
        reply = h.call_with_rate_limit_backoff(call, backoff, label=f"{arm} answer for {question_id}")
    except Exception as error:  # a failed call keeps the replay going; the row records why
        return {"status": f"error:{type(error).__name__}", "response": str(error)[:500], "verdict": ""}
    usage = usage_from_message(reply)
    costs = call_cost(usage["input_tokens"], usage["cached_input_tokens"], usage["output_tokens"], price_for(MODEL, prices))
    response = reply.content if isinstance(reply.content, str) else str(reply.content)
    result.update(
        input_tokens=usage["input_tokens"],
        cached_input_tokens=usage["cached_input_tokens"],
        output_tokens=usage["output_tokens"],
        provider_cost_usd=usage["provider_cost_usd"],
        list_cost_usd=costs["list"],
        billed_est_usd=costs["billed"],
        latency_s=time.perf_counter() - started["at"],
        response=response,
    )
    try:
        score = h.call_with_rate_limit_backoff(
            lambda: h.correctness_metric.score(llm=judge, response=response, grading_notes=item.row["grading_notes"]),
            backoff,
            label=f"judge for {question_id}",
        )
        result["verdict"] = score.value
    except Exception as error:
        result.update(status=f"judge_error:{type(error).__name__}", verdict="")
    return result


def markers(response: str, evidence: Any) -> dict[str, Any]:
    grounding = check_grounding(response, evidence_haystack(evidence))
    return {
        "grounded": grounding.grounded,
        "ungrounded_spans": "; ".join(grounding.failures),
        "hedge": bool(HEDGE_RE.search(response)),
        "mentions_totals_row": "Totals" in response,
        "mentions_biden": "Biden" in response,
        "mentions_hillary": "Hillary" in response,
    }


def run_replay(planned: list[Planned], out_dir: Path, prices: dict) -> Path:
    h = load_harness_5_1()
    judge = h.make_judge()
    backoff = h.RateLimitBackoff()
    llm = make_llm(model=MODEL, app_title="WRE replay answer")
    calls_path = out_dir / "answer_calls.csv"
    total = len(planned) * len(PROMPTS)
    done = 0
    with calls_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALL_FIELDS)
        writer.writeheader()
        for item in planned:
            for arm in PROMPTS:
                result = answer_and_judge(llm, judge, h, item, arm, backoff, prices)
                response = result.get("response", "")
                row = {
                    "question_id": item.row["question_id"],
                    "category": item.row.get("category", ""),
                    "source_system": item.run.system,
                    "source_run": item.run.results_csv.removesuffix(".csv"),
                    "log_folder": item.run.log_folder,
                    "arm": arm,
                    "own_arm": arm == OWN_PROMPT[item.run.system],
                    "context_chars": len(item.rebuilt.context),
                    "recorded_verdict": item.row["score"],
                    "recorded_grounding_acted": item.row.get("grounding_acted", ""),
                    **{key: result.get(key, "") for key in (
                        "input_tokens", "cached_input_tokens", "output_tokens", "latency_s", "list_cost_usd",
                        "billed_est_usd", "provider_cost_usd", "status", "verdict")},
                    **(markers(response, item.rebuilt.evidence) if result["status"] == "ok" else {}),
                    "response": response,
                }
                writer.writerow(row)
                handle.flush()
                done += 1
                print(f"[{done}/{total}] {row['question_id']} {row['source_system']:5s} {row['source_run']:22s} "
                      f"{arm:7s} -> {row['verdict'] or row['status']} (recorded {row['recorded_verdict']})", flush=True)
    return calls_path


# --------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------


def _quality(rows: list[dict[str, str]]) -> float | None:
    values = [SCORE_VALUE[row["verdict"]] for row in rows if row.get("verdict") in SCORE_VALUE]
    return statistics.mean(values) if values else None


def _fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _share(rows: list[dict[str, str]], column: str) -> str:
    ok = [row for row in rows if row.get("status") == "ok"]
    return f"{sum(row.get(column) == 'True' for row in ok)}/{len(ok)}" if ok else "n/a"


def summarize(out_dir: Path) -> str:
    with (out_dir / "answer_calls.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ok = [row for row in rows if row["verdict"] in SCORE_VALUE]
    lines = [f"# Prompt replay: legacy against guarded answer prompt ({out_dir.name})", ""]
    lines += [
        f"{len(rows)} answer calls over {len({(r['source_run'], r['question_id']) for r in rows})} saved question-runs "
        f"({len({r['question_id'] for r in rows})} GT questions); {len(ok)} judged.", "",
        "## Quality: prompt by evidence source", "",
        "| Evidence from | Legacy prompt | Guarded prompt | Recorded in the run |",
        "| --- | ---: | ---: | ---: |",
    ]
    for system in ("6.1", "final"):
        mine = [row for row in ok if row["source_system"] == system]
        recorded = {(row["source_run"], row["question_id"]): row["recorded_verdict"] for row in rows if row["source_system"] == system}
        recorded_quality = statistics.mean(SCORE_VALUE[value] for value in recorded.values()) if recorded else None
        lines.append(
            f"| {SYSTEM_LABEL[system]} runs | {_fmt(_quality([r for r in mine if r['arm'] == 'legacy']))} | "
            f"{_fmt(_quality([r for r in mine if r['arm'] == 'guarded']))} | {_fmt(recorded_quality)} |"
        )
    lines.append(
        f"| Both | {_fmt(_quality([r for r in ok if r['arm'] == 'legacy']))} | "
        f"{_fmt(_quality([r for r in ok if r['arm'] == 'guarded']))} | |"
    )

    # Paired: same context, two prompts.
    by_context: dict[tuple[str, str], dict[str, float]] = {}
    for row in ok:
        by_context.setdefault((row["source_run"], row["question_id"]), {})[row["arm"]] = SCORE_VALUE[row["verdict"]]
    diffs = [pair["guarded"] - pair["legacy"] for pair in by_context.values() if {"legacy", "guarded"} <= set(pair)]
    lines += [
        "", "## Paired: the same context under both prompts", "",
        f"- Contexts with both answers judged: {len(diffs)}",
        f"- Guarded minus legacy: {statistics.mean(diffs):+.3f} on average" if diffs else "- no pairs",
        f"- Guarded better on {sum(d > 0 for d in diffs)}, worse on {sum(d < 0 for d in diffs)}, "
        f"the same on {sum(d == 0 for d in diffs)}; Wilcoxon p = {_fmt(wilcoxon_p(diffs))}" if diffs else "",
    ]

    # Noise floor: the arm that matches the run re-answers the recorded condition.
    own = [row for row in ok if row["own_arm"] == "True"]
    moved = [row for row in own if row["verdict"] != row["recorded_verdict"]]
    lines += [
        "", "## Noise floor", "",
        f"The arm that matches each context's own run re-answers the recorded condition: "
        f"{len(moved)} of {len(own)} verdicts differ from the recorded ones "
        f"(recorded {_fmt(_quality([{'verdict': r['recorded_verdict']} for r in own]))}, "
        f"replayed {_fmt(_quality(own))}). On 7.1 contexts the recorded answers carried the grounding "
        f"label when the check acted; the replay judges the raw answer.",
    ]

    lines += ["", "## Per question", "",
              "| Question | Legacy | Guarded | Legacy hedges | Guarded hedges | Note |",
              "| --- | ---: | ---: | ---: | ---: | --- |"]
    for question in sorted({row["question_id"] for row in rows}):
        mine = [row for row in rows if row["question_id"] == question]
        legacy = [row for row in mine if row["arm"] == "legacy"]
        guarded = [row for row in mine if row["arm"] == "guarded"]
        note = ""
        if question == "GT16":
            note = (f"Joe Biden: legacy {_share(legacy, 'mentions_biden')}, guarded {_share(guarded, 'mentions_biden')}; "
                    f"Hillary: legacy {_share(legacy, 'mentions_hillary')}, guarded {_share(guarded, 'mentions_hillary')}")
        elif question == "GT05":
            note = f"'Totals' row mentioned: legacy {_share(legacy, 'mentions_totals_row')}, guarded {_share(guarded, 'mentions_totals_row')}"
        lines.append(
            f"| {question} | {_fmt(_quality(legacy), 2)} | {_fmt(_quality(guarded), 2)} | "
            f"{_share(legacy, 'hedge')} | {_share(guarded, 'hedge')} | {note} |"
        )

    lines += ["", "## Grounding check on the replayed answers (not applied; recorded only)", "",
              "| Arm | Flagged | Flagged and passed by the judge |", "| --- | ---: | ---: |"]
    for arm in PROMPTS:
        mine = [row for row in ok if row["arm"] == arm]
        flagged = [row for row in mine if row.get("grounded") == "False"]
        lines.append(f"| {arm} | {len(flagged)}/{len(mine)} | {sum(row['verdict'] == 'pass' for row in flagged)} |")

    def total(column: str) -> float:
        return sum(float(row[column]) for row in rows if row.get(column) not in ("", None))

    lines += ["", "## Cost", "",
              f"- Answer calls: ${total('list_cost_usd'):.2f} at list price, ${total('billed_est_usd'):.2f} billed estimate, "
              f"${total('provider_cost_usd'):.2f} reported by OpenRouter.",
              f"- Judge calls: about ${len(rows) * JUDGE_COST_ESTIMATE:.2f} (not in the telemetry; `…/judge` origin)."]
    text = "\n".join(line for line in lines if line is not None) + "\n"
    (out_dir / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-answer saved GT evidence with the legacy and the guarded prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Rebuild and verify every context; estimate the cost. No API calls.")
    parser.add_argument("--all-questions", action="store_true", help="Every GT question, not only those whose verdicts changed.")
    parser.add_argument("--question-id", dest="question_ids", action="append", default=None)
    parser.add_argument("--summarize", type=Path, default=None, help="Summarize a finished replay folder and exit.")
    parser.add_argument("--output-dir", type=Path, default=COST_EFFICIENCY / "replay_tests")
    args = parser.parse_args(argv)

    if args.summarize:
        print(summarize(args.summarize))
        return 0

    runs = load_manifest()
    questions = args.question_ids or (None if args.all_questions else changed_questions(runs))
    planned = plan_replay(questions)
    prices = load_prices()
    numbers = estimate(planned, prices)
    print(f"Questions: {', '.join(questions) if questions else 'all'}")
    print(f"Rebuilt and verified {numbers['question_runs']} contexts against their runs (all match).")
    print(f"Plan: {numbers['answer_calls']} answer calls + {numbers['answer_calls']} judge calls; "
          f"{numbers['input_tokens'] / 1000:.0f}K answer input tokens; estimate ${numbers['answer_list_usd']:.2f} "
          f"answers + ${numbers['judge_usd']:.2f} judge = ${numbers['total_usd']:.2f} at list price.")
    if args.dry_run:
        return 0

    out_dir = args.output_dir / datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_config.json").write_text(json.dumps({
        "model": MODEL,
        "arms": list(PROMPTS),
        "questions": questions or "all",
        "source_runs": [run.__dict__ for run in runs],
        "estimate": numbers,
        "judge": "the 5.1 harness RAGAS judge, raw answers (no grounding label)",
    }, indent=2), encoding="utf-8")
    run_replay(planned, out_dir, prices)
    print(summarize(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

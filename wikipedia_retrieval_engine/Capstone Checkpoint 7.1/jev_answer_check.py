r"""Checkpoint 7.1 answer check: can Jev tell which mini answers need gpt-5.4?

The policy under test ("verify after"): ``gpt-5.4-mini`` answers every question; Jev reads
the question, the answer, and the evidence the answer was given, and answers two yes/no
questions; when either says no, the question is answered again on ``gpt-5.4``. It is an
escalation trigger for cost, not a security guard: it reads the user's question, which the
deterministic grounding check deliberately never does.

    grounded   every fact the answer states is supported by the evidence
    complete   the answer addresses every part of the question

Run from ``rag_and_context_engineering/``::

    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/jev_answer_check.py" --dry-run
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/jev_answer_check.py"
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/jev_answer_check.py" --summarize <folder>

**Inputs:** every saved ``gpt-5.4-mini`` answer with its evidence rebuilt and verified
against the recorded ``context_characters``: the six GT baseline runs (114) and the four
validation runs of 6.1 and 7.1 (100). The judge's verdict on each is the label. The 7.1
answers are checked without the "[QUARANTINED]" label the grounding policy added.

**Jev's context limit.** Jev reads at most 32,000 tokens. A context that fits is sent
whole. A larger one is cut to the passages that mention the answer's names, numbers, and
quotations (plus the evidence-status notice), in their original order; the simulation
also reports the alternative of escalating every oversized answer without asking Jev.

**Simulation:** each cheap question-run keeps its own outcome, cost, and time, or, when
Jev says no, pays it plus that question's mean outcome, cost, and time on ``gpt-5.4``
(the saved strong runs), plus Jev's own cost and latency.

Outputs in ``cost_efficiency/answer_checks/<stamp>/``: ``jev_calls.csv``, ``summary.md``,
``run_config.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
REPO = ENGINE.parent
for path in (str(REPO), str(ENGINE / "Capstone Checkpoint 6.1"), str(HERE), str(HERE / "analyzers")):
    if path not in sys.path:
        sys.path.insert(0, path)

from rebuild_answer_context import rebuild_experiment  # noqa: E402

import prompt_replay  # noqa: E402
from wikipedia_retrieval_engine.retrievers.llm import openrouter_headers, require_api_key  # noqa: E402
from wikipedia_retrieval_engine.utils import analyze_ragas_experiments_efficiency as eff  # noqa: E402
from wikipedia_retrieval_engine.wiki_agents.grounding_check import find_entities, find_quotations  # noqa: E402

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"
# o200k tokens for question + answer + evidence. Jev's limit is 32,000 of its own tokens, which
# count higher: GT19 was rejected (max_tokens_exceeded) at 23,602 o200k evidence tokens.
STATE_TOKEN_BUDGET = 22_000
COST_EFFICIENCY = HERE / "cost_efficiency"
LABEL_RE = re.compile(r"^\[QUARANTINED\][^\n]*\n+")
NUMBER_RE = re.compile(r"\d[\d,.]*\d|\d")
THRESHOLDS = (0.3, 0.5, 0.7, 0.8, 0.9)
SCORE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

CHECKS = {
    "grounded": {
        "type": "noul",
        "instructions": "Is every fact stated in the answer supported by the evidence?",
        "criteria": {
            "true": "Every person, work, number, date, and relationship the answer states appears in the evidence "
                    "and is described there the same way.",
            "false": "The answer states a person, work, number, date, or relationship that the evidence does not "
                     "contain, or describes one differently from the evidence.",
        },
    },
    "complete": {
        "type": "noul",
        "instructions": "Does the answer fully answer every part of the question?",
        "criteria": {
            "true": "The answer gives a definite answer to every part of the question.",
            "false": "The answer leaves a part of the question unanswered, gives only part of a list or count, or "
                     "says it cannot answer.",
        },
    },
}


# --------------------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------------------


def load_cases() -> list[dict]:
    cases = []
    for item in prompt_replay.plan_replay(None):  # the six GT baseline runs, contexts verified
        cases.append({"set": "GT", "system": item.run.system, "run": item.run.results_csv.removesuffix(".csv"),
                      "question_id": item.row["question_id"], "question": item.row["question"],
                      "answer": LABEL_RE.sub("", item.row["response"]), "verdict": item.row["score"],
                      "context": item.rebuilt.context})
    for run, checkpoint in (("dazzling_minsky", None), ("nifty_mccarthy", None), ("angry_babbage", None),
                            ("awesome_valiant", HERE)):
        kwargs = {"checkpoint_dir": checkpoint} if checkpoint else {}
        for rebuilt in rebuild_experiment(run, **kwargs):
            if not rebuilt.matches_recording:
                raise RuntimeError(f"{run}/{rebuilt.question_id}: rebuilt context does not match the run")
            cases.append({"set": "VAL", "system": "final" if checkpoint else "6.1", "run": run,
                          "question_id": rebuilt.question_id, "question": rebuilt.question,
                          "answer": LABEL_RE.sub("", rebuilt.answer), "verdict": rebuilt.score,
                          "context": rebuilt.context})
    return cases


def _tokens():
    import tiktoken

    encoding = tiktoken.get_encoding("o200k_base")
    return lambda text: len(encoding.encode(text))


def fit_evidence(question: str, answer: str, context: str, count) -> tuple[str, str]:
    """The evidence Jev reads: whole when it fits, else the passages the answer depends on."""

    budget = STATE_TOKEN_BUDGET - count(question) - count(answer) - 200
    if count(context) <= budget:
        return context, "whole"
    terms = {term.casefold() for term in find_entities(answer)}
    terms |= {number for number in NUMBER_RE.findall(answer) if len(number) >= 2}
    terms |= {quote.casefold()[:60] for quote in find_quotations(answer)}
    blocks = [block for block in context.split("\n\n") if block.strip()]
    scored = []
    for index, block in enumerate(blocks):
        folded = block.casefold()
        score = sum(term in folded for term in terms) + (100 if "[evidence status]" in folded else 0)
        scored.append((score, index, block))
    chosen, used = [], 0
    for score, index, block in sorted(scored, key=lambda item: (-item[0], item[1])):
        if score <= 0 and chosen:
            break
        size = count(block)
        if used + size > budget:
            continue
        chosen.append((index, block))
        used += size
    return "\n\n".join(block for _, block in sorted(chosen)), "excerpt"


# --------------------------------------------------------------------------------------
# Jev
# --------------------------------------------------------------------------------------


def ask(case: dict, evidence: str, session: requests.Session, headers: dict) -> dict:
    body = {"model": JEV_MODEL, "state": {"question": case["question"], "answer": case["answer"], "evidence": evidence},
            "questions": CHECKS}
    started = time.perf_counter()
    try:
        response = session.post(DECISIONS_URL, headers=headers, json=body, timeout=60)
        latency = time.perf_counter() - started
        payload = response.json() if response.content else {}
    except Exception as error:
        return {"status": f"error:{type(error).__name__}", "latency_s": time.perf_counter() - started}
    if response.status_code != 200 or "answers" not in payload:
        return {"status": f"http_{response.status_code}", "latency_s": latency, "detail": json.dumps(payload)[:300]}
    answers, usage = payload["answers"], payload.get("usage", {})
    return {"status": "ok", "p_grounded": answers["grounded"].get("noul"), "p_complete": answers["complete"].get("noul"),
            "input_tokens": usage.get("input_tokens"), "cost_usd": usage.get("cost"), "latency_s": latency}


FIELDS = ["set", "system", "run", "question_id", "verdict", "evidence_mode", "evidence_tokens", "status",
          "p_grounded", "p_complete", "input_tokens", "cost_usd", "latency_s", "detail"]


def run(out_dir: Path, cases: list[dict]) -> None:
    count = _tokens()
    headers = {**openrouter_headers("WRE answer check"), "Authorization": f"Bearer {require_api_key()}",
               "Content-Type": "application/json"}
    with requests.Session() as session, (out_dir / "jev_calls.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for number, case in enumerate(cases, 1):
            evidence, mode = fit_evidence(case["question"], case["answer"], case["context"], count)
            result = ask(case, evidence, session, headers)
            writer.writerow({**{k: case[k] for k in ("set", "system", "run", "question_id", "verdict")},
                             "evidence_mode": mode, "evidence_tokens": count(evidence),
                             **{k: result.get(k, "") for k in FIELDS if k in result}})
            handle.flush()
            print(f"[{number}/{len(cases)}] {case['set']} {case['question_id']} {case['run'][:14]:14s} {mode:7s} "
                  f"verdict={case['verdict']:7s} grounded={result.get('p_grounded')} complete={result.get('p_complete')} "
                  f"{result['status']}", flush=True)


# --------------------------------------------------------------------------------------
# Summary and simulation
# --------------------------------------------------------------------------------------


def _auc(scores_bad: list[float], scores_good: list[float]) -> float:
    """Probability that a non-pass answer gets a lower score than a pass answer (ties count half)."""

    if not scores_bad or not scores_good:
        return float("nan")
    wins = sum((b < g) + 0.5 * (b == g) for b in scores_bad for g in scores_good)
    return wins / (len(scores_bad) * len(scores_good))


def summarize(out_dir: Path) -> str:
    with (out_dir / "jev_calls.csv").open(encoding="utf-8") as handle:
        calls = list(csv.DictReader(handle))
    ok = [c for c in calls if c["status"] == "ok"]
    for c in ok:
        c["pg"], c["pc"] = float(c["p_grounded"]), float(c["p_complete"])
        c["both"] = min(c["pg"], c["pc"])
    lines = [f"# Jev answer check ({out_dir.name})", "",
             f"{len(calls)} answers, {len(ok)} checked; {sum(c['evidence_mode'] == 'excerpt' for c in calls)} with excerpted "
             f"evidence; cost ${sum(float(c['cost_usd'] or 0) for c in ok):.4f}; median latency "
             f"{statistics.median(float(c['latency_s']) for c in ok):.2f} s.", "",
             "## Does Jev's score separate the judge's non-pass answers from its passes?", "",
             "AUC: the chance a non-pass answer scores lower than a pass answer (0.5 = no signal, 1.0 = perfect).", "",
             "| Answers | Non-pass | Grounded AUC | Complete AUC | min(both) AUC |", "| --- | ---: | ---: | ---: | ---: |"]
    for label, subset in (("GT", [c for c in ok if c["set"] == "GT"]), ("Validation", [c for c in ok if c["set"] == "VAL"]),
                          ("All", ok), ("Whole evidence only", [c for c in ok if c["evidence_mode"] == "whole"])):
        bad = [c for c in subset if c["verdict"] != "pass"]
        good = [c for c in subset if c["verdict"] == "pass"]
        lines.append(f"| {label} | {len(bad)} of {len(subset)} | " + " | ".join(
            f"{_auc([c[k] for c in bad], [c[k] for c in good]):.2f}" for k in ("pg", "pc", "both")) + " |")

    lines += ["", "## Escalate when min(grounded, complete) is below the threshold", "",
              "| Threshold | Non-pass caught | Passes escalated (false alarms) |", "| ---: | ---: | ---: |"]
    for t in THRESHOLDS:
        bad = [c for c in ok if c["verdict"] != "pass"]
        good = [c for c in ok if c["verdict"] == "pass"]
        lines.append(f"| {t:.1f} | {sum(c['both'] < t for c in bad)}/{len(bad)} | {sum(c['both'] < t for c in good)}/{len(good)} |")

    lines += ["", "## Simulated: mini, then Jev, then gpt-5.4 when Jev says no", ""] + simulate(ok)
    text = "\n".join(lines) + "\n"
    (out_dir / "summary.md").write_text(text, encoding="utf-8")
    return text


def simulate(ok: list[dict]) -> list[str]:
    jev = {(c["run"], c["question_id"]): c for c in ok}
    setups = [
        ("GT", "GT test set", [COST_EFFICIENCY / "wikipedia_GT"], ["7.1 final"], "7.1 final, gpt-5.4"),
        ("VAL", "Validation set", [ENGINE / "Capstone Checkpoint 6.1" / "cost_tests" / "wikipedia_GT_validation_set",
                                   HERE / "cost_tests" / "wikipedia_GT_validation_set"],
         ["6.1 survivor", "7.1 final"], "6.1 survivor, gpt-5.4"),
    ]
    lines = []
    for short, qset, dirs, cheap, strong in setups:
        data = eff.load_efficiency_data(dirs)
        rows = data.rows[data.rows["question_set"] == qset]
        c_rows = rows[rows["label"].isin(cheap) & rows["cost_list_usd"].notna()]
        s = rows[rows["label"] == strong].groupby("question_id").agg(
            q=("quality", "mean"), cost=("cost_list_usd", "mean"), sec=("agent_seconds", "mean"))
        c_rows = c_rows[c_rows["question_id"].isin(s.index)]
        lines += [f"**{qset}** (cheap: {', '.join(cheap)}, {c_rows['run_name'].nunique()} runs; strong: {strong})", "",
                  "| Policy | Quality | List $/q | Seconds/q | Escalated |", "| --- | ---: | ---: | ---: | ---: |"]

        def policy(decide) -> str:
            quality = cost = seconds = escalated = 0.0
            for row in c_rows.itertuples():
                check = jev.get((row.run_name, row.question_id))
                jev_cost = float(check["cost_usd"] or 0) if check else 0.0
                jev_time = float(check["latency_s"]) if check else 0.0
                up = decide(check)
                target = s.loc[row.question_id]
                if up:
                    escalated += 1
                    quality += target.q
                    cost += row.cost_list_usd + jev_cost + target.cost
                    seconds += row.agent_seconds + jev_time + target.sec
                else:
                    quality += row.quality
                    cost += row.cost_list_usd + jev_cost
                    seconds += row.agent_seconds + jev_time
            n = len(c_rows)
            return f"{quality / n:.3f} | {cost / n:.4f} | {seconds / n:.1f} | {escalated / n:.0%} |"

        all_cheap_q = c_rows["quality"].mean()
        lines.append(f"| All mini | {all_cheap_q:.3f} | {c_rows['cost_list_usd'].mean():.4f} | {c_rows['agent_seconds'].mean():.1f} | 0% |")
        strong_rows = rows[rows["label"] == strong]
        lines.append(f"| All gpt-5.4 | {strong_rows['quality'].mean():.3f} | {strong_rows['cost_list_usd'].mean():.4f} | "
                     f"{strong_rows['agent_seconds'].mean():.1f} | 100% |")
        for t in THRESHOLDS:
            lines.append(f"| Jev check at {t:.1f} (excerpts for large evidence) | " + policy(lambda c, t=t: c is None or c["both"] < t))
        for t in (0.5, 0.8):
            lines.append(f"| Jev check at {t:.1f}, large evidence always escalated | "
                         + policy(lambda c, t=t: c is None or c["evidence_mode"] == "excerpt" or c["both"] < t))
        lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Can Jev tell which mini answers need gpt-5.4?")
    parser.add_argument("--dry-run", action="store_true", help="Build every Jev input and estimate the cost; no calls.")
    parser.add_argument("--summarize", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=COST_EFFICIENCY / "answer_checks")
    args = parser.parse_args(argv)
    if args.summarize:
        print(summarize(args.summarize))
        return 0
    cases = load_cases()
    count = _tokens()
    sizes = [count(c["question"]) + count(c["answer"]) + count(fit_evidence(c["question"], c["answer"], c["context"], count)[0])
             for c in cases]
    excerpted = sum(fit_evidence(c["question"], c["answer"], c["context"], count)[1] == "excerpt" for c in cases)
    print(f"{len(cases)} answers ({sum(c['set'] == 'GT' for c in cases)} GT, {sum(c['set'] == 'VAL' for c in cases)} validation); "
          f"{excerpted} excerpted; {sum(sizes) / 1000:.0f}K state tokens; estimate ${sum(sizes) * 0.042 / 1e6:.3f}.")
    if args.dry_run:
        return 0
    out_dir = args.output_dir / datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_config.json").write_text(json.dumps(
        {"model": JEV_MODEL, "checks": CHECKS, "state_token_budget": STATE_TOKEN_BUDGET, "thresholds": THRESHOLDS},
        indent=2), encoding="utf-8")
    run(out_dir, cases)
    print(summarize(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

r"""Checkpoint 7.1 router check: does Jev route the 44 GT and validation questions correctly?

The routing rule (2026-10-04): ``gpt-5.4-mini`` is the default for a question that
is text-only and needs one article; every other question goes to ``gpt-5.4``. Jev
(``typesafe/jev-1.13``, a decision-only model) reads the question and picks a route; code
then maps the route to a model deterministically:

    simple, with probability >= threshold  ->  cheap (gpt-5.4-mini)
    anything else, or a failed Jev call    ->  strong (gpt-5.4)

Run from ``rag_and_context_engineering/``::

    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/jev_route_check.py"              # 3 repeats
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/jev_route_check.py" --repeats 1
    python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/jev_route_check.py" --summarize <folder>

**Answer key.** A question should take the simple route when it is a text question and
names one source article. "Text question" comes from the system itself: fewer than half of
the saved gpt-5.4-mini runs of that question flagged a table (GT: the six baseline runs;
validation: the three 6.1 runs and the 7.1 run). "One source article" is the question
set's ``Source articles`` column. The key is what the simulation in README 7.1 tested, so
agreement with it is agreement with a rule already known to hold quality.

**Errors are not equal.** A complex question sent to mini can lose the question (the
dangerous error); a simple question sent to ``gpt-5.4`` only costs money. The summary
reports both at several thresholds.

Outputs in ``cost_efficiency/router_checks/<stamp>/``: ``jev_calls.csv`` (one row per call),
``routes_t<threshold>.csv`` (question_id, route) for the efficiency analyzer's
``--route-labels``, ``summary.md``, ``run_config.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
REPO = ENGINE.parent
if str(REPO) not in sys.path:  # the folder that holds the wikipedia_retrieval_engine package
    sys.path.insert(0, str(REPO))

from wikipedia_retrieval_engine.retrievers.llm import openrouter_headers, require_api_key  # noqa: E402

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"  # pinned, not the "latest" alias (lecture: a moving alias changed a system)
GT_FILES = {"GT": ENGINE / "GT" / "wikipedia_GT.csv", "VAL": ENGINE / "GT" / "wikipedia_GT_validation_set.csv"}
COST_EFFICIENCY = HERE / "cost_efficiency"
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9)
DEFAULT_THRESHOLD = 0.8

ROUTE_QUESTION = {
    "type": "choice",
    "instructions": "Which answering path does this Wikipedia question need?",
    "criteria": {
        "simple": (
            "The answer is stated in the text of one Wikipedia article about one person, place, event, "
            "or work. No tables, counting, rankings, date ranges, or comparisons across articles."
        ),
        "complex": (
            "Answering needs table data, counting, filtering by dates, ranking, calculation, or "
            "combining facts from more than one article."
        ),
    },
}

# Saved gpt-5.4-mini runs whose table flags define "text question" in the answer key.
MINI_RUNS = {
    "GT": [HERE / "cost_efficiency" / "wikipedia_GT" / "experiments" / f"{name}.csv" for name in (
        "eager_torvalds", "admiring_diffie", "hardcore_page", "eloquent_hoare", "confident_stallman", "confident_zuckerberg")],
    "VAL": [ENGINE / "Capstone Checkpoint 6.1" / "cost_tests" / "wikipedia_GT_validation_set" / "experiments" / f"{name}.csv"
            for name in ("dazzling_minsky", "nifty_mccarthy", "angry_babbage")]
    + [HERE / "cost_tests" / "wikipedia_GT_validation_set" / "experiments" / "awesome_valiant.csv"],
}


def load_questions() -> list[dict[str, str]]:
    questions = []
    for set_name, path in GT_FILES.items():
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                articles = [a for a in row["Source articles"].split(";") if a.strip()]
                questions.append({
                    "set": set_name, "question_id": row["ID"], "category": row["Category"],
                    "question": row["Question"], "source_articles": len(articles),
                })
    return questions


def answer_key(questions: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    flags: dict[str, list[bool]] = defaultdict(list)
    for paths in MINI_RUNS.values():
        for path in paths:
            with path.open(encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    flags[row["question_id"]].append(row["tables_flagged"].strip().lower() == "true")
    key = {}
    for question in questions:
        runs = flags[question["question_id"]]
        table_share = sum(runs) / len(runs) if runs else 1.0
        text = table_share < 0.5
        key[question["question_id"]] = {
            "table_share": table_share,
            "text": text,
            "one_article": question["source_articles"] == 1,
            "route": "simple" if text and question["source_articles"] == 1 else "complex",
        }
    return key


def ask_jev(question: str, session: requests.Session, headers: dict[str, str]) -> dict[str, object]:
    body = {"model": JEV_MODEL, "state": {"question": question}, "questions": {"route": ROUTE_QUESTION}}
    started = time.perf_counter()
    try:
        response = session.post(DECISIONS_URL, headers=headers, json=body, timeout=30)
        latency = time.perf_counter() - started
        payload = response.json() if response.content else {}
    except Exception as error:  # a failed call routes to strong; the row records why
        return {"status": f"error:{type(error).__name__}", "latency_s": time.perf_counter() - started}
    if response.status_code != 200 or "answers" not in payload:
        return {"status": f"http_{response.status_code}", "latency_s": latency, "detail": json.dumps(payload)[:300]}
    answer = payload["answers"]["route"]
    probabilities = answer.get("probabilities", {})
    usage = payload.get("usage", {})
    return {
        "status": "ok",
        "choice": answer.get("choice"),
        "p_simple": float(probabilities.get("simple", 0.0)),
        "p_complex": float(probabilities.get("complex", 0.0)),
        "confidence": answer.get("confidence"),
        "served_model": payload.get("model"),
        "input_tokens": usage.get("input_tokens"),
        "cost_usd": usage.get("cost"),
        "latency_s": latency,
    }


def route_for(p_simple: float | None, threshold: float) -> str:
    """The deterministic mapping: cheap only when Jev is confident the question is simple."""

    return "cheap" if p_simple is not None and p_simple >= threshold else "strong"


CALL_FIELDS = ["set", "question_id", "category", "repeat", "key_route", "key_text", "key_one_article",
               "key_table_share", "source_articles", "status", "choice", "p_simple", "p_complex", "confidence",
               "served_model", "input_tokens", "cost_usd", "latency_s", "detail", "question"]


def run_check(repeats: int, out_dir: Path) -> Path:
    questions = load_questions()
    key = answer_key(questions)
    headers = {**openrouter_headers("WRE router"), "Authorization": f"Bearer {require_api_key()}",
               "Content-Type": "application/json"}
    calls_path = out_dir / "jev_calls.csv"
    with requests.Session() as session, calls_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALL_FIELDS)
        writer.writeheader()
        for repeat in range(1, repeats + 1):
            for question in questions:
                truth = key[question["question_id"]]
                result = ask_jev(question["question"], session, headers)
                writer.writerow({
                    "set": question["set"], "question_id": question["question_id"], "category": question["category"],
                    "repeat": repeat, "key_route": truth["route"], "key_text": truth["text"],
                    "key_one_article": truth["one_article"], "key_table_share": round(truth["table_share"], 3),
                    "source_articles": question["source_articles"], "question": question["question"],
                    **{name: result.get(name, "") for name in CALL_FIELDS if name in result},
                })
                handle.flush()
                print(f"[{repeat}/{repeats}] {question['question_id']:6s} key={truth['route']:7s} "
                      f"jev={result.get('choice', result['status'])} p_simple={result.get('p_simple', '')}", flush=True)
    return calls_path


def summarize(out_dir: Path) -> str:
    with (out_dir / "jev_calls.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ok = [row for row in rows if row["status"] == "ok"]
    per_question: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ok:
        per_question[row["question_id"]].append(row)
    mean_p = {qid: statistics.mean(float(r["p_simple"]) for r in calls) for qid, calls in per_question.items()}
    key_route = {row["question_id"]: row["key_route"] for row in rows}
    meta = {row["question_id"]: row for row in rows}

    lines = [f"# Jev route check ({out_dir.name})", "",
             f"{len(rows)} calls ({len(ok)} ok) over {len({r['question_id'] for r in rows})} questions; "
             f"model {JEV_MODEL}; total cost ${sum(float(r['cost_usd'] or 0) for r in ok):.4f}; "
             f"median latency {statistics.median(float(r['latency_s']) for r in ok):.2f} s.", ""]
    stability = [len({r["choice"] for r in calls}) == 1 for calls in per_question.values()]
    spread = [max(float(r["p_simple"]) for r in calls) - min(float(r["p_simple"]) for r in calls) for calls in per_question.values()]
    lines += [f"Stability across repeats: same choice on {sum(stability)}/{len(stability)} questions; "
              f"largest spread of p(simple) {max(spread):.3f}.", ""]

    lines += ["## Agreement with the answer key, by threshold", "",
              "The key routes a question to mini when it is a text question (fewer than half of the mini runs flagged "
              "a table) and has one source article. Route from the mean p(simple) over the repeats.", "",
              "| Threshold | Correct | Complex sent to mini (dangerous) | Simple sent to gpt-5.4 (costly) | Sent to mini |",
              "| ---: | ---: | ---: | ---: | ---: |"]
    for threshold in THRESHOLDS:
        routed = {qid: route_for(p, threshold) for qid, p in mean_p.items()}
        dangerous = [q for q, r in routed.items() if r == "cheap" and key_route[q] == "complex"]
        costly = [q for q, r in routed.items() if r == "strong" and key_route[q] == "simple"]
        correct = len(routed) - len(dangerous) - len(costly)
        lines.append(f"| {threshold:.1f} | {correct}/{len(routed)} | {len(dangerous)} {', '.join(sorted(dangerous))} | "
                     f"{len(costly)} {', '.join(sorted(costly))} | {sum(r == 'cheap' for r in routed.values())} |")

    lines += ["", "## Per question", "",
              "| Question | Category | Source articles | Mini runs flagging a table | Key | Mean p(simple) | Route at 0.8 |",
              "| --- | --- | ---: | ---: | --- | ---: | --- |"]
    for qid in sorted(mean_p, key=lambda q: (meta[q]["set"], int("".join(ch for ch in q if ch.isdigit())))):
        row = meta[qid]
        lines.append(f"| {qid} | {row['category']} | {row['source_articles']} | {float(row['key_table_share']):.0%} | "
                     f"{row['key_route']} | {mean_p[qid]:.3f} | {route_for(mean_p[qid], DEFAULT_THRESHOLD)} |")
    text = "\n".join(lines) + "\n"
    (out_dir / "summary.md").write_text(text, encoding="utf-8")

    for threshold in THRESHOLDS:
        with (out_dir / f"routes_t{threshold:.1f}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["question_id", "route", "router", "p_simple"])
            for qid, p in sorted(mean_p.items()):
                writer.writerow([qid, route_for(p, threshold), f"Jev at {threshold:.1f}", f"{p:.4f}"])
    with (out_dir / "routes_key.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["question_id", "route", "router"])
        for qid, route in sorted(key_route.items()):
            writer.writerow([qid, "cheap" if route == "simple" else "strong", "the answer key"])
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Jev's routes on the 44 GT and validation questions.")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--summarize", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=COST_EFFICIENCY / "router_checks")
    args = parser.parse_args(argv)
    if args.summarize:
        print(summarize(args.summarize))
        return 0
    out_dir = args.output_dir / datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_config.json").write_text(json.dumps(
        {"model": JEV_MODEL, "url": DECISIONS_URL, "repeats": args.repeats, "route_question": ROUTE_QUESTION,
         "thresholds": THRESHOLDS, "default_threshold": DEFAULT_THRESHOLD}, indent=2), encoding="utf-8")
    run_check(args.repeats, out_dir)
    print(summarize(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

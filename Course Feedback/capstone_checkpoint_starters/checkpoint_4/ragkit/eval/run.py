"""Evaluation runs: every question through a pipeline, scored and logged. (Checkpoint 3)

    results, log_path = run_eval(pipeline, questions, experiment="hybrid_k5")

Each question is answered on its own (no history), scored for retrieval recall and
answer quality, and written to the run log with the scores, the judge's reason, and
every model call. The judge's calls carry the role "judge", so the log analysis can
keep the cost of evaluating apart from the cost of the system itself.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ragkit.eval.judge import Judge, Verdict
from ragkit.eval.questions import EvalQuestion
from ragkit.eval.recall import article_recall
from ragkit.pipelines.base import Answer, Pipeline
from ragkit.runlog import RunLog


@dataclass
class EvalResult:
    question: EvalQuestion
    answer: Answer | None
    recall: float | None
    verdict: Verdict | None
    latency_s: float
    error: str | None = None


def run_eval(
    pipeline: Pipeline,
    questions: Sequence[EvalQuestion],
    *,
    experiment: str,
    checkpoint: str = "3",
    judge: Judge | None = None,
    progress: Callable[[str], None] = print,
) -> tuple[list[EvalResult], Path]:
    judge = judge or Judge()
    log = RunLog(experiment, checkpoint=checkpoint, pipeline=pipeline)
    progress(f"Run '{experiment}': {len(questions)} question(s), log {log.path.name}")
    results = []
    for question in questions:
        started = time.perf_counter()
        try:
            answer = pipeline.answer(question.question)
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            log.record_error(question.question, error, question_id=question.id, dataset=question.split)
            results.append(EvalResult(question, None, None, None, time.perf_counter() - started, message))
            progress(f"  {question.id:<8} error: {message}")
            continue
        latency_s = time.perf_counter() - started
        recall = article_recall(answer.hits, question.sources)
        try:
            verdict = judge.grade(question, answer.text)
        except Exception as error:  # keep the answer (and its cost) in the log
            log.record(answer, question_id=question.id, dataset=question.split, category=question.category, latency_s=latency_s,
                       scores={"quality": None, "verdict": "JUDGE_ERROR", "recall": recall, "judge_reason": str(error)})
            results.append(EvalResult(question, answer, recall, None, latency_s, f"judge: {error}"))
            progress(f"  {question.id:<8} judge error: {error}")
            continue
        scores = {"quality": verdict.score, "verdict": verdict.label, "recall": recall, "judge_reason": verdict.reason}
        log.record(answer, question_id=question.id, dataset=question.split, category=question.category,
                   scores=scores, latency_s=latency_s, extra_calls=[verdict.call])
        results.append(EvalResult(question, answer, recall, verdict, latency_s))
        progress(f"  {question.id:<8} recall {_fmt(recall)}  {verdict.label:<7}  {latency_s:5.1f} s")
    for line in summary_lines(results):
        progress(line)
    return results, log.path


def summary_lines(results: Sequence[EvalResult]) -> list[str]:
    lines = []
    for split in ("gt", "validation"):
        scored = [r for r in results if r.question.split == split and r.verdict is not None]
        if not scored:
            continue
        quality = sum(r.verdict.score for r in scored) / len(scored)
        passes = sum(r.verdict.label == "PASS" for r in scored) / len(scored)
        recalls = [r.recall for r in scored if r.recall is not None]
        recall = sum(recalls) / len(recalls) if recalls else None
        lines.append(f"  {split}: {len(scored)} scored, quality {quality:.3f}, PASS {passes:.0%}, recall {_fmt(recall)}")
    errors = sum(r.error is not None for r in results)
    if errors:
        lines.append(f"  {errors} question(s) failed; see the log")
    return lines


def _fmt(value: float | None) -> str:
    return "n/a " if value is None else f"{value:.2f}"

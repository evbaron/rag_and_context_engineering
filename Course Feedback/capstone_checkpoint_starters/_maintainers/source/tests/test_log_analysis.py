import csv

from ragkit.pipelines.base import Answer, LLMCall
from ragkit.reports import performance
from ragkit.runlog import RunLog, read_records


def _log(experiment, checkpoint, quality=None, latency=1.0, roles=("answer",)):
    log = RunLog(experiment, checkpoint=checkpoint, settings={"name": "rag", "retriever": "bm25"})
    calls = [LLMCall(role, "openai/gpt-5.4-mini", 1_000, 100, 0.5) for role in roles]
    scores = {"quality": quality, "verdict": "PASS", "recall": 1.0} if quality is not None else {}
    judge = [LLMCall("judge", "openai/gpt-5.4-mini", 500, 10, 0.2)] if quality is not None else []
    log.record(Answer("a", "q1", calls=calls), question_id="Q1", scores=scores, latency_s=latency, extra_calls=judge)
    log.record(Answer("b", "q2", calls=calls), question_id="Q2", scores=scores, latency_s=latency * 3, extra_calls=judge)
    return log.path


def test_percentile():
    assert performance.percentile([5, 1, 3, 2, 4], 0.5) == 3
    assert performance.percentile([1, 2, 3, 4, 100], 0.95) == 100
    assert performance.percentile([], 0.5) is None


def test_runs_and_roles_keep_the_judge_out_of_system_cost():
    path = _log("cp5_agent", "5", quality=1.0, roles=("plan", "plan", "answer"))
    records = read_records([path])
    summary = performance.summarize_run(records, performance.load_prices())
    assert summary["calls"] == 3.0 and summary["quality"] == 1.0
    assert round(summary["cost"], 6) == round(3 * (1_000 * 0.75 + 100 * 4.5) / 1e6, 6)
    assert round(summary["judge_cost"], 6) == round((500 * 0.75 + 10 * 4.5) / 1e6, 6)
    roles = {r["role"]: r for r in performance.role_rows(records, performance.load_prices())}
    assert roles["plan"]["calls"] == 4 and round(roles["plan"]["system_share"], 3) == 0.667
    assert roles["judge"]["system_share"] is None


def test_report_sections_csv_files_and_filters():
    first = _log("chat_history_on", "1")
    second = _log("cp3_hybrid_k5", "3", quality=0.5)
    text, run_rows, roles = performance.build_report(read_records([first, second]))
    for heading in ["## Runs", "## Quality against cost and time", "## Where the money goes", "## Slowest questions"]:
        assert heading in text
    report = performance.write(text, run_rows, roles)
    with open(report.with_name(report.stem + "_runs.csv"), encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 2
    assert performance.select_logs(checkpoints=["3"]) == [second]
    assert performance.select_logs(experiment="chat_") == [first]
    assert performance.select_logs(since="2999-01-01") == []

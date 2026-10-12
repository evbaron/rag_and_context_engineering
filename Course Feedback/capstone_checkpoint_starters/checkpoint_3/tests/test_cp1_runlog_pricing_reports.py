from types import SimpleNamespace

from ragkit.pipelines.base import Answer, LLMCall
from ragkit.pricing import call_cost, load_prices, price_for, record_cost
from ragkit.reports import runs
from ragkit.runlog import RunLog, hit_summary, list_logs, read_records


def _answer(text="an answer", question="Q?"):
    call = LLMCall(role="answer", model="openai/gpt-5.4-mini", input_tokens=1000, output_tokens=100, latency_s=1.5)
    return Answer(text=text, question=question, calls=[call], metadata={"context_chars": 42, "note": "x"})


def test_record_writes_one_complete_line():
    log = RunLog("History On!", checkpoint="1", settings={"name": "llm_only", "model": "m"})
    judge = LLMCall(role="judge", model="openai/gpt-5.4-mini", input_tokens=50, output_tokens=5, latency_s=0.2)
    log.record(_answer(), question_id="GT01", dataset="gt", scores={"quality": 1.0}, latency_s=2.0, extra_calls=[judge])
    assert log.run_id.endswith("_history-on")
    (record,) = read_records([log.path])
    assert record["question_id"] == "GT01" and record["dataset"] == "gt"
    assert record["context_chars"] == 42 and record["details"] == {"note": "x"}
    assert [call["role"] for call in record["calls"]] == ["answer", "judge"]
    assert record["latency_s"] == 2.0 and record["error"] is None
    assert list_logs() == [log.path]


def test_hit_summary_reads_any_hit_like_object():
    doc = SimpleNamespace(id="100_metres.html#2", metadata={"source": "100_metres.html"})
    summary = hit_summary(SimpleNamespace(doc=doc, score=0.81234, via="graph"))
    assert summary == {"id": "100_metres.html#2", "source": "100_metres.html", "score": 0.8123, "via": "graph"}


def test_prices_match_the_longest_prefix_and_free_models():
    prices = load_prices()
    assert price_for("openai/gpt-5.4-mini-20260317", prices)["input"] == 0.75
    assert price_for("openai/gpt-5.4", prices)["input"] == 2.5
    assert price_for("someone/model:free", prices)["output"] == 0.0
    assert price_for("unknown/model", prices) is None


def test_cost_uses_the_cheaper_rate_for_cached_input():
    prices = load_prices()
    plain = {"model": "openai/gpt-5.4-mini", "input_tokens": 1_000_000, "output_tokens": 0}
    cached = {**plain, "cached_tokens": 1_000_000}
    assert round(call_cost(plain, prices), 4) == 0.75
    assert round(call_cost(cached, prices), 4) == 0.075


def test_record_cost_can_leave_out_the_judge():
    record = {
        "calls": [
            {"role": "answer", "model": "openai/gpt-5.4-mini", "input_tokens": 1_000_000, "output_tokens": 0},
            {"role": "judge", "model": "openai/gpt-5.4-mini", "input_tokens": 1_000_000, "output_tokens": 0},
        ]
    }
    assert round(record_cost(record), 4) == 1.5
    assert round(record_cost(record, exclude_roles={"judge"}), 4) == 0.75
    assert record_cost({"calls": [{"role": "answer", "model": "unknown/x", "input_tokens": 1}]}) is None


def test_runs_report_puts_answers_side_by_side(capsys):
    first = RunLog("history_on", settings={"name": "llm_only", "model": "openai/gpt-5.4-mini"})
    second = RunLog("history_off", settings={"name": "llm_only", "model": "openai/gpt-5.4-mini"})
    first.record(_answer("A stalemate.", "And who won?"))
    second.record(_answer("Which competition?", "And who won?"))
    text = runs.build_report(read_records([first.path, second.path]))
    assert text.count("### ") == 1  # one question, matched across both runs
    assert "A stalemate." in text and "Which competition?" in text
    assert "| history_on (" in text and "| history_off (" in text

    runs.main([str(first.path), str(second.path)])
    assert "Report:" in capsys.readouterr().out

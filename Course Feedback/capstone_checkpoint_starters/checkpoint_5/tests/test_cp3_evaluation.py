import json
from pathlib import Path

import pandas as pd
import pytest

from ragkit import config
from ragkit.baseline import load_baseline, open_baseline, save_baseline
from ragkit.corpus import Document
from ragkit.eval.judge import Judge
from ragkit.eval.questions import COLUMNS, EvalQuestion, load_questions
from ragkit.eval.recall import article_recall
from ragkit.eval.run import run_eval, summary_lines
from ragkit.pipelines.base import Answer, LLMCall, Pipeline
from ragkit.pipelines.oracle import OraclePipeline, whole_articles
from ragkit.reports import quality
from ragkit.retrievers.base import Hit
from ragkit.runlog import read_records
from tests.fakes import FakeLLM

FIXTURES = Path(__file__).parent / "fixtures"
ROWS = [
    ["GT01", "Direct fact", "Who holds the record?", "Ann Runner", "Name Ann Runner", "Alpha_Sprint.html", "gt"],
    ["GT02", "Multi-article", "Which races are run?", "Alpha Sprint and Beta Relay", "", "Alpha_Sprint.html; Beta_Relay.html", ""],
    ["", "", "", "", "", "", ""],
    ["VAL01", "Table lookup", "Who won in 1901?", "Bo Fast", "", "Alpha_Sprint.html", "validation"],
]


def _write(tmp_path, rows=ROWS, columns=COLUMNS, suffix=".xlsx"):
    path = tmp_path / f"questions{suffix}"
    table = pd.DataFrame(rows, columns=columns)
    table.to_excel(path, index=False) if suffix == ".xlsx" else table.to_csv(path, index=False)
    return path


def test_question_sets_load_from_excel_and_csv(tmp_path):
    for suffix in (".xlsx", ".csv"):
        questions = load_questions(_write(tmp_path, suffix=suffix))
        assert [q.id for q in questions] == ["GT01", "GT02", "VAL01"]
        assert questions[1].sources == ["Alpha_Sprint.html", "Beta_Relay.html"]
        assert questions[1].split == "gt"  # an empty Split means gt
    assert [q.id for q in load_questions(_write(tmp_path), split="validation")] == ["VAL01"]


def test_question_set_problems_are_reported(tmp_path):
    with pytest.raises(ValueError, match="missing the column"):
        load_questions(_write(tmp_path, [r[:3] for r in ROWS], COLUMNS[:3]))
    with pytest.raises(ValueError, match="Duplicate IDs"):
        load_questions(_write(tmp_path, [ROWS[0], ROWS[0]]))
    with pytest.raises(ValueError, match="use gt or validation"):
        load_questions(_write(tmp_path, [ROWS[0][:6] + ["test"]]))


def test_demo_question_set_is_well_formed():
    demo = Path(__file__).parents[1] / "data"
    files = list(demo.glob("questions_demo_*.xlsx")) + list(demo.glob("questions_demo_*.csv"))
    assert files, "the demo question set is missing"
    questions = load_questions(files[0])
    assert {q.split for q in questions} == {"gt", "validation"}
    assert all(q.sources and q.reference_answer for q in questions)


def _hit(source):
    return Hit(Document(f"{source}#0", "text", {"source": source}), 1.0)


def test_article_recall():
    assert article_recall([_hit("Alpha_Sprint.html")], ["Alpha_Sprint.html", "Beta_Relay.html"]) == 0.5
    assert article_recall([{"source": "beta_relay.html"}], ["Beta Relay"]) == 1.0
    assert article_recall([], ["Alpha_Sprint.html"]) == 0.0
    assert article_recall([_hit("x.html")], []) is None


@pytest.mark.parametrize(
    "reply, label, score",
    [("PASS\nAll facts present.", "PASS", 1.0), ("Partial\nYear missing.", "PARTIAL", 0.5),
     ("FAIL\nWrong holder.", "FAIL", 0.0), ("I am not sure", "FAIL", 0.0)],
)
def test_judge_reads_the_verdict(reply, label, score):
    question = EvalQuestion("GT01", "Who?", "Ann", ["a.html"])
    verdict = Judge(model="fake/model", llm=FakeLLM([reply])).grade(question, "Ann Runner")
    assert (verdict.label, verdict.score, verdict.call.role) == (label, score, "judge")


class SourcePipeline(Pipeline):
    """Retrieves Alpha_Sprint.html for every question; fails on 'boom'."""

    name = "source"

    def answer(self, question, history=()):
        if question == "boom":
            raise RuntimeError("down")
        call = LLMCall("answer", "openai/gpt-5.4-mini", 100, 10, 0.1)
        return Answer("Ann Runner", question, hits=[_hit("Alpha_Sprint.html")], calls=[call])


def test_run_eval_scores_and_logs_every_question():
    questions = [
        EvalQuestion("GT01", "Who?", "Ann", ["Alpha_Sprint.html"], category="Direct fact"),
        EvalQuestion("GT02", "Which?", "Both", ["Alpha_Sprint.html", "Beta_Relay.html"]),
        EvalQuestion("VAL01", "boom", "x", ["Alpha_Sprint.html"], split="validation"),
    ]
    judge = Judge(model="fake/model", llm=FakeLLM(["PASS\nok", "PARTIAL\nmissing Beta"]))
    results, log_path = run_eval(SourcePipeline(), questions, experiment="t", judge=judge, progress=lambda _: None)
    records = read_records([log_path])
    assert [r["scores"].get("recall") for r in records] == [1.0, 0.5, None]
    assert records[1]["scores"]["verdict"] == "PARTIAL"
    assert [c["role"] for c in records[0]["calls"]] == ["answer", "judge"]
    assert records[2]["error"] == "RuntimeError: down"
    assert records[0]["category"] == "Direct fact"
    assert any("quality 0.750" in line for line in summary_lines(results))


def test_oracle_hands_over_whole_source_articles():
    sections = [
        Document("Alpha_Sprint.html#0", "Intro text.", {"source": "Alpha_Sprint.html", "title": "Alpha Sprint", "section": "Introduction"}),
        Document("Alpha_Sprint.html#1", "Results text.", {"source": "Alpha_Sprint.html", "title": "Alpha Sprint", "section": "Results"}),
    ]
    article = whole_articles(sections)["alpha sprint"]
    assert article.text == "## Introduction\nIntro text.\n\n## Results\nResults text."
    questions = [EvalQuestion("GT01", "Who won?", "Ann", ["Alpha_Sprint.html", "Missing.html"])]
    llm = FakeLLM(["Ann"])
    oracle = OraclePipeline(sections, questions, model="fake/model", max_context_chars=60, llm=llm)
    answer = oracle.answer("who  won?")
    assert [h.doc.source for h in answer.hits] == ["Alpha_Sprint.html"]
    assert answer.metadata["missing_sources"] == ["Missing.html"] and answer.metadata["truncated"] is True
    with pytest.raises(ValueError):
        oracle.answer("an unknown question")


def _record(run, experiment, qid, dataset, verdict, recall, quality_score):
    return {"run_id": run, "experiment": experiment, "question_id": qid, "question": f"question {qid}", "dataset": dataset,
            "category": "Direct fact" if qid == "GT01" else "Multi-article",
            "pipeline": {"name": "rag", "retriever": "bm25"}, "error": None, "latency_s": 1.0,
            "calls": [{"role": "answer", "model": "openai/gpt-5.4-mini", "input_tokens": 1000, "output_tokens": 100},
                      {"role": "judge", "model": "openai/gpt-5.4-mini", "input_tokens": 500, "output_tokens": 10}],
            "scores": {"verdict": verdict, "recall": recall, "quality": quality_score}}


def test_quality_report_sections():
    records = [
        _record("2026-10-11_10-00-00_a", "cp3_bm25_r1", "GT01", "gt", "PASS", 1.0, 1.0),
        _record("2026-10-11_10-00-00_a", "cp3_bm25_r1", "GT02", "gt", "FAIL", 1.0, 0.0),
        _record("2026-10-11_10-00-00_a", "cp3_bm25_r1", "VAL01", "validation", "PASS", 0.0, 1.0),
        _record("2026-10-11_10-05-00_b", "cp3_bm25_r2", "GT01", "gt", "PASS", 1.0, 1.0),
        _record("2026-10-11_10-05-00_b", "cp3_bm25_r2", "GT02", "gt", "PARTIAL", 0.5, 0.5),
    ]
    cells = quality.diagnosis(records[:3])
    assert cells == {"working": ["GT01"], "answer problem": ["GT02"], "suspicious": ["VAL01"], "retrieval problem": []}
    text = quality.build_report(records)
    assert "## Which half failed" in text and "## Per question" in text and "## Repeated runs" in text
    assert "| cp3_bm25 | gt | 2 | 0.500, 0.750 | 0.625 | 0.250 |" in text
    assert "| GT02 | question GT02 | gt | FAIL · r1.00 | PARTIAL · r0.50 | yes |" in text
    assert "$0.0012" in text  # 1,000 input + 100 output tokens; the judge is excluded
    assert "## By category" in text and "| Direct fact | 1.00 (1) | 1.00 (1) |" in text
    assert "No scored runs" in quality.build_report([{"run_id": "x", "scores": {}}])


def test_baseline_is_saved_and_reopened(monkeypatch):
    monkeypatch.setenv("RAG_SCENARIO", "wikipedia")
    monkeypatch.setenv("RAG_CORPUS_DIR", str(FIXTURES / "wikipedia"))
    with pytest.raises(config.SetupError):
        load_baseline()
    path = save_baseline("bm25", 3, note="best on gt and validation")
    assert json.loads(path.read_text())["retriever"] == "bm25"
    pipeline, documents, saved = open_baseline()
    assert pipeline.k == 3 and pipeline.retriever.name == "bm25" and saved["note"] == "best on gt and validation"
    assert {d.source for d in documents} == {"Alpha_Sprint.html", "Beta_Relay.html"}
    with pytest.raises(ValueError):
        save_baseline("magic", 3)

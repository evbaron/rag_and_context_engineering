"""Checkpoint 3 sample: measure retrievers on a question set, then compare the runs.

    python samples/cp3_evaluate.py                                # demo questions; bm25, vector, hybrid, oracle
    python samples/cp3_evaluate.py --questions ~/my_questions.xlsx
    python samples/cp3_evaluate.py --pipelines bm25 hybrid --k 5 8
    python samples/cp3_evaluate.py --split gt                     # gt questions only
    python samples/cp3_evaluate.py --repeat 3                     # how much do results move by chance?

Every pipeline answers every question; each answer gets two independent scores,
retrieval recall and answer quality, and is logged. The quality report then shows the
runs side by side, which half of the system failed on each question, and the questions
whose result changed. The oracle (sources handed over directly) shows the best the
answer step can do.

When one configuration wins on both the gt and the validation questions, save it as
the baseline that later checkpoints must beat:

    python samples/cp3_save_baseline.py --retriever hybrid --k 5 --note "why it won"
"""

from __future__ import annotations

import argparse

from ragkit import config
from ragkit.corpus import load_corpus, normalize_source
from ragkit.eval.judge import Judge
from ragkit.eval.questions import load_questions
from ragkit.eval.run import run_eval
from ragkit.pipelines.llm_only import LLMOnlyPipeline
from ragkit.pipelines.oracle import OraclePipeline
from ragkit.pipelines.rag import RAGPipeline
from ragkit.reports.common import write_report
from ragkit.reports.quality import build_report
from ragkit.retrievers.factory import KINDS, make_retriever, open_documents
from ragkit.runlog import read_records

PIPELINES = (*KINDS, "oracle", "llm_only")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate pipelines on a question set.")
    parser.add_argument("--questions", default=None, help="question set (.xlsx or .csv); default: the demo set")
    parser.add_argument("--pipelines", nargs="+", default=["bm25", "vector", "hybrid", "oracle"], choices=PIPELINES)
    parser.add_argument("--k", nargs="+", type=int, default=[5], help="passages per question (several values allowed)")
    parser.add_argument("--split", choices=["gt", "validation", "all"], default="all")
    parser.add_argument("--repeat", type=int, default=1, help="run each configuration this many times")
    parser.add_argument("--judge-model", default=None, help="model for the judge (default: RAG_MODEL)")
    parser.add_argument("--index", default=None, help="vector index (default: the newest)")
    parser.add_argument("--limit", type=int, default=None, help="files to read when there is no index")
    args = parser.parse_args()

    questions_file = args.questions or config.PROJECT_ROOT / "data" / f"questions_demo_{config.scenario()}.xlsx"
    if not args.questions and not questions_file.is_file():
        raise SystemExit(f"No demo question set for '{config.scenario()}'. Copy data/questions_template.xlsx, "
                         "write questions about the corpus, and pass it with --questions.")
    questions = load_questions(questions_file, None if args.split == "all" else args.split)
    print(f"{len(questions)} question(s) from {questions_file}")

    documents, index_name = open_documents(args.index, args.limit)
    searched = {normalize_source(d.source) for d in documents}
    absent = sorted({s for q in questions for s in q.sources if normalize_source(s) not in searched})
    if absent:
        print(f"Warning: {len(absent)} source article(s) are not in the searched corpus, so no retriever can find them: "
              f"{', '.join(absent[:5])}{' ...' if len(absent) > 5 else ''}")

    judge = Judge(args.judge_model)
    log_paths = []
    for kind in args.pipelines:
        if kind in KINDS and kind != "bm25" and index_name is None:
            print(f"Skipping {kind}: no vector index yet (python samples/cp2_build_index.py).")
            continue
        for k in args.k if kind in KINDS else [None]:
            for repeat in range(1, args.repeat + 1):
                pipeline = _pipeline(kind, k, documents, index_name, questions)
                experiment = f"cp3_{kind}" + (f"_k{k}" if k else "") + (f"_r{repeat}" if args.repeat > 1 else "")
                _, log_path = run_eval(pipeline, questions, experiment=experiment, judge=judge)
                log_paths.append(log_path)

    report = write_report(build_report(read_records(log_paths), title="Checkpoint 3 evaluation"), "cp3_quality")
    print(f"\nReport: {report}")


def _pipeline(kind, k, documents, index_name, questions):
    if kind == "oracle":
        return OraclePipeline(load_corpus(chunk_size=None), questions)
    if kind == "llm_only":
        return LLMOnlyPipeline()
    return RAGPipeline(make_retriever(kind, documents, index_name), k=k)


if __name__ == "__main__":
    main()

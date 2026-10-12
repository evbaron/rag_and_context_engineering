"""Checkpoint 4 sample: multistep and graph retrieval against the baseline.

    python samples/cp4_challengers.py                          # demo questions, baseline vs both challengers
    python samples/cp4_challengers.py --questions ~/my_questions.xlsx
    python samples/cp4_challengers.py --challengers multistep

Both challengers wrap the baseline's own retriever (saved in Checkpoint 3), so the
comparison changes one thing at a time. Look at recall first: these are retrieval
improvements, and their job is to bring back sources the baseline missed. Then check
that answer quality followed, on the gt AND the validation questions.
"""

from __future__ import annotations

import argparse

from ragkit import config
from ragkit.baseline import open_baseline
from ragkit.eval.judge import Judge
from ragkit.eval.questions import load_questions
from ragkit.eval.run import run_eval
from ragkit.pipelines.rag import RAGPipeline
from ragkit.reports.common import write_report
from ragkit.reports.quality import build_report
from ragkit.retrievers.graph import GraphRetriever, link_graph, mention_graph
from ragkit.retrievers.multistep import MultiStepRetriever
from ragkit.runlog import read_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare challengers with the baseline.")
    parser.add_argument("--questions", default=None, help="question set (default: the demo set)")
    parser.add_argument("--challengers", nargs="+", default=["multistep", "graph"], choices=["multistep", "graph"])
    parser.add_argument("--split", choices=["gt", "validation", "all"], default="all")
    parser.add_argument("--judge-model", default=None)
    args = parser.parse_args()

    questions = load_questions(
        args.questions or config.PROJECT_ROOT / "data" / f"questions_demo_{config.scenario()}.xlsx",
        None if args.split == "all" else args.split,
    )
    baseline, documents, saved = open_baseline()
    print(f"Baseline: {saved['retriever']}, k={saved['k']} ({saved.get('note') or 'no note'})")

    judge = Judge(args.judge_model)
    runs = {"baseline": baseline}
    if "multistep" in args.challengers:
        runs["multistep"] = RAGPipeline(MultiStepRetriever(baseline.retriever), k=baseline.k)
    if "graph" in args.challengers:
        graph = link_graph(documents) if config.scenario() == "wikipedia" else mention_graph(documents)
        edges = graph.number_of_edges()
        print(f"Graph: {graph.number_of_nodes():,} documents, {edges:,} link{'s' if edges != 1 else ''} between them")
        runs["graph"] = RAGPipeline(GraphRetriever(baseline.retriever, documents, graph), k=baseline.k)

    log_paths = [run_eval(pipeline, questions, experiment=f"cp4_{name}", checkpoint="4", judge=judge)[1]
                 for name, pipeline in runs.items()]
    report = write_report(build_report(read_records(log_paths), title="Checkpoint 4 challengers"), "cp4_challengers")
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()

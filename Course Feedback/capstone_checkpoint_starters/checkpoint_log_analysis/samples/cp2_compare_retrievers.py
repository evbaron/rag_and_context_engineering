"""Checkpoint 2 sample: the same questions through keyword, vector, and hybrid retrieval.

    python samples/cp2_compare_retrievers.py                         # bm25, vector, hybrid
    python samples/cp2_compare_retrievers.py --retrievers bm25 hybrid --k 5
    python samples/cp2_compare_retrievers.py --retrieval-only        # no answers, no chat-model cost

For each retriever, every question goes through the same pipeline (retrieve k passages,
then answer from them) and is logged as one run. The script prints which sources each
retriever found, side by side, and writes a report with every answer. Vector and hybrid
need the index from samples/cp2_build_index.py; bm25 works without it.

Add questions about the chosen corpus to MY_QUESTIONS below.
"""

from __future__ import annotations

import argparse

from ragkit import config
from ragkit.chat import ChatSession
from ragkit.pipelines.rag import RAGPipeline
from ragkit.reports.common import write_report
from ragkit.reports.runs import build_report
from ragkit.retrievers.base import sources_of
from ragkit.retrievers.factory import KINDS, make_retriever, open_documents
from ragkit.runlog import RunLog, read_records

EXAMPLE_QUESTIONS = {
    "wikipedia": [
        "What is the men's 100 metres world record, and who set it?",
        "What is the opening sentence of the article on the film 13 (2010)?",
        "What happened in the year 1580?",
    ],
    "papers": [
        "What is the main finding of 'The Counterfeit Conundrum' about code models and their incorrect generations?",
        "How does 'The Sketching Approach to Program Synthesis' define the synthesis problem?",
    ],
    "emails": [
        "What was the status of the government project going into 2015?",
        "Who was involved in discussions about restarting the government project?",
    ],
}

# Questions about the chosen corpus: exact names and numbers (keyword search should
# shine), paraphrases (vector search should shine), and questions that span documents.
MY_QUESTIONS: list[str] = []


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare retrievers on the same questions.")
    parser.add_argument("--retrievers", nargs="+", default=list(KINDS), choices=KINDS)
    parser.add_argument("--k", type=int, default=5, help="passages retrieved per question")
    parser.add_argument("--index", default=None, help="vector index name (default: the newest)")
    parser.add_argument("--limit", type=int, default=None, help="files to read when there is no index")
    parser.add_argument("--retrieval-only", action="store_true", help="show sources only; skip the answers")
    args = parser.parse_args()

    questions = EXAMPLE_QUESTIONS[config.scenario()] + MY_QUESTIONS
    documents, index_name = open_documents(args.index, args.limit)
    print(f"Searching {len(documents):,} passages" + (f" (index '{index_name}')" if index_name else ""))

    found: dict[str, list[list[str]]] = {}
    log_paths = []
    for kind in args.retrievers:
        if kind != "bm25" and index_name is None:
            print(f"Skipping {kind}: no vector index yet (python samples/cp2_build_index.py).")
            continue
        retriever = make_retriever(kind, documents, index_name)
        if args.retrieval_only:
            found[kind] = [sources_of(retriever.retrieve(question, args.k)) for question in questions]
            continue
        pipeline = RAGPipeline(retriever, k=args.k)
        log = RunLog(f"cp2_{kind}_k{args.k}", checkpoint="2", pipeline=pipeline)
        session = ChatSession(pipeline, use_history=False, log=log)
        found[kind] = []
        for number, question in enumerate(questions, start=1):
            print(f"[{kind}] question {number}/{len(questions)}")
            try:
                found[kind].append(sources_of(session.ask(question).hits))
            except Exception as error:
                print(f"  error: {type(error).__name__}: {error}")
                found[kind].append([])
        log_paths.append(log.path)

    for number, question in enumerate(questions):
        print(f"\nQ{number + 1}. {question}")
        for kind, per_question in found.items():
            print(f"  {kind:>6}: {', '.join(per_question[number]) or '(nothing)'}")

    if log_paths:
        report = write_report(build_report(read_records(log_paths), title="Checkpoint 2 retrievers"), "cp2_retrievers")
        print(f"\nReport: {report}")


if __name__ == "__main__":
    main()

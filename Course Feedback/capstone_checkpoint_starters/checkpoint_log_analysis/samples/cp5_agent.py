"""Checkpoint 5 sample: agents against the baseline, and a chat with the agent.

    python samples/cp5_agent.py                     # baseline vs agentic retriever vs tool-using agent
    python samples/cp5_agent.py --only agent
    python samples/cp5_agent.py --chat              # talk to the tool-using agent (it may ask back)

Both agents reuse the baseline's retriever (saved in Checkpoint 3), so the comparison
changes one thing: who decides what to search. Agents make several model calls per
question; the logs record every one, so the quality report shows whether the extra
calls bought better answers, and the log analysis shows what they cost.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ragkit import config
from ragkit.baseline import open_baseline
from ragkit.chat import ChatSession, chat_loop
from ragkit.eval.judge import Judge
from ragkit.eval.questions import load_questions
from ragkit.eval.run import run_eval
from ragkit.pipelines.agent import AgentPipeline
from ragkit.pipelines.rag import RAGPipeline
from ragkit.reports.common import write_report
from ragkit.reports.quality import build_report
from ragkit.retrievers.agentic import AgenticRetriever
from ragkit.retrievers.vector import VectorRetriever
from ragkit.runlog import RunLog, read_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agents, or chat with one.")
    parser.add_argument("--questions", default=None, help="question set (default: the demo set)")
    parser.add_argument("--only", nargs="+", default=["baseline", "agentic", "agent"], choices=["baseline", "agentic", "agent"])
    parser.add_argument("--split", choices=["gt", "validation", "all"], default="all")
    parser.add_argument("--max-steps", type=int, default=5, help="tool-using agent: step limit")
    parser.add_argument("--chat", action="store_true", help="chat with the tool-using agent instead of evaluating")
    parser.add_argument("--judge-model", default=None)
    args = parser.parse_args()

    baseline, _, saved = open_baseline()
    folder = _corpus_folder(saved)
    print(f"Baseline: {saved['retriever']}, k={saved['k']}")

    if args.chat:
        agent = AgentPipeline(baseline.retriever, k=baseline.k, max_steps=args.max_steps, corpus_folder=folder)
        chat_loop(ChatSession(agent, log=RunLog("chat_agent", checkpoint="5", pipeline=agent)))
        return

    questions = load_questions(
        args.questions or config.PROJECT_ROOT / "data" / f"questions_demo_{config.scenario()}.xlsx",
        None if args.split == "all" else args.split,
    )
    runs = {}
    if "baseline" in args.only:
        runs["baseline"] = baseline
    if "agentic" in args.only:
        runs["agentic"] = RAGPipeline(AgenticRetriever(baseline.retriever), k=baseline.k)
    if "agent" in args.only:
        runs["agent"] = AgentPipeline(baseline.retriever, k=baseline.k, max_steps=args.max_steps,
                                      allow_clarify=False, corpus_folder=folder)
    judge = Judge(args.judge_model)
    log_paths = [run_eval(pipeline, questions, experiment=f"cp5_{name}", checkpoint="5", judge=judge)[1]
                 for name, pipeline in runs.items()]
    report = write_report(build_report(read_records(log_paths), title="Checkpoint 5 agents"), "cp5_agents")
    print(f"\nReport: {report}")


def _corpus_folder(saved: dict) -> Path | None:
    """The folder the baseline's index was built from (the agent reads whole files there)."""
    info = VectorRetriever.info(saved["index"]) if saved.get("index") else None
    return Path(info["corpus"]["folder"]) if info else None


if __name__ == "__main__":
    main()

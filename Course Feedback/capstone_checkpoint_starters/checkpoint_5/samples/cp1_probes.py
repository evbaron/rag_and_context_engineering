"""Checkpoint 1 sample: probe the model without retrieval, log every answer, compare runs.

    python samples/cp1_probes.py                     # default model, once
    python samples/cp1_probes.py --models openai/gpt-5.4-mini openai/gpt-5.4-nano
    python samples/cp1_probes.py --repeat 3          # the same probes 3 times

Each probe is sent alone (no history). Each model, and each repeat, is one run with its
own log file under RAG_WORK_DIR/logs/. At the end, a report puts the runs' answers next
to each other. Read every answer against the real document and note whether it is
correct, made up, hedged, or generic; repeats show whether the model is consistent.
That is the evidence for the Checkpoint 1.1 write-up.

Add probes about the chosen corpus to MY_PROBES below.
"""

from __future__ import annotations

import argparse

from ragkit import config
from ragkit.chat import ChatSession
from ragkit.pipelines.llm_only import LLMOnlyPipeline
from ragkit.reports.common import write_report
from ragkit.reports.runs import build_report
from ragkit.runlog import RunLog, read_records

# Example probes for each scenario (from the Checkpoint 1.1 starter and the labs).
EXAMPLE_PROBES = {
    "wikipedia": [
        "According to the Wikipedia article on the 100 metres, what is the current men's "
        "world record, who holds it, and when was it set? Quote the article.",
        "Quote the opening sentence of the Wikipedia article titled '13 (2010 film)'.",
        "List three significant events recorded in the Wikipedia article for the year 1580, "
        "quoting the article for each.",
    ],
    "papers": [
        "In the paper 'The Counterfeit Conundrum: Can Code Language Models Grasp the Nuances "
        "of Their Incorrect Generations?' (Gu et al., ACL 2024), what is the main finding about "
        "how code models perceive their own incorrect generations? Quote the relevant sentence.",
        "Quote, word for word, the first sentence of the abstract of 'The Sketching Approach "
        "to Program Synthesis'.",
        "Compare how 'The Sketching Approach to Program Synthesis' and other program-synthesis "
        "papers in this collection define the synthesis problem. Cite each paper.",
    ],
    "emails": [
        "What was the status of the government project going into 2015?",
        "Who was involved in discussions about restarting the government project?",
        "What is the CEO's home phone number?",
    ],
}

# Probes about the chosen corpus: a fact that lives in one document, a verbatim quote,
# a question across documents, and a question the corpus cannot answer.
MY_PROBES: list[str] = [
    # "A probe about the chosen corpus",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the model without retrieval.")
    parser.add_argument("--models", nargs="+", default=[config.model()], help="one or more chat models")
    parser.add_argument("--repeat", type=int, default=1, help="how many times to run the probes")
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args()

    probes = EXAMPLE_PROBES[config.scenario()] + MY_PROBES
    log_paths = []
    for model in args.models:
        for repeat in range(1, args.repeat + 1):
            pipeline = LLMOnlyPipeline(model=model, temperature=args.temperature)
            experiment = f"probes_{model.split('/')[-1]}"
            if args.repeat > 1:
                experiment += f"_r{repeat}"
            log = RunLog(experiment, checkpoint="1", pipeline=pipeline)
            session = ChatSession(pipeline, use_history=False, log=log)
            for number, probe in enumerate(probes, start=1):
                print(f"[{experiment}] probe {number}/{len(probes)}: {probe[:70]}...")
                try:
                    session.ask(probe)
                except Exception as error:
                    print(f"  error: {type(error).__name__}: {error}")
            log_paths.append(log.path)

    report = write_report(build_report(read_records(log_paths), title="Checkpoint 1 probes"), "cp1_probes")
    print(f"\nLogs:   {', '.join(path.name for path in log_paths)}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()

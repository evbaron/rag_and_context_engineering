"""Checkpoint 1 sample: chat with the model, with history on or off.

    python samples/cp1_chat.py                 # history on
    python samples/cp1_chat.py --no-history    # every question is sent alone

Try the two-turn test from Lab 1.1 in both modes:

    You: When was the War of 1812?
    You: And who won?

With history off, the second question has nothing to refer to. Type :history to see
exactly what is re-sent. Every turn is logged under RAG_WORK_DIR/logs/; compare the two
runs afterwards with:  python -m ragkit.reports.runs
"""

from __future__ import annotations

import argparse

from ragkit.chat import ChatSession, chat_loop
from ragkit.pipelines.llm_only import LLMOnlyPipeline
from ragkit.runlog import RunLog


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the model (no retrieval).")
    parser.add_argument("--no-history", action="store_true", help="send each question alone")
    parser.add_argument("--model", default=None, help="chat model (default: RAG_MODEL or gpt-5.4-mini)")
    args = parser.parse_args()

    pipeline = LLMOnlyPipeline(model=args.model)
    use_history = not args.no_history
    experiment = "chat_history_on" if use_history else "chat_history_off"
    log = RunLog(experiment, checkpoint="1", pipeline=pipeline)
    chat_loop(ChatSession(pipeline, use_history=use_history, log=log))


if __name__ == "__main__":
    main()

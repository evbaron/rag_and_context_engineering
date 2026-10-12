"""Checkpoint 2 sample: chat over the corpus with any retriever.

    python samples/cp2_chat.py                          # hybrid retrieval, history on
    python samples/cp2_chat.py --retriever bm25 --no-history
    python samples/cp2_chat.py --retriever vector --k 8

The same chat as Checkpoint 1, with retrieval in front of the model: each answer shows
the sources it came from. Every turn is logged.
"""

from __future__ import annotations

import argparse

from ragkit.chat import ChatSession, chat_loop
from ragkit.pipelines.rag import RAGPipeline
from ragkit.retrievers.factory import KINDS, make_retriever, open_documents
from ragkit.runlog import RunLog


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat over the corpus.")
    parser.add_argument("--retriever", default="hybrid", choices=KINDS)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-history", action="store_true")
    parser.add_argument("--index", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    documents, index_name = open_documents(args.index, args.limit)
    pipeline = RAGPipeline(make_retriever(args.retriever, documents, index_name), k=args.k)
    log = RunLog(f"chat_{args.retriever}", checkpoint="2", pipeline=pipeline)
    chat_loop(ChatSession(pipeline, use_history=not args.no_history, log=log))


if __name__ == "__main__":
    main()

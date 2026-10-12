"""Checkpoint 3 sample: save the configuration that later checkpoints have to beat.

    python samples/cp3_save_baseline.py --retriever hybrid --k 5 --note "best recall and quality on gt and validation"
    python samples/cp3_save_baseline.py --show

The baseline is saved to RAG_WORK_DIR/baseline.json, next to the logs, so it carries
over to the next checkpoint's folder. Checkpoints 4 and 5 open it with
ragkit.baseline.open_baseline() and compare every new idea against it.
"""

from __future__ import annotations

import argparse
import json

from ragkit.baseline import load_baseline, save_baseline
from ragkit.retrievers.factory import KINDS, open_documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Save or show the baseline configuration.")
    parser.add_argument("--retriever", choices=KINDS)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--weight-keyword", type=float, default=0.5, help="hybrid only: weight of keyword search")
    parser.add_argument("--model", default=None)
    parser.add_argument("--index", default=None, help="vector index (default: the newest)")
    parser.add_argument("--note", default="", help="why this configuration won (runs, scores)")
    parser.add_argument("--show", action="store_true", help="print the saved baseline")
    args = parser.parse_args()

    if args.show:
        print(json.dumps(load_baseline(), indent=2))
        return
    if not args.retriever:
        parser.error("--retriever is required (or use --show)")
    _, index_name = open_documents(args.index)
    path = save_baseline(args.retriever, args.k, index=index_name, model=args.model,
                         weight_keyword=args.weight_keyword, note=args.note)
    print(f"Baseline saved: {path}")
    print(json.dumps(load_baseline(), indent=2))


if __name__ == "__main__":
    main()

"""Checkpoint 2 sample: build the vector index (needed for vector and hybrid search).

    python samples/cp2_build_index.py                 # the whole corpus
    python samples/cp2_build_index.py --limit 200     # only the first 200 files, to try things out
    python samples/cp2_build_index.py --chunk-size 800

Reads the corpus, splits it into passages, shows how many tokens embedding will take
and what it will cost, and asks before spending anything. An interrupted build can be
run again: it continues where it stopped. The index is saved under
RAG_WORK_DIR/indexes/ and is reused by every later checkpoint.
"""

from __future__ import annotations

import argparse

from ragkit.corpus import DEFAULT_CHUNK_SIZE, DEFAULT_OVERLAP, load_corpus
from ragkit.embeddings import estimate_embedding_cost
from ragkit.reports.common import usd
from ragkit.retrievers.factory import corpus_settings, default_index_name
from ragkit.retrievers.vector import VectorRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the vector index.")
    parser.add_argument("--limit", type=int, default=None, help="read only the first N files")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="characters per passage")
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    parser.add_argument("--name", default=None, help="index name (default: scenario, passage size, limit)")
    parser.add_argument("--yes", action="store_true", help="do not ask before embedding")
    args = parser.parse_args()

    settings = corpus_settings(args.chunk_size, args.overlap, args.limit)
    name = args.name or default_index_name(args.chunk_size, args.limit)
    documents = load_corpus(chunk_size=args.chunk_size, overlap=args.overlap, limit=args.limit)
    sources = {document.source for document in documents}
    tokens, dollars = estimate_embedding_cost(document.text for document in documents)
    cost = f"about {usd(dollars)}" if dollars is not None else "unknown (model not in pricing.json)"
    print(f"Index '{name}': {len(documents):,} passages from {len(sources):,} files")
    print(f"Embedding: {tokens:,} tokens, {cost}")

    if not args.yes and input("Build it? [y/N] ").strip().lower() != "y":
        print("Nothing built.")
        return
    retriever = VectorRetriever.build(name, documents, settings)
    print(f"Done: {retriever.count():,} passages in {retriever.path}")


if __name__ == "__main__":
    main()

# Checkpoint 2: retrieval with keyword, vector, and hybrid search

Retrieval puts the corpus in front of the model. This checkpoint adds three retrievers
that share one interface, `retrieve(query, k)`: each is one file, and any of them plugs
into the same pipeline, chat, and logs from Checkpoint 1.

## New in this checkpoint

| File | What it does |
|---|---|
| `ragkit/corpus.py` | Reads the corpus into Documents (Wikipedia by section, papers by page, emails one per file), splits them into passages, and caches the result |
| `ragkit/embeddings.py` | The embedding client, plus token and cost estimates |
| `ragkit/retrievers/base.py` | `Hit` and `BaseRetriever`; scores are always "higher is better" |
| `ragkit/retrievers/bm25.py` | Keyword search (BM25) |
| `ragkit/retrievers/vector.py` | Vector search over a Chroma index (cosine similarity) |
| `ragkit/retrievers/hybrid.py` | Keyword and vector scores, rescaled and combined |
| `ragkit/retrievers/factory.py` | `open_documents` and `make_retriever`: every retriever searches the same passages |
| `ragkit/pipelines/rag.py` | Retrieve, then answer from the numbered passages, citing them |
| `samples/cp2_build_index.py` | Builds the vector index, showing the cost first |
| `samples/cp2_compare_retrievers.py` | The same questions through all three retrievers |
| `samples/cp2_chat.py` | Chat over the corpus with any retriever |

Continuing from Checkpoint 1 in the same project: copy these files into it (no earlier
file changes). Starting fresh from this folder instead: copy `.env` across and repeat
steps 3 and 4 of `README_SETUP.md`.

## How to use it

1. Start with keyword search: it needs no index, and searching costs nothing.
   ```
   python samples/cp2_compare_retrievers.py --retrievers bm25
   ```
   The first run reads the whole corpus: about 9 minutes for Wikipedia's 2,418
   articles, about 3 minutes for the 153 papers. Later runs read the cache in seconds.
2. Build the vector index. The script prints the tokens and the cost, then asks:
   ```
   python samples/cp2_build_index.py --limit 200    # a small trial: the first 200 files
   python samples/cp2_build_index.py                # the whole corpus
   ```
   Measured in October 2026 at the prices in `ragkit/pricing.json`: the whole Wikipedia
   corpus is 73,546 passages and 18.6 million tokens, about $0.37; the papers corpus is
   16,105 passages and 5.7 million tokens, about $0.11. An interrupted build continues
   where it stopped.
3. Compare the three retrievers on the same questions; add questions to `MY_QUESTIONS`:
   ```
   python samples/cp2_compare_retrievers.py
   python samples/cp2_compare_retrievers.py --retrieval-only    # sources only, no answers, no chat cost
   ```
4. Chat over the corpus: `python samples/cp2_chat.py --retriever hybrid`. Each answer
   lists the sources it came from.

## What to look for

- Exact names and numbers: keyword search usually finds them; vector search may not.
- Paraphrases ("fastest sprint ever run" for "100 metres world record"): vector search
  usually wins.
- Hybrid is rarely the worst of the three.
- Follow-up questions ("And who won?") retrieve badly: retrieval sees only the current
  question, not the history. Worth noting, and worth fixing later.

## For the Checkpoint 2.1 write-up

The comparison report shows, for every question, each retriever's sources and answer
side by side, with tokens and time. The logs keep every run for the measurements in
Checkpoint 3.

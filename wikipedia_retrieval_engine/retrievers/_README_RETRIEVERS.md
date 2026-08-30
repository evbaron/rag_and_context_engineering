# Wikipedia retrievers

This package adapts the Module 2 lab solutions to the Wikipedia HTML corpus:

| Retriever | Lab | What it is good at |
|---|---|---|
| `Bm25Retriever` | 1.2 | Exact terms, names, years, titles |
| `VectorRetriever` | 2.1 | Paraphrases and semantic similarity |
| `HybridRetriever` | 2.2 | Weighted fusion of the two |

Retrieval ranking lives in the retriever classes. LLM and embedding calls—and the
single authoritative system prompt—live in `llm.py`. This separation lets Checkpoint
2.1 run the same questions through several retrieval settings while keeping answer
generation consistent and collecting comparable evidence.

```
wikipedia_retrieval_engine/
  Wikipedia/                          # ~2,400 HTML articles
  retrievers/
    __init__.py                       # public API + make_retriever()
    corpus.py                         # HTML → text chunks
    base.py                           # RetrieverSpec, tokenize, BaseRetriever
    bm25.py                           # keyword retriever
    vector.py                         # Chroma retriever
    hybrid.py                         # composes BM25 + vector and fuses their results
    llm.py                            # system prompt, OpenRouter chat, embeddings
    evidence.py                       # one evidence log per configuration
    db/
      wikipedia/                      # default persistent Chroma database
  Capstone Checkpoint 2.1/
    capstone_checkpoint_2_1_baseline_retrieval_starter.py
    logs/                             # timestamped evidence files
```

The checkpoint script adds `wikipedia_retrieval_engine/` to `sys.path`, then imports `retrievers`. If you run code from another folder, do the same.

---

## Shared retrieval API

Every retriever subclass implements:

| Method | Returns | Purpose |
|---|---|---|
| `getTopK(query, k=None)` | `list[tuple[str, str, float]]` | `(doc_id, chunk_text, score)` |
| `retrievedContext(query, k=None)` | `str` | Same hits formatted for the LLM |
| `format_context(hits)` | `str` | Format existing hits without retrieving again |
| `settings()` | `dict` | Kind, label, and knobs used for this run |

`doc_id` looks like `1972_Winter_Olympics.html#0` (article file + chunk index).

`k` defaults to the retriever’s `top_k`. Scores are **not** comparable across kinds: BM25 is higher-is-better raw, Chroma is a distance (lower-is-better), hybrid is a fused `[0, 1]` weighted sum.

---

## File-by-file

### `__init__.py`

Package entry point. Re-exports the classes and helpers you usually need, and defines `make_retriever()`.

`make_retriever(spec, *, chunks=None, db=None, wiki_dir=None, chroma_db_name="wikipedia", ...)` builds one of:

- `"bm25"` → `Bm25Retriever`
- `"vector"` → `VectorRetriever`
- `"hybrid"` → `HybridRetriever`

Pass either a `RetrieverSpec` or a kind string (`"bm25"`). Optional keyword overrides (`top_k`, `weight_bm25`, …) apply on top of the spec.

Pass the same `chunks` and `db` into every experiment so Wikipedia is parsed once and Chroma is opened once.

### `corpus.py`

Turns Wikipedia HTML into the units that BM25 and Chroma index.

**Constants**

- `DEFAULT_WIKI_DIR` — `wikipedia_retrieval_engine/Wikipedia`
- `DEFAULT_CHROMA_DB_ROOT` — `retrievers/db`
- `DEFAULT_CHROMA_DB_NAME` — `wikipedia`
- `DEFAULT_CHROMA_DIR` — compatibility constant for `retrievers/db/wikipedia`
- `CHUNK_SIZE = 1600`, `CHUNK_OVERLAP = 200`

**`WikiChunk`** — one indexable piece:

- `doc_id` — unique, e.g. `100_metres.html#2`
- `source` — filename
- `title` — article title
- `text` — extracted plain text
- `chunk_index` — 0-based position in that article

**Pipeline**

1. `extract_title_and_body(raw)` — title from `mw-page-title-main` (fallback: `<title>`). Body from `mw-content-text` up to References / Notes.
2. `html_to_text()` — stdlib `HTMLParser`; drops `script` / `style` / `svg` and `[edit]` links.
3. `chunk_text()` — ~1600-character windows with overlap, breaking on paragraphs or sentences when possible. Long articles stay inside the embedding token limit.
4. `load_wikipedia_chunks(wiki_dir=None, *, filenames=None, max_files=None, chunk_size=..., overlap=...)` — walks `*.html` (skips names starting with `_`). Use `filenames=[...]` for a small test set.

### `base.py`

Retrieval-only. No LangChain, no API calls.

**Defaults** (override per experiment; do not treat these as fixed):

| Name | Default | Used by |
|---|---|---|
| `DEFAULT_TOP_K` | 4 | All retrievers — how many chunks to return |
| `DEFAULT_CANDIDATE_POOL` | 10 | Hybrid — how many hits to pull from **each** side before fusion |
| `DEFAULT_WEIGHT_BM25` | 0.5 | Hybrid fusion weight |
| `DEFAULT_WEIGHT_VECTOR` | 0.5 | Hybrid fusion weight |

**`RetrieverSpec`** — one experiment row:

```python
RetrieverSpec(
    kind="hybrid",              # "bm25" | "vector" | "hybrid"
    label="hybrid_bm25_heavy",  # name written into logs
    top_k=4,
    candidate_pool=10,          # hybrid only
    weight_bm25=0.7,            # hybrid only
    weight_vector=0.3,          # hybrid only
)
```

`RetrieverSpec` validates configuration when it is created: `top_k >= 1`, a nonempty
label, a supported kind, nonnegative hybrid weights, and
`candidate_pool >= top_k` for hybrid retrieval. At least one hybrid weight must be
greater than zero. `as_dict()` is a compact settings snapshot for logging.

**Helpers**

- `tokenize(text)` — lowercase alphanumeric tokens, stopwords removed (same tokenizer for index and query).
- `normalize_scores(scores, invert=False)` — min-max to `[0, 1]`. `invert=True` flips Chroma distance so **higher = more similar**.

**`BaseRetriever`** — abstract: `getTopK`, plus `retrievedContext`,
`format_context`, and `settings`.

Prefer `format_context(hits)` after calling `getTopK()`. This guarantees the LLM sees
the exact hits that were printed and logged. `retrievedContext(query)` is a convenience
method that performs retrieval itself.

### `bm25.py` — `Bm25Retriever`

Lab 1.2 keyword search via `rank_bm25.BM25Okapi`.

- Builds an in-memory index over chunk texts.
- `getTopK` tokenizes the query, scores every chunk, returns the top `k` with score `> 0`.
- No embeddings and no API key.

Constructor: `Bm25Retriever(wiki_dir=None, chunks=None, top_k=4, label="bm25")`. Prefer passing `chunks` if you already loaded the corpus.

### `vector.py` — `VectorRetriever` and `build_or_load_db`

Lab 2.1 semantic search via Chroma + OpenRouter embeddings (`openai/text-embedding-3-small`).

**`build_or_load_db(wiki_dir=None, chroma_db_name="wikipedia", chunks=None)`**

- Resolves the index path as `retrievers/db/<chroma_db_name>`.
- If that named directory already has files, it **loads** them (no re-embed), including after
  Python or the computer has restarted.
- Otherwise it embeds chunks in batches of 64 and persists to that directory.
- Names may contain letters, numbers, `.`, `_`, and `-`; path separators and traversal
  names are rejected.
- First full-corpus build is slow and uses embedding credits. Remove or rename only
  the selected named directory if you intentionally need to rebuild it.

**`VectorRetriever`**

- `getTopK` calls `similarity_search_with_score`. The returned score is a **distance** (lower is closer).
- Metadata on each Chroma document: `source` (doc_id), `title`, `article` (filename).

Requires `OPENROUTER_API_KEY` because both the initial document embeddings and every
new query embedding go through OpenRouter. Loading the persisted database avoids
re-embedding documents, but searches still embed their query.

### `hybrid.py` — `HybridRetriever`

Lab 2.2 fusion. It composes `Bm25Retriever` from `bm25.py` and
`VectorRetriever` from `vector.py`; it does not duplicate either retrieval
implementation.

```text
Bm25Retriever ───┐
                 ├── HybridRetriever → normalize → weight → rank
VectorRetriever ─┘
```

For each query:

1. Take `candidate_pool` hits from BM25 and `candidate_pool` from vector.
2. Min-max normalize BM25 scores (higher stays better).
3. Min-max normalize vector **distances** with `invert=True`.
4. Normalize the configured weights so `7 / 3` and `0.7 / 0.3` mean the same thing.
5. Fused score:  
   `weight_bm25 * bm25_norm + weight_vector * vector_norm`
6. A chunk seen on only one side contributes `0` from the missing side.
7. Sort by fused score descending and keep `top_k`.

`make_retriever()` constructs and injects both component retrievers. You may also
inject `bm25_retriever=` and `vector_retriever=` directly when constructing
`HybridRetriever`, which is useful for testing or explicit reuse.

Constructor knobs: `top_k`, `candidate_pool`, `weight_bm25`, and `weight_vector`.
When components are not injected, shared `chunks` / `db` may be provided and the
hybrid constructor creates them.

Raise `weight_bm25` when queries use exact names/years. Raise `weight_vector` when queries paraphrase the article wording.

### `llm.py`

All model I/O. Retrievers do not import this except `vector.py` → `get_embeddings()`.

| Symbol | Role |
|---|---|
| `LLM_MODEL` | `openai/gpt-5.4-mini` (course credits) |
| `EMBEDDING_MODEL` | `openai/text-embedding-3-small` |
| `SYSTEM_PROMPT` | The single default prompt: answer only from Wikipedia context, quote, and do not guess |
| `load_api_key()` / `require_api_key()` | Reads `.env` from `rag_and_context_engineering/`, `capstone/`, or cwd |
| `make_llm()` | Chat client |
| `get_embeddings()` | Embedding client for Chroma |
| `answer(query, context, llm=None, system_prompt=SYSTEM_PROMPT)` | Sends a `SystemMessage` plus the retrieved context and question. Does not search. |

The ChatOpenAI client itself does not store a system prompt. `answer()` explicitly
passes `system_prompt` as a LangChain `SystemMessage` on every call. The checkpoint
does not define a second prompt or a second model factory.

### `evidence.py` — `EvidenceLogger`

Evidence logging is separate from retrieval and LLM calls. One `EvidenceLogger` is
created for each retriever configuration at the start of a checkpoint run.

Each file begins with a JSON configuration header containing:

- run ID and creation time
- complete retriever settings and score interpretation
- corpus directory, article count, and chunk count
- chunking strategy, character size, and overlap
- Chroma database name, directory, and embedding model (when applicable)
- LLM model, temperature, and full system prompt
- question count and logged snippet length

Each question then records:

1. The original query.
2. Unique retrieved article filenames, ranked by the first matching chunk.
3. Every retrieved chunk ID, score, rank, and text snippet.
4. The grounded LLM answer.

`format_articles(hits)` and `format_chunks(hits)` are also used for readable terminal
output. Article aggregation is important because several retrieved chunks may come
from the same Wikipedia article.

---

## How to run experiments (Checkpoint 2.1)

1. Activate the course venv and install extras if needed:

   ```bash
   pip install python-dotenv langchain-openai langchain-core langchain-chroma rank-bm25
   ```

2. Put `OPENROUTER_API_KEY=...` in `rag_and_context_engineering/.env`.

3. In `Capstone Checkpoint 2.1/capstone_checkpoint_2_1_baseline_retrieval_starter.py`, edit `EXPERIMENTS` and `my_representative_queries()`.

4. Run that script. `run_wikipedia()` will:

   - load Wikipedia chunks once
   - open or build `retrievers/db/<CHROMA_DB_NAME>` once only if a spec is
     `vector` or `hybrid`
   - share that loaded Chroma object among vector and hybrid experiments
   - create one configuration-specific evidence file per retriever
   - for each query × each spec: retrieve once, format those exact hits, call
     `answer()`, print, and append to that retriever's evidence file

Example experiment list:

```python
EXPERIMENTS = [
    RetrieverSpec(kind="bm25", label="bm25_k4", top_k=4),
    RetrieverSpec(kind="vector", label="vector_k4", top_k=4),
    RetrieverSpec(kind="hybrid", label="hybrid_50_50", top_k=4,
                  weight_bm25=0.5, weight_vector=0.5),
    RetrieverSpec(kind="hybrid", label="hybrid_bm25_heavy", top_k=4,
                  weight_bm25=0.7, weight_vector=0.3),
    RetrieverSpec(kind="hybrid", label="hybrid_vector_heavy", top_k=4,
                  weight_bm25=0.3, weight_vector=0.7),
]
```

Example filenames:

```text
20260829_120000_123456__bm25-k4__chars1600-o200.log
20260829_120000_123456__vector-k4__index-wikipedia_chars1600_overlap200.log
20260829_120000_123456__hybrid-k4-p10-bm70-vec30__index-wikipedia_chars1600_overlap200.log
```

The shared run ID groups files produced by the same execution. BM25 filenames identify
their character chunking because there is no persistent index. Vector and hybrid
filenames identify the Chroma index, whose name should describe its chunking strategy.
Human labels are deliberately omitted because they often repeat the generated settings.
The header remains the authoritative full configuration and still records the label.
If identical settings occur twice in one run, the later filename receives `__2`,
`__3`, and so on instead of overwriting an earlier file.

For every question, the log contains both a unique article list and chunk-level
evidence. This supports manual review: you can compare which articles each strategy
found, identify irrelevant results, and record an article you expected but did not see.

`run_sample_corpus()` is the original 6-document toy baseline. It is commented out at the bottom of the checkpoint script.

---

## How to use the package directly

```python
import sys
from pathlib import Path

engine = Path(".../wikipedia_retrieval_engine")
sys.path.insert(0, str(engine))

from retrievers import RetrieverSpec, load_wikipedia_chunks, make_retriever, build_or_load_db
from retrievers.llm import answer, make_llm

chunks = load_wikipedia_chunks()          # or filenames=["100_metres.html", ...]
db = build_or_load_db(
    chroma_db_name="wikipedia_full",
    chunks=chunks,
)                                          # skip this for BM25-only

bm25 = make_retriever(RetrieverSpec(kind="bm25", label="bm25_k4", top_k=4), chunks=chunks)
hybrid = make_retriever(
    RetrieverSpec(kind="hybrid", label="hybrid_70_30", weight_bm25=0.7, weight_vector=0.3),
    chunks=chunks,
    db=db,
    chroma_db_name="wikipedia_full",
)

query = "Where were the 1972 Winter Olympics held?"
hits = bm25.getTopK(query)
context = bm25.format_context(hits)  # reuse exactly what was retrieved/logged

# optional: generate a grounded answer
llm = make_llm()
print(answer(query, context, llm=llm))
```

You can also construct classes without the factory:

```python
from retrievers import Bm25Retriever, VectorRetriever, HybridRetriever

Bm25Retriever(chunks=chunks, top_k=6, label="bm25_k6")
VectorRetriever(db=db, top_k=4, label="vector_k4")
bm25_component = Bm25Retriever(chunks=chunks, top_k=15, label="hybrid_bm25")
vector_component = VectorRetriever(db=db, top_k=15, label="hybrid_vector")
HybridRetriever(bm25_retriever=bm25_component,
                vector_retriever=vector_component,
                top_k=4, candidate_pool=15,
                weight_bm25=0.6, weight_vector=0.4,
                label="hybrid_custom")
```

---

## Practical notes

- **BM25-only** needs no embeddings and is the cheapest way to collect first evidence.
- **Vector / hybrid** need an API key. The first embed writes
  `retrievers/db/<chroma_db_name>` and later runs reuse it.
- Use different names for genuinely different indexes, for example
  `wikipedia_chunk_1600` and `wikipedia_chunk_800`.
- The current loader considers any nonempty named database directory reusable. It does not yet
  validate an index manifest.
- Rebuild Chroma if the source corpus, extraction logic, embedding model,
  `CHUNK_SIZE`, or `CHUNK_OVERLAP` changes; otherwise the persisted vectors may be
  stale. Remove or rename only the specific directory under `retrievers/db/` when
  intentionally rebuilding.
- Hybrid weights do not need to sum to `1.0`; the constructor normalizes them.
- `candidate_pool` should be `>= top_k`. Larger pools give fusion more documents to choose from.
- Importing the checkpoint is safe: experiments run only under its
  `if __name__ == "__main__"` guard.
- Do not commit `.env` or API keys. Chroma directories under `retrievers/db/` can be
  large; keep them local unless you intentionally version them.

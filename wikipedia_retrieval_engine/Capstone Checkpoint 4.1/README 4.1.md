# Preparation
Recording steps here.

## Corpus re-architecture: DOM-based extraction (Markdown + JSON sidecar)

**What changed.** Replaced the original HTML→plain-text pipeline (Python's stdlib
`html.parser`, a *stream / event-based* parser with no model of the document tree) with
**DOM-based extraction**: BeautifulSoup + lxml parse each article into a navigable tree,
and markdownify serializes the cleaned prose. Code is in `retrievers/corpus.py`
(`build_or_load_markdown_store`, `extract_markdown_article`, `MarkdownArticleStore`).
Full detail lives in `retrievers/_README_ARTCILE_CORPUS.md`.

*Extractor v2 refinement:* navigation templates are stripped by `[role="navigation"]`
plus `.sidebar` (v1 stripped only `.navbox`/`.vertical-navbox`, so `.sidebar`
templates — present in ~10% of articles — leaked into the markdown as tables and
polluted the sidecar link buckets). Verified: 0 `role="navigation"` nodes remain after
stripping, and all data (`.wikitable`) tables are preserved.

**Why.** The text approach *flattened* each page to plain text, discarding its document
structure — including the row/column relationships tables use to encode facts (e.g.,
which entry in a results table is the winner vs. a nominee, or values compared across
years). A stream parser can't reconstruct a table grid, so tables collapsed and links
were dropped. This surfaced as partial answers on table/aggregation questions and weak
article-level recall.

**What it produces.** Two artifacts per article, in
`retrievers/db/article_text/wikipedia_markdown/` (2,417 articles, 0 failures, ~287 MB):

- `<source>.html.md` — a **content representation** preserving document structure:
  section hierarchy (`##`/`###`), the infobox as key→value bullets, data tables as
  GitHub-flavored Markdown tables, blockquotes, captions, and inline links.
- `<source>.html.json` — a **structured-metadata sidecar** (the substrate for the graph):
  title, categories, sections, infobox fields, table headers + rows, and links.

**Link classification.** Every link is bucketed so we can tell what is locally
referenceable from what is external:

- `local` — `/wiki/<X>` where `<X>.html` is in our corpus (an in-corpus article→article edge);
- `wiki` — a real Wikipedia article not in our corpus (pullable later via its URL);
- `external` — off-wiki links (citations, YouTube, official sites).

**Why it matters for retrieval.** The Markdown feeds cleaner, structure-aware chunks;
the sidecar exposes **relationships between articles** (shared categories, hyperlinks)
that a flat chunk index cannot represent — the foundation for graph-augmented retrieval.
The signal is dense enough to be useful: 83% of articles have an infobox, 61% a data
table, the in-corpus link graph has ~17k edges (only 6% of articles isolated), and 80%
of articles share a category with another.

## Validation set (guard against overfitting / the "sharpshooter fallacy")

Built a 25-question validation set used only to *review* results, never for
development/tuning: 10 rephrased from the development GT + 15 new. An independent set
avoids tuning to the very questions we measure on.

> **Resolved — independence/difficulty:** audited all 10 rephrases against their GT
> twins. None were verbatim. Four had drifted *easier* (added hints/procedural detail):
> VAL03 (revealed the "total vs gold-rank" trap), VAL05, VAL07, VAL08. All four were
> rewritten to *parity* — same reference answer, reworded surface, hints removed. VAL01
> and VAL04 were judged acceptable (they only name output fields). A validation rephrase
> must vary surface form while holding answer + difficulty constant; harder *or* easier
> both bias the estimate.
>
> **Open item — variance:** LLM outputs are non-deterministic, so a single run is not
> conclusive. Run the validation set (and the matching baseline) 2–3× and compare
> averages, not single runs (mirrors the Checkpoint 3.1 finding). First multi-question
> re-run already looks more typical than the near-perfect first run.

## Failure analysis: where the baseline breaks (baseline vs oracle)

Ran the baseline retriever and the **oracle** (perfect / gold-article context) on the
evaluation set, grouped by task family. The **oracle gap** (oracle quality − baseline
quality) is the key column: a large positive gap means *retrieval* is the bottleneck; a
gap near zero means better retrieval wouldn't help — the failure is elsewhere.

| Task family | Q | Baseline quality | Fail % | Oracle quality | Oracle gap | Article recall |
|---|---|---|---|---|---|---|
| Exhaustive list or time filter | 5 | 0.340 | 64.0% | 0.322 | −0.018 | 86.7% |
| Evidence selection or explanation | 3 | 0.767 | 20.0% | 0.815 | +0.048 | 100.0% |
| Entity relationship or historical synthesis | 6 | 0.867 | 10.0% | 1.000 | +0.133 | 87.5% |
| Cross-table quantitative reasoning | 2 | 1.000 | 0.0% | 0.972 | −0.028 | 75.0% |
| Direct fact or table lookup | 3 | 1.000 | 0.0% | 1.000 | +0.000 | 100.0% |

Reading it:

- **Exhaustive list / time filter** is the dominant failure (64% fail, quality 0.340).
  Its oracle gap is **≈ 0** (−0.018) with **86.7% recall** — retrieval already finds the
  article, and *perfect* context doesn't help. The bottleneck is **not retrieval**: the
  answer-bearing content (tables) is destroyed in the flattened plain-text context, so
  even the gold article is unusable.
- **Entity relationship / historical synthesis** has a **positive** oracle gap (+0.133) —
  better context *does* help → a *retrieval* limitation (later target for decomposition /
  graph).
- Direct lookups and (n=2) cross-table are already near ceiling.

**Two distinct failure modes:** (1) table/aggregation answers lost to **flattened
context** (representation); (2) cross-article synthesis limited by **single-pass
retrieval**. Caveat: oracle-gap≈0 can't by itself separate "mangled tables" from "model
can't aggregate," because the oracle context *also* used plain-text. The markdown swap
below is the experiment that discriminates them.

## Strategy + architecture change: markdown context swap (isolate one variable)

- **Baseline pipeline:** retrieve top-k character chunks → dedupe to articles → send
  **full plain-text articles** to the LLM (context = `wikipedia_plain_text`).
- **Change:** keep retrieval *identical*; swap the context source to the **markdown**
  store (tables/infobox preserved). This changes a **single variable** (context
  representation), so any gain is attributable to it — a clean ablation and the direct
  test of failure mode (1).
- **Implementation:** `CONTEXT_SOURCE = "markdown"` in
  `capstone_checkpoint_4_1_with_retriever.py` (switch between `plain_text` and
  `markdown`); `MarkdownArticle` exposes `.text` so it drops into the existing
  full-article context path. **No re-embedding, no index rebuild.**
- **New base:** re-run GT + validation as `starting_quality_base_4.1`, 2–3× (variance).

## Reusable evaluation scripts
Need to establish exisitng base line for new validation set
Checkpoint 4.1 contains copies of the oracle-context and end-to-end retrieval
evaluators from Checkpoint 3.1:

- `capstone_checkpoint_4_1_oracle_AI_only.py`
- `capstone_checkpoint_4_1_with_retriever.py`

The Checkpoint 3.1 scripts remain unchanged. Both Checkpoint 4.1 scripts require two
named command-line arguments:

- `--gt-set`: the CSV evaluation set to load. It must use the
  `wikipedia_GT.csv` column schema.
- `--output-dir`: the RAGAS root directory in which datasets and experiment CSVs
  will be saved. The directory is created when it does not exist.
- `--experiment-name` / `--config-name`: optional comparison label written into
  each result row. Use names like `oracle`, `oracle_markdown`, or
  `vector_search_base`. If omitted, `analyze_ragas_experiments.py` derives the
  configuration name from the run metadata as before.

From the `rag_and_context_engineering` repository root, run the validation set with
oracle context:

```bash
cd rag_and_context_engineering/wikipedia_retrieval_engine
python "Capstone Checkpoint 4.1/capstone_checkpoint_4_1_oracle_AI_only.py" \
  --gt-set "GT/wikipedia_GT_validation_set.csv" \
  --output-dir "Capstone Checkpoint 4.1/ragas_validation_experiments" \
  --experiment-name oracle_markdown
```

Run the same validation set through the active retriever configuration:

```bash
python "Capstone Checkpoint 4.1/capstone_checkpoint_4_1_with_retriever.py" \
  --gt-set "GT/wikipedia_GT_validation_set.csv" \
  --output-dir "Capstone Checkpoint 4.1/ragas_validation_experiments" \
  --experiment-name vector_search_base
```

Using a separate output directory for validation prevents its results from being
silently mixed with the Checkpoint 3.1 development experiments. The same scripts can
run another compatible GT set by changing only the two command-line paths.

## Analyze the validation experiments

After the oracle and retriever runs have created experiment CSVs, generate the PDF
comparison report with:

```bash
python "utils/analyze_ragas_experiments.py" \
  --experiments-dir "Capstone Checkpoint 4.1/ragas_validation_experiments/experiments" \
  --output "Capstone Checkpoint 4.1/ragas_validation_evaluation_report.pdf" \
  --title "Capstone Checkpoint 4.1 validation-set RAGAS evaluation"
```

Run this command from `rag_and_context_engineering/wikipedia_retrieval_engine`, the
same directory selected by the `cd` command in the oracle example above. The analyzer
reads saved CSV files and does not make LLM or API calls. When a CSV includes
`experiment_name` or `config_name`, that value becomes the comparison group shown in
the report; older or unnamed CSVs still use the analyzer's derived configuration name.

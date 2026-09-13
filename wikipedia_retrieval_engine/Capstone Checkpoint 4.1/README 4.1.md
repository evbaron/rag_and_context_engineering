# Preparation
Recording steps here.

## Corpus re-architecture: DOM-based extraction (Markdown + JSON sidecar)

**What changed.** Replaced the original HTML→plain-text pipeline (Python's stdlib
`html.parser`, a *stream / event-based* parser with no model of the document tree) with
**DOM-based extraction**: BeautifulSoup + lxml parse each article into a navigable tree,
and markdownify serializes the cleaned prose. Code is in `retrievers/corpus.py`
(`build_or_load_markdown_store`, `extract_markdown_article`, `MarkdownArticleStore`).
Full detail lives in `retrievers/_README_ARTCILE_CORPUS.md`.

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

> **Open item — independence:** confirm the validation set does not reuse development
> questions *verbatim*. Overlaps to check: GT-03≙VAL02, GT-07≙VAL05, GT-10≙VAL07.
>
> **Open item — variance:** LLM outputs are non-deterministic, so a single run is not
> conclusive. Run the validation set (and the matching baseline) 2–3× and compare
> averages, not single runs (mirrors the Checkpoint 3.1 finding).

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

From the `rag_and_context_engineering` repository root, run the validation set with
oracle context:

```bash
cd rag_and_context_engineering/wikipedia_retrieval_engine
python "Capstone Checkpoint 4.1/capstone_checkpoint_4_1_oracle_AI_only.py" \
  --gt-set "GT/wikipedia_GT_validation_set.csv" \
  --output-dir "Capstone Checkpoint 4.1/ragas_validation_experiments"
```

Run the same validation set through the active retriever configuration:

```bash
python "Capstone Checkpoint 4.1/capstone_checkpoint_4_1_with_retriever.py" \
  --gt-set "GT/wikipedia_GT_validation_set.csv" \
  --output-dir "Capstone Checkpoint 4.1/ragas_validation_experiments"
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
reads saved CSV files and does not make LLM or API calls.

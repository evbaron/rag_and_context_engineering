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

### Analyze the validation experiments

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

## Failure analysis: where the baseline breaks (baseline vs oracle)

Ran the baseline retriever and the **oracle** (perfect / gold-article context) on the
evaluation set, grouped by task family. The **oracle gap** (oracle quality − baseline
quality) is the key column: a large positive gap means *retrieval* is the bottleneck; a
gap near zero means better retrieval wouldn't help — the failure is elsewhere.


| Task family                                 | Q   | Baseline quality | Fail % | Oracle quality | Oracle gap | Article recall |
| ------------------------------------------- | --- | ---------------- | ------ | -------------- | ---------- | -------------- |
| Exhaustive list or time filter              | 5   | 0.340            | 64.0%  | 0.322          | −0.018     | 86.7%          |
| Evidence selection or explanation           | 3   | 0.767            | 20.0%  | 0.815          | +0.048     | 100.0%         |
| Entity relationship or historical synthesis | 6   | 0.867            | 10.0%  | 1.000          | +0.133     | 87.5%          |
| Cross-table quantitative reasoning          | 2   | 1.000            | 0.0%   | 0.972          | −0.028     | 75.0%          |
| Direct fact or table lookup                 | 3   | 1.000            | 0.0%   | 1.000          | +0.000     | 100.0%         |


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

## Controlled ablation: does context representation cause the table failures? (markdown vs plain-text)

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
- **How it was run:** `vector_k7` on the char index, GT set, flipping `CONTEXT_SOURCE`
between `plain_text` and `markdown`, compared against the Checkpoint 3.1 plain-text run
(`retriever_active_vector_search`) — same retriever, index, and question set, so only the
context representation differs. Result in the next section.



## Ablation result (Step 5): context representation — no measurable effect

Matched comparison — **only the context representation differs**. Both runs are `vector_k7`,
char index, GT set (19 Q), and article **recall is identical (0.899)**, which confirms retrieval
was held constant (plain-text = Checkpoint 3.1 `retriever_active_vector_search`; markdown =
Checkpoint 4.1 markdown run).


| metric                                    | plain_text | markdown | Δ (md − pt) |
| ----------------------------------------- | ---------- | -------- | ----------- |
| Retriever — overall quality               | 0.747      | 0.754    | **+0.007**  |
| Retriever — exhaustive-list / time-filter | 0.340      | 0.367    | +0.027      |
| Oracle (perfect context) — overall        | 0.789      | 0.737    | **−0.053**  |
| Oracle — exhaustive-list / time-filter    | 0.322      | 0.267    | −0.055      |


Both overall deltas sit within run-to-run noise (3–5 runs each). **Conclusion: markdown context
neither helped nor hurt.** The dominant failure family (exhaustive-list / time-filter) stayed at
~0.34–0.37 regardless of format, and *even with perfect gold markdown articles* scored ~0.27. So
the original hypothesis — "preserving tables in markdown will fix the table/aggregation
questions" — is **not supported**. This clean ablation rules representation out as the cause.

## Impact analysis (Step 6): the bottleneck is reasoning, not retrieval or representation

Two suspects are now eliminated with evidence:

- ❌ **Retrieval** — oracle ≈ retriever (gap ≈ 0): perfect gold articles don't beat retrieved ones.
- ❌ **Representation** — markdown ≈ plain-text (Δ ≈ 0, above): clean tables don't beat mangled ones.
- ✅ **Reasoning** — the model cannot reliably *enumerate → filter-by-year → aggregate* over a
table, even when the pristine table sits in the gold context. Format is irrelevant if the model
won't compute over it correctly.

**Where the markdown work still pays off:** not prettier LLM context (a wash), but the
**structured sidecar** — table headers+rows, categories, links — which is the substrate a
reasoning fix needs (compute over structured rows, or decompose the question) instead of hoping
the LLM reads a 30-row table correctly. It also remains the foundation for graph retrieval.

**Next strategy (evidence-justified):** **query decomposition** (Lab 4.1) for the
exhaustive-list / aggregation family — break each question into enumerate / filter / count steps —
optionally paired with structured-table reasoning from the sidecar. Ruling out retrieval and
representation is precisely what *justifies* choosing decomposition rather than guessing at it.

# Decomposition



## Advanced retrieval: query decomposition + reasoning (GT set, k=7)

**What it does.** `MultiStepRetriever` decomposes each question into ≤4 focused
sub-queries, runs vector search for each **in parallel**, and merges (a chunk found by
several sub-queries ranks higher). The same step emits **reasoning instructions** that
are appended to the answer prompt (reasoning-decomposition). Chroma index, markdown
context, and GT set are held identical to the baseline, so only the retrieval+reasoning
strategy changes. Code: `retrievers/multistep.py` (`retrieve_with_reasoning`) +
`capstone_checkpoint_4_1_advanced_retrieval_starter.py`.

**Results vs the markdown baseline** 

([Query Decomposition w/Reasoning - full RAGAS report](ragas_GT_evaluation_decomposed_wReasoning.pdf)):


| metric                                   | base_k7   | decomp+reason_k7 |
| ---------------------------------------- | --------- | ---------------- |
| overall quality                          | 0.744     | 0.763            |
| overall article recall                   | 0.897     | 0.896            |
| **Exhaustive-list / aggregation family** | **0.257** | **0.375**        |
| Entity-relationship / synthesis          | 0.917     | 0.896            |
| Evidence selection / explanation         | 0.786     | 0.750            |


Overall quality is ~flat (+0.019, within run-to-run noise), but that hides a **targeted
win on the aggregation family** (0.257 → 0.375):

- **GT07** (Best Actor, most wins 2000–2020): **0.50 → 0.88** — the reasoning steps
(list winners → filter years → count) worked.
- **GT13** (Russia-identity timeline): **0.71 → 1.00**.
- GT03 (3-ceremony intersection), GT10 / GT11 (large Sport/Years tables): still ~0 —
reasoning did not crack big-table or cross-article aggregation. These are the target
for **structured-table computation** over the sidecar rows (future work).

Retrieval-side, decomposition also lifted multi-article **recall** (e.g. GT09 0.50→1.00,
GT14 0.75→1.00), converting some to passes.

**Top-k: 7 beats 5.** k=5 dropped recall (0.897 → 0.848) and quality (0.763 → 0.737):
with fewer slots the merge can't fit every article a multi-source question needs (the
crowding effect). Using **k=7**.

## The easy-family dip — and the targeted-reasoning fix

The reasoning steps **help the aggregation family but slightly hurt the easy families** —
Entity-synthesis 0.917 → 0.896, Evidence 0.786 → 0.750. Appending "steps to follow" to
questions that don't need multi-step reasoning mildly over-scaffolds them, which is why
the overall number stays flat (aggregation gains ≈ easy-family losses). Overall recall is
unchanged (0.896 vs 0.897), so this is a *reasoning* effect, not a retrieval one.

**Fix — targeted reasoning:** emit reasoning instructions **only** for questions that
need multi-step reasoning (enumeration / filtering / counting / cross-referencing); for
simple lookups, emit `NONE` so the answer step runs the plain baseline path. Keeps the
aggregation win without the easy-question penalty — and it's principled regardless of how
much of the small dip is noise (don't add steps a question doesn't need).

## Targeted Decomposition with Reasoning (correcting slight dip in the simple question queries)

([Query Targeted Decomposition w/Reasoning - full RAGAS report](ragas_GT_evaluation_targeted_decomposition.pdf)):

Gating reasoning to multi-step questions only (`NONE` for simple lookups) partly recovered
the easy-family dip, but the effect is within noise and overall quality stayed flat:

| family (GT, k=7) | base | decomp+reason (blanket) | targeted |
|---|---|---|---|
| Entity synthesis | 0.917 | 0.883 | 0.896 |
| Evidence selection | 0.786 | 0.733 | 0.750 |
| Exhaustive-list / aggregation | 0.257 | 0.320 | 0.300 |
| **overall quality** | **0.744** | **0.742** | **0.743** |

The gate fired reasoning on 63% of questions (vs 80% blanket) and nudged the easy families back
toward base — but they stayed marginally below it, and with only 3–6 questions per family these
deltas are within run-to-run noise. **Net: overall quality is flat across base / blanket / targeted
(~0.744).** The robust, cross-run wins are per-question (GT07, GT13) and multi-article recall, not an
overall lift.

## Validation Set Run

Ran targeted decomposition on the independent validation set (25 Q):

| config (validation) | quality | recall |
|---|---|---|
| plain-text baseline (3.1, no decomposition) | 0.907 | 0.973 |
| markdown + targeted decomposition | 0.845 | 0.953 |

**Caveat — confounded comparison:** the only validation baseline on hand is plain-text /
no-decomposition (Checkpoint 3.1); the decomposition run is markdown + decomposition + reasoning,
so this mixes three changes. A clean comparator (markdown, no-decomposition, on validation) was not
run.

Even so, the signal matches the GT set and is honest: **the advanced pipeline does not beat the
simple baseline overall**, and on validation it *regressed* Entity-synthesis (1.00 → 0.75) and
aggregation (0.60 → 0.40). Decomposition + reasoning add two non-deterministic LLM calls, so the
pipeline is **higher-variance** — matched GT/VAL twins diverge sharply (GT07 0.88 vs VAL05 0.375;
GT13 1.00 vs VAL08 0.625), and retrieval crowding cost recall on some multi-article questions.

**Conclusion.** Decomposition + reasoning is a **targeted** tool: it fixes specific single-table
aggregation questions (GT07/GT13) but does not raise overall quality, and it adds variance and
occasional regressions on questions single-pass already handled — the cost/latency of the extra LLM
calls isn't repaid in aggregate on this corpus. The remaining hard questions (cross-article
intersection, large tables) need structured-table computation.

# Structured Table Computation

**Proposal (not implemented — time).** The stuck questions (GT03 intersection, GT10/GT11 large
Sport/Years tables, VAL02/VAL07) fail because the LLM can't reliably compute over a many-row table
even when it sits in context. The **sidecar already parses every table into `headers` + `rows`** — so
instead of asking the LLM to eyeball a 30-row table, load the relevant table's rows and do the
filter / count / intersection in **Python**, then hand the LLM the computed result to phrase.
Deterministic aggregation can't miscount. Open piece: routing a question to the right table
(heuristics over the question + the retrieved article's sidecar). This is the highest-leverage
remaining lever for the aggregation family.


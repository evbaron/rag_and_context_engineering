# MITxPRO RAG and Context Engineering Capstone Project

This repository contains a Wikipedia retrieval engine developed across the MIT xPRO
RAG and Context Engineering capstone checkpoints. The project separates four parts of
the system so that they can be tested independently: corpus preparation, retrieval,
context construction, and answer generation.

The selected capstone scenario is the **Wikipedia Retrieval Engine**. It answers
single-article and multi-article questions over a local collection of 2,419 Wikipedia
HTML files. The evaluation set includes direct facts and quotations, table lookups,
time-bounded lists, cross-article comparisons, relationships among people and places,
geopolitical timelines, calculations, conflicting estimates, and questions that
require caution about causal inference.

## Documentation map

For a practical introduction to the LangChain APIs used by this project—including
LCEL, OpenRouter configuration, Chroma, RAG patterns, version migration, adaptive
LangGraph workflows, and common failure modes—see
[LangChain tutorial, reference, and gotchas](LANGCHAIN_GUIDE.md).

Checkpoint READMEs record the project decisions and experimental evidence:

- [Checkpoint 2.1 retrieval notes](wikipedia_retrieval_engine/Capstone%20Checkpoint%202.1/README%202.1.md)
- [Checkpoint 3.1 baseline evaluation](wikipedia_retrieval_engine/Capstone%20Checkpoint%203.1/README%203.1.md)
- [Checkpoint 4.1 advanced retrieval](wikipedia_retrieval_engine/Capstone%20Checkpoint%204.1/README%204.1.md)
- [Checkpoint 5.1 agentic evidence graph](wikipedia_retrieval_engine/Capstone%20Checkpoint%205.1/README%205.1.md)
- [Checkpoint 6.1 security and cost audit](wikipedia_retrieval_engine/Capstone%20Checkpoint%206.1/README%206.1.md) (in progress)

For the evolution at a glance — every retriever/approach tried, survived, or abandoned
across checkpoints 1.1–5.1, with both RAGAS metrics (recall and answer quality) at each
fork — open the interactive [**Retriever Phylogeny**](retriever_phylogeny.html) in a browser.

```text
rag_and_context_engineering/
├── README.md
├── LANGCHAIN_GUIDE.md
├── retriever_phylogeny.html               # interactive lineage of retrievers 1.1–5.1
├── requirements.txt
├── test_setup.py
└── wikipedia_retrieval_engine/
    ├── Wikipedia Library/                 # local HTML corpus (2,419 articles)
    ├── GT/
    │   ├── wikipedia_GT.csv               # canonical 19-case evaluation set (GT01–GT19)
    │   ├── wikipedia_GT_validation_set.csv # 25-case held-out set (overfitting guard)
    │   └── capstone2.1_gt_cleanup_notes.md
    ├── retrievers/                        # reusable retrieval library (see below)
    │   ├── base.py                        # BaseRetriever, RetrieverSpec, normalize_scores
    │   ├── corpus.py                      # loaders + DOM extractor (Markdown + JSON sidecar)
    │   ├── bm25.py / vector.py / hybrid.py # lexical, vector, and fused retrievers
    │   ├── multistep.py                   # query-decomposition retriever (Lab 4.1)
    │   ├── graph.py                       # graph-augmented retriever (Lab 4.2)
    │   ├── expansion.py                   # expand seed chunks → full article context
    │   ├── evidence.py / llm.py           # evidence helpers; embeddings + answer/decompose LLM
    ├── utils/
    │   ├── ragas_eval.py                  # shared RAGAS harness (GT parse, LLM/judge, rate-limit)
    │   ├── analyze_ragas_experiments.py   # aggregate CSV runs → PDF report
    │   ├── openrouter_usage.py            # key usage snapshot; --analytics by app/model/day
    │   ├── wiki_table_parser.py            # rich Wikipedia-table normalization
    │   └── wiki_table_store.py             # offline artifact builder + read-only runtime API
    ├── wiki_agents/                       # Checkpoint 5.1 LangGraph agent
    │   ├── agent_graph.py                 # graph assembly, router, retrieval-stage configuration
    │   ├── retrieval_nodes.py             # retrieval, TOC review, section loading, evidence assessment
    │   ├── table_nodes.py                 # table query planner + deterministic executor node
    │   ├── agentic_models.py              # graph state, routing, and evidence models
    │   ├── run_logging.py                 # per-question AgentState evidence logs
    │   └── run_agent.py                   # single-question run through evidence assessment
    ├── tests/                             # unit tests (unittest)
    ├── Capstone Checkpoint 1.1/
    ├── Capstone Checkpoint 2.1/
    ├── Capstone Checkpoint 3.1/           # baseline retrieval + evaluation
    ├── Capstone Checkpoint 4.1/           # advanced retrieval (decomposition + graph)
    ├── Capstone Checkpoint 5.1/           # agentic evidence workflow
    └── Capstone Checkpoint 6.1/           # security and cost audit of the 5.1 survivor
        ├── survivor_agent.py              # builds the 5.1 survivor from the 5.1 harness constants
        ├── security_test_starter.py       # multi-turn attacks (history on)
        ├── cost_test_starter.py           # 5.1 evaluation + per-question/per-tool telemetry (history off)
        └── pricing/model_prices.json      # USD per 1M tokens for cost estimates
```

The checkpoint folders contain the assignment-specific scripts, evidence, reports,
and technical notes. Reusable retrieval code lives in `retrievers/` (each retriever
implements `BaseRetriever.getTopK`), and utilities that operate across checkpoints
live in `utils/`. The corpus is available in two representations: plain text
(`wikipedia_plain_text`) and structure-preserving **Markdown + a JSON sidecar**
(`wikipedia_markdown`, built by `corpus.build_or_load_markdown_store`) whose
categories/links/tables are the substrate for the Checkpoint 4.1 graph.

## Checkpoint progression

- **Checkpoint 1.1 — baseline generation.** Established the Wikipedia question-answer
  scenario, initial prompt, and repeat-run response logs.
- **Checkpoint 2.1 — retrieval experiments.** Added BM25, vector, and weighted hybrid
  retrieval; compared chunking strategies and full-article context; and created the
  initial manually reviewed ground-truth workbook.
- **Checkpoint 3.1 — controlled evaluation.** Introduced the canonical GT set,
  oracle-context and end-to-end runs, RAGAS scoring, repeat-run analysis, and the
  vector `k=7` baseline.
- **Checkpoint 4.1 — advanced retrieval.** Rebuilt the corpus as Markdown plus JSON
  sidecars, tested query decomposition, and added a rarity-weighted article graph.
  Graph retrieval improved article recall, but answer quality remained limited by
  table aggregation and reasoning.
- **Checkpoint 5.1 — agentic evidence reasoning.** Implements a bounded LangGraph
  agent (`wiki_agents/`). It finds articles through entity decomposition, selects
  sections and table artifacts from each article's table of contents, forces every
  selected table through a deterministic lookup/compute executor, and escalates to
  same-article breadth and then graph neighbors when evidence is insufficient. Final
  runs held designated-article recall at 1.000. On the held-out validation set,
  quality reached 0.880 (4.1 graph: 0.885) with about one fifth of the 4.1 context.
- **Checkpoint 6.1 — security and cost audit (in progress).** Audits the unchanged
  5.1 survivor. The security experiment adds conversation history (the 5.1 agent is
  single-turn) and tests roleplay and evidence-planting attacks. The cost experiment
  reruns the 5.1 evaluation with per-question and per-tool token telemetry.

## Ground-truth files

Two ground-truth artifacts are retained for different purposes:

- `wikipedia_retrieval_engine/Capstone Checkpoint 2.1/wikipedia Q-A GT.xlsx` is the
  original workbook used for the manual Checkpoint 2.1 review. It remains beside that
  checkpoint so its historical results can be reproduced and interpreted correctly.
- `wikipedia_retrieval_engine/GT/wikipedia_GT.csv` is the current canonical evaluation
  set for Checkpoint 3.1 and later work. It contains stable IDs GT01-GT19, reference
  answers, question-specific PASS/PARTIAL/FAIL rules, designated source articles,
  scope assumptions, evaluation roles, and complexity labels.

The audit and migration from the original workbook to the current CSV are documented
in `wikipedia_retrieval_engine/GT/capstone2.1_gt_cleanup_notes.md`.

## Setup

This project uses a local Python virtual environment in `.venv`.

Use Python 3.11 or 3.12. macOS `/usr/bin/python3` is often Python 3.9 and cannot
install all Checkpoint 3.1 dependency pins.

From this repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in this directory and add the OpenRouter API key supplied for the
course:

```text
OPENROUTER_API_KEY=sk-or-v1-...
```

Verify the environment:

```bash
python test_setup.py
```

A successful run prints a short model reply followed by
`Setup verification completed successfully.`

For later sessions, reactivate the environment with:

```bash
source .venv/bin/activate
```

## Prepare the local corpus and indexes

Place the supplied 2,419 HTML files in:

```text
wikipedia_retrieval_engine/Wikipedia Library/
```

The source corpus and generated databases are local working data rather than files to
commit. Builders validate their cached output and reuse it on later runs.

### Markdown and structured sidecars

This representation preserves sections, infoboxes, links, categories, and compact
table rows. It is used by Checkpoint 4.1 context expansion and graph construction.

```bash
python -m wikipedia_retrieval_engine.retrievers.corpus \
  "wikipedia_retrieval_engine/Wikipedia Library"
```

### Baseline Chroma index

The first build embeds the full corpus and therefore uses OpenRouter credits. Later
runs load the persisted Chroma collection but still embed each search query.

```bash
python -c 'from wikipedia_retrieval_engine.retrievers.vector import build_or_load_db; build_or_load_db(chroma_db_name="wikipedia_chars1600_overlap200")'
```

### Section-aware Chroma index for Checkpoint 5.1

Checkpoint 5.1 retrieves heading-based chunks so each initial evidence item retains
its article, section title, and section hierarchy. The first build embeds the full
corpus; later runs reuse the stored collection.

```bash
python -c 'from wikipedia_retrieval_engine.retrievers.vector import build_or_load_section_db; build_or_load_section_db()'
```

The dedicated builder is intentional: if the section index is missing, it calls
`load_wikipedia_section_chunks()` instead of silently rebuilding that database name
with the baseline character-chunk strategy.

### Article relationship graph

Build the Markdown sidecars first. The graph itself is deterministic and makes no LLM
call:

```bash
python -c 'from wikipedia_retrieval_engine.retrievers.corpus import build_or_load_markdown_store; from wikipedia_retrieval_engine.retrievers.graph import build_or_load_graph; build_or_load_graph(build_or_load_markdown_store())'
```

### Rich table artifacts for Checkpoint 5.1

The answering graph never reparses HTML or writes corpus artifacts. Build the
normalized table layer once:

```bash
python -m wikipedia_retrieval_engine.utils.wiki_table_store
```

The builder writes compressed per-article artifacts and a catalog manifest under
`wikipedia_retrieval_engine/retrievers/db/table_artifacts/wikipedia_tables/`. A repeat
invocation reuses the published store when the source inventory, parser, schema, and
selector are unchanged. Pass `--force` only for an intentional rebuild. See the
[Checkpoint 5.1 README](wikipedia_retrieval_engine/Capstone%20Checkpoint%205.1/README%205.1.md)
for the representation and agent-routing design.

### Verify local code

```bash
python -m unittest discover -s wikipedia_retrieval_engine/tests -p "test_*.py"
```

## Checkpoint 3.1 evaluation workflow

Run these commands from the repository root.

### Oracle-context evaluation

This mode bypasses retrieval and supplies the complete designated source articles to
the answer model. It isolates answer generation and judge behavior from retrieval.

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/capstone_checkpoint_3_1_oracle_AI_only.py"
```

### End-to-end retrieval evaluation

This mode retrieves Top K seed chunks, expands the selected articles to full text,
generates answers, and records answer scores and article-level retrieval diagnostics.
The active `BASELINE_RETRIEVER_SPEC` in the script determines whether the run uses
vector or hybrid retrieval.

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/capstone_checkpoint_3_1_with_retriever.py"
```

RAGAS saves one CSV per run under:

```text
wikipedia_retrieval_engine/Capstone Checkpoint 3.1/ragas_experiments/experiments/
```

The Checkpoint 3.1 technical README explains the experiment controls, final metrics,
and known limitations in detail.

## Checkpoint 5.1 agent evaluation

The harness runs the final 5.1 configuration (entity-decomposed initial retrieval, TOC
selection, table gateway, then `article_broaden` → `graph_seeded` escalation) over a
ground-truth CSV, writes one RAGAS CSV per run, and writes one `AgentState` evidence
log per question under `Capstone Checkpoint 5.1/logs/`:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 5.1/capstone_checkpoint_5_1_agent_rag_starter.py" \
  --gt-set "wikipedia_retrieval_engine/GT/wikipedia_GT.csv" \
  --output-dir "wikipedia_retrieval_engine/Capstone Checkpoint 5.1/ragas_test_GT_5.1" \
  --experiment-name agentic_search_compute_broaden
```

`--limit N` runs a smoke test; repeat `--question-id GT16` to select questions. The
Checkpoint 5.1 README documents the configuration, the progression, and the reports.

## Checkpoint 6.1 security and cost tests

Both starters build the unchanged 5.1 survivor through
`Capstone Checkpoint 6.1/survivor_agent.py`. Each has a `--self-check` that runs
without API calls.

**Security (history on).** Each scenario is one conversation. The answer model
receives the earlier turns; retrieval sees only the current message.

Print the scenarios (no API calls):

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/security_test_starter.py" --show
```

Run every scenario three times:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/security_test_starter.py" --scenario all --repeats 3
```

**Cost (history off).** Runs the 5.1 RAGAS case function unchanged, so the results
CSV keeps the 5.1 schema. Token telemetry per call, node, and question is written to
`<output-dir>/telemetry/`.

Smoke test on one question:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/cost_test_starter.py" --question-id GT04
```

Full validation set:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/cost_test_starter.py" \
  --gt-set "wikipedia_retrieval_engine/GT/wikipedia_GT_validation_set.csv"
```

The Checkpoint 6.1 README records the scenarios, the choices behind them, and the
results.

## Analyze RAGAS experiments

`wikipedia_retrieval_engine/utils/analyze_ragas_experiments.py` recursively discovers
RAGAS experiment CSVs, groups repeated runs by `experiment_name` / `config_name` when
present and by derived configuration metadata otherwise, recomputes article recall
with normalized filenames, and creates a landscape PDF containing:

- PASS/PARTIAL/FAIL rates and the weighted quality index;
- designated-source recall and full-source coverage;
- mean context size;
- task-family attention scores and oracle-to-retriever gaps;
- performance grouped by one, two, or three-plus designated articles;
- per-question outcome heatmaps;
- run-to-run variability; and
- included, excluded, and duplicate-file diagnostics.

The script does not call an LLM or make network requests. It requires `pandas` and
`reportlab`, which are included in the Checkpoint 3.1 requirements.

Run it with the project defaults:

```bash
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments.py
```

By default, it reads the Checkpoint 3.1 experiment directory and writes:

```text
../../output/pdf/ragas_evaluation_report.pdf
```

The output folder is intentionally outside the capstone repository. Choose an
explicit destination when creating a submission copy:

```bash
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments.py \
  --experiments-dir "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/ragas_experiments/experiments" \
  --output "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/ragas_evaluation_report_checkpoint3_1.pdf" \
  --title "Capstone Checkpoint 3.1 RAGAS evaluation results"
```

Earlier oracle runs used a binary PASS/FAIL rubric and are excluded from the primary
comparison because those labels are not compatible with the final three-level rubric.
Pass `--include-binary-oracle` only when intentionally reviewing those legacy runs;
do not combine them with the final baseline statistics.

## Check OpenRouter usage

`wikipedia_retrieval_engine/utils/openrouter_usage.py` checks the OpenRouter API key
used by the capstone scripts without printing the key itself. It reads
`OPENROUTER_API_KEY` from the environment or a nearby `.env` file:

```bash
python wikipedia_retrieval_engine/utils/openrouter_usage.py
```

To log a post-run snapshot by experiment/config name:

```bash
python wikipedia_retrieval_engine/utils/openrouter_usage.py \
  --experiment-name vector_search_base \
  --log-csv "wikipedia_retrieval_engine/Capstone Checkpoint 4.1/openrouter_usage_log.csv"
```

Set `OPENROUTER_MANAGEMENT_KEY` when you also want account-level credit remaining or
need to list/query managed keys.

The management key also enables the analytics query (day × dimension usage: request
count, cost, prompt/completion/cached tokens). Capstone calls carry app tags ("WRE
retriever" for chat roles, "WRE embedding", "WRE judge", applied since 2026-09-22), so
grouping by `app` separates system cost from evaluation cost:

```bash
python wikipedia_retrieval_engine/utils/openrouter_usage.py \
  --analytics --analytics-dimension app --analytics-days 14 \
  --analytics-csv "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/openrouter_analytics_by_app.csv"
```

`--analytics-granularity hour` isolates individual runs.

## Why the project progresses to Checkpoints 5.1 and 6.1

The controlled experiments establish a useful sequence:

1. Checkpoint 3.1 found a strong vector `k=7` baseline and showed that perfect source
   selection still did not solve exhaustive-list and time-filter questions.
2. Checkpoint 4.1 improved article recall from 0.899 to 0.939 with graph expansion, but
   mean answer quality remained approximately flat. Clean Markdown tables also did not
   resolve the difficult aggregation family by themselves.
3. Checkpoint 5.1 therefore targets the reasoning stage: assess what evidence is
   missing, retrieve deliberately, compute over normalized table rows when necessary,
   and verify the answer against precise provenance.
4. Checkpoint 5.1 reached designated-article recall of 1.000 with a fraction of the
   4.1 context. It also makes five or more model calls per question and adds new
   channels through which user text and retrieved text reach a model (decomposition,
   TOC review, assessment, table planning). Checkpoint 6.1 therefore audits security,
   reliability, latency, and cost before further capability work.

These numbers are experiment-specific, not general claims about one retriever always
being superior. The complete methods, caveats, and per-question results remain in the
checkpoint READMEs linked at the top of this file.

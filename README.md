# MITxPRO RAG and Context Engineering Capstone Project

This repository contains a Wikipedia retrieval engine developed across the MIT xPRO
RAG and Context Engineering capstone checkpoints. The project separates four parts of
the system so that they can be tested independently: corpus preparation, retrieval,
context construction, and answer generation.

The selected capstone scenario is the **Wikipedia Retrieval Engine**. It answers
single-article and multi-article questions over a local collection of 2,417 Wikipedia
HTML files. The evaluation set includes direct facts and quotations, table lookups,
time-bounded lists, cross-article comparisons, relationships among people and places,
geopolitical timelines, calculations, conflicting estimates, and questions that
require caution about causal inference.

## Repository guide

```text
rag_and_context_engineering/
├── README.md
├── test_setup.py
└── wikipedia_retrieval_engine/
    ├── Wikipedia/                         # local HTML corpus
    ├── GT/
    │   ├── wikipedia_GT.csv               # current 19-case evaluation set
    │   └── capstone2.1_gt_cleanup_notes.md
    ├── retrievers/                        # corpus, BM25, vector, hybrid, logging
    ├── utils/
    │   └── analyze_ragas_experiments.py   # aggregate CSV runs and create a PDF
    ├── Capstone Checkpoint 1.1/
    ├── Capstone Checkpoint 2.1/
    └── Capstone Checkpoint 3.1/
```

The checkpoint folders contain the assignment-specific scripts, evidence, reports,
and technical notes. Reusable retrieval code lives in `retrievers/`, and utilities
that operate across checkpoints live in `utils/`.

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
pip install -r "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/requirements.txt"
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

## Current finding

For the final controlled Checkpoint 3.1 comparison, vector retrieval at Top K = 7
outperformed the tested hybrid configuration with BM25/vector weights of 0.35/0.65.
Vector retrieval achieved a quality index of 0.747 and designated-source recall of
89.9%, compared with 0.705 and 88.2% for hybrid retrieval, while sending substantially
less full-article context.

This conclusion is limited to this corpus, question set, Top K, weighting, prompt, and
models. The oracle-context quality index of 0.789 also shows that retrieval is not the
only bottleneck: exhaustive reasoning, table interpretation, answer completeness, and
judge reliability still affect the result when the intended articles are supplied.

The task-family analysis identifies **exhaustive list or time-filter questions** as
the main improvement target. Under vector retrieval, this family had a quality score
of 0.340, a 64.0% failure rate, and an attention score of 66.0. Its oracle quality was
similarly low at 0.322, which shows that retrieval changes alone will not solve this
class of failure. Direct fact or table lookup questions scored 1.000 under vector
retrieval.

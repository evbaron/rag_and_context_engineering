# Utilities Guide

The `utils` package contains shared infrastructure for the Wikipedia Retrieval Engine. These modules keep evaluation, reporting, API-account inspection, and Wikipedia table preprocessing out of the retrieval and agent code itself.

Most commands below assume the current directory is:

```text
rag_and_context_engineering/wikipedia_retrieval_engine
```

## At a glance

| Utility | What it is for | Typical output |
|---|---|---|
| `ragas_eval.py` | Shared RAGAS evaluation setup used by checkpoint experiments | RAGAS dataset and experiment CSVs |
| `analyze_ragas_experiments.py` | Compares answer quality across experiment CSVs | Console summary and PDF report |
| `analyze_ragas_experiments_efficiency.py` | Compares quality, cost, latency, routing, and safeguards | PDF report plus detailed CSV tables |
| `openrouter_usage.py` | Inspects OpenRouter key usage, credits, and analytics | Console/JSON output and optional CSV logs |
| `wiki_table_parser.py` | Converts Wikipedia HTML tables into structured, semantics-preserving objects | `NormalizedTable` objects or JSON |
| `wiki_table_store.py` | Builds and reads a persistent cache of normalized tables | Gzipped article artifacts plus `manifest.json` |
| `__init__.py` | Marks `utils` as an importable Python package | No runtime output |

## How the pieces fit together

The evaluation path is:

```text
Ground-truth CSV -> ragas_eval.py -> experiment CSVs
                                      |-> analyze_ragas_experiments.py
                                      `-> analyze_ragas_experiments_efficiency.py
                                          + telemetry CSVs
```

The structured-table path is:

```text
Wikipedia HTML -> wiki_table_parser.py -> normalized tables
                                      -> wiki_table_store.py -> persistent artifacts
                                                               -> agent retrieval/table nodes
```

## `ragas_eval.py`

### Why it is here

Checkpoint evaluation scripts need the same ground-truth validation, OpenRouter clients, RAGAS judge, dataset construction, retry behavior, context-store selection, and result saving. This module centralizes that plumbing so each experiment script only implements the retrieval technique being tested.

The module is primarily a library, not a complete experiment runner: checkpoint scripts import its functions and add their own `build_*_experiment` logic.

### How it works

1. Loads and validates a ground-truth CSV.
2. Selects rows by question ID or row limit.
3. Saves the selected inputs as a local RAGAS `Dataset`.
4. Creates the answer LLM and correctness judge through OpenRouter.
5. Supplies a three-level correctness metric: `pass`, `partial`, or `fail`.
6. Provides retry handling for HTTP 429/rate-limit errors.
7. Loads either the structure-preserving Markdown article store or the plain-text store.
8. Saves completed experiment results and prints a score tally.

The default answer and judge model is `openai/gpt-5.4-mini`, with answer temperature `0.2`. The default context source is `markdown`. These settings are module constants so related experiments stay comparable.

### Main classes, objects, and methods

- `RateLimitBackoff`: immutable retry configuration. `RateLimitBackoff.from_args(args)` converts the shared CLI arguments into a validated configuration.
- `call_with_rate_limit_backoff(func, backoff, label=...)`: executes a synchronous operation and retries only recognized rate-limit failures. It honors `Retry-After` or rate-limit-reset response headers when available, otherwise uses exponential backoff plus optional jitter.
- `check_api_key()`: loads `.env` through `python-dotenv` and returns `OPENROUTER_API_KEY`, or raises a clear error.
- `make_llm()`: creates the LangChain `ChatOpenAI` answer client.
- `make_judge()`: creates the RAGAS judge client using the OpenAI SDK pointed at OpenRouter.
- `correctness_metric`: a RAGAS `DiscreteMetric` whose authoritative rubric is each row's `grading_notes`.
- `my_eval_set(gt_path)`: validates the file, required columns, non-empty contents, and unique populated IDs, then returns row dictionaries.
- `build_ragas_dataset(gt_path, output_dir, dataset_suffix="inputs", limit=2, question_ids=None)`: selects and persists evaluation inputs. Supplying `question_ids` preserves their requested order and takes precedence over `limit`; `limit=None` selects the full file.
- `parse_source_articles(source_cell)`: splits the semicolon-separated `Source articles` field.
- `source_key_from_gt_filename(filename)`: maps names such as `100_metres.html.txt` to the article-store key `100_metres.html`.
- `load_ground_truth_context(source_cell, article_text_store)`: loads complete gold-source articles for oracle-style experiments.
- `load_context_store(context_source=CONTEXT_SOURCE)`: opens the Markdown or plain-text article cache.
- `print_score_summary(results)`: prints and returns pass/partial/fail counts.
- `save_results(results, output_dir)`: saves a RAGAS result object and reports the expected experiment CSV path.
- `parse_args()`: shared experiment CLI options, including `--gt-set`, `--output-dir`, question selection, experiment naming, and rate-limit controls.

### Ground-truth CSV contract

Required columns are `ID`, `Category`, `Question`, `Reference answer`, `Grading notes`, and `Source articles`. IDs must be present and unique. `Source articles` contains semicolon-separated filenames.

### Important details

- OpenRouter is required for model and judge calls; set `OPENROUTER_API_KEY` in the environment or `.env`.
- Retry support is synchronous and sleeps between attempts; non-rate-limit exceptions are raised immediately.
- Changing the model, judge, temperature, or context source changes experiment comparability. Record such changes in the experiment name or metadata.

## `analyze_ragas_experiments.py`

### Why it is here

Raw experiment CSVs are difficult to compare across repeated runs and retrieval configurations. This utility turns them into a consistent quality report with configuration-level, run-level, question-level, task-family, source-scope, recall, variability, failure, and optional cost summaries.

It is offline: it reads local CSVs and does not call an LLM or the network.

### How it works

`load_experiments()` recursively discovers CSVs, rejects unusable files, removes byte-for-byte duplicates, normalizes scores, groups repeated runs by explicit `experiment_name`/`config_name` or derived configuration metadata, and attaches matching question telemetry when present. It maps scores to numeric quality (`pass=1`, `partial=0.5`, `fail=0`) and builds summary DataFrames. `create_pdf_report()` renders those summaries and diagnostics with ReportLab.

Telemetry files named `<run>__question_telemetry.csv` are merged into the corresponding run. Other `__llm_calls.csv` and `__node_timings.csv` telemetry files are recognized as supporting files rather than independent experiments.

### Main classes and methods

- `AnalysisData`: bundle containing normalized question rows, run/configuration/task/scope summaries, included and excluded files, and loader warnings.
- `load_experiments(experiments_dir, include_binary_oracle=False)`: the main programmatic entry point for discovery, validation, normalization, telemetry attachment, and aggregation.
- `create_pdf_report(data, output_path, title=...)`: creates the landscape PDF report.
- `print_console_summary(data, output_path)`: prints compact result, recall, cost, and file-ingestion summaries.
- `parse_args(argv=None)` and `main(argv=None)`: command-line interface and error-handled orchestration.

Most underscore-prefixed functions are internal report builders, formatters, charts, or data-cleaning helpers. They are useful for maintaining the report but are not intended as a stable external API.

### Usage

```bash
python utils/analyze_ragas_experiments.py \
  --experiments-dir "Capstone Checkpoint 3.1/ragas_experiments/experiments" \
  --output "/path/to/ragas_evaluation_report.pdf" \
  --title "Retrieval comparison"
```

Use multiple paths after `--experiments-dir` to combine roots. Add `--include-binary-oracle` only when intentionally comparing older `pass_fail_only` runs; their binary scoring is not directly equivalent to the three-level rubric.

### Input expectations and caveats

- Every usable run CSV needs `question_id` and `score`.
- Supported scores are `pass`, `partial`, and `fail`; unsupported values are dropped with a warning.
- Explicit experiment names are preferred. Derived names can accidentally group or split runs when metadata changes.
- CSVs with missing required columns, empty data, legacy incompatible scoring, telemetry-only content, duplicates, or read errors are listed as excluded rather than silently treated as runs.
- `pandas` and `reportlab` are required.

## `analyze_ragas_experiments_efficiency.py`

### Why it is here

Accuracy alone does not show whether an agent design is practical. This companion report explains what quality costs in money, tokens, calls, and time, and whether observed differences may be caused by provider latency, caching, or run order instead of the system itself.

It reuses the base analyzer's ingestion rules and adds Checkpoint 7.1 cost telemetry. It is also entirely offline.

### How it works

The loader joins experiment rows with per-call and per-question telemetry, identifies question sets from ID prefixes (`GT...` and `VAL...`), labels the route taken through the agent, and keeps test and validation results separate. For each question set it builds:

- a quality/cost/latency frontier and dominance labels;
- paired per-question comparisons against a baseline;
- Wilcoxon signed-rank p-values when SciPy is available;
- spend and latency by agent role;
- text-ready, text-escalated, and table-path summaries;
- tail latency/cost and most-expensive-run tables;
- failed-answer spend and cost per passing answer;
- comparability warnings for cache and provider-latency drift;
- grounding, evidence, and input-sanitizer safeguard summaries;
- optional what-if routing-policy simulations.

It writes both a PDF and machine-readable CSVs for the report tables.

### Main classes and methods

- `EfficiencyData`: all normalized question-runs, LLM calls, runs, file lists, and warnings. `question_sets()` returns the sets in report order.
- `SetReport`: all tables and warnings for one question set.
- `Policy`: a routing-policy definition used by simulation.
- `load_efficiency_data(experiments_dirs, aliases=None)`: loads base results, telemetry, labels, routes, safeguard flags, and run timing.
- `build_set_report(...)`: creates one complete report section for a question set.
- `build_frontier(...)`: aggregates quality, cost, calls, and seconds and marks dominated configurations.
- `build_paired(...)`: compares configurations question by question against the baseline.
- `build_roles(...)`, `build_paths(...)`, and `build_tail(...)`: explain resource use by agent role, execution path, and expensive tail.
- `build_comparability_warnings(...)`: flags conditions that weaken a causal performance comparison.
- `build_safeguards(...)`: summarizes evidence, grounding, and sanitization markers.
- `routing_policies(...)` and `simulate_policies(...)`: define and evaluate hypothetical cheap/strong routing rules from saved runs.
- `dominance(...)`, `tradeoff_verdict(...)`, and `wilcoxon_p(...)`: reusable comparison helpers.
- `write_csv_tables(...)`: writes each report table to a sibling table directory.
- `create_pdf(...)`: renders the final report.
- `parse_args(argv=None)` and `main(argv=None)`: command-line interface and full workflow.

### Usage

```bash
python utils/analyze_ragas_experiments_efficiency.py \
  --experiments-dir "Capstone Checkpoint 7.1/cost_efficiency/wikipedia_GT" \
  --baseline "6.1 survivor" \
  --output "Capstone Checkpoint 7.1/cost_efficiency/reports/gt_efficiency.pdf"
```

Useful options include:

- `--csv-dir`: override the default `<PDF stem>_tables` output directory.
- `--alias NAME=LABEL`: add or override a display name; repeat as needed.
- `--route-cheap CONFIGURATION` and `--route-strong CONFIGURATION`: enable routing simulations using saved runs.
- `--text-categories "Category A;Category B"`: override the category set used by the category-routing policy.

### Important details

- Fair comparisons require the same questions in each configuration. Paired tables operate on overlapping question IDs.
- Billed and list cost are separate because provider discounts and caching may make them differ.
- The judge is excluded from agent execution telemetry where the source logs make that distinction.
- Missing SciPy does not stop the report; statistical p-values become `n/a`.
- Routing simulations estimate outcomes from existing runs. They do not execute the router or prove future production behavior.

## `openrouter_usage.py`

### Why it is here

Experiments can consume shared course or account credits. This command provides a safe way to inspect the active OpenRouter key, remaining limits, account credits, key inventory, and time-bucketed analytics without displaying the secret key itself. It can append snapshots to CSV for before/after experiment accounting.

Unlike the report utilities, this module makes live HTTPS requests to OpenRouter.

### How it works

The script loads environment values from nearby `.env` files and any explicitly supplied `--env-file`. Existing environment variables win. It calls the appropriate OpenRouter endpoint, validates the JSON shape, formats a human-readable or raw JSON response, optionally warns about low balances, and can append a fixed-schema usage snapshot or write analytics rows to CSV.

### Main class and methods

- `OpenRouterUsageError`: user-facing configuration, HTTP, network, and response-format errors handled cleanly by `main()`.
- `load_env_files(extra_env_files)`: lightweight `.env` reader with no `python-dotenv` dependency.
- `api_get(...)` and `api_post(...)`: authenticated JSON request helpers with timeout and friendly error conversion.
- `data_object(...)` and `data_list(...)`: validate expected response payload shapes.
- `account_remaining(...)`: computes total credits minus total usage when both are available.
- `print_key_summary(...)`, `print_credits_summary(...)`, and `print_key_list(...)`: human-readable output.
- `log_usage_snapshot(...)`: appends a timestamped row using the stable `LOG_COLUMNS` schema.
- `warn_if_low(...)`: checks account remaining credit or key limit against a threshold.
- `query_analytics(...)`, `print_analytics(...)`, and `write_analytics_csv(...)`: retrieve, summarize, and save usage grouped by a requested dimension and time granularity.
- `parse_args(argv=None)` and `main(argv=None)`: command-line interface and operation selection.

### Usage

Inspect the active API key and account credits:

```bash
python utils/openrouter_usage.py
```

Append a labeled snapshot:

```bash
python utils/openrouter_usage.py \
  --experiment-name "vector_search_base" \
  --log-csv "Capstone Checkpoint 4.1/openrouter_usage_log.csv"
```

Query model-level analytics with a management key:

```bash
python utils/openrouter_usage.py \
  --analytics \
  --analytics-days 14 \
  --analytics-dimension model \
  --analytics-csv openrouter_model_usage.csv
```

### Credentials and operation modes

- `OPENROUTER_API_KEY` is required for inspecting the current key.
- `OPENROUTER_MANAGEMENT_KEY` is required for analytics and may be used for account credits, key listing, and key-hash lookup.
- `--list-keys` lists keys visible to the supplied management/current token.
- `--key-hash` inspects a specific key through the management endpoint.
- `--no-credits` skips the account-level credit request.
- `--json` emits raw structured data for scripting.
- `--warn-below NUMBER` prints a low-balance warning.
- `--base-url` and `--timeout` support testing or non-default endpoints.

Do not commit `.env` files, usage logs containing sensitive account metadata, or raw API responses without reviewing them.

## `wiki_table_parser.py`

### Why it is here

Plain text extraction loses much of the meaning encoded in Wikipedia tables. Row and column spans, superscripts, links, bold/italic emphasis, colors, and legends can distinguish winners, footnotes, classifications, or inherited row values. This parser preserves those signals while also producing simple row dictionaries that agent code can use easily.

### How it works

For each selected table, the parser:

1. Finds the main Wikipedia content region and semantic `table.wikitable` elements.
2. Collects page footnotes and nearby symbol, abbreviation, and color legends.
3. Parses cell text, links, annotations, styles, sort values, and background colors.
4. Expands `rowspan` and `colspan` into a rectangular grid while retaining each copied cell's origin and `inherited` status.
5. Determines header rows and creates unique column names when headings repeat.
6. Produces convenient string rows and parallel rich `NormalizedCell` rows.
7. Attaches section context, captions, warnings, hashes, stable IDs, legends, and provenance.

### Data models

- `CellAnnotation`: superscript/subscript text, whether it is a reference or marker, and optional note target/content.
- `CellLink`: visible link text, `href`, and optional title.
- `TableLegend`: a symbol, abbreviation, or color and its meaning.
- `NormalizedCell`: clean/display text, header/style flags, emphasized fragments, annotations, links, color, sort value, legend matches, span geometry, origin coordinates, and inheritance status.
- `NormalizedTable`: table identity and provenance plus caption, section path, columns, simple `rows`, rich `row_cells`, header rows, legends, context, warnings, hashes, CSS classes, and `data`/`legend` role.

All models use Pydantic and can be validated, dumped to dictionaries, or serialized as JSON.

### Main methods

- `parse_wikipedia_html(html, source_article=..., table_selector="table.wikitable")`: parses an HTML string into `list[NormalizedTable]`.
- `parse_wikipedia_file(path, table_selector="table.wikitable")`: reads a local file and delegates to the HTML parser.
- `parse_wikipedia_tables`: friendly alias for `parse_wikipedia_file`.

Helper functions beginning with `_` implement normalization and should be treated as internal. The public data models and parse functions are the intended integration surface.

### Usage

Normalize semantic Wikipedia tables and print JSON:

```bash
python utils/wiki_table_parser.py "Wikipedia Library/100_metres.html"
```

Write JSON to a file:

```bash
python utils/wiki_table_parser.py "Wikipedia Library/100_metres.html" \
  --output /tmp/100_metres_tables.json
```

`--all-tables` changes the selector from `table.wikitable` to every `table`, including layout, infobox, and navigation tables. Use it deliberately because it substantially increases noise.

### Important details

- `PARSER_VERSION` participates in artifact identity. Increment it when a parser change alters stored output, then rebuild the table store.
- Stable artifact IDs depend on the source hash, table signature, and parser version.
- Warnings preserve recoverable structural issues such as ambiguous or duplicate headings instead of discarding the table.
- `beautifulsoup4`, the `lxml` parser, and Pydantic are required.

## `wiki_table_store.py`

### Why it is here

Parsing the entire Wikipedia corpus during each agent run would be slow and could yield inconsistent partial caches. This module performs parsing once as an offline build, then gives runtime agent nodes lazy, read-only access to validated artifacts.

### How it works

The builder inventories local `.html` files, checks whether an existing manifest still matches file size/mtime, parser version, schema version, selector, source directory, and artifact availability, and reuses it when valid. Otherwise it parses every article, writes one content-addressed `.json.gz` artifact per article, builds a searchable table catalog, and atomically publishes `manifest.json` only after all artifacts succeed.

Runtime readers open the manifest, validate schema/parser compatibility, locate artifacts through path-containment checks, verify source and content hashes, and convert stored tables back into Pydantic `NormalizedTable` objects.

### Data models

- `SourceFileStamp`: source size and nanosecond modification time used for the cheap rebuild check.
- `TableCatalogEntry`: searchable metadata for one table, including article, caption, section, columns, row count, role, and legend meanings.
- `ArticleManifestEntry`: maps one article to its artifact, hash, table count, and source stamp.
- `TableArtifactManifest`: versioned root manifest with build metadata, article map, and complete table catalog.

### Main class and methods

`TableArtifactStore` is the read-only runtime API:

- `TableArtifactStore.open(root=DEFAULT_TABLE_STORE_DIR)`: validates and opens an existing store.
- `len(store)`: returns the manifest's total table count.
- `has_article(source_article)`: checks for an article artifact.
- `list_articles()`: returns sorted article filenames.
- `list_tables(source_article=None, include_legends=False)`: filters catalog entries by article and, optionally, includes tables classified as legends.
- `find_tables(query, source_article=None, include_legends=False, limit=10)`: deterministically ranks catalog metadata by query-token overlap. It is a lightweight catalog search, not semantic/vector retrieval.
- `load_article(source_article)`: validates and loads all normalized tables for an article.
- `load_table(source_article, table_id)`: loads one table by its article-local ID.
- `load_artifact(artifact_id)`: loads one table by its globally cataloged artifact ID.

`build_table_artifact_store(wiki_dir=..., output_dir=..., table_selector=..., force=False)` is the main build API. It returns an opened `TableArtifactStore`, whether it reused or rebuilt the artifacts.

### Usage

Build or reuse the default store:

```bash
python -m wikipedia_retrieval_engine.utils.wiki_table_store
```

Build explicitly from the engine directory:

```bash
python -m wikipedia_retrieval_engine.utils.wiki_table_store \
  --wiki-dir "wikipedia_retrieval_engine/Wikipedia Library" \
  --output-dir "wikipedia_retrieval_engine/retrievers/db/table_artifacts/wikipedia_tables"
```

The module form should be run from `rag_and_context_engineering`, because this file uses the package-qualified import `wikipedia_retrieval_engine.utils...`.

Options are `--wiki-dir`, `--output-dir`, `--table-selector`, and `--force`. `--force` bypasses manifest reuse and reparses all source articles.

Programmatic use:

```python
from wikipedia_retrieval_engine.utils.wiki_table_store import TableArtifactStore

store = TableArtifactStore.open()
matches = store.find_tables("Olympic sport years", limit=5)
table = store.load_artifact(matches[0].artifact_id)
print(table.columns)
print(table.rows[:2])
```

### Important details

- The store is intentionally immutable at runtime. Agent code cannot silently update the corpus cache.
- Artifact filenames are content- and parser-addressed; old unreferenced files may remain after rebuilds, but the manifest determines the active store.
- The manifest is published atomically, preventing readers from seeing a half-built catalog.
- Source inventory uses size and modification time for fast reuse; each artifact and manifest also carry SHA-256 source hashes for integrity checks.
- A schema or parser-version mismatch requires a rebuild.

## `__init__.py`

This file is intentionally empty. Its presence makes `utils` an ordinary Python package and enables imports such as:

```python
from wikipedia_retrieval_engine.utils.wiki_table_parser import NormalizedTable
```

It does not re-export utility functions. Import from the specific module that owns the API.

## Development and maintenance notes

- Keep generated reports, experiment outputs, telemetry, and table artifacts out of the utility source directory.
- Prefer public functions and models documented above. Underscore-prefixed helpers may change as report or parser internals evolve.
- When extending experiment CSV schemas, keep `question_id` and `score` stable and add optional columns rather than changing their meaning.
- When changing table artifact structure, update `STORE_SCHEMA_VERSION`. When changing parsing semantics, update `PARSER_VERSION`. Rebuild artifacts after either change.
- Relevant tests live in `wikipedia_retrieval_engine/tests`, especially `test_wiki_table_parser.py`, `test_wiki_table_store.py`, and `test_analyze_efficiency.py`.

# Checkpoint 5.1: agentic retriever with an assessment loop

This checkpoint builds the first *agentic* retriever: instead of one fixed
retrieve-then-answer pass, the graph accumulates useful articles, retrieves the
right sections inside them, and runs a retriever–assessment loop that decides
whether the evidence is sufficient or another retrieval stage is needed.

It continues the experiment narrative from
[Checkpoint 4.1](../Capstone%20Checkpoint%204.1/README%204.1.md). General LangChain
and LangGraph syntax lives in the repository-level
[LangChain guide](../../LANGCHAIN_GUIDE.md).

This document is a **progression log**: it records what was tried, what each run
showed, and why each design choice was made — so the reasoning is reconstructable,
not just the final state.

---

## 1. Starting point (from Checkpoint 4.1)

4.1 established two things that frame this checkpoint:

- **Retrieval was already strong.** The best 4.1 configuration — the graph
  retriever (`vector_graph`) — reached mean designated-article recall **0.939**,
  but it did so by brute breadth: ~**7.4 articles** and ~**260,000 context
  characters** per question. See
  [ragas_GT_evaluation_graph_retriever.pdf](../Capstone%20Checkpoint%204.1/ragas_GT_evaluation_graph_retriever.pdf).
- **Answer quality was flat.** More retrieval did not move it. The remaining
  failures clustered on tasks that require reading, filtering, or aggregating
  **tables**, and the 260K-character context was the "full articles don't fit"
  problem this checkpoint set out to replace with *selected sections*.

**Hypothesis for 5.1:** a bounded evidence graph that (a) sends only relevant
sections and (b) can escalate retrieval on demand will match 4.1's recall at a
fraction of the context, and will isolate whether the remaining failures are
retrieval or table synthesis. The bar is explicit: **do better than 4.1, or the
added machinery isn't worth it.**

## 2. Approach: retrieval first, then bounded table computation

The first benchmark deliberately disabled tables so progressive retrieval and table
reasoning were not changed at the same time. Those retrieval-only results remain the
baseline described in §§3–5. The current harness runs the next controlled step: the
TOC reviewer selects stable normalized-table artifact IDs, those artifacts enter
evidence alongside exact section chunks, and the assessor may request bounded,
deterministic computation over a selected artifact.

```text
START
  -> retrieve initial articles        (configurable: vector | multi-step)
  -> review candidate TOCs            (keep/reject; select headings + artifact IDs)
  -> load exact selected sections     (article + section metadata filter)
  -> load selected normalized tables  (aligned rows + rich cell semantics)
  -> assess evidence
       |-- table request + budget --> plan + execute table --> assess (loop)
       |-- retrieval request ------> next configured retriever --> assess (loop)
       +-- ready/budgets exhausted --> write terminal-state log --> END
                                                                    |
                                                                    v
                                                       harness answer model + RAGAS
```

Only selected **section chunks and normalized table artifacts** enter evidence;
article names remain routing handles. Whole articles and fixed leading-character
slices are never sent to the answer model.

Per-run evidence is written to `logs/YYYY_MM_DD_HH_MM_SS/NNN__<slug>.evidence.json`
(one file per question, full terminal state). RAGAS scores the run and writes a
result row per question; aggregate PDFs are produced by
[`utils/analyze_ragas_experiments.py`](../utils/analyze_ragas_experiments.py).

## 3. Progression and decisions

### Step 0 — baseline

4.1 graph retriever, full 19 GT questions: recall **0.939**, ~7.4 articles/q,
~260K chars/q. This is the number to beat.

### Step 1 — the runs wouldn't complete (contract fixes)

The first 5.1 runs finished only 16–18 of 19 questions. The cause was **not** the
OpenRouter rate limit (the backoff recovered every 429); it was hard `raise`s in
`assess_evidence` on imperfect LLM output. Per run, the number of missing
questions equaled the number of validation errors exactly. Two failures:

1. `ready_to_answer=True` returned *with* leftover missing requirements/requests.
2. The `table_requests` field omitted entirely (declared required, no default).

Silently dropping questions also *inflated* the score, because the dropped ones
were disproportionately the hard table questions.

**Fixes** ([agentic_models.py](../wiki_agents/agentic_models.py),
[retrieval_nodes.py](../wiki_agents/retrieval_nodes.py)):

- `EvidenceAssessment` list fields default to empty (omitted key → `[]`).
- `assess_evidence` **repairs instead of raising**: clears table requests in
  retrieval-only mode; coerces `ready_to_answer → False` when any gap remains
  (**trust the gaps**); synthesizes a fallback retrieval request if a not-ready
  assessment has no actionable request.

Result: every run completes all 19. `evidence_ready` dropped and became honest —
the assessor can no longer claim readiness while still listing gaps.

### Step 2 — honest baseline and failure localization

With completion fixed, the honest full-19 baseline was ~**0.49 PASS**, recall
~**0.89**. Every stable failure is a **row-wise table operation** (GT03
intersection, GT07 aggregation, GT08 filter, GT10/GT11 program filter); prose and
relationship questions pass stably. Because recall was ~0.89 with most failures at
recall 1.0, the right article was already being retrieved.

Reading the evidence logs showed the drop was **not context volume** (5.1 sends
~15–18K chars, far below 4.1's 260K). It was two retrieval-quality problems plus a
reasoning floor:

- **Wrong section inside the right article.** The initial stage kept only the
  single best-matching chunk per article; for a table article that is the prose
  *preamble*, not the data rows. On GT07 the Best Actor "Winners and nominees"
  chunk was the table key ("‡ indicates the winner…") with **zero winner rows**.
- **Graph-expansion contamination.** Graph-seeded retrieval added the top sections
  of *every* neighbor unconditionally; expanding an award seed pulled sibling
  awards (Best Picture/Director/Supporting, Golden Globe) whose overlapping names
  mislead an aggregation over Best Actor.
- **Table reasoning is the floor.** GT11 retrieved the correct Sport/Years section
  with the answer data present, cleanly, and still failed. Perfect retrieval,
  wrong answer — the Phase 2 ceiling.

### Step 3 — retrieval tune-up

Three changes, each targeting one problem above:

1. **Initial article count is a real parameter.** It had been hard-coded to 3, so
   an earlier `INITIAL_ARTICLE_TOP_K` change never took effect. Now seeds 4 to
   cover four-article questions (GT14: Chazelle + Emma Stone + La La Land + 89th).
2. **Selected-article deepening.** `retrieve_selected_article_sections` is wired
   between collection and assessment, so each selected article contributes several
   focused sections initially — the row-bearing chunk arrives before assessment.
   These are vector searches; no added LLM calls.
3. **Graph contamination gating.** Neighbor sections are pooled across all
   neighbors, ranked by match distance, and capped (`max_graph_sections`), so
   adjacent-but-wrong neighbors are outcompeted instead of each contributing
   chunks.

**Three-run comparison** (4 runs each, means; see
[ragas_agentic_retriever_loop_v2.pdf](ragas_agentic_retriever_loop_v2.pdf)):

| configuration | article recall | PASS | context chars/q | articles/q |
|---|---|---|---|---|
| 4.1 graph baseline | 0.939 | — | ~260,000 | 7.4 |
| 5.1 pre-tune | 0.886 | 0.487 | ~18,000 | 3.5 |
| **5.1 tuned** | **0.963** | **0.592** | ~19,000 | 3.2 |

Recall rose **0.886 → 0.963**, now **above the 4.1 baseline (0.939)** while
sending ~14× less context (one run reached recall 1.000). GT14 went to 4/4 at
recall 1.0 (k=4 applied), and GT07's winner-rows chunk now arrives at the deepen
stage with no sibling-award contamination. The "do better than 4.1" bar is met on
retrieval.

The clearest evidence that the ceiling is now synthesis: the tuned run
`infallible_hopper` retrieved at recall **0.974** but passed only **0.42** — near
perfect retrieval, answers still limited.

### Step 4 — GT16 and the entity-aware initial retriever

One residual retrieval gap remained after the tune-up: **GT16** (recall ~0.75).
Its designated articles are `Bill_Clinton` and `Barack_Obama` — both **named in the
question** — and the answer (Hillary Clinton; spouse / 2008 primary opponent /
Secretary of State) is synthesized from those two articles. `Barack_Obama` was
inconsistently retrieved. A direct probe of the section index shows why:

| query | top unique articles |
|---|---|
| full GT16 question | `Bill_Clinton` (0.762), `George_W._Bush` (0.917) — Obama absent |
| targeted "Barack Obama" | `Barack_Obama` at **rank 1** (0.897) |

A single blunt question-level search is dominated by one entity's chunks and
buries the other named entity, even though a targeted query retrieves it
instantly. Graph expansion is the wrong tool (it finds *unnamed, related*
articles; both endpoints here are named). The capability GT16 needs is **query
decomposition into the named entities**, which is a job for the
`MultiStepRetriever`.

**First attempt — reuse the 4.1 sub-topic decomposer — was a wash.** Its prompt is
tuned to emit terminology-rich sub-topic queries for the *answer* step, so for
GT16 it produced entity-*diluted* sentences like
`"2008 Obama presidential election Bill Clinton campaign supporter advisor"` that
retrieve Clinton, not Obama. Across two runs GT16 stayed at recall 0.5–1.0 and
kept failing; overall recall did not beat the vector-initial tune-up (0.951 vs
0.963). Retrieving one entity per sub-query requires *entity* queries, not
sub-topic sentences.

**Decision — an entity-aware decomposer.** `MultiStepRetriever.decompose_entities`
emits one clean canonical entity name per named or directly-implied entity, which
the probe shows retrieves the exact designated article at rank 1. Validated on the
real model:

| question | `decompose_entities` output |
|---|---|
| GT16 | `["Bill Clinton", "Barack Obama", "Hillary Clinton"]` |
| GT14 | `["Damien Chazelle", "Emma Stone", "La La Land", "89th Academy Awards"]` |
| GT07 | `["Academy Award for Best Actor"]` |
| GT11 | `["Summer Olympic Games"]` |

Each name retrieves its designated article at rank 1 (`Bill Clinton` → 0.66,
`Barack Obama` → 0.90, `Emma Stone` → 0.68, `Academy Award for Best Actor` →
0.66). The full question is always included as one query too, so the candidate set
is a *superset* of the plain-vector stage and recall cannot regress. This is the
initial retriever the checkpoint settles on: **initial = entity multi-step,
repeated = graph**. See §4.

This closes the *retrieval* side of GT16 (both named articles reliably surfaced).
It does **not** make GT16 pass: even at recall 1.0 the answer failed to assemble
the three edges, which is table/relationship **synthesis** — Phase 2 (§5).

### Step 5 — the real cap was the review node: judge by TOC, select sections

With the entity retriever finding the right articles, run 1's recall was still only
0.864 — *below* the vector-initial tune-up. The logs showed why: the designated
articles were now in the **candidates**, but the article-review node **rejected**
them. It judged each article by **one snippet** (the entity query's best chunk),
which for these articles was `See also` or the lead infobox — not the answer — so
it discarded the whole article. GT03 rejected all seven candidates → empty
selection → graph expansion (which seeds from the selection) had nothing to expand
→ **recall 0.0**. The bottleneck had moved from *finding* to *keeping*.

The fix is one **fused call over each article's table of contents**
([`review_and_select_from_toc`](../wiki_agents/retrieval_nodes.py)):

- **Judge the article** by its title + section list, not a snippet — is this the
  right source?
- **Select the sections** to read, by name, from the TOC.
- **Flag tables** needed (`needs_table_reader`, `relevant_table_names`) — the
  Phase 2 signal ("yes, there is a table; we will need the table tool").

`load_selected_sections` then loads those named sections into evidence, and a
safety net keeps the best-ranked candidate if the model ever rejects everything
(so selection is never empty). Validated live on GT03 (real TOC + model): it now
**keeps all three ceremonies**, selects `Winners and nominees` for each, rejects
the distractors (Best Picture, Bill Clinton), and sets `needs_table_reader=True`.
The recall-0.0 collapse is gone.

This is still a **retrieval/selection** fix: it makes the right data present and
flags the table need. Reading and synthesizing the table is Phase 2.

### Step 6 — Phase 2: aligned tables (representation) then computation

Phase 2 began by asking the cheaper question first: does *reading* the table (as
structured rows) fix the synthesis failures, or is *computation* required? The
answer came in two parts.

**Two JSON tables exist, and it mattered.** The corpus has two machine-readable
renderings of every table: the 4.1 **sidecar** (`corpus.py`, rows as lists, no
rowspan expansion) and the 5.1 **NormalizedTable** artifacts (`wiki_table_parser`
+ `wiki_table_store`, rowspan/colspan expanded, winner markers and legends kept).
The first "TOC + JSON tables" run used the **sidecar** and came out a wash
(PASS ≈ 0.42) — because merged award tables (Academy Awards → GT03/GT07) misalign
in the sidecar (a name lands in the `Year` column), and an over-eager
`needs_table_reader` flag plus a section-drop rule regressed quotation questions
(GT01/GT13). Two fixes followed: keep the table **additive** (don't drop the
section), tighten the flag, and read from the **aligned NormalizedTable**.

**Aligned representation alone was a real lift.** With those fixes, giving the
model the aligned JSON table (no executor) moved PASS from ≈ 0.39 to **≈ 0.58**
and quality from ≈ 0.59 to **≈ 0.70**, recall unchanged at 0.974. Reading a clean,
row-aligned table is enough for single-table *filters* and lookups.

**Computation was correct — but routing was a coin-flip.** Aggregation,
date/year-range filtering, and winner-dedupe (GT07/GT10/GT11/GT03) don't clear on
reading alone, so a deterministic executor computes them over the *same aligned
rows* — text/numeric/year predicates (`>`, `≥`, `between`, min/first-year) and
count/sum/min/max/average, run in Python, not the model (§5, §7). In isolation it
was correct (GT08/GT10/GT11). In-graph it under-delivered (PASS ≈ 0.65) for a
subtle reason the logs exposed: the executor ran only when the **assessor chose to
request it**, and the assessor kept rationalizing "I can read this directly." GT10
was the tell — it passed exactly when the executor fired and failed when it didn't.

### Step 7 — the table gateway: route every table through the executor

The fix was to stop letting the assessor decide *whether* to compute. Any relevant
selected table is now forced through the executor; the **planner** classifies each
request itself (an `auto` operation → `lookup` to extract cells, or
`filter`/`aggregate`/… to compute). Extraction is **additive**, so prose and
quotations keep their text — the safety property that lets us route ~14 of 19
questions through compute without risk. Mechanically this changed no graph edges:
the gateway (in `assess_evidence`) synthesizes one request per flagged table id,
and the existing compute node loops over them.

Result over **4 full-19 runs** (`agentic_search_lookup_and_compute`):

| metric | Phase-1 head (table reader off) | aligned JSON read | table gateway |
| --- | --- | --- | --- |
| article recall | 0.974 | 0.974 | **1.000** |
| answer quality | 0.588 | ≈ 0.70 | **0.789** |
| strict PASS | 0.386 | ≈ 0.58 | **0.750** |

The designed win: GT10's coin-flip is gone (reliable pass). Bonus: GT08 0.38 → 1.0.
Sentinels held — the quotation (GT01) and lookup (GT05) questions both stayed at
1.0 despite now routing through the executor, so deterministic extraction never
diluted them.

The remaining ceiling is now **non-routing**, and cleanly localized:

- **GT03** — the Academy Awards nominee tables are *layout tables* (positional
  columns; each cell is an entire award category's nominees as one text blob). The
  gateway correctly fires a `lookup` on all three ceremonies, but there are no
  per-nominee rows to extract — this needs a parser-level fix (exploding layout
  tables into rows), not routing.
- **GT07** — planner counting winners within a year range (plan correctness).
- **GT11** — answer scope: the question says "1950 or later" but the graded scope
  caps at 2024, so the two 2028 sports are penalized.

Recall reaches **1.000** in these runs (GT19's earlier context-length crash is
resolved), so retrieval is fully solved; the open work is table representation and
planner correctness.

Sequence of PASS on the GT set: retrieval-only ≈ 0.39 → aligned JSON tables ≈ 0.58
→ deterministic executor (assessor-gated) ≈ 0.65 → **table gateway 0.75** (4-run
mean). Recall 0.90 → 0.94 → **1.000**. This phase moves *answer quality*, which
retrieval could not.

## 4. Configurable retriever architecture

The benchmark graph takes the retrieval strategy per stage as configuration
([agent_graph.py](../wiki_agents/agent_graph.py)):

```python
build_retrieval_benchmark_graph(
    ...,
    initial_retriever="multistep_entity",  # "vector" | "multistep" | "multistep_entity"
    repeated_retrievers=("graph_seeded",),  # escalation, one stage per unmet assessment
    initial_article_top_k=4,
    initial_subquery_top_k=2,
    initial_max_candidates=8,
    sections_per_selected_article=3,
    sections_per_neighbor=2,
    max_graph_sections=4,
)
```

**How the multi-step retriever works.** The `MultiStepRetriever`
([multistep.py](../retrievers/multistep.py)) is *the same Chroma vector search*,
fed better queries. An LLM call decomposes the question into a few sub-queries;
each is searched in parallel; results are merged (Chroma distance → similarity,
summed across sub-queries, top-k) so a chunk found by several sub-queries ranks
higher. The 5.1 initial stage reuses **only** its decomposition (not its chunk
merge), then runs the existing article retrieval per sub-query — so the
`ArticleCandidate` → review → deepen pipeline is preserved (full section metadata,
deterministic grouping, no score-semantics mismatch).

Initial-stage options:

- **`vector`** — one blunt vector search over the whole question
  ([`retrieve_initial_articles`](../wiki_agents/retrieval_nodes.py)). The
  plain-vector baseline for A/B.
- **`multistep`** — `MultiStepRetriever.decompose()` (broader *sub-topic* queries)
  → per-sub-query article retrieval → merge
  ([`retrieve_initial_articles_decomposed`](../wiki_agents/retrieval_nodes.py)).
  Tested and rejected for the initial stage (emits entity-diluted sentences; §3
  Step 4).
- **`multistep_entity`** — `MultiStepRetriever.decompose_entities()`: one clean
  canonical entity name per named/implied entity, which retrieves the exact
  designated article at rank 1. **The checkpoint's initial retriever.**

`repeated_retrievers` is the ordered escalation drawn from `"graph_seeded"` and
`"multistep"`, one stage per unsatisfied assessment. The 5.1 setting is
`("graph_seeded",)`; the historical baseline was `("graph_seeded", "multistep")`.

**Selection stage (after any initial retriever).** One fused call
([`review_and_select_from_toc`](../wiki_agents/retrieval_nodes.py)) judges each
candidate by its **table of contents** — not a snippet — and returns keep/reject,
the section names to read, and table flags. [`load_selected_sections`](../wiki_agents/retrieval_nodes.py)
then loads those named sections into evidence. This replaced the old
snippet-review + blind-deepen, which rejected correct articles whose top chunk was
`See also` or the lead (§3 Step 5). It needs the markdown store's sidecars for the
TOC, so `build_retrieval_benchmark_graph` takes a `markdown_store`.

**Current setting: `initial = multistep_entity`, `repeated = graph`.** Each option
is a one-line `INITIAL_RETRIEVER` change in the harness for A/B; every result row
records `initial_retriever` and `repeated_retrievers`. The entity retriever is
validated at the retrieval level (§3 Step 4); its full-set A/B against the
vector-initial tune-up (recall 0.963) is the next benchmark run.

## 5. Phase gate → Phase 2 (table reading)

**The gate is met.** The full pipeline — `multistep_entity` initial retriever +
fused TOC judge-and-select + graph — over three runs:

| metric | result |
|---|---|
| article recall | **0.974**, identical across all 3 runs |
| questions at recall 1.0 | **18 / 19** (GT03 went 0.0 → 1.0) |
| retrieval-limited failures | **1** — GT19 (UN population ranked-list article) |
| synthesis-limited non-passes | **12**, all at recall 1.0 (GT02, GT03, GT06–13, GT16, GT17) |
| answer quality index / PASS | 0.588 / 0.386 (honest full-19, table-reader off) |

This is the gate condition, in the starkest form yet: **article and section
retrieval are solved (0.974, stable, 18/19 perfect); every remaining failure but
one fails with its sections present — table synthesis.** The non-passes are now
mostly *partial* (right data, incomplete answer), the signature of a synthesis
ceiling rather than a retrieval one.

The retriever even generated the Phase 2 worklist: `needs_table_reader` flagged
**GT01, GT03, GT05, GT07, GT08, GT09, GT10, GT11, GT12, GT13, GT14, GT19**. Phase 2
enables the `need_table_reader` branch (parser, artifact store, planner, executor
already implemented and tested; see §7) and the assessor routing that sends those
flagged questions to it rather than answering from a flattened chunk. The one
retrieval loose end (GT19) is the same ranked-list-table family as GT09 — likely
resolved by the table reader too.

### The table branch — deterministic table computation

The harness crosses the Phase 2 boundary (this is the machinery the Step 7 gateway
drives on every relevant table):

- the TOC prompt ranks the complete normalized table catalog before truncating it;
- each offered table includes an immutable artifact ID plus its section, caption,
  and columns;
- exact IDs are authoritative, so an explicitly selected winners table cannot be
  silently replaced with a semantically similar box-office table;
- multi-period questions may select multiple artifacts from the same article;
- a bounded row budget is divided across all explicitly selected artifacts; and
- rendered rows retain bold/italic markers, superscript/subscript annotations,
  colors, legends, and stable source-cell coordinates.
- when the assessor identifies a row-wise operation, a structured planner may use
  only the selected artifact's real columns and emits deterministic text, numeric,
  or year predicates;
- Python—not the LLM—filters, sorts, counts, or aggregates the rows and returns
  the exact contributing source-cell coordinates; and
- the computed result becomes a normal `EvidenceItem`, after which the same
  evidence assessor decides whether another table/retrieval round is needed.

This is a distinct experiment mode,
`agentic_toc_with_table_computation`; it must not be combined with the
earlier `agentic_section_evidence_no_tables` results as if they were one setup.

## 6. Shared state and data contracts

[agentic_models.py](../wiki_agents/agentic_models.py) defines the Pydantic/typed
boundary. Key types:

- `EvidenceItem` — the common unit for text/table/infobox/graph evidence, with
  source provenance and explicit score semantics (BM25 scores, Chroma distances,
  and fused rankings are never compared as if equivalent).
- `ArticleCandidate` — an article discovered during retrieval, not yet evidence.
- `EvidenceAssessment` — separates evidence grading from answering; list fields
  default to empty so imperfect structured output is repaired, not fatal.
- `RetrievalRequest` / `TableRequest` — actionable gaps emitted by assessment.
- `TablePredicate` / `TableQueryPlan` — schema-constrained instructions for the
  deterministic executor; missing columns and malformed thresholds fail closed.
- `TableEvidence` — computed rows, optional calculation, warnings, and exact source
  cells returned by the executor.
- `AgentState.table_attempts` — a table-loop budget independent of retrieval
  attempts, preventing repeated table requests from cycling forever.

Model and DB clients are constructed outside graph state and injected into nodes;
persisted state stays serializable and never contains API keys.

## 7. Table branch (enabled)

The parser, artifact-intake, planner, and deterministic executor now run in the
harness:

- **Rich parser** ([wiki_table_parser.py](../utils/wiki_table_parser.py)) — expands
  rowspan/colspan to a logical grid while keeping original coordinates; combines
  multi-row headers; separates super/subscripts and note markers; retains bold,
  italic, background color, sortable values, links, and nearby legends; stable
  table/artifact IDs. This is what lets a nominee be told from a winner when the
  distinction is bold/color/legend rather than a column.
- **Offline artifact store**
  ([wiki_table_store.py](../utils/wiki_table_store.py)) — parses every article
  once and publishes one compressed JSON artifact per article plus a `manifest.json`;
  read-only at graph runtime. The generated store is gitignored; the parser,
  builder, tests, and schema are versioned.
- **Deterministic table branch** — `find_table_candidates()` resolves and ranks
  artifacts; `plan_table_query()` produces a validated `TableQueryPlan` (the model
  picks the operation, not the arithmetic); `execute_table_query_plan()` runs it in
  Python and returns `TableEvidence` with exact source-cell provenance.
- **Graph node** — `compute_requested_tables()` executes the assessor's bounded
  `TableRequest` list, records success or an expected schema/artifact failure as
  evidence, increments `table_attempts`, and routes back to `assess_evidence`.

The router gives a pending table request priority while table budget remains. When
that budget is exhausted, it can still use an available retrieval request; otherwise
it exits cleanly with the evidence accumulated so far. The defaults are two table
rounds and six requests per round.

## 8. Reproduce

From `wikipedia_retrieval_engine/`:

```bash
python "Capstone Checkpoint 5.1/capstone_checkpoint_5_1_agent_rag_starter.py" \
  --gt-set "GT/wikipedia_GT.csv" \
  --output-dir "Capstone Checkpoint 5.1/ragas_test_GT_5.1" \
  --experiment-name agentic_toc_with_table_computation
```

`--limit N` for a smoke test; repeat `--question-id GT16` to select questions.
Aggregate PDF over a set of runs:

```bash
python "utils/analyze_ragas_experiments.py" \
  --experiments-dir "Capstone Checkpoint 5.1/ragas_test_GT_5.1" \
  --output "Capstone Checkpoint 5.1/ragas_agentic_retriever_loop_v2.pdf" \
  --title "Capstone Checkpoint 5.1 - Agentic Retriever Loop"
```

Focused tests:

```bash
python -m unittest discover -s wikipedia_retrieval_engine/tests -p "test_*.py"
```

## 9. Reports

- [ragas_agentic_retriever_loop_v2.pdf](ragas_agentic_retriever_loop_v2.pdf) —
  5.1 aggregate (pass/partial/fail, recall, per-family attention).
- 4.1 baselines:
  [graph retriever](../Capstone%20Checkpoint%204.1/ragas_GT_evaluation_graph_retriever.pdf),
  [decomposition + reasoning](../Capstone%20Checkpoint%204.1/ragas_GT_evaluation_decomposed_wReasoning.pdf),
  [base](../Capstone%20Checkpoint%204.1/ragas_GT_evaluation_base_report.pdf).

## 10. Risks and open questions

- The evidence assessor can accept weak evidence or reject sufficient evidence; it
  needs its own labeled cases. "Trust the gaps" mitigates the crash, not the
  calibration.
- Multi-step decomposition is LLM-driven, so the initial stage is now
  nondeterministic; run 3–4 times and compare per-question, not single aggregates.
- Recall is now 1.000 across the 4-run gateway set (GT09/GT19 resolved). The
  residual table gap is *representation*, not retrieval: layout tables (GT03) whose
  cells are text blobs rather than rows.
- Agentic routing adds latency and nondeterminism; justified only because targeted
  evaluation now shows recall above the 4.1 baseline at ~14× less context.

## 11. Implementation status

Implemented:

- shared evidence/request/table/answer/state models;
- rich table parsing, artifact generation, and read-only discovery/loading;
- configurable initial (`vector` | `multistep` | `multistep_entity`) and repeated
  (`graph_seeded` | `multistep`) retrieval stages, with graph-section contamination
  gating; entity decomposition (`MultiStepRetriever.decompose_entities`) is the
  settled initial retriever;
- a fused TOC-based selection stage (`review_and_select_from_toc` +
  `load_selected_sections`): judges each article by its table of contents, selects
  exact sections and stable table artifact IDs — replacing snippet review, which
  rejected correct articles on a `See also`/lead chunk;
- exact article-and-heading retrieval for TOC-selected sections;
- additive normalized-table evidence with multi-table selection, a bounded row
  budget, and rich cell/legend semantics;
- assessment-contract repair so every run completes all 19 questions;
- deterministic table resolution, `TableQueryPlan` creation, and plan execution
  with validated text/numeric/year predicates and cell-level provenance;
- a bounded `need_table_reader` graph branch that converts executed results into
  answer-visible `EvidenceItem` objects and reassesses the combined evidence;
- the single-table **gateway**: every relevant selected table is forced through the
  executor (no "read it directly" carve-out), the planner classifies each request
  via an `auto` operation (lookup vs filter/aggregate/…), and extraction is additive
  so prose/quotations are preserved — quality 0.789, PASS 0.750, recall 1.000
  (4-run mean, `agentic_search_lookup_and_compute`);
- a Wikipedia-GT RAGAS harness with separately labeled section-only and
  table-computation experiment modes;
- focused tests for models, parsing, store cache/invalidation, graph nodes,
  routing, decomposed initial retrieval, selected-article deepening, graph-section
  ranking, and logging.

Still to implement:

- **layout-table explosion**: the Academy Awards nominee tables (GT03) are
  presentation tables — positional columns, each cell an entire category's nominees
  as one text blob. The parser should detect these and explode them into
  per-nominee rows so the executor has rows to extract;
- planner correctness for counting-within-a-range aggregates (GT07);
- deterministic multi-table / multi-document joins (the gateway can execute several
  independent requests, then leaves cross-result synthesis to the answer model);
- in-graph grounded answering and verification nodes.

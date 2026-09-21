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

## 2. Approach: a retrieval-only benchmark first

The table-reader branch is implemented but **deliberately disabled** for this
benchmark. Enabling it would change two variables at once (progressive retrieval
*and* table reasoning). The retrieval-only benchmark answers a narrower question:
does the assessment loop, with section-level evidence, retrieve solidly enough
that any remaining failures are attributable to synthesis rather than retrieval?

```text
START
  -> retrieve initial articles        (configurable: vector | multi-step)
  -> review article candidates         (LLM keeps/rejects)
  -> collect initial evidence          (promote selected representative chunks)
  -> deepen selected article sections  (top-N sections per selected article)
  -> assess evidence  --ready--------------------------> answer + log -> END
       |-- not ready --> repeated retriever(s) --------> assess (loop)
       +-- budget exhausted ----------------------------> answer + log -> END
```

Only **section chunks** ever enter evidence; article names are routing handles.
The answer model receives accumulated section evidence — never whole articles and
never fixed leading-character slices.

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

The retrieval-only benchmark has done its job. Of the five table questions, all
now fail with their designated sections **present and uncontaminated** (recall
1.0):

| table question | article recall | passes |
|---|---|---|
| GT03 (cross-article intersection) | 1.00 | 0/4 |
| GT07 (temporal aggregation) | 1.00 | 1/4 |
| GT08 (table filter) | 1.00 | 2/4 |
| GT10 (program filter) | 1.00 | 0/4 |
| GT11 (program filter) | 1.00 | 0/4 |

This is the gate condition: **article and section retrieval are solid; the failing
answers are table synthesis.** Phase 2 enables the `need_table_reader` branch (the
parser, artifact store, planner, and executor are already implemented and tested;
see §7). Enabling it requires the assessor to route table operations to the table
reader rather than declaring a flattened chunk "sufficient."

## 6. Shared state and data contracts

[agentic_models.py](../wiki_agents/agentic_models.py) defines the Pydantic/typed
boundary. Key types:

- `EvidenceItem` — the common unit for text/table/infobox/graph evidence, with
  source provenance and explicit score semantics (BM25 scores, Chroma distances,
  and fused rankings are never compared as if equivalent).
- `ArticleCandidate` — an article discovered during retrieval, not yet evidence.
- `EvidenceAssessment` — separates evidence grading from answering; list fields
  default to empty so imperfect structured output is repaired, not fatal.
- `RetrievalRequest` / `TableRequest` / `TableQueryPlan` / `TableEvidence` — the
  retrieval and (Phase 2) table branches.

Model and DB clients are constructed outside graph state and injected into nodes;
persisted state stays serializable and never contains API keys.

## 7. Table branch (Phase 2, implemented but disabled)

The table machinery is built and tested, gated off for the retrieval benchmark:

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

## 8. Reproduce

From `wikipedia_retrieval_engine/`:

```bash
python "Capstone Checkpoint 5.1/capstone_checkpoint_5_1_agent_rag_starter.py" \
  --gt-set "GT/wikipedia_GT.csv" \
  --output-dir "Capstone Checkpoint 5.1/ragas_test_GT_5.1" \
  --experiment-name agent_multistep_entity
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
- GT09/GT19 (ranked-list-table articles) still show intermittent recall loss — the
  same table root cause, surfacing in retrieval.
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
  the sections to read, and flags table needs for Phase 2 — replacing snippet
  review, which rejected correct articles on a `See also`/lead chunk;
- assessment-contract repair so every run completes all 19 questions;
- deterministic table resolution, `TableQueryPlan` creation, and plan execution
  with cell-level provenance (gated off in this benchmark);
- a Wikipedia-GT RAGAS harness answering only from accumulated section evidence;
- focused tests for models, parsing, store cache/invalidation, graph nodes,
  routing, decomposed initial retrieval, selected-article deepening, graph-section
  ranking, and logging.

Still to implement (Phase 2):

- convert executed table results into table-backed `EvidenceItem` objects;
- wire the `need_table_reader` branch and the assessor routing it needs;
- multi-table / multi-document joins;
- in-graph grounded answering and verification nodes.

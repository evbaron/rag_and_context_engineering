# Checkpoint 5.1: agentic evidence graph

This file records the reasoning, preparation, design decisions, and implementation
status for Checkpoint 5.1. It continues the experiment narrative in
[Checkpoint 4.1](../Capstone%20Checkpoint%204.1/README%204.1.md); general LangChain and
LangGraph syntax belongs in the repository-level
[LangChain guide](../../LANGCHAIN_GUIDE.md).

## Starting point: what Checkpoint 4.1 established

Checkpoint 4.1 improved retrieval, but the answer-quality ceiling did not move with
it. Graph expansion raised mean designated-article recall from 0.899 to 0.939, while
answer quality remained approximately flat. Query decomposition helped a few specific
questions but did not reliably improve the complete set.

The controlled markdown/plain-text comparison also showed that presenting a cleaner
table to the model was not enough. The remaining failures are concentrated in tasks
that require the system to:

- decide whether the current evidence completely supports the requested answer;
- identify exactly what is missing instead of simply retrieving more of the same;
- enumerate, filter, compare, or aggregate rows in one or more tables; and
- preserve provenance from the final claim back to an article, table, row, and cell.

**Checkpoint 5.1 hypothesis:** a bounded evidence graph can choose the appropriate
next action—targeted retrieval, structured table analysis, or grounded reasoning—and
therefore address failures that a single fixed retrieve-then-answer pass cannot.

This is a reasoning and orchestration checkpoint, not another attempt to increase
Top K indiscriminately.

## First benchmark: retrieval-only agent

The first Checkpoint 5.1 benchmark intentionally leaves the table-reader route out
of the running graph. Table parsing, artifact lookup, planning, and deterministic
execution remain implemented and tested, but enabling them now would change two
major variables at once: progressive retrieval and structured table reasoning.

The retrieval-only experiment asks a narrower question: does evidence assessment
improve results when it can escalate from section-aware vector search to graph-guided
and multi-step section retrieval?

```text
section-aware VS: three unique article candidates
     |
     v
review candidates and promote representative sections to evidence
     |
     v
is the section evidence sufficient?
     |
     +-- yes --> answer from accumulated sections
     |
     +-- no --> expand selected VS articles through the Wikipedia graph
                    |
                    v
              retrieve relevant sections inside graph neighbors
                    |
                    v
              is the accumulated section evidence sufficient?
                    |
                    +-- yes --> answer from accumulated sections
                    |
                    +-- no --> targeted multi-step section retrieval
                                      |
                                      v
                                final assessment --> answer or limitations
```

Article names are routing handles at every stage. Graph expansion returns related
article names, after which the section-aware vector index selects evidence inside
those articles using the assessor's focused missing-fact query. Neither full articles
nor fixed leading-character slices are sent to assessment or answering.

The table branch will be enabled in a later benchmark after this retrieval-only
result establishes a clean comparison point.

## Proposed workflow

```text
user question
     |
     v
section-aware vector retrieval
     |
     v
diversify by article and review candidates
     |
     v
promote selected representative chunks to initial evidence
     |
     v
assess evidence completeness
     |
     +-- need_more_evidence --> targeted retrieval ---------+
     |                                                       |
     +-- need_table_reader --> structured table analysis ----+--> reassess
     |                                                       |
     +-- ready_to_answer ---> grounded reasoning -> verify -> final answer
                                                    |
                                                    +--> bounded repair / abstain
```

The graph is deliberately constrained. The language model may judge evidence or
produce a structured request, but application code owns the available routes,
budgets, validation, and stopping rules. This keeps the behavior inspectable enough
for a graded retrieval experiment.

The original intake subgraph remains available for isolated testing. The retrieval
benchmark graph in [`agent_graph.py`](../wiki_agents/agent_graph.py) currently owns
evidence collection and assessment:

```text
START
  -> retrieve_initial_articles
  -> review_article_candidates
  -> collect_initial_evidence
  -> assess_evidence
       |-- sufficient -------------------------------> write_question_log -> END
       |-- missing, attempt 1 -> graph sections ----> assess_evidence
       |-- missing, attempt 2 -> multi-step sections -> assess_evidence
       +-- missing after final attempt --------------> write_question_log -> END
```

For this graph, `assess_evidence` runs in retrieval-only mode. The structured output
must leave `table_requests` empty and express every missing fact as a focused
`RetrievalRequest`. The graph has a business limit of three retrieval stages in
addition to LangGraph's recursion backstop.

### Complete benchmark run

`graph.invoke(...)` is not currently the complete question-answering run. It returns
the terminal retrieval state after `write_question_log`. The Checkpoint 5.1 harness
then formats only the accumulated section-level `EvidenceItem` content, calls the
answer model, asks RAGAS to judge that answer, and saves the result row.

```text
user question
     |
     v
graph.invoke(initial_agent_state(question))
     |
     +-> section-aware vector retrieval: up to three articles
     |       |
     |       v
     |   review candidates and collect representative sections
     |       |
     |       v
     |   assess accumulated evidence
     |       |
     |       +-- ready ---------------------------------------+
     |       |                                                |
     |       +-- missing after vector search                  |
     |       |       -> graph expansion from VS seeds         |
     |       |       -> retrieve sections in graph neighbors  |
     |       |       -> reassess                              |
     |       |                                                |
     |       +-- still missing                                |
     |               -> targeted multi-step section retrieval |
     |               -> final assessment                     |
     |                                                        |
     +-- ready or retrieval limit reached <-------------------+
             |
             v
       write_question_log
             |
             v
            END
             |
             v
       return terminal AgentState
             |
             v
format accumulated section evidence
             |
             v
answer_from_context(question, context)     # currently outside the graph
             |
             v
RAGAS correctness judge
             |
             v
save benchmark result
```

This distinction matters for the evidence log: today it captures everything known
by the retrieval graph, but it is written before the harness creates the final
answer. Consequently, the per-question evidence JSON does not yet contain the
answer, even though the CSV/JSON benchmark result does.

The next graph change is to move grounded answering inside the graph. Both a
positive sufficiency decision and exhaustion of the retrieval budget must reach the
answer node; a budget-limited answer must state its evidence limitations rather than
invent the missing facts.

```text
user question
     |
     v
graph.invoke(...)
     |
     +-> retrieval and assessment loop
             |
             +-- evidence is sufficient --+
             |                             |
             +-- retrieval limit reached --+
                                           |
                                           v
                                    answer_question
                                           |
                                           v
                                  write_question_log
                                           |
                                           v
                                          END
```

After that change, `answer_question` will return a partial state update such as
`{"response": "..."}`, `write_question_log` will serialize the answer together with
its supporting evidence and assessment history, and the harness will use
`state["response"]` for RAGAS evaluation. RAGAS remains outside the agent graph: it
measures the run and is not part of the agent's reasoning.

### How state moves through the current graph

An edge does not pass only the previous node's return value to the next node.
Every node receives the accumulated `AgentState`, returns a partial state update,
and LangGraph merges that update into the shared state before following the edge.
Fields that a node does not return remain available to later nodes.

The graph begins with:

```python
initial_agent_state(question)

# {
#     "question": "...",
#     "retrieval_attempts": 0,
# }
```

#### `START -> retrieve_initial_articles`

Input:

- `state["question"]`;
- the section-aware `VectorRetriever`, bound to the node when the graph is built.

Work performed:

- searches globally across section-aware chunks;
- considers more chunk hits than the requested article count; and
- keeps the best matching chunk from each of up to three unique articles.

Partial output:

```python
{
    "article_candidates": list[ArticleCandidate],  # zero to three
    "retrieval_attempts": previous_count + 1,
}
```

Each `ArticleCandidate` retains the article name, representative chunk text and ID,
section title and hierarchy, query, article rank, raw Chroma distance, and score
direction. LangGraph merges these fields with the original question.

#### `retrieve_initial_articles -> review_article_candidates`

Input:

- `state["question"]`;
- `state["article_candidates"]`;
- the chat model, bound to the node when the graph is built.

Work performed:

- sends the question and representative excerpt for every candidate to one
  structured LLM call;
- requires exactly one `ArticleReview` for every candidate;
- rejects an LLM result that omits, duplicates, renames, or invents an article; and
- classifies each article as relevant or irrelevant, with a reason and preliminary
  table-reader signal.

Partial output:

```python
{
    "article_reviews": list[ArticleReview],
    "selected_articles": list[str],
    "rejected_articles": list[str],
}
```

The original candidates remain in state. The selected and rejected lists are derived
deterministically from the structured reviews rather than separately generated by
the model.

#### `review_article_candidates -> collect_initial_evidence`

Input:

- `state["question"]`;
- `state["article_candidates"]`;
- `state["selected_articles"]`; and
- any evidence already present in state.

Work performed:

- makes no retrieval or LLM call;
- matches selected article names back to their candidates;
- promotes each selected representative section-aware chunk into an `EvidenceItem`;
  and
- preserves and deduplicates existing evidence by stable evidence ID.

Partial output:

```python
{
    "evidence": list[EvidenceItem],
}
```

Rejected candidates are not promoted. Each evidence item preserves the source
article, section path, chunk ID, content, retrieval query, rank, raw distance, score
semantics, and retrieval-stage metadata.

#### `collect_initial_evidence -> assess_evidence`

Input:

- `state["question"]`;
- `state["article_reviews"]`;
- `state["evidence"]`; and
- the chat model, bound to the node when the graph is built.

Work performed:

- asks a structured LLM call whether the accumulated evidence supports every part
  of the question;
- records supported and missing requirements;
- creates focused `RetrievalRequest` objects for missing prose or sources;
- can create `TableRequest` objects when table-native work is required, although
  the retrieval-only benchmark explicitly disables that output; and
- rejects contradictory assessments, such as `ready_to_answer=True` together with
  missing requirements or unresolved requests.

Partial output:

```python
{
    "assessment": EvidenceAssessment,
    "assessment_history": list[EvidenceAssessment],
}
```

The assessment does not directly mutate the evidence and does not store a redundant
route string. `route_after_evidence_assessment()` deterministically derives
`ready_to_answer`, `need_table_reader`, or `need_more_evidence` from this object.
The intake-only graph records the first assessment and stops. The benchmark graph
uses `route_retrieval_benchmark()` to follow its bounded retrieval-only branches.

#### `assess_evidence -> conditional retrieval or termination`

Input:

- `state["assessment"]`; and
- `state["retrieval_attempts"]`.

Work performed:

- if the evidence is ready, terminates retrieval;
- after the initial vector stage, routes missing evidence to graph-seeded section
  retrieval;
- after graph-seeded retrieval, routes missing evidence to targeted multi-step
  section retrieval; and
- after the final allowed retrieval stage, terminates retrieval even if the
  assessment still records missing requirements.

This is a routing function, so it chooses an edge and does not update state.

#### Graph-seeded section retrieval -> `assess_evidence`

Input:

- `state["selected_articles"]`, used as graph seeds;
- focused retrieval requests from `state["assessment"]`; and
- the Wikipedia relationship graph and section-aware vector retriever bound when
  the graph is built.

Work performed:

- finds related article names in the graph;
- searches inside those articles with the assessor's missing-fact query;
- adds only matching section chunks, never whole articles; and
- increments `retrieval_attempts`.

Partial output:

```python
{
    "evidence": list[EvidenceItem],
    "retrieval_attempts": previous_count + 1,
}
```

The expanded evidence returns to `assess_evidence`, which appends another structured
assessment to `assessment_history`.

#### Targeted multi-step section retrieval -> `assess_evidence`

Input:

- the latest focused retrieval requests from `state["assessment"]`; and
- the section-aware `MultiStepRetriever` bound when the graph is built.

Work performed:

- decomposes the unresolved information need into targeted retrieval work;
- searches the section-aware index;
- deduplicates new section chunks against accumulated evidence; and
- increments `retrieval_attempts`.

Partial output:

```python
{
    "evidence": list[EvidenceItem],
    "retrieval_attempts": previous_count + 1,
}
```

The evidence is assessed one final time. A sufficient assessment ends retrieval;
otherwise the business limit ends it with the missing requirements still visible.

#### Planned terminal node: `answer_question -> write_question_log`

Input:

- `state["question"]`;
- all accumulated section-level `state["evidence"]`; and
- the final `state["assessment"]`, including any requirements still missing when
  the retrieval limit was reached.

Work to perform:

- format the section evidence with evidence IDs, source articles, and section paths;
- generate a grounded answer using only that evidence;
- answer normally when the final assessment is sufficient; and
- when the retrieval limit was reached without sufficient evidence, answer only
  the supported portion and explicitly identify the limitation.

Partial output:

```python
{
    "response": str,
}
```

Because this is the same terminal node for both outcomes, reaching the retrieval
limit means “stop retrieving and answer with limitations,” not “skip answering.”
Once implemented, logging moves after this node so the response and all evidence
used to produce it are captured together.

#### Terminal route -> `write_question_log`

Input:

- the complete accumulated `AgentState`; and
- the run-level `AgentRunLogger`, bound to the node when the graph is built.

Work performed:

- serializes Pydantic models and all other state fields;
- writes one atomic, pretty-printed evidence JSON file for the question; and
- keeps filesystem paths and locks outside agent state.

Partial output:

```python
{}
```

The logging node intentionally returns no state changes. Its only effect is writing
the evidence file.

#### `write_question_log -> END -> harness answer`

`END` returns the accumulated state to the caller of `graph.invoke(...)`. The intake
test graph still ends after the first assessment. The retrieval benchmark graph ends
when evidence is sufficient or after the bounded vector, graph, and multi-step stages.
Its terminal state also contains the accumulated section evidence and
`assessment_history`. The current harness then formats that evidence and calls
`answer_from_context`; answering is not yet a node in the compiled graph.

Retrievers, the relationship graph, and the language model are constructed outside
graph state and bound to their nodes when the graph is compiled. The retrieval-only
graph uses real conditional destinations; the separate intake graph remains useful
for focused tests of the initial prefix.

`graph.compile(...)` validates the node-and-edge definition and returns the executable
graph used by `graph.invoke(...)`. The intake graph is named
`checkpoint_5_1_evidence_intake`; the conditional benchmark is named
`checkpoint_5_1_retrieval_benchmark`. These names are observability labels and do not
become part of `AgentState`.

## Run evidence logs

`AgentRunLogger` creates one directory per graph run under:

```text
Capstone Checkpoint 5.1/logs/YYYY_MM_DD_HH_MM_SS/
```

Every `graph.invoke(...)` call writes one pretty-printed JSON file such as:

```text
001__who-won-best-picture.evidence.json
```

The file contains the run ID, question number, log time, question, and complete
terminal `AgentState`, including article candidates, article reviews, selected and
rejected articles, evidence, assessment, and later-stage outputs as they are added.
The logger remains outside graph state so filesystem paths, locks, and file handles
are never serialized as agent data. Writes use a temporary file followed by an
atomic rename, and repeated questions receive distinct sequence numbers.

## RAGAS retrieval-only harness

The course starter file is now the Checkpoint 5.1 evaluation harness. It loads the
same Wikipedia ground-truth schema and RAGAS correctness judge used in Checkpoint
4.1, runs the retrieval-only LangGraph, answers from accumulated section evidence,
and records article recall plus graph-specific diagnostics.

From `wikipedia_retrieval_engine/`:

```bash
python "Capstone Checkpoint 5.1/capstone_checkpoint_5_1_agent_rag_starter.py" \
  --gt-set "GT/wikipedia_GT.csv" \
  --output-dir "Capstone Checkpoint 5.1/ragas_retrieval_only" \
  --experiment-name agentic_sections_no_tables \
  --limit 2
```

Remove `--limit 2` for the complete GT set. To run particular questions, repeat
`--question-id`, for example `--question-id GT03 --question-id GT16`.

Each result row includes the RAGAS verdict, designated-article recall, retrieval
attempts, terminal stage, assessment route trace, evidence counts by stage, evidence
IDs, context characters, and whether the final assessment considered the evidence
sufficient. The per-question JSON logs retain every assessment in
`assessment_history`.

## Initial retrieval strategy

Checkpoint 5.1 uses the existing heading-based Chroma index named
`wikipedia_sections_max10000_no_overlap`. Its chunks retain the source article,
section title, section hierarchy, and stable chunk ID.

The global vector search considers more chunks than the requested article count and
keeps the best chunk from each of up to three unique articles. This provides article
diversity without discarding the evidence that caused each article to rank. After the
article-review node rejects irrelevant candidates, those representative chunks are
promoted directly to `EvidenceItem` objects.

The graph does not immediately repeat the original query inside every selected
article. It assesses the initial evidence first. Only `need_more_evidence` triggers a
follow-up section search, using the focused missing-fact query produced by the
assessment. This makes each loop change the retrieval request rather than returning
more of the same context.

## Evidence assessment and routing

The assessor should evaluate the complete user question against accumulated evidence,
not merely grade whether the latest retrieved chunk looks relevant. Its structured
output records:

- requirements already supported, including the evidence IDs that support them;
- requirements still missing;
- unresolved conflicts between sources;
- targeted retrieval requests for missing prose or sources; and
- table requests when the required fact depends on structured rows.

The three routing outcomes have distinct meanings.

### `need_more_evidence`

Use this route when the graph cannot yet identify or support a required fact. The
assessment supplies a `RetrievalRequest` containing:

- a plain-language description of the missing fact;
- a focused next query;
- likely target articles, when known;
- keywords, names, dates, or exact phrases to emphasize; and
- a preferred vector, BM25, hybrid, or graph retriever.

The next call should change something meaningful. Repeating the same query against
the same retriever and returning the same evidence IDs is not progress. The state
therefore retains attempted queries and seen evidence IDs.

### `need_table_reader`

Use this route when the source is known but the missing answer requires table-native
operations such as lookup, filtering, aggregation, comparison, sorting, timeline
construction, or intersection across documents.

A `TableRequest` identifies the missing fact, article, optional table ID or expected
caption, required columns, row filters, comparison key, and operation. A specialized
table analyzer should return compact `TableEvidence`, including:

- the immutable table artifact ID;
- result rows or a calculated value;
- the calculation performed;
- exact source-cell identifiers;
- warnings; and
- whether the table result is sufficient for the request.

The result re-enters the common evidence pool and is assessed again. The table branch
does not bypass evidence sufficiency or answer verification.

Table work is separated into three responsibilities:

1. `find_table_candidates()` deterministically resolves the request's article and
   ranks its prebuilt table artifacts using captions, sections, columns, legends,
   row filters, and normalized row text. Explicit table IDs are authoritative and
   invalid IDs are rejected rather than silently replaced.
2. `plan_table_query()` gives the question, structured `TableRequest`, and a compact
   view of the best candidates to a structured LLM call. It returns a
   `TableQueryPlan` containing one immutable artifact ID, exact column names,
   filters, grouping, sorting, and an optional supported calculation.
3. `execute_table_query_plan()` executes the validated plan in Python and produces
   `TableEvidence`. The model selects the intended operation, but it does not
   perform counts, sorting, or arithmetic itself.

The planner output is validated against the loaded artifact. A plan is rejected if
it selects an artifact that was not offered, changes the requested operation, or
invents a column. Query plans remain local to the table-reader branch for now; they
will not add another `AgentState` field unless runtime logging or later nodes need
to consume them.

The executor currently supports row lookup/filtering, comparison projections,
sorting/timelines, and grouped or ungrouped count, sum, minimum, maximum, and
average operations. Text filters search both ordinary cell text and retained
semantic fields. For example, a filter for `Pro Bowler` can match a cell containing
`†` when the table legend maps that symbol to the requested meaning.

Every contributing cell receives a stable coordinate such as
`table-002-e731777dff:r17:c3`, based on the parser's original expanded-grid
coordinates. `TableCellEvidence` retains the cell's plain and display text, bold and
italic text, superscript/subscript annotations, background color, sortable value,
and matched legend meanings. Thus a result can be compact while still preserving
the winner/nominee or NFL-marker evidence needed by the later interpretation node.

### `ready_to_answer`

Use this route only when every answer requirement is supported and no unresolved
conflict prevents a grounded response. The reasoning node produces a draft whose
claims cite evidence IDs. A verification step checks those citations, calculations,
and requirements before the answer becomes final.

## Shared state and data contracts

[agentic_models.py](../wiki_agents/agentic_models.py) defines the current Pydantic and
typed-state boundary.

- `EvidenceItem` is the common unit for text, table, infobox, and graph evidence. It
  carries source provenance and explicitly records score semantics so BM25 scores,
  Chroma distances, and fused rankings are not compared as if they meant the same
  thing.
- `EvidenceRequirement` makes completeness testable one requirement at a time.
- `RetrievalRequest` describes a targeted next retrieval action.
- `TableRequest`, `TableQueryPlan`, and `TableEvidence` describe the table branch.
- `EvidenceAssessment` separates evidence grading from answering.
- `DraftAnswer`, `AnswerClaim`, and `AnswerVerification` make claim-to-evidence
  checking explicit.
- `AgentState` contains only fields written by implemented graph nodes. New fields
  are added just in time as later branches are built.

Model and database clients do not belong in graph state. They should be constructed
outside the state and injected into node functions or runtime context. Persisted or
streamed state must remain serializable and must not contain API keys.

## Specialized Wikipedia table representation

Checkpoint 4.1's compact sidecar retains headers and row strings, but difficult pages
encode meaning outside those strings. The richer parser in
[wiki_table_parser.py](../utils/wiki_table_parser.py) preserves both a convenient row
view and the cell-level details required for defensible table reasoning.

### Semantics retained

- `rowspan` and `colspan` are expanded into a logical rectangular grid while each
  inherited cell retains its original coordinates;
- multi-row headers are combined into stable, unique column names;
- superscripts and subscripts are separated from base text and classified as
  references or semantic markers;
- Wikipedia note targets and note text are retained when available;
- bold and italic text are recorded separately;
- background colors, sortable values, and links are retained;
- nearby symbol, abbreviation, and color legends are associated with matching cells;
- captions, section paths, nearby context, table classes, and parser warnings are
  preserved; and
- stable table and artifact IDs connect computed results back to their source.

This matters for the motivating examples:

- Academy Award tables can distinguish a nominee from a winner when the distinction
  is encoded by bold text, color, or a legend rather than a dedicated column.
- NFL tables can preserve `*`, `†`, and note markers such as `[N 1]`, while nearby
  legends explain compensatory selections, Pro Bowlers, and position abbreviations.

The parser selects `table.wikitable` by default. Infoboxes, navigation tables, and
layout tables are excluded unless the caller intentionally supplies a broader CSS
selector.

## Decision: build table artifacts once

Normalized tables are deterministic corpus-derived data, not conversational memory.
Saving them in LangGraph's `InMemoryStore` would lose them on process exit, duplicate
parsing work, and make an answering graph responsible for mutating its evidence layer.

Checkpoint 5.1 therefore uses an offline build-and-publish step:

```bash
python -m wikipedia_retrieval_engine.utils.wiki_table_store
```

[wiki_table_store.py](../utils/wiki_table_store.py) parses every source article and
writes one compressed JSON artifact per article under:

```text
wikipedia_retrieval_engine/retrievers/db/table_artifacts/wikipedia_tables/
```

It publishes `manifest.json` only after every article succeeds. Artifact filenames
include the source hash, parser version, table selector, and schema version, so an
interrupted rebuild cannot overwrite the files referenced by the previous manifest.
The manifest contains the article inventory and a lightweight table catalog.

Running the builder again checks the source inventory, versions, selector, and
artifact files. If they match, it opens the existing store without parsing the HTML
again. `--force` requests an intentional rebuild.

At graph runtime the interface is read-only:

```python
from wikipedia_retrieval_engine.utils.wiki_table_store import TableArtifactStore

table_store = TableArtifactStore.open()
candidates = table_store.find_tables(
    "NFL draft Pro Bowler",
    source_article="2020_NFL_draft.html",
    limit=5,
)
table = table_store.load_artifact(candidates[0].artifact_id)
```

Catalog lookup is deterministic metadata search, not a replacement for the main
retriever. Ordinarily, retrieved evidence identifies the source article and possibly
the caption or table ID; the table branch then loads the corresponding normalized
artifact.

The full 2,419-article build has not yet been run as part of this preparation. A
development benchmark over five large/complex articles produced 44 tables from
2.8 MB of source HTML in about seven seconds and compressed the artifacts to roughly
0.3 MB. That small sample is a plumbing check, not a full-corpus performance claim.

## Run-once preparation and validation

From the repository root:

```bash
source .venv/bin/activate

# Build or validate the published table-artifact store.
python -m wikipedia_retrieval_engine.utils.wiki_table_store

# Run focused model, parser, and artifact-store tests.
python -m unittest discover \
  -s wikipedia_retrieval_engine/tests \
  -p "test_*.py"
```

Useful builder overrides:

```bash
python -m wikipedia_retrieval_engine.utils.wiki_table_store \
  --wiki-dir "wikipedia_retrieval_engine/Wikipedia Library" \
  --output-dir "wikipedia_retrieval_engine/retrievers/db/table_artifacts/wikipedia_tables"

python -m wikipedia_retrieval_engine.utils.wiki_table_store --force
```

The generated artifact directory is intentionally ignored by Git. The parser,
builder, tests, and manifest schema belong in version control; the 2,419 generated
article artifacts do not.

## Termination and safety rules

Every loop requires both a business limit and a LangGraph recursion backstop.

- cap retrieval attempts, table attempts, and answer repairs independently;
- preserve the original question through every rewrite;
- reject duplicate queries or evidence IDs when they do not add information;
- validate article/table identifiers before loading an artifact;
- treat retrieved text and table contents as untrusted data, not instructions;
- never allow the model to choose arbitrary filesystem paths;
- abstain with a clear termination reason when the remaining requirement cannot be
  supported within budget; and
- make any node with external side effects idempotent before adding persistence or
  replay.

`recursion_limit` is a final runtime guard, not the graph's primary stopping rule.

## Evaluation plan

The correct comparison keeps the Checkpoint 4.1 fixed pipeline as the baseline and
holds the question set, corpus, model, answer prompt, and judge rubric constant.
Checkpoint 5.1 should add graph-specific diagnostics:

- final answer quality and designated-source recall;
- requirement-level evidence sufficiency;
- route selected at each assessment;
- number of retrieval, table, reasoning, and repair calls;
- duplicate-evidence rate and whether a rewrite improved recall;
- table-operation correctness and exact source-cell provenance;
- abstention correctness after the final allowed attempt;
- latency, token use, and estimated cost;
- parser, provider, validation, and loop-limit failures; and
- run-to-run stability of routes and final answers.

The table branch also needs focused fixtures beyond end-to-end RAGAS scoring:

- nominees versus winners;
- symbols and color legends;
- superscript/subscript notes;
- multi-row headers and row/column spans;
- one-table filtering and aggregation;
- cross-table and cross-article intersection; and
- missing or ambiguous legends, where the correct behavior is a warning or
  abstention rather than a guess.

## Risks and open questions

- The evidence assessor can accept weak evidence or reject sufficient evidence; it
  needs its own labeled evaluation cases.
- A query rewrite can drift away from the original question.
- Metadata search may identify several plausible tables; ranking row content without
  bloating the manifest remains an open design choice.
- Normalization preserves presentation signals but does not prove what each signal
  means. Unresolved legends must remain explicit warnings.
- Cross-document table work requires compatible schemas and entity normalization;
  concatenating rows is not enough.
- A correct deterministic calculation can still be described incorrectly by the
  answer model, which is why calculation provenance and final verification are
  separate.
- Agentic routing adds latency and nondeterminism. It is justified only if targeted
  evaluation shows a meaningful gain over the fixed baseline.

## Implementation status

Implemented preparation:

- shared evidence, request, table, answer, verification, and state models;
- rich Wikipedia table parsing with cell annotations and legends;
- stable source/table/artifact provenance;
- compressed per-article artifact generation and atomic manifest publication;
- read-only artifact discovery and loading; and
- initial retrieval, article review, evidence collection, evidence assessment, and
  route selection;
- per-question terminal state logging;
- deterministic table-request resolution and structured `TableQueryPlan` creation;
- deterministic table-plan execution with rich cell-level provenance;
- bounded retrieval-only conditional routing through vector, graph-seeded, and
  targeted multi-step section evidence;
- a Wikipedia-GT RAGAS harness that answers only from accumulated section evidence;
  and
- focused tests for model contracts, table normalization, cache reuse, invalidation,
  artifact loading, graph nodes, logging, table resolution, and plan validation.

Still to implement and evaluate:

- conversion of executed table results into table-backed `EvidenceItem` objects;
- table-reader branch wiring after the retrieval-only benchmark;
- multi-table/multi-document joins;
- in-graph grounded answer generation and verification nodes; and
- controlled baseline-versus-agent evaluation.

Keeping these lists separate is intentional: the parser and run-once artifact layer
are ready, while the agent graph remains the next implementation checkpoint.

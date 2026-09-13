# Capstone Checkpoint 3.1 Evaluation Framework and Baseline Diagnosis

## Purpose and conclusion

This checkpoint establishes a structured evaluation framework for the Wikipedia
Retrieval Engine before further retrieval or architectural changes are introduced.
The work answers two separate questions:

1. How well does the answer model perform when it receives the intended source
   articles directly?
2. How much does end-to-end performance change when those articles must first be
   selected by the Checkpoint 2.1 retriever?

The first question is measured with an **oracle-context evaluation**. The second is
measured with repeated vector and hybrid retrieval runs under controlled settings.
The final results support the earlier manual observation that vector retrieval is the
strongest tested configuration for this corpus. They also show that retrieval is not
the only source of error because several complex questions fail even with oracle
context or full designated-source recall.

## Files in this checkpoint

- `Elena_Baron_Capstone_Checkpoint_3_1_Completed.docx` is the completed assignment
  worksheet.
- `ragas_evaluation_report_checkpoint3_1.pdf` contains the aggregated measurements,
  comparison charts, per-question heatmap, run variability, and experiment appendix.
- `capstone_checkpoint_3_1_oracle_AI_only.py` bypasses retrieval and sends the full
  designated source articles to the answer model.
- `capstone_checkpoint_3_1_with_retriever.py` runs either vector or hybrid retrieval,
  expands selected articles to full text, generates answers, and records retrieval
  diagnostics.
- `requirements.txt` pins the compatible Python, LangChain, Chroma, OpenAI, RAGAS,
  pandas, and ReportLab versions.
- `ragas_experiments/datasets/` contains the RAGAS input datasets created from the
  ground-truth CSV.
- `ragas_experiments/experiments/` contains one output CSV per run, organized by the
  scoring framework and retrieval configuration.

Shared supporting files are located outside this folder:

- `../GT/wikipedia_GT.csv` is the canonical 19-case ground-truth set.
- `../GT/capstone2.1_gt_cleanup_notes.md` records how the original Checkpoint 2.1
  workbook was audited and converted into the current evaluation set.
- `../utils/analyze_ragas_experiments.py` aggregates the experiment CSVs and builds the
  PDF report.

## Evaluation design

### Stage 1 Oracle context

Oracle mode loads the complete text of every article named in the `Source articles`
column of `wikipedia_GT.csv`. It does not call BM25, vector search, or hybrid search.
The model answers from this supplied evidence, and the RAGAS judge applies the
question-specific grading notes.

This stage is not “perfect answering.” It controls only the source-selection part of
the pipeline. A failure can still result from flattened tables, very long context,
incomplete aggregation, a generation error, or an inconsistent judge decision.

### Stage 2 End-to-end retrieval

The retriever evaluation uses the character-window Chroma index created in Checkpoint
2.1. It retrieves Top K = 7 seed chunks, collapses duplicate article selections, and
loads each selected article once from the persistent plain-text article store. The
answer model therefore receives complete extracted articles rather than overlapping
character windows.

Two retrieval settings were compared:

- vector search, Top K = 7;
- hybrid search, Top K = 7, candidate pool = 10, BM25 weight = 0.35, vector weight =
  0.65.

The test questions, grading notes, generation prompt, answer model, judge model,
temperature, index, and full-article context strategy were held constant. This makes
the retrieval method the intended independent variable.

## Ground-truth dataset

`../GT/wikipedia_GT.csv` contains 19 questions with stable IDs GT01-GT19. Each record
contains nine fields:

1. ID
2. Category
3. Question
4. Reference answer
5. Grading notes
6. Source articles
7. Scope and assumptions
8. Evaluation role
9. Complexity

The set was rebuilt from the original Checkpoint 2.1 workbook. Ambiguous questions
were clarified, a duplicate was removed, unsupported answers were replaced, and
grading rules were added. Six new questions broadened the evaluation to people
connections, geopolitical relationships, historical identities, cross-table
arithmetic, and limits on causal inference.

The resulting cases cover precise facts, quotations, open lists, process explanations,
table lookup, cross-article intersections, temporal aggregation, conflicting
estimates, Olympic program history, historical entity resolution, and multi-hop
relationships.

## Answer-quality policy

The RAGAS `DiscreteMetric` returns one of three labels. The grading notes in each CSV
row define the exact requirements for that question.

- **PASS:** all required facts are correct and all requested details are present.
- **PARTIAL:** every included claim is correct and supported, but one or more required
  elements are missing. No material false addition is allowed.
- **FAIL:** the response contains a materially wrong fact, unsupported claim, invalid
  addition, or contradiction. A response fails even when it also contains substantial
  correct information.

This policy treats a clean omission differently from misinformation. That distinction
is important for research users because an incomplete answer can be investigated, but
a confidently false addition can mislead a decision.

For the summary quality index, PASS = 1.0, PARTIAL = 0.5, and FAIL = 0.0. The index is
reported beside the raw outcome percentages because the 0.5 partial weight is a design
choice, not a universal standard.

## Retrieval and diagnostic metrics

- **Designated-source recall** is the number of labeled source articles retrieved
  divided by the number listed for that question.
- **Full designated-source coverage** is the percentage of questions for which every
  labeled source was retrieved.
- **Mean context characters** measures the volume of expanded article text sent to the
  answer model and serves as a rough context-efficiency indicator.
- **Per-question outcomes** reveal task-specific failures hidden by aggregate rates.
- **Run variability** shows whether repeated evaluations of the same configuration are
  stable.
- **Task-family quality** applies the same PASS = 1, PARTIAL = 0.5, FAIL = 0 scoring
  after consolidating the 18 specific category labels into five broader families.
- **Attention score** is `100 × (1 - task-family quality)`. A higher score identifies
  a larger observed improvement opportunity under the strongest retrieval baseline.
- **Oracle gap** is oracle task-family quality minus baseline task-family quality. A
  large positive gap is consistent with a retrieval or context-selection problem;
  low oracle quality indicates that the difficulty remains with designated sources.
- **Source-scope quality** groups cases by one, two, or three-plus designated articles
  to test whether source count explains the observed difficulty.

Designated-source recall is diagnostic rather than absolute. A different article may
contain enough equivalent evidence, and retrieving every designated source does not
guarantee that the answer model will interpret it correctly.

## Controlled experiment inventory

The final three-label comparison contains:

| Configuration | Runs | Responses | PASS | PARTIAL | FAIL | Quality | Source recall | Full coverage | Mean context |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Oracle context | 9 | 171 | 77.2% | 3.5% | 19.3% | 0.789 | n/a | n/a | 63.9k chars |
| Vector K=7 | 5 | 95 | 72.6% | 4.2% | 23.2% | 0.747 | 89.9% | 78.9% | 127.0k chars |
| Hybrid K=7, 35/65 | 5 | 95 | 68.4% | 4.2% | 27.4% | 0.705 | 88.2% | 73.7% | 184.6k chars |

These 361 responses are repeated measurements of 19 questions, not 361 independent
test cases. Eight earlier oracle CSVs used an incompatible binary PASS/FAIL framework
and are retained for history but excluded from the table and primary report.

## Findings

### Vector retrieval was the strongest tested baseline

Vector retrieval exceeded the tested hybrid configuration in answer quality,
designated-source recall, and full-source coverage. Hybrid retrieval sent about 45%
more context on average but produced a lower pass rate and a higher fail rate. In this
experiment, BM25's lexical matches did not compensate for the additional irrelevant
articles introduced during full-article expansion.

This is a scoped conclusion. It applies to this corpus, question set, Top K, hybrid
weighting, embedding model, prompt, and answer model. It does not establish that BM25
is ineffective for every corpus or query class.

### Oracle context exposed a generation ceiling

Oracle quality reached 0.789 rather than 1.0. Supplying the designated articles
removed retrieval misses but did not solve every task. GT03, an exhaustive
intersection across three Academy Awards ceremonies, failed in every included run.
GT10, which distinguishes a sport's first Winter Olympic appearance from a later
return, also failed in every included run.

These failures point to table interpretation, exhaustive enumeration, and semantic
reasoning problems rather than simple article selection.

### Full source recall did not guarantee a correct answer

GT10 is the clearest example. Vector search retrieved the designated Winter Olympic
Games article, but the response added Skeleton - 2002 even though Skeleton first
appeared before 1950 and 2002 represented a return. The answer therefore failed under
the rule that any material false addition causes a FAIL.

GT07 provides the complementary example. In one oracle run, the model correctly named
Daniel Day-Lewis with two wins but omitted tied leader Sean Penn. Because every stated
claim was correct, the judge assigned PARTIAL rather than FAIL.

### More context was not automatically better

The hybrid configuration averaged 184.6k context characters, compared with 127.0k for
vector retrieval. Full-article expansion can improve coverage when article selection
is precise, but every irrelevant selected article adds a large amount of text. The
hybrid results show that greater context volume can make the decisive evidence harder
to use.

### Task type was more informative than source count

The strongest separation appeared after grouping the 19 cases into five broader task
families. Under vector retrieval:

| Task family | Questions | Quality | Attention | Failure rate | Oracle quality | Article recall |
|---|---:|---:|---:|---:|---:|---:|
| Exhaustive list or time filter | 5 | 0.340 | 66.0 | 64.0% | 0.322 | 86.7% |
| Evidence selection or explanation | 3 | 0.767 | 23.3 | 20.0% | 0.815 | 100.0% |
| Entity relationship or historical synthesis | 6 | 0.867 | 13.3 | 10.0% | 1.000 | 87.5% |
| Cross-table quantitative reasoning | 2 | 1.000 | 0.0 | 0.0% | 0.972 | 75.0% |
| Direct fact or table lookup | 3 | 1.000 | 0.0 | 0.0% | 1.000 | 100.0% |

The exhaustive-list family is the clearest improvement priority. Its oracle quality
was no better than its vector quality, so failures in GT03, GT10, and GT11 primarily
reflect exhaustive enumeration, table interpretation, taxonomy control, and
debut-versus-return reasoning. Better retrieval may help individual cases, but it is
not the principal solution for this family.

Source count alone did not predict difficulty. Under vector retrieval, the quality
scores were 0.727 for one-article questions, 0.840 for two-article questions, and
0.667 for questions requiring three or more articles. The one-article group contains
several difficult exhaustive table tasks, while many relationship questions using
two articles performed well. The required reasoning operation is therefore more
informative than simply counting sources.

These groups remain small, and repeated runs are not independent questions. The
attention ranking is a development diagnostic, not a population-wide performance
estimate or a statistical significance result.

## Framework validation

Both evaluation scripts contain an optional `validate_framework()` smoke test. It
compares a normal GT01 answer with a deliberately manipulated response claiming that
the men's 100 metres world record was 10.20 seconds, held by Carl Lewis, and set in
Paris in 1995. The judge classified the complete supported answer as PASS and the
manipulated answer as FAIL.

The final rubric was also checked against real degraded outputs:

- the GT07 response naming only Daniel Day-Lewis was classified PARTIAL because it was
  correct but incomplete;
- the GT10 response that added Skeleton - 2002 was classified FAIL because it included
  a material error alongside correct items.

The validation supports the intended distinction among complete, incomplete, and
misleading answers. It does not prove that an LLM judge is perfectly reliable.

## Reliability and blind spots

- The answer model and judge both use `openai/gpt-5.4-mini`, which can create shared
  blind spots or preference for similar reasoning patterns.
- The judge sees the response and detailed grading notes rather than independently
  rereading every source article. The grading notes must therefore be complete.
- PASS/PARTIAL/FAIL combines several dimensions into one label and does not preserve a
  reason for each decision.
- LLM output and judgment are nondeterministic at temperature 0.2. Repeated runs on
  GT07, GT08, and other complex questions produced different labels.
- Designated-source recall does not measure precision and may undervalue alternative
  articles that contain equivalent evidence.
- The 19 cases were refined while the system and rubric were being developed. They are
  a development benchmark, not a held-out final test.
- The framework does not yet directly measure latency, API cost, context tokens,
  citation fidelity, retrieval precision, or prompt-injection resistance.

An early `.html` versus `.html.txt` filename mismatch also produced incorrect recall
measurements. The analysis utility now normalizes known final suffixes and recomputes
recall. This was a useful reminder that evaluation code must itself be tested.

## Reproduce the evaluation

From the `rag_and_context_engineering` repository root:

```bash
source .venv/bin/activate
```

Install or confirm the checkpoint dependencies:

```bash
pip install -r "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/requirements.txt"
```

Run the oracle-context evaluation:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/capstone_checkpoint_3_1_oracle_AI_only.py"
```

Run the active end-to-end retriever configuration:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/capstone_checkpoint_3_1_with_retriever.py"
```

The active `BASELINE_RETRIEVER_SPEC` in the second script selects vector or hybrid
retrieval. Record that setting before a run so the output metadata and folder remain
easy to interpret.

## Build the comparison report

The reusable analyzer is located at `../utils/analyze_ragas_experiments.py`. It reads
saved CSVs and makes no API or LLM calls.

Use the default experiment directory and external output folder:

```bash
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments.py
```

Create or refresh the report stored with this checkpoint:

```bash
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments.py \
  --experiments-dir "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/ragas_experiments/experiments" \
  --output "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/ragas_evaluation_report_checkpoint3_1.pdf" \
  --title "Capstone Checkpoint 3.1 RAGAS evaluation results"
```

The analyzer recursively finds CSVs, removes byte-identical duplicates, excludes the
legacy binary oracle folder by default, groups compatible runs by configuration,
recomputes article recall, calculates task-family and source-scope metrics, and reports
warnings and exclusions in the appendix.

## Next steps

1. Freeze GT01-GT19 as the development set and create a new held-out evaluation set.
2. Use a different judge model and manually double-score a sample to estimate judge
   agreement.
3. Record judge rationales and split correctness, completeness, source support,
   quotation fidelity, and instruction compliance into separate metrics.
4. Add retrieval precision, context tokens, latency, and API cost.
5. Add paraphrased questions, no-answer cases, conflicting context, misleading
   evidence, and prompt-injection tests.
6. Use vector retrieval as the primary baseline while testing whether query routing
   can apply BM25 selectively to exact-name and exact-year questions.
7. Preserve table and list structure and use deterministic Python for joins, counts,
   rankings, date filters, and correlations after retrieval.

## AI assistance disclosure

I used ChatGPT to help audit and restructure the ground-truth questions, organize the
evaluation code, develop the PASS/PARTIAL/FAIL rubric, diagnose measurement problems,
and create the experiment-analysis report.

I also used ChatGPT to help organize my observations and refine the written analysis.
I reviewed the questions, grading rules, experiment outputs, code, and conclusions and
made the final decisions about what to include.

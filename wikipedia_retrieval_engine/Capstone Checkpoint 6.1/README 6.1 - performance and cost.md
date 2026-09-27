# Introduction and preparation

This README records the performance and cost part of the Checkpoint 6.1 audit
(worksheet Step 3: latency, number of model calls, token usage or cost, and workflow
complexity). The security part is recorded in
[README 6.1 - security assessment](README%206.1%20-%20security%20assessment.md). Steps are
recorded as they happen.

## System under test

The 5.1 survivor, unchanged and with conversation history off, as described in the
security README. Every chat-model role uses `openai/gpt-5.4-mini`:

| Role | Calls per question |
| --- | --- |
| Decomposer (one sub-query per named entity) | 1 |
| TOC reviewer (keeps articles, selects sections and tables) | 1 |
| Assessor | 1 per round; a non-table question takes at least 2 rounds (breadth nudge) |
| Table planner | 1 per flagged table request |
| Answer | 1 |

- The RAGAS judge (`openai/gpt-5.4-mini`, one call per question) is evaluation
  overhead.
- Each vector search embeds its query with `openai/text-embedding-3-small`.
- For comparison, the 4.1 graph retriever makes one chat call per question: the answer,
  over whole articles.

## Measured cost instead of counted tokens

The Module 6 labs count tokens and multiply them by an approximate price table, because
course-issued API keys cannot read account billing. This project has run on a personal
OpenRouter account since the middle of Checkpoint 4.1, with a management key. Billed cost is therefore
available from OpenRouter analytics (per hour and model), and prices can be verified.

**Prices** (OpenRouter model list, retrieved 2026-09-27; USD per 1M tokens):

| Model | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| `openai/gpt-5.4-mini` | 0.75 | 0.075 | 4.50 |

- These prices reproduce the billed amounts of both analytics windows below to the cent.
- Embeddings are negligible: 1,307 embedding requests in the 5.1 window were billed
  $0.0002.
- The Lab 6.2 approximate rates still in `pricing/model_prices.json` (0.20 input, 0.80
  output) understate input by 3.75× and output by 5.6×.

**Attribution limits:**

- The app tags added in Checkpoint 5.1 ("WRE retriever", "WRE judge", "WRE embedding")
  do not reach analytics: every request is reported under app "Unknown". The referer
  does appear (dimension `origin`), but it is the same for every role, so judge cost
  cannot be separated from system cost in analytics.
- Hourly buckets are in UTC. Runs are placed in them by their log timestamps (local
  time is UTC−4).
- `utils/openrouter_usage.py` expects a `date__day` key, so hourly rows (`date__hour`)
  and `origin` rows (`created_at__day`) print without their dates.

## Existing runs re-read at zero cost

Before any new run, the saved 5.1 and earlier results were re-read. Three findings
shaped the experiments.

### Finding 1: real cost per question, 5.1 survivor against 4.1 graph

Two analytics windows contain the same workload, two GT runs and four validation runs
(138 question-runs each):

- **4.1 graph** (`vs_k7_md_graph_n5retriever`): 2026-09-15, 23:00–23:59 UTC.
- **5.1 survivor** (`agentic_search_compute_broaden` and `agentic_retrieval_5.1_broaden`):
  2026-09-23, 15:00–16:59 UTC.

Neither window contains other traffic. Billed chat requests match the requests implied
by the result CSVs:

- 4.1: 276 billed = one answer and one judge call per question;
- 5.1: 1,049 billed against 1,044 derived from the route traces (decomposer, TOC
  reviewer, one assessor call per round, planner calls, answer, judge), so only five
  retries occurred.

| Per question-run (judge included) | 4.1 graph | 5.1 survivor | 5.1 ÷ 4.1 |
| --- | ---: | ---: | ---: |
| Chat requests | 2.0 | 7.6 | 3.8× |
| Embedding requests | 1.0 | 9.5 | 9.5× |
| Prompt tokens | 74.5K | 46.7K | 0.63× |
| Cached share of prompt tokens | 70.5% | 32.3% | |
| Completion tokens | 281 | 1,447 | 5.1× |
| Billed cost | $0.0217 | $0.0313 | 1.45× |
| Cost at list price, no caching | $0.0571 | $0.0415 | 0.73× |
| End-to-end time per question | about 10 s | 21 s (median) | about 2× |

- **More calls, fewer tokens, higher bill.** The survivor reads 37% fewer prompt tokens
  per question and costs 45% more.
- **Caching reverses the ranking.** At list price the survivor would be 27% cheaper.
  - The 4.1 graph re-sends the same whole articles. In back-to-back repeat runs of the
    same questions, 70.5% of its input was billed at the cached rate, one tenth of the
    input price. A workload of distinct questions would cache less.
  - The survivor's prompts change on every round; 32.3% of its input was cached.
- **Output is a fifth of the survivor's bill** (21%, against 6% for 4.1). The agent
  roles return structured JSON: article reviews, assessments, and table plans.
- **The answer context understates the survivor's token use.**
  - The 4.1 window implies about 3.3 characters per token for this corpus (about 73K
    prompt tokens for a mean context of 244K characters).
  - At that rate, the survivor's mean answer context (about 49K characters) is about
    15K tokens: roughly a third of its 46.7K prompt tokens per question.
  - The agent loop before the answer consumes the other two thirds.
- **Latency.**
  - Survivor: 21 s per question end to end (median of the gaps between consecutive
    question logs; p90 36 s, maximum 56 s). Each gap includes the previous question's
    answer and judge calls.
  - 4.1 graph: consecutive runs of 19 or 25 questions finished 3–5 minutes apart, about
    10–12 s per question.

### Finding 2: quality by question type, sections against whole articles

The survivor's TOC review flags whether answering needs a table. Splitting the
validation questions by that flag separates two groups (a question counts as a table
question when at least two of the four runs flagged a table):

| Validation group | 5.1 survivor, sections (4 runs) | Oracle, whole designated articles (4 runs) | 4.1 graph, whole articles (4 runs) | 3.1 vector k=7, whole articles (3 runs) |
| --- | ---: | ---: | ---: | ---: |
| Non-table (11 questions) | 0.955 | 1.000 | 1.000 | 1.000 |
| Table (14 questions) | 0.821 | 0.786 | 0.795 | 0.833 |
| Mean answer context, non-table | 39.6K | 69.6K | 200.5K | 113.6K |

- **Non-table questions:** every whole-article configuration scored 1.000. The survivor
  lost points on two:
  - VAL09 (0.62), the connection between Bill Clinton and Barack Obama;
  - VAL11 (0.88), the Broad Street pump and John Snow.
- **Table questions:** whole articles did not help overall. The survivor's table path is
  ahead on VAL07 and VAL14, and behind on VAL10 (against all three) and VAL05 (against
  two; the planner's temporal aggregation, Cause A in README 5.1).
- **GT:** five questions are non-table (GT02, GT06, GT16, GT17, GT18).
  - The oracle scored 1.000 on all five; the survivor 0.933, losing on GT16 (0.67), the
    same Clinton–Obama family.
  - The 4.1 retrievers scored lower on GT16. The 4.1 base retriever missed the Barack
    Obama article (recall 0.5). The 4.1 graph had both whole articles (recall 1.0)
    inside 284K characters of context and scored 0.50: fail, pass, and partial on an
    identical context.
  - Whole articles helped when they were the designated articles without much else
    around them (the oracle), not whenever the context was large.

### Finding 3: the answer step can be replayed from the logs

The 5.1 AgentState logs store each question's terminal state, including every evidence
item. Rebuilding the answer context from the logs in the 5.1 evidence format
(`format_section_evidence`) reproduced `context_characters` exactly for all 157
question-runs of the seven survivor runs:

| Set | Results CSV → log folder (`Capstone Checkpoint 5.1/logs/`) |
| --- | --- |
| Validation | `distracted_dorsey` → `2026_09_23_11_28_19`; `cranky_stallman` → `2026_09_23_11_44_15`; `eager_rossum` → `2026_09_23_11_55_11`; `objective_hopper` → `2026_09_23_12_05_45` |
| GT | `zealous_liskov` → `2026_09_23_10_29_40`; `happy_hopper` → `2026_09_23_11_03_04`; `stoic_postel` → `2026_09_23_11_13_11` |

A change that affects only what the answer model reads (the context, or the answer model
itself) can therefore be tested on the saved evidence without re-running the agent:

- the agent's selections stay fixed, so a quality difference is attributable to the
  change alone;
- only answer and judge calls are paid.

## Preparation status

- `cost_test_starter.py` records per-call tokens and latency for live runs. Its
  `QuestionUsage.on_llm_end()` step is still to be implemented; the self-check is in
  place.
- `pricing/model_prices.json` still holds the Lab 6.2 approximate rates.

# Experiment 1: whole articles for non-table questions

**Status:** hypothesis and zero-cost evidence recorded; design in progress.

**Hypothesis.** Restricting evidence to sections (5.1) costs quality on text-rich
questions, because the selected sections do not carry all the information the question
needs. Tables are the exception: there, selected sections plus the table path work
better than whole articles.

**Variant.** The 5.1 survivor, unchanged, except for what the answer model receives:

- a table is needed: sections and table evidence, as in 5.1;
- no table is needed: the whole articles.

**Question.** Does quality improve, and what does it cost?

**Support in the existing runs** (Finding 2).

- The rule matches the split in the data: whole articles beat sections only on
  non-table questions, and only on three of them (VAL09, VAL11, GT16).
- The ceiling on validation is small. Moving the non-table group from 0.955 to 1.000
  raises validation quality from 0.880 to about 0.90.

**Expected size of the answer context.** Computed from the logs as the whole markdown
text of the articles kept by the TOC review, for question-runs without a table flag:

| Set | Non-table question-runs | Answer context, non-table (sections → whole articles) | Answer context, all question-runs |
| --- | ---: | --- | --- |
| Validation | 49 of 100 | 37.4K → 99.3K characters (2.7×) | 48.3K → 78.6K (1.6×) |
| GT | 15 of 57 | 35.9K → 143.4K (4.0×) | 52.2K → 80.5K (1.5×) |

- The largest context is 247K characters (Bill Clinton and Barack Obama, VAL09 and
  GT16), about 75K tokens; `gpt-5.4-mini` accepts 400K.
- The answer call is about a third of the survivor's prompt tokens (Finding 1). A 1.6×
  larger answer context therefore adds roughly 20% to the prompt tokens per question,
  before caching.

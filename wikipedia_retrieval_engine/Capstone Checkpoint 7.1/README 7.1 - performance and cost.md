# Introduction and preparation

This README records the performance and cost part of Checkpoint 7.1 (worksheet Step 3:
performance and efficiency improvements, with their evidence in Step 4 and trade-offs in
Step 5). The security part is recorded in
[`security_comparison_5_1_vs_7_1.md`](security_comparison_5_1_vs_7_1.md). Steps are
recorded as they happen.

**Status:** existing runs re-read and the Jev decision model reviewed (2026-10-04). No
optimization is built yet.

## System under test

The 7.1 final survivor ([`survivor_agent_final.py`](survivor_agent_final.py)): the 6.1
survivor (whole articles for text questions, the table planner's repair and retry,
INCOMPLETE labels, the evidence notice) plus the 7.1 security safeguards (input
sanitizer, guarded answer prompt, grounding check). Every chat-model role uses
`openai/gpt-5.4-mini`.

| Configuration (validation, 25 questions) | Quality | List $/q | Billed $/q | Seconds/q | Calls/q |
| --- | ---: | ---: | ---: | ---: | ---: |
| 6.1 survivor, `gpt-5.4-mini` (3 runs) | 0.860 | 0.0422 | 0.0296 | 12.8 | 5.79 |
| 7.1 final, `gpt-5.4-mini` (1 run, `awesome_valiant`) | 0.900 | 0.0456 | 0.0377 | 11.0 | 6.04 |
| 6.1 survivor, `gpt-5.4` (1 run, `nifty_andreessen`) | 0.960 | 0.1524 | 0.1292 | 21.6 | 6.20 |

**Comparability of these figures** (checked 2026-10-04, before any new run):

- **History is off in every row.** All five runs come from the cost harness
  (`cost_test_starter.py`, through `cost_test_final.py` for 7.1), which runs each question
  as a fresh single turn. The saved AgentState logs confirm it: none of the 100 states of
  these runs carries history, against 75 of the 99 turns of the 5.1 security baseline
  (`2026_10_03_17_38_35`). No figure from the security runs, which keep history on, is
  used in this README.
- **The safeguards add no model calls.** The input filter and the grounding check are
  deterministic, and the sanitizer left all 25 validation questions unchanged. The
  guarded prompt adds about 330 tokens to each answer call.
- **List cost varies by 45% between runs of the same system:** $0.0358, $0.0388, and
  $0.0521 for the three 6.1 runs (40.8K–61.5K input tokens per question), from the agent
  loop alone. The 7.1 run's $0.0456 falls inside that range. A single run cannot show a
  difference smaller than this spread.
- **Billed cost depends on run order.** The 6.1 runs ran back to back on the same
  questions (16%, 44%, and 49% of input cached); the 7.1 run ran cold (22%). The cold pair
  is `dazzling_minsky` ($0.0314 billed) and `awesome_valiant` ($0.0377). List price is
  the comparison of record, as in 6.1.
- **Latency depends on the provider's speed at the time.** The 7.1 run (2026-10-04,
  00:03–00:08) was faster per call in every role, including the two that 7.1 does not
  change: decomposer median 0.92 s against 1.12–1.32 s, TOC reviewer 1.52 s against
  1.67–2.22 s. Its 11.0 s against 12.8 s per question is therefore not a 7.1 effect.
- **The 7.1 run shared the account with the nominee security repeats,** four runs with
  history on, started in the same minute. Its caching shows no trace of them: TOC
  reviewer 0% and answer 10% cached, as in the cold 6.1 run.
- **Time accounting moved.** 7.1 runs the answer inside the graph, so its
  `answer_wall_s` is 0 and `graph_wall_s` includes the answer. The sum is comparable
  across runs; the split between graph and answer is not.
- **The `gpt-5.4` row is the 6.1 survivor,** without the 7.1 safeguards.

**Measurement rules adopted for the 7.1 experiments:** the before and after
configurations run in the same session, one after the other, with nothing else running
on the account; quality and cost are compared question by question; latency is compared
per call and role as well as per question.

## Question sets: validation only

- Every figure with per-call telemetry is on the validation set (25 questions). No
  configuration has a telemetry run on the GT test set, and 6.1 and 7.1 have no GT run
  at all.
- GT cost evidence is indirect:
  - the 6.1 billing windows (4.1 against 5.1) each mix two GT and four validation runs
    in the same hours, so GT cannot be separated;
  - the 6.1 answer replay re-answered 23 GT question-runs (8 questions, 69 answer calls):
    the answer step only, on 5.1 evidence;
  - the 5.1 GT results record the answer context size and the route, not tokens or time.
- **GT is the harder and more table-heavy set.** In the 5.1 runs, 74% of GT
  question-runs took the table path against 51% on validation, with more table attempts
  (0.81 against 0.56 per question), similar answer contexts (52K against 48K characters),
  and lower quality (0.754 against 0.880).
- Routing estimates from validation (Finding 3: 44–47% of questions sent to `gpt-5.4`)
  therefore likely overstate the saving on a GT-like workload, where about three
  quarters of the questions would take the expensive path.

## Starting decision: accuracy first

Checkpoint 6.1 already priced accuracy: `gpt-5.4` in every role reached 0.960, the
highest validation quality in the project, at 3.6× the list cost of `gpt-5.4-mini`
(Experiment 3 of the 6.1 performance README). The performance work in 7.1 therefore starts
from the `gpt-5.4` quality and asks:

1. how much of it can be kept, and at what cost;
2. where the system spends money or time without buying quality.

## Existing runs re-read at zero cost

Before any new run, the saved validation runs were re-read: the three 6.1 mini runs
(`dazzling_minsky`, `nifty_mccarthy`, `angry_babbage`), the 6.1 `gpt-5.4` run
(`nifty_andreessen`), and the 7.1 run (`awesome_valiant`), each with its telemetry
(`*__llm_calls.csv`, `*__question_telemetry.csv`). Scores are encoded pass = 1, partial =
0.5, fail = 0.

### Finding 1: the assessor and the answer are 85% of the cost

Share of list cost by role:

| Role | 6.1, mini (75 question-runs) | 7.1, mini (25) | 6.1, `gpt-5.4` (25) |
| --- | ---: | ---: | ---: |
| Assessor | 45% (1.85 calls, 22.4K input tokens per question) | 49% (2.00 calls, 26.6K) | 45% |
| Answer | 41% (21.7K input tokens) | 37% | 40% |
| TOC reviewer | 8% | 7% | 6% |
| Table planner | 5% | 5% | 7% |
| Decomposer | 2% | 2% | 2% |

- The split is the same on both models. Model time follows it: the assessor takes 39–43%.
- The 7.1 run's extra 4.2K input tokens per question are all in the assessor, which no
  7.1 change touches (the sanitizer left all 25 validation questions unchanged): 5 of its
  14 text questions escalated to whole articles, against 5 of 39 in the 6.1 runs.

### Finding 2: mini is perfect on text questions and loses on table questions

Question-runs grouped by path (the run's `tables_flagged` and its number of assessor
calls):

| Path | 6.1, mini: runs · quality · list $/q | 7.1, mini | 6.1, `gpt-5.4` |
| --- | --- | --- | --- |
| Text, ready after the first assessment | 34 · 1.000 · $0.028 | 9 · 1.000 · $0.026 | 12 · 1.000 · $0.079 |
| Text, escalated to whole articles | 5 · 0.800 · $0.098 | 5 · 1.000 · $0.070 | 2 · 1.000 · $0.310 |
| Table | 36 · 0.736 · $0.048 | 11 · 0.773 · $0.051 | 11 · 0.909 · $0.204 |

- **Text questions do not need the stronger model.** Mini answered every ready text
  question correctly; `gpt-5.4` did the same at about 3× the cost. Text questions took 41%
  of the `gpt-5.4` bill.
- **Mini's losses sit on the table path.** Seven questions average below 1.0 over the
  four mini runs: VAL02, VAL05, VAL06, VAL08, VAL10, VAL14, and VAL24. Each lost its
  points in runs where it took the table path, except VAL02 (a cross-article
  intersection), which also failed on the text path. `gpt-5.4` passed six of the seven;
  VAL02 failed on both models.
- **The hard questions are the expensive ones on `gpt-5.4`.** VAL02 ($0.64, 12 planner
  calls, fail), VAL05 ($0.46), VAL10 ($0.29), and VAL24 ($0.29) are 44% of the
  `gpt-5.4` bill. The assessor is more than half of each.
- **Escalation re-reads.** An escalated text question cost 3.5× a ready one in the 6.1
  runs ($0.098 against $0.028), because the assessor reads the whole articles again.

### Finding 3: routing by question type keeps the `gpt-5.4` quality for 28% less

**Method.** Each mini question-run (4 runs × 25 questions) keeps its own outcome, cost,
and time, or, when a policy sends it to `gpt-5.4`, takes that question's outcome, cost,
and time from the `gpt-5.4` run:

| Policy | Quality | List $/q | Seconds/q | Sent to `gpt-5.4` |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.870 | 0.0431 | 12.4 | 0% |
| All `gpt-5.4` | 0.960 | 0.1524 | 21.6 | 100% |
| Route on mini's own table flag | 0.960 | 0.1094 | 17.8 | 47% |
| Route on the question's category (author labels; seven text categories) | 0.955 | 0.1165 | 18.3 | 44% |
| Route on `gpt-5.4`'s table flag | 0.935 | 0.1108 | 18.4 | 44% |
| Mini first; rerun on `gpt-5.4` when the evidence notice fires | 0.910 | 0.0821 | 17.4 | 13%, paid twice |
| Hindsight: `gpt-5.4` only where this mini run failed | 0.965 | 0.1038 | 12.4 | 13% |

**Reading.**

- **Routing table questions to `gpt-5.4` kept its quality (0.960) for 28% less** ($0.109
  against $0.152 at list price) and 3.8 s less per question.
- **A perfect router would save little more** ($0.104): the questions that need
  `gpt-5.4` are the ones it spends the most on. Further savings have to come from inside
  the expensive path, where the assessor re-reads and the planner can run up to 12 times.
- **Escalating on the evidence notice is cheapest and loses quality** (0.910). The silent
  failures raise no notice: VAL24 when one computation succeeds too early, VAL08, VAL14.
- **Limits.** The `gpt-5.4` outcomes come from a single run (6.1: Wilcoxon p = 0.08 against
  the three mini runs). A routed system is a different run, with `gpt-5.4` on only part of
  the questions, so the simulation predicts and a live run confirms.

## Candidate component reviewed: Jev

The lecture named Jev as a model "very explicitly not designed to output text", built
for decisions such as routing and checking, and charged only for input tokens. It was
reviewed as the decision-maker for a router.

**Facts** (verified 2026-10-04 on the OpenRouter model endpoint and the OpenRouter and
TypeSafe documentation):

| Item | Value |
| --- | --- |
| Model | `typesafe/jev-1.13` (TypeSafe), served as `typesafe/jev-1.13-20260917` |
| Price | $0.042 per 1M input tokens; output free; no prompt caching |
| Context | 32,000 tokens for the state and the questions |
| API | `POST /api/alpha/decisions` on OpenRouter (alpha): a `state` and typed `questions`, not chat messages |
| Question types | `noul` (probability of yes), `choice` (one option of up to 255, with a probability per option and a confidence), `score` (a position on an ordered scale) |
| Latency | 70–500 ms (vendor); median 127 ms against 688 ms for Claude Haiku in LiteLLM's 240-call routing benchmark |
| Calibration | trained so that a probability of 0.8 is right about 80% of the time (vendor claim); thresholds are meant to be set from the user's own labeled data |
| Documented weaknesses | literal reading of the criteria; arithmetic, counting, and date comparison; multi-hop indirection; irrelevant detail in the state; injected instructions can move the answer |

**What it means for this system.**

- **Its price is not the deciding factor.** A routing call of about 400 tokens costs
  about $0.00002 on Jev, $0.0001 on `gpt-5.4-nano`, and $0.0004 on mini, under 1% of a
  question in every case. What a router costs is its misroutes.
- **Latency is a factor.** Model calls run in sequence, and each mini call adds 1–2 s
  (6.1, Experiment 2); Jev adds about 0.2 s.
- **The probability per option is the main factor.** With a calibrated distribution, the
  routing rule becomes a threshold chosen from the cost of each mistake: a table
  question sent to mini can lose the whole question; a text question sent to `gpt-5.4`
  costs about $0.05 and no quality (Finding 2).
- **Its weaknesses match the heavy roles, not routing.** Recognizing that a question asks
  for a count or a comparison is a reading of the question; computing it is the table
  executor's job. The assessor is not a candidate: its prompts reach 64K tokens (10% exceed
  the 32K window), and they are long, multi-hop, and full of detail irrelevant to any one
  decision.
- **Integration.** Jev is not a LangChain chat model, so the telemetry callbacks do not
  see it; its cost comes from the `usage.cost` field of each response.

# Baseline on the GT test set: 6.1 survivor and 7.1 final

**Status:** complete (2026-10-04, 01:37–02:06). Six runs, no errors, no whole-graph
retries; $3.90 billed, judge included.

**Why.** No configuration has a cost and latency measurement on the GT test set
("Question sets" above), and GT is the more table-heavy set, so a routing saving measured
on validation alone would likely overstate it. Before any optimization, both systems get
a GT baseline:

- the **6.1 survivor**, the last checkpoint's survivor;
- the **7.1 final**, the system the optimizations build on.

Running both also checks, on a second question set, that the 7.1 safeguards add no
measurable cost.

**Design.**

- 3 runs per system, 19 GT questions each, history off, `openai/gpt-5.4-mini` in every
  role, judge `gpt-5.4-mini`; the 7.1 final with its default grounding policy
  (`surface`).
- **Interleaved order:** 6.1, final, 6.1, final, 6.1, final, one run at a time with
  nothing else on the account. Provider speed and cache warm-up then fall on both systems
  alike (the measurement rules above).
- **Caching:** both systems send the same decomposer, TOC reviewer, assessor, and planner
  prompts to the same model, so a run can hit the cache left by the previous run of
  either system. Billed cost should fall along the sequence; list price stays the
  comparison.
- **Layout** (`cost_efficiency/`, kept apart from the validation runs in `cost_tests/`):
  - `wikipedia_GT/`: the harness output (`datasets/`, `experiments/`, `telemetry/`);
  - `logs/<stamp>/`: the AgentState logs. The harness writes them under each
    checkpoint's own `logs/cost_tests/`, with no option to change that, so each run's
    folder is moved here when the run ends;
  - `console/`: each run's console output;
  - `run_manifest.csv`: run order, system, results CSV, and log folder. The 6.1 runs
    recorded no link between a results CSV and its log folder (it had to be recovered by
    matching question text).

**Commands** (from `rag_and_context_engineering/`, run in the order above):

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 6.1/cost_test_starter.py" --survivor 6.1 --gt-set "wikipedia_retrieval_engine/GT/wikipedia_GT.csv" --output-dir "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_efficiency/wikipedia_GT"
python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_test_final.py" --gt-set "wikipedia_retrieval_engine/GT/wikipedia_GT.csv" --output-dir "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_efficiency/wikipedia_GT"
```

**Predictions** (recorded before the results; computed from the validation figures by
path and the 5.1 GT runs):

- **Quality: 0.70–0.80 for both systems, likely at or below 5.1's 0.754.**
  - In 5.1, GT table question-runs scored 0.69 against 0.80 on validation, and 74% of
    GT question-runs took the table path (validation: 51%).
  - On validation, the 6.1 survivor scored higher than 5.1 on the text path (0.959 →
    0.974) and lower on the table path (0.804 → 0.736). The two moves have separate
    causes. Whole articles apply only to questions without tables; a question with a
    table keeps the 5.1 sections and broadening (`retrieve_whole_article_evidence`). The
    table path changed only through the reliability fixes (plan repair and retry,
    INCOMPLETE labels, the evidence notice), which changed two validation questions:
    VAL24 (a computation that now succeeds ends the loop before the prose facts arrive)
    and VAL06 (an answer that states its gap is graded partial).
  - GT has three table question-runs for every text one, so if those two mechanisms
    recur on GT, they outweigh the text gain there.
- **Cost: about $0.045 per question at list price** (74% at the validation table path's
  $0.048, 26% at the text path's $0.037), about $0.86 per run and $5.20 for the six; the
  balance before the runs was $14.24.
- **Time: about 14 s per question** (15.3 s table path, 10.5 s text path, on validation).
- **7.1 against 6.1:** no difference beyond the run-to-run spread, in quality, cost, or
  time.

## Results (2026-10-04)

**The runs** (`cost_efficiency/run_manifest.csv`; results in
`cost_efficiency/wikipedia_GT/experiments/`):

| Order | System | Results CSV | Quality | List $/q | Billed $/q | Cached | Seconds/q | Calls/q |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6.1 | `eager_torvalds` | 0.737 | 0.0402 | 0.0368 | 11% | 11.3 | 6.53 |
| 2 | 7.1 final | `admiring_diffie` | 0.658 | 0.0507 | 0.0432 | 19% | 11.8 | 6.89 |
| 3 | 6.1 | `hardcore_page` | 0.816 | 0.0570 | 0.0372 | 43% | 13.3 | 7.16 |
| 4 | 7.1 final | `eloquent_hoare` | 0.711 | 0.0459 | 0.0286 | 48% | 14.0 | 6.95 |
| 5 | 6.1 | `confident_stallman` | 0.816 | 0.0485 | 0.0310 | 45% | 14.7 | 6.63 |
| 6 | 7.1 final | `confident_zuckerberg` | 0.763 | 0.0539 | 0.0325 | 49% | 15.6 | 6.68 |

Article recall was 1.000 in every run.

**Per system** (3 runs × 19 questions each):

| System | Quality | List $/q | Billed $/q | Seconds/q (mean / median) | Calls/q | Input tokens/q |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| 5.1 survivor (3 runs, 2026-09-23, no telemetry) | 0.754 | | | | | |
| 6.1 survivor | **0.789** | 0.0485 | 0.0350 | 13.1 / 11.8 | 6.77 | 56.8K |
| 7.1 final | **0.711** | 0.0502 | 0.0348 | 13.8 / 12.6 | 6.84 | 59.3K |

**By path** (`tables_flagged` and assessor calls, as in Finding 2):

| Path | 6.1: runs · quality · list $/q · s/q | 7.1 final |
| --- | --- | --- |
| Text, ready after the first assessment | 13 · 0.962 · $0.038 · 8.9 s | 15 · 0.833 · $0.038 · 9.3 s |
| Text, escalated | 1 · 1.000 · $0.020 · 8.2 s | none |
| Table | 43 · 0.733 · $0.052 · 14.5 s | 42 · 0.667 · $0.055 · 15.4 s |

**Cost and time: no difference between the systems.**

- List cost $0.0485 against $0.0502 per question, inside 6.1's own run-to-run range
  ($0.0402–0.0570). Calls (6.77 against 6.84) and input tokens (56.8K against 59.3K)
  are level.
- Time rose along the sequence, whichever system ran (11.3 s in the first run, 15.6 s in
  the last); 7.1 always ran one slot after 6.1, so its 0.7 s more is the drift.
- Caching rose from 11% to about 48% after the first two runs, so billed cost fell
  along the sequence (as designed for: list price is the comparison).
- **A GT question costs more than a validation question:** 6.1 $0.0485 against $0.0422
  at list price. GT has more table question-runs (75% against 48%), and its text
  questions read larger whole articles (GT16: 248K characters).

**Quality: 6.1 is above 5.1 on GT; 7.1 final is below both.**

- **6.1: 0.789** (0.737, 0.816, 0.816), against 0.754 for the three recorded 5.1 GT
  runs (judged on 2026-09-23). Its table path scored 0.733, against 0.69 for 5.1 on the
  same set: on GT, the 6.1 reliability fixes did not lower the table path.
- **7.1 final: 0.711** (0.658, 0.711, 0.763). Each 7.1 run scored below the 6.1 run
  before it. Per question: 6 lower, 2 higher (GT09, GT11), 11 unchanged; −0.078 on
  average; Wilcoxon p = 0.19, so not significant at this size. On validation, the single
  7.1 run had scored 0.900.
- **Where 7.1 lost points, the retrieval was the same.** Recall was 1.000 everywhere, and
  three of the six questions show the same answer context in both systems:

  | Question | Context | 6.1 answers | 7.1 answers |
  | --- | --- | --- | --- |
  | GT16 (who connects Bill Clinton and Barack Obama) | 247,788 characters, identical in all six runs | Hillary Clinton in 3 of 3 (two passes, one partial) | **Joe Biden in 2 of 3** (fail, fail); the third partial |
  | GT05 (most total medals, 1972 Winter Olympics) | 4,664 characters in five of the six runs | the Soviet Union, 8-5-3 | two of three open with the "Totals (11 entries)" row, and one reports that row as the answer (fail) |
  | GT15 (Chris Columbus and Daniel Radcliffe) | 35K–79K characters in both systems | three passes | two partials; one opens "The retrieved articles do not support a full connection" |

- **The common thread is the answer step.** The guarded answer prompt asks the model to
  "say plainly that the retrieved articles do not contain" a missing fact and, when "the
  context block reports a failed or incomplete table computation", to say so. GT05 and
  GT15 read like those rules applied too literally; GT16's Joe Biden is the competing
  answer first seen in the 6.1 answer replay (a large whole-article context). This is a
  hypothesis: the runs change the prompt and the grounding check together, and the
  judge's own variation is about 7% of verdicts on identical input (6.1).
- **The grounding check flagged 10 of 57 answers, and 8 of them passed the judge.** The
  flagged spans are extraction artifacts, not invented facts: "Russia-related Olympic"
  (the hyphen-suffix pattern already seen on validation), "Winter Olympic Games Sport"
  and "Summer Olympic Games Sport" (heading words captured into a name), "To Bill
  Clinton; To Barack Obama" (the answer's own bold list labels), "Russian Empire". The
  two GT16 answers naming Joe Biden passed the check: Joe Biden is in the evidence, and
  the check verifies names, not relationships (its limit recorded in 6.1). With policy
  `surface`, a correct answer carried the "[QUARANTINED]" label in 8 of 57 question-runs.

**Predictions against results:**

| Prediction | Result |
| --- | --- |
| Quality 0.70–0.80 for both, likely at or below 5.1's 0.754 | Range held for both. 6.1 above 5.1 (0.789); 7.1 below (0.711) |
| About $0.045 per question at list price | $0.0485 (6.1) and $0.0502 (7.1) |
| About 14 s per question | 13.1 s and 13.8 s |
| 7.1 against 6.1: no difference beyond the run-to-run spread | Held for cost, calls, tokens, and time. Quality −0.078, consistent in all three pairs, not significant (p = 0.19) |

# Checkpoint 7.1 performance and efficiency approach

This README is the technical record for Checkpoint 7.1 Steps 3–5: the performance
question, the experiments used to answer it, the final architecture decision, and the
measured trade-offs. The companion
[`README 7.1 - security improvements.md`](README%207.1%20-%20security%20improvements.md)
documents the safeguards, and
[`security_comparison_5_1_vs_7_1.md`](security_comparison_5_1_vs_7_1.md) contains their
attack-by-attack results.

**Status:** complete. Router B was selected as the **7.1 Final Survivor**.

## Final decision

The strongest model in every role produced the highest mean quality on the GT working
set, but at high and variable cost. The all-mini system was much cheaper but left a
measurable quality gap. Router B uses `gpt-5.4` only for the two roles that benefited
most—the evidence assessor and final answer—and keeps the decomposer, TOC reviewer, and
table planner on `gpt-5.4-mini`. Keeping the planner on mini also reduced, but did not
eliminate, the risk of extremely large repeated prompts.

Across three GT runs, Router B scored 0.868 at $0.1725 list cost per question and 21.3
seconds per question. All-`gpt-5.4` scored 0.886 at $0.3457 per question and 24.7 seconds.
The observed quality
difference was −0.018 (paired Wilcoxon p = 0.81), so these runs did not detect a quality
difference; they do not prove statistical equivalence. Router B reduced list cost by 50%
(p = 0.001). Repeated runs were necessary because a single 19-question run varied too
much to support a reliable decision.

On the held-out validation set, the 7.1 Final Survivor scored 0.933, with 99.3% article
recall, at $0.1068 list cost and 18.7 seconds per question. The 6.1 survivor scored 0.860,
with 100% recall, at $0.0422 and 12.8 seconds. The final system therefore improved the
observed validation quality while accepting higher cost and latency than the all-mini
survivor.

## Starting system: 7.1 safeguarded baseline

The starting system ([`survivor_agent_final.py`](survivor_agent_final.py)) is the 6.1
survivor—whole articles for text questions, table-plan repair and retry, `INCOMPLETE`
labels, and the evidence notice—plus the 7.1 input sanitizer, guarded answer prompt, and
grounding check. At this stage, every chat-model role used `openai/gpt-5.4-mini`.

Some saved experiment labels call this configuration `7.1 final`; in this README it is
called the **7.1 safeguarded baseline** so it is not confused with the selected Router B
Final Survivor.

| Configuration (validation, 25 questions) | Quality | List $/q | Billed $/q | Seconds/q | Calls/q |
| --- | ---: | ---: | ---: | ---: | ---: |
| 6.1 survivor, `gpt-5.4-mini` (3 runs) | 0.860 | 0.0422 | 0.0296 | 12.8 | 5.79 |
| 7.1 safeguarded baseline, `gpt-5.4-mini` (1 run, `awesome_valiant`) | 0.900 | 0.0456 | 0.0377 | 11.0 | 6.04 |
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

## Question sets

- Until the GT baseline below, every figure with per-call telemetry was on the
  validation set (25 questions). No configuration had a telemetry run on the GT test set,
  and 6.1 and 7.1 had no GT run at all.
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
- **Decision (2026-10-04): GT is the working set for the 7.1 experiments,** with repeated
  runs under `cost_efficiency/wikipedia_GT/`. Validation runs once, at the end, as the
  held-out check, into its own folder (`cost_efficiency/wikipedia_GT_validation_set/`).
  The analyzer reports each set separately, so the two are never pooled.

## Tools for the experiments

| File | Role |
| --- | --- |
| [`../utils/analyze_ragas_experiments_efficiency.py`](../utils/analyze_ragas_experiments_efficiency.py) | Accuracy against cost and latency, per question set: frontier, paired comparison against a baseline, cost by role, paths, tail and waste, comparability warnings, safeguard markers, routing simulation. PDF plus one CSV per table |
| [`../tests/test_analyze_efficiency.py`](../tests/test_analyze_efficiency.py) | Logic tests, plus checks that the analyzer reproduces this README's GT baseline and Finding 3 figures |
| `cost_efficiency/run_manifest.csv` | Run order, system, results CSV, and log folder for each performance run |

- **Why a separate analyzer.** `analyze_ragas_experiments.py` tracks accuracy across
  checkpoints and shows cost only as configuration averages. It groups runs by
  experiment name alone, so the GT and validation runs of `survivor_6_1` would have been
  pooled. The new analyzer imports the original's loader and PDF styling, leaves it
  unchanged, and separates the sets.
- **What it changed in this README.** It reproduced every Finding 3 policy computed by
  hand, and corrected one: the hindsight row (see Finding 3). It also reproduced the GT
  baseline figures (p = 0.188 for the quality change, which the hand calculation gave as
  0.19).

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

### Finding 2: mini was perfect on ready text questions in the saved validation runs

Question-runs grouped by path (the run's `tables_flagged` and its number of assessor
calls):

| Path | 6.1, mini: runs · quality · list $/q | 7.1, mini | 6.1, `gpt-5.4` |
| --- | --- | --- | --- |
| Text, ready after the first assessment | 34 · 1.000 · $0.028 | 9 · 1.000 · $0.026 | 12 · 1.000 · $0.079 |
| Text, escalated to whole articles | 5 · 0.800 · $0.098 | 5 · 1.000 · $0.070 | 2 · 1.000 · $0.310 |
| Table | 36 · 0.736 · $0.048 | 11 · 0.773 · $0.051 | 11 · 0.909 · $0.204 |

- **The stronger model did not improve ready text questions in these validation runs.**
  Mini answered every ready text question correctly; `gpt-5.4` did the same at about 3×
  the cost. Text questions took 41% of the `gpt-5.4` bill. This is evidence for the tested
  set, not a claim that every future text question can stay on mini.
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

### Finding 3: preliminary routing simulation

**Method.** Each mini question-run (4 runs × 25 questions) keeps its own outcome, cost,
and time, or, when a policy sends it to `gpt-5.4`, takes that question's outcome, cost,
and time from the `gpt-5.4` run. First computed with a one-off script; the efficiency
analyzer (§8, below) reproduces every row:

| Policy | Quality | List $/q | Seconds/q | Sent to `gpt-5.4` |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.870 | 0.0431 | 12.4 | 0% |
| All `gpt-5.4` | 0.960 | 0.1524 | 21.6 | 100% |
| Route on mini's own table flag | 0.960 | 0.1094 | 17.8 | 47% |
| Route on the question's category (author labels; seven text categories) | 0.955 | 0.1165 | 18.3 | 44% |
| Route on `gpt-5.4`'s table flag | 0.935 | 0.1108 | 18.4 | 44% |
| Mini first; rerun on `gpt-5.4` when the evidence notice fires | 0.910 | 0.0821 | 17.4 | 13%, paid twice |
| Perfect router (hindsight): `gpt-5.4` only where it scores higher than this mini run, paying only the path taken | 0.965 | 0.0717 | 14.6 | 14% |

**Reading.**

- **The simulated table router reproduced the one observed `gpt-5.4` run's 0.960 score
  for 28% less** ($0.109 against $0.152 at list price) and 3.8 s less per question. This
  was a retrospective combination of saved outcomes, not a live routed-system result.
- **A precise router could save up to a third more.** A router that knew the outcomes
  would send only 14% of the question-runs to `gpt-5.4` and cost $0.072 for the same
  quality, against the table-flag router's 47% and $0.109. Most table questions are ones
  mini already answers; the gap between the two is the value of routing precision. The
  first version of this row charged both paths for every routed question ($0.104) and led
  to the opposite reading; the analyzer's definition (only the path taken) is the right
  bound. The other lever is the expensive path itself, where the assessor re-reads and
  the planner can run up to 12 times.
- **Escalating on the evidence notice is cheapest and loses quality** (0.910). The silent
  failures raise no notice: VAL24 when one computation succeeds too early, VAL08, VAL14.
- **Limits.** The `gpt-5.4` outcomes come from a single run (6.1: Wilcoxon p = 0.08 against
  the three mini runs). A routed system is a different run, with `gpt-5.4` on only part of
  the questions. The simulation therefore motivated the live routing experiments below;
  it was not used as the final evidence for the decision.

## Candidate component reviewed: Jev

The lecture named Jev as a model "very explicitly not designed to output text", built
for decisions such as routing and checking, and charged only for input tokens. It was
reviewed as the decision-maker for a router.

**Facts** (verified 2026-10-04 using the official
[OpenRouter model endpoint](https://openrouter.ai/typesafe/jev-1.13/api) and
[OpenRouter Jev guide](https://openrouter.ai/blog/tutorials/how-to-use-jev/)):

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

# Baseline on the GT test set: 6.1 survivor and 7.1 safeguarded baseline

**Status:** complete (2026-10-04, 01:37–02:06). Six runs, no errors, no whole-graph
retries; $3.90 billed, judge included.

**Why.** No configuration has a cost and latency measurement on the GT test set
("Question sets" above), and GT is the more table-heavy set, so a routing saving measured
on validation alone would likely overstate it. Before any optimization, both systems get
a GT baseline:

- the **6.1 survivor**, the last checkpoint's survivor;
- the **7.1 safeguarded baseline**, the system the optimizations build on.

Running both also checks, on a second question set, that the 7.1 safeguards add no
measurable cost.

**Design.**

- 3 runs per system, 19 GT questions each, history off, `openai/gpt-5.4-mini` in every
  role, judge `gpt-5.4-mini`; the 7.1 safeguarded baseline with its default grounding policy
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
| 2 | 7.1 safeguarded baseline | `admiring_diffie` | 0.658 | 0.0507 | 0.0432 | 19% | 11.8 | 6.89 |
| 3 | 6.1 | `hardcore_page` | 0.816 | 0.0570 | 0.0372 | 43% | 13.3 | 7.16 |
| 4 | 7.1 safeguarded baseline | `eloquent_hoare` | 0.711 | 0.0459 | 0.0286 | 48% | 14.0 | 6.95 |
| 5 | 6.1 | `confident_stallman` | 0.816 | 0.0485 | 0.0310 | 45% | 14.7 | 6.63 |
| 6 | 7.1 safeguarded baseline | `confident_zuckerberg` | 0.763 | 0.0539 | 0.0325 | 49% | 15.6 | 6.68 |

Article recall was 1.000 in every run.

**Per system** (3 runs × 19 questions each):

| System | Quality | List $/q | Billed $/q | Seconds/q (mean / median) | Calls/q | Input tokens/q |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| 5.1 survivor (3 runs, 2026-09-23, no telemetry) | 0.754 | | | | | |
| 6.1 survivor | **0.789** | 0.0485 | 0.0350 | 13.1 / 11.8 | 6.77 | 56.8K |
| 7.1 safeguarded baseline | **0.711** | 0.0502 | 0.0348 | 13.8 / 12.6 | 6.84 | 59.3K |

**By path** (`tables_flagged` and assessor calls, as in Finding 2):

| Path | 6.1: runs · quality · list $/q · s/q | 7.1 safeguarded baseline |
| --- | --- | --- |
| Text, ready after the first assessment | 13 · 0.962 · $0.038 · 8.9 s | 15 · 0.833 · $0.038 · 9.3 s |
| Text, escalated | 1 · 1.000 · $0.020 · 8.2 s | none |
| Table | 43 · 0.733 · $0.052 · 14.5 s | 42 · 0.667 · $0.055 · 15.4 s |

**Cost and time: no separable system effect was detected.**

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

**Quality in these runs: 6.1 is above 5.1 on GT; the 7.1 safeguarded baseline is below both.**

- **6.1: 0.789** (0.737, 0.816, 0.816), against 0.754 for the three recorded 5.1 GT
  runs (judged on 2026-09-23). Its table path scored 0.733, against 0.69 for 5.1 on the
  same set: on GT, the 6.1 reliability fixes did not lower the table path.
- **7.1 safeguarded baseline: 0.711** (0.658, 0.711, 0.763). Each 7.1 run scored below the 6.1 run
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
  judge's own variation is about 7% of verdicts on identical input (6.1). *The prompt
  replay below did not reproduce a prompt-driven gap.*
- **The grounding check flagged 10 of 57 answers, and 8 of them passed the judge.** The
  flagged spans are extraction artifacts, not invented facts: "Russia-related Olympic"
  (the hyphen-suffix pattern already seen on validation), "Winter Olympic Games Sport"
  and "Summer Olympic Games Sport" (heading words captured into a name), "To Bill
  Clinton; To Barack Obama" (the answer's own bold list labels), "Russian Empire". The
  two GT16 answers naming Joe Biden passed the check: Joe Biden is in the evidence, and
  the check verifies names, not relationships (its limit recorded in 6.1). With policy
  `surface`, a correct answer carried the "[QUARANTINED]" label in 8 of 57 question-runs.

**Report:** `cost_efficiency/reports/gt_baseline_6_1_vs_7_1.pdf`, tables in
`cost_efficiency/reports/gt_baseline_6_1_vs_7_1_tables/`. Two of its markers add to the
reading above:

- **The tail is GT09** (a cross-table comparison): $0.31 at list price in one 6.1 run
  (partial) and $0.24 in one 7.1 run (pass), against a median question of $0.033. The
  most expensive question-run costs 6.5x the mean question-run in 6.1, and 4.7x in 7.1.
- **The grounding check cannot see most wrong answers:** 12 of 7.1's 13 failed answers
  passed it, Joe Biden included. 13% of 6.1's list spend and 23% of 7.1's went to
  failed answers.

**Predictions against results:**

| Prediction | Result |
| --- | --- |
| Quality 0.70–0.80 for both, likely at or below 5.1's 0.754 | Range held for both. 6.1 above 5.1 (0.789); 7.1 below (0.711) |
| About $0.045 per question at list price | $0.0485 (6.1) and $0.0502 (7.1) |
| About 14 s per question | 13.1 s and 13.8 s |
| 7.1 against 6.1: no difference beyond the run-to-run spread | Held for cost, calls, tokens, and time. Quality −0.078, consistent in all three pairs, not significant (p = 0.19) |

# Prompt replay on the GT contexts: legacy against guarded answer prompt

**Status:** complete (2026-10-04, `cost_efficiency/replay_tests/2026_10_04_09_34_37/`);
96 answers and 96 judge calls, no errors, $1.26 billed for the answers. **Result: the
replay did not detect a quality loss caused by the guarded prompt.**

**Why.** The GT baseline put the 7.1 safeguarded baseline 0.08 below the 6.1 survivor, with the losses in
the answer step on identical contexts. The two systems differ in three things at once:
the answer prompt, the grounding check (its label on flagged answers), and what the agent
collected in each run. Before any optimization is built on the safeguarded baseline, the prompt is
tested alone.

**Design** ([`prompt_replay.py`](prompt_replay.py), the answer replay method of 6.1
Experiment 1):

- **Evidence held fixed.** Each saved GT context is rebuilt from its run's AgentState log
  with `analyzers/rebuild_answer_context.rebuild_row`, and must match its recorded
  `context_characters` before anything is paid: 48 of 48 matched (114 of 114 for all GT
  questions).
- **Two arms, one change.** Every context is answered with the legacy prompt (2.1-6.1)
  and with the guarded prompt (7.1), through the `build_answer_messages` both systems use,
  on `gpt-5.4-mini` at temperature 0.2.
- **Contexts from both systems.** The three 6.1 and the three 7.1 runs of each question
  are replayed, so the result separates the prompt (same context, two prompts) from the
  evidence (same prompt, contexts from different runs).
- **Questions:** the eight whose verdicts differed between the systems (GT05, GT07, GT09,
  GT10, GT11, GT15, GT16, GT19): 48 question-runs, 96 answers, 96 judge calls,
  estimated $1.93 at list price. The other eleven were level in the baseline.
- **Judging:** the cost runs' RAGAS judge grades the raw answer in both arms. The
  grounding label is not applied, so the comparison holds the prompt's effect alone; the
  check's verdict on each answer is recorded offline.
- **Noise floor:** the arm matching each context's own run (legacy on 6.1 contexts,
  guarded on 7.1 contexts) re-answers the recorded condition.
- **Markers counted per arm:** Joe Biden and Hillary Clinton in GT16 answers, the "Totals"
  row in GT05 answers, and hedges ("do not contain", "do not support", …).
- Outputs: `cost_efficiency/replay_tests/<stamp>/` (`answer_calls.csv`, `summary.md`,
  `run_config.json`).

**Predictions** (recorded before the results):

- On these eight questions the baseline gap is larger than overall: 6.1 0.708 against 7.1
  0.521 (−0.19). They were selected because they differed, so part of that gap is
  selection by chance, and any replay difference should be smaller.
- **If the guarded prompt is the cause:** guarded below legacy on the same contexts, by
  roughly 0.05–0.15; the Joe Biden answers on GT16 and the "Totals" answers on GT05 appear
  mostly under the guarded prompt, on contexts from both systems; more hedges under the
  guarded prompt.
- **If the evidence or chance is the cause:** the two prompts score about the same on the
  same contexts, and any difference follows the context's source (contexts from 7.1 runs
  lower under both prompts).

## Results (2026-10-04)

**Quality on the same 48 contexts:**

| Evidence from | Legacy prompt | Guarded prompt | Recorded in the run |
| --- | ---: | ---: | ---: |
| 6.1 survivor runs (24) | 0.688 | 0.688 | 0.708 |
| 7.1 safeguarded baseline runs (24) | 0.688 | 0.688 | 0.521 |

- **The prompts score the same.** Paired on each context, guarded minus legacy is +0.000:
  better on 8, worse on 9, the same on 31 (Wilcoxon p = 0.94).
- **The 7.1 evidence was not worse.** Contexts from the 7.1 runs score exactly what
  contexts from the 6.1 runs score, under either prompt.
- **The replay found no repeatable prompt-driven gap on these questions.** The 7.1 runs'
  recorded 0.521 became 0.688 when the same contexts were answered again with the same
  guarded prompt. This supports run-to-run answer or judge variation as the explanation,
  but does not prove that chance was the only cause.
- **Re-asking moves verdicts more than changing the prompt.** The arm matching each
  context's own run changed 22 of 48 recorded verdicts (9 of 24 on 6.1 contexts, 13 of 24
  on 7.1 contexts); switching the prompt on the same context changed 17 of 48. These eight
  questions were chosen because they differed between the systems, so they are the
  unstable ones: 6.1 measured a noise floor of 6 in 84 on a broader set.

**The markers behind the hypothesis:**

| Marker | Legacy prompt | Guarded prompt |
| --- | --- | --- |
| GT16 answers naming Joe Biden as the connecting person | 1 of 6 (a 7.1 context) | 2 of 6 (6.1 contexts) |
| GT05 answers mentioning the "Totals" row | 1 of 6 (quality 0.83) | 0 of 6 (quality 1.00) |
| Hedges ("do not contain", "do not support", …) | 8 of 48 | 17 of 48 |
| Grounding check flags (not applied) / of those, judge passes | 9 / 6 | 8 / 6 |

- **Joe Biden is the answer model's instability on GT16's 248K-character context,** with
  either prompt and on either system's evidence. It is the competing answer first seen in
  the 6.1 answer replay.
- **The "Totals" answers came from the legacy prompt** in the replay, the opposite of the
  baseline's appearance.
- **The guarded prompt hedges twice as often,** without lowering the verdicts on these
  questions (GT05 and GT09 hedge most and still score 1.00 and 0.83).
- **The grounding check's false alarms do not depend on the prompt** (6 of 9 and 6 of 8
  flagged answers passed).

**Predictions against results:**

| Prediction | Result |
| --- | --- |
| Any replay difference smaller than the baseline's −0.19 on these questions | Held: 0.000 |
| If the prompt is the cause: guarded 0.05–0.15 below legacy, Biden and "Totals" mostly under the guarded prompt, more hedges | Only the hedges held. Quality level; Biden under both prompts; "Totals" under the legacy prompt |
| If run-to-run variation or the evidence is the cause: the prompts level on the same contexts | Held; the replay found no difference by prompt or context source |

**Reading.**

- **The 7.1 safeguarded baseline remains the base for the performance work.** The replay
  detected no quality loss attributable to the guarded prompt; its security benefit
  therefore remains part of the design.
- **The GT gap between 6.1 and 7.1 (−0.08, p = 0.19) was not statistically significant.**
  The replay did not reproduce a prompt effect, so the evidence is consistent with
  run-to-run answer or judge variation.
- **Measurement lesson.** Half the verdicts on the unstable GT questions move when the
  same evidence is answered again. Three runs of 19 questions cannot resolve a difference
  of 0.08, so later comparisons are paired by question and, where only the answer step
  changes, replayed on fixed evidence.

# Grounding check: name-extraction fixes (offline)

**Status:** complete (2026-10-04); no API calls.

**Why.** The GT baseline found the grounding check flagging correct answers: 8 of its 10
flags on the 7.1 safeguarded baseline were answers the judge passed. Under policy `surface` each of those
reaches the user with the "[QUARANTINED]" label, a usability cost of the safeguard, and
the same artifacts would follow every later run.

**Method.** Every saved answer was re-checked with its rebuilt evidence (verified against
the recorded `context_characters`): the six GT baseline runs (114 answers) and the four
validation runs of 6.1 and 7.1 (100). The recorded "[QUARANTINED]" label is stripped
first, because re-checking a labelled answer flags the label itself. The security floor
is every answer or draft in the security runs that contains a planted name (13 answers,
57 mentions of names such as "Marisol Quennell" and "Rafe Dunmoor"): each must stay
flagged.

**What the flags were.** Five extraction artifacts, each a span no answer asserted:

| Artifact | Example (recorded answer) | Invented span | Flags |
| --- | --- | --- | ---: |
| Lowercase hyphen suffix | "The Russia-related Olympic identities" | Russia-related Olympic | 10 |
| Table header joined by a slash | "the Winter Olympic Games Sport/Years table" | Winter Olympic Games Sport | 6 |
| Capitalised connector opening a label | "- **To Bill Clinton:** his wife"; "Among Best Actor winners" | To Bill Clinton; Among Best Actor | 7 |
| Brackets and quotes removed, gluing a title to a name | "*Sense and Sensibility* (“Kate Winslet –" | Sensibility Kate Winslet | 4 |
| Possessive removed | "Obama’s Secretary of State" | Obama Secretary | 3 |

**Changes** (`wiki_agents/grounding_check.py`, name extraction only; quotations unchanged):

- a hyphen continues a name only before a capital or a digit ("Austria-Hungary" stays one
  name; "Russia-related" ends at "Russia");
- a slash-joined word, a bracket, a double quote, and a possessive end a name;
- "To" and "Among" join the sentence openers.

**Results:**

| | Before | After |
| --- | ---: | ---: |
| Answers flagged (of 214) | 45 | 22 |
| … of them passed by the judge (false alarms) | 32 | 15 |
| Answers flagged for a name | 29 | 5 |
| Spans the change introduced | | 0 |
| Planted-name mentions flagged (security floor) | 57 of 57 | 57 of 57 |
| 6.1 validation replay (`analyzers/replay_grounding.py`): trigger rate; quality under `withhold` | 21%; 0.693 | 13%; 0.760 |

- **Left as they are, by design:**
  - "Russian Empire" (4), a negated mention of an entity absent from the evidence ("did
    not show any hosting by the Russian Empire"), the same accepted cost as a refusal that
    names a fabricated entity;
  - "Summer Games" (2) and "Prince Leopold" (1), paraphrases or titles the evidence does
    not contain;
  - the quotation rule (17 flagged answers), strict on purpose: some are inexact quotes
    the guarded prompt targets, and the rest quote the evidence notice or the table
    request, which are kept out of the trusted evidence because a planted text can reach
    them.
- **Cost of the change:** a name that itself contains a possessive ("People's Republic
  of China") is no longer checked as one span, the same limit as single-word names; 777
  names checked against 809 before.
- **Tests:** `tests/test_grounding_extraction.py` covers each removed artifact and checks
  that planted names next to every new boundary remain flagged; the module also includes
  a self-check.
- **The security result stands:** every planted name the recorded security runs caught
  is still caught.

# GT run on gpt-5.4: the strong path

**Status:** complete (2026-10-04, 10:04–10:12, `adoring_hopper`); one run, no errors.

**Why.** The performance work starts from the `gpt-5.4` quality (accuracy first), and on
GT that quality was unknown: the 0.960 came from one validation run, and GT's table
questions are harder. A router to `gpt-5.4` is worth building only if `gpt-5.4` clearly
beats mini on GT, and the routing simulation (efficiency analyzer §8) needs a strong
outcome for every GT question.

**Design.** The 7.1 safeguarded baseline (the system kept after the prompt replay, with the corrected
grounding check) with `--model openai/gpt-5.4` for every agent role and the answer; judge
`gpt-5.4-mini` as in every run; history off; GT, 19 questions. One run, about $3.3
estimated: a reference point, not a final comparison.

**Commands** (from `rag_and_context_engineering/`):

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_test_final.py" --gt-set "wikipedia_retrieval_engine/GT/wikipedia_GT.csv" --output-dir "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_efficiency/wikipedia_GT" --model openai/gpt-5.4
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments_efficiency.py --baseline "7.1 final" --route-cheap "7.1 final" --route-strong "7.1 final, gpt-5.4" --output "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_efficiency/reports/gt_7_1_mini_vs_gpt54.pdf"
```

## A pricing rule found on the way

The run's billed cost ($5.30) came out above its list cost ($4.96), which list price
should never allow. `gpt-5.4` doubles its input price for prompts above 272K tokens
(OpenRouter endpoint pricing, `overrides.min_prompt_tokens`), and two GT09 calls (the
assessor and the answer) sent 293K tokens each. With the tier, the price table reproduces
what OpenRouter billed for both calls to the tenth of a cent ($0.798 and $1.473).

- `pricing/model_prices.json` carries the tier, `usage_accounting.call_cost` applies it,
  and the efficiency analyzer recomputes every run's list cost from its calls with the
  current table (the recorded figure stays in `cost_list_recorded_usd`).
- Only this run had prompts above 272K tokens; every mini and every earlier `gpt-5.4` run
  is unchanged. This run's list cost goes from $4.96 to $6.43 (+30%).

## Results (2026-10-04)

| GT, 19 questions | Quality | List $/q | Billed $/q | Seconds/q | Calls/q |
| --- | ---: | ---: | ---: | ---: | ---: |
| 7.1 safeguarded baseline, `gpt-5.4-mini` (3 runs) | 0.711 | 0.0502 | 0.0348 | 13.8 | 6.84 |
| Safeguarded graph, `gpt-5.4` in all roles (1 run) | **0.868** | **0.3387** | 0.2787 | 24.2 | 7.11 |

- **Quality +0.158 over mini** (7 questions better, 2 worse; Wilcoxon p = 0.074), at 6.7x
  the list cost and 10 s more per question: $0.18 per question for each +0.10 quality.
- **By path:** table questions 0.667 → 0.821; text questions 0.833 → 1.000 (5
  question-runs). On GT, unlike validation, mini is not perfect on text questions
  (GT16, the Joe Biden answer).
- **Where `gpt-5.4` won:** GT07 and GT16 (+0.83), GT08 (+0.67), GT05, GT10, GT15, GT19
  (+0.33). **Where it lost:** GT09 (1.00 → 0.50) and GT11 (0.17 → 0).
- **One question is half the bill.** GT09 (the cross-table population and life-expectancy
  comparison) cost $3.44 at list price, 53% of the run's $6.43, in 12 calls and 773K input
  tokens, and scored partial, where mini scores 1.00 for $0.12. Its two largest prompts
  crossed the 272K tier. The most expensive question-run costs 10x the run's mean
  (mini: 4.7x).
- **By role:** the assessor is 52% of the `gpt-5.4` bill and the answer 37%; together
  89%. The decomposer, TOC reviewer, and table planner are 11%.

**Routing simulated on these runs** (analyzer §8; cheap = the three 7.1 mini runs,
strong = this run):

| Policy | Quality | List $/q | Sent to `gpt-5.4` | Saving against all `gpt-5.4` |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.711 | 0.0502 | 0% | 85% |
| All `gpt-5.4` | 0.868 | 0.3387 | 100% | 0% |
| Route on the question type (table flag) | 0.825 | 0.3072 | 74% | 9% |
| Route on the question's category | 0.825 | 0.3180 | 79% | 6% |
| Mini first; rerun on `gpt-5.4` when the evidence notice fires | 0.772 | 0.1494 | 30%, paid twice | 56% |
| Perfect router (hindsight) | 0.904 | 0.1029 | 25% | 70% |

**Reading.**

- **`gpt-5.4` is worth routing to on GT:** the quality gain is large, and it comes from
  both table and text questions.
- **A question-type router saves little on GT.** Three quarters of GT question-runs are
  table questions, so the type router sends 74% to `gpt-5.4` and saves 9% against all
  `gpt-5.4`, while losing 0.04 quality on the text questions it keeps on mini. On
  validation the same router saved 28% (44–47% sent).
- **The cost of the strong path is concentrated.** One question (GT09) is half of it, at
  a lower verdict than mini's. A cap on the strong path's context (below the 272K tier)
  or on its table rounds would remove most of that tail; the perfect router's $0.103 shows
  how much precision is worth.
- **Router B's room is small on cost.** Routing only the assessor and the answer to
  `gpt-5.4` keeps 11% of the strong path on mini; its difference from router A is mostly
  a quality question (6.1: the `gpt-5.4` TOC reviewer's table flag fixed VAL24).

# Router check: Jev on the 44 questions

**Status:** complete (2026-10-04, `cost_efficiency/router_checks/2026_10_04_11_15_58/`);
132 Jev calls, all ok, $0.0023.

**The routing rule (decided 2026-10-04).** `gpt-5.4-mini` is the default for a question
that is text-only and needs one article; every other question goes to `gpt-5.4`. In the
saved runs this rule loses no quality on either set (GT 0.868, validation 0.960, the same
as all `gpt-5.4`), because every question it keeps on mini is one mini answers correctly.
The single-article condition is what protects GT16 (two articles), which mini fails.

**How the router decides.** Jev makes one decision, the route; code makes the rest:

- Jev (`typesafe/jev-1.13`, pinned) reads only the question and answers one `choice`
  question with two written routes: *simple* ("stated in the text of one Wikipedia article
  about one person, place, event, or work; no tables, counting, rankings, date ranges, or
  comparisons across articles") and *complex* (tables, counting, date filters, ranking,
  calculation, or facts from more than one article). It returns a probability for each.
- Code maps the answer to a model: *simple* with probability at or above a threshold goes
  to mini; anything else, including a failed call, goes to `gpt-5.4`. Jev never sees the
  articles, so "one article" is a reading of the question's wording, not knowledge of the
  corpus.

**Design of the check** ([`jev_route_check.py`](jev_route_check.py)):

- All 44 questions (GT and validation), three repeats each.
- **Answer key:** *simple* when fewer than half of the saved mini runs flagged a table and
  the question set lists one source article; *complex* otherwise.
- **Two error kinds:** a complex question sent to mini can lose the question; a simple
  question sent to `gpt-5.4` only costs money.
- The routes are then simulated on the saved outcomes with the efficiency analyzer
  (`--route-labels`), which is the real test: agreement with the key matters only where
  it changes a verdict.

## Results

- **Cost and speed:** $0.000017 per decision (about 400 input tokens), median 0.20 s.
- **Stable:** the same choice in all three repeats on 43 of 44 questions; p(simple) varied
  by at most 0.09.
- **Agreement with the key:** 32 to 34 of 44, depending on the threshold. The
  disagreements that send a "complex" question to mini are questions mini answers
  correctly: GT01 and GT04 (direct facts the TOC reviewer routed through a table), and
  VAL11–VAL13 (the Broad Street cholera explanations, which list two source articles).

**Simulated on the saved outcomes:**

| Router | GT quality | GT list $/q | GT to `gpt-5.4` | Validation quality | Validation list $/q | Validation to `gpt-5.4` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All `gpt-5.4` | 0.868 | 0.3387 | 100% | 0.960 | 0.1524 | 100% |
| The answer key (the rule, applied perfectly) | 0.868 | 0.3293 | 84% | 0.960 | 0.1324 | 68% |
| Jev at 0.5 | 0.868 | 0.3274 | 74% | 0.955 | 0.1182 | 36% |
| Jev at 0.8 | 0.868 | 0.3327 | 84% | 0.955 | 0.1270 | 52% |
| Jev at 0.9 | 0.868 | 0.3327 | 84% | 0.960 | 0.1379 | 76% |
| Perfect router (hindsight) | 0.904 | 0.1029 | 25% | 0.965 | 0.0717 | 14% |

**Reading.**

- **Jev applies the rule without losing quality** on GT at any threshold and loses 0.005 on
  validation below 0.9, for a fraction of a cent per question and 0.2 s.
- **Lower thresholds are cheaper and no worse here:** at 0.5 Jev sends more questions to
  mini than the key does (it reads GT01, GT04, and the Broad Street questions as simple),
  and mini answers them correctly. The threshold was chosen from the same 44 questions it
  is scored on, so the difference between 0.5 and 0.8 is not evidence of a better cutoff.
- **The rule saves little on GT:** 2–3% against all `gpt-5.4` (16–26% of GT goes to mini),
  and 17–22% on validation. The questions that need `gpt-5.4` are the expensive ones, and
  one of them (GT09) is half of the strong path's GT cost.

# Answer check: Jev decides when a mini answer needs gpt-5.4

**Status:** complete (2026-10-04, `cost_efficiency/answer_checks/2026_10_04_12_06_53/`);
offline over saved answers, 214 Jev calls, $0.15.

**Why.** The routers decide from the question alone, before anything runs, and on GT they
send three quarters of the questions to `gpt-5.4` (2–3% saving). The perfect router
($0.103 on GT) shows that most of the strong path is spent on questions mini answers
correctly; what a router cannot see is whether mini *did*. A check after the answer can.

**The policy ("verify after").** `gpt-5.4-mini` answers every question. Jev reads the
question, the answer, and the evidence the answer was given, and answers two yes/no
questions in one call:

- *grounded*: "Is every fact stated in the answer supported by the evidence?" (a person,
  work, number, date, or relationship absent or described differently counts as no);
- *complete*: "Does the answer fully answer every part of the question?" (a missing part,
  a partial list or count, or "cannot answer" counts as no).

When Jev's probability falls below a threshold, the question is answered again on
`gpt-5.4`, and both are paid. This is an escalation trigger for cost, not a security
guard: it reads the user's question, which the deterministic grounding check never does.
A question crafted to steer Jev can at worst keep mini's answer or cost one extra
`gpt-5.4` run.

**Design** ([`jev_answer_check.py`](jev_answer_check.py)):

- every saved `gpt-5.4-mini` answer with its evidence rebuilt and verified: the six GT
  baseline runs (114) and the four validation runs (100); the judge's verdict is the label;
  7.1 answers are checked without the grounding label;
- evidence that does not fit Jev's 32K-token window (57 of 214) is cut to the passages
  mentioning the answer's names, numbers, and quotations, plus the evidence notice; the
  simulation also shows escalating every oversized answer instead;
- simulated on the saved outcomes: an escalated question-run pays mini, Jev, and that
  question's mean `gpt-5.4` cost and time, and takes its `gpt-5.4` verdict.

## Results

- **213 of 214 checked,** median 0.33 s, about $0.0007 per answer. One call (GT19) was
  rejected as too long: Jev counts more tokens than the `o200k` estimate, so the budget is
  now 22K `o200k` tokens. The simulation escalates a failed check.
- **"Complete" predicts the judge; "grounded" much less.** AUC, the chance a non-pass
  answer scores lower than a pass (0.5 = no signal):

  | | GT (36 of 113 non-pass) | Validation (18 of 100) |
  | --- | ---: | ---: |
  | grounded | 0.68 | 0.83 |
  | complete | 0.76 | 0.93 |
  | the lower of the two | 0.71 | 0.91 |

  Mini's wrong answers are mostly incomplete or wrong in substance, not invented, which is
  also why the deterministic grounding check passed 12 of 13 failed 7.1 answers.

**Simulated policies (escalate on "complete"; excerpts for large evidence):**

| GT | Quality | List $/q | Seconds/q | Escalated |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.711 | 0.0502 | 13.8 | 0% |
| All `gpt-5.4` | 0.868 | 0.3387 | 24.2 | 100% |
| Router (Jev on the question, 0.8) | 0.868 | 0.3327 | 23.6 | 84% |
| Answer check, threshold 0.3 | 0.789 | 0.0717 | 18.5 | 14% |
| **Answer check, threshold 0.5** | **0.833** | **0.1079** | 22.3 | 25% |
| Answer check, threshold 0.7 | 0.833 | 0.3204 | 28.2 | 44% |
| Answer check, 0.5, large evidence always escalated | 0.860 | 0.2797 | 28.6 | 51% |

| Validation | Quality | List $/q | Seconds/q | Escalated |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.870 | 0.0431 | 12.4 | 0% |
| All `gpt-5.4` | 0.960 | 0.1524 | 21.6 | 100% |
| Router (Jev on the question, 0.8) | 0.955 | 0.1270 | 18.8 | 52% |
| Answer check, threshold 0.5 | 0.930 | 0.0889 | 18.3 | 14% |
| **Answer check, threshold 0.7** | **0.955** | **0.1163** | 20.6 | 21% |

**Reading.**

- **The answer check reaches trade-off points the routers cannot.** On GT, threshold 0.5
  keeps 78% of the quality gain from mini to `gpt-5.4` (+0.122 of +0.157) for 20% of the
  extra cost ($0.058 of $0.289). On validation, threshold 0.7 matches the router's quality
  (0.955) for a little less.
- **GT09 decides the price above 0.5.** Between thresholds 0.5 and 0.7 the GT cost triples
  ($0.108 → $0.320) for no quality: the higher threshold escalates GT09, whose `gpt-5.4`
  run costs $3.44 and scores lower than mini. The cap on the strong path and the answer
  check address the same tail from two sides.
- **It is slower on escalated questions,** which pay mini, Jev, and `gpt-5.4` in sequence:
  22.3 s per question on GT at 0.5 against 24.2 s for all `gpt-5.4` and 13.8 s for mini.
- **Limits.** The thresholds were read off the same answers they are scored on, and the
  `gpt-5.4` outcomes on GT come from one run, so a live run has to confirm the trade-off.
  Escalation reruns the whole question; rerunning only the answer step on the saved
  evidence would be cheaper but leaves the evidence as mini collected it.

# Options for the live runs, side by side

**Status:** compiled 2026-10-04 from the sections above.

**Decision (2026-10-04): three live GT runs first,** and further combinations chosen
after their results:

1. **Router by question type:** after the TOC review, a question flagged for a table
   runs the assessor, the table planner, and the answer on `gpt-5.4`.
2. **Router B:** the same trigger; only the assessor and the answer switch to `gpt-5.4`,
   so the two runs differ in one role, the table planner.
3. **Answer check at 0.5, large evidence straight to `gpt-5.4`.**

Escalation on the evidence notice is not run: its trigger is recorded in the saved runs,
so its simulation is already reliable, and it is the weakest option on both sets. The cap
on the strong path is not part of these runs; each run's cost is reported with and
without GT09.

Every option starts from the 7.1 safeguarded baseline and uses two models:
`gpt-5.4-mini` (cheap) and
`gpt-5.4` (strong). The two "All" rows are measured runs (GT: three mini runs, one
`gpt-5.4` run; validation: four mini runs, one `gpt-5.4` run). Every other row is
simulated on those runs: a question-run sent to `gpt-5.4` takes that question's measured
`gpt-5.4` outcome, cost, and time. "Gain kept" is the share of the quality gain from all
mini to all `gpt-5.4` that an option keeps; "extra cost" is the share of the cost
difference it spends.

## How each option decides

| Option | Decides from | When the model is chosen | Extra calls | Main risk |
| --- | --- | --- | --- | --- |
| All `gpt-5.4-mini` | nothing | fixed | none | table computations and multi-article questions fail |
| All `gpt-5.4` | nothing | fixed | none | 6.7x the cost; one question (GT09) is half of the GT bill |
| Router by question type | the TOC reviewer's table flag | after the TOC review | none | sends three quarters of GT to `gpt-5.4`; keeps failing text questions on mini |
| Router A, the routing rule | Jev on the question: simple (text, one article) or complex | before retrieval | one Jev call (0.2 s) | Jev reads only the wording; saves little on GT |
| Router B (assessor and answer on `gpt-5.4` when routed) | same as A, or the evidence size after the TOC review | after the TOC review | as A | not measurable from saved runs; keeps the TOC reviewer, whose table flag mattered in 6.1, on mini |
| Answer check | Jev on question, mini's answer, and evidence: "complete?" | after mini answers | one Jev call (0.3 s); escalated questions run twice | slower on escalated questions; thresholds read off the same data |
| Answer check, large evidence straight to `gpt-5.4` | the check, plus the evidence size | after the TOC review for large evidence | as above | large contexts are where `gpt-5.4` is most expensive |
| Escalate on the evidence notice | the 6.1 evidence-status notice | after mini answers | none | silent failures raise no notice |

## Results

| Option | GT quality | GT list $/q | GT s/q | GT to `gpt-5.4` | GT gain kept / extra cost | Val quality | Val list $/q | Val to `gpt-5.4` | Val gain kept / extra cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All `gpt-5.4-mini` (measured) | 0.711 | 0.0502 | 13.8 | 0% | 0% / 0% | 0.870 | 0.0431 | 0% | 0% / 0% |
| All `gpt-5.4` (measured) | 0.868 | 0.3387 | 24.2 | 100% | 100% / 100% | 0.960 | 0.1524 | 100% | 100% / 100% |
| Router by question type | 0.825 | 0.3072 | 22.6 | 74% | 73% / 89% | 0.960 | 0.1094 | 47% | 100% / 61% |
| Router A, the routing rule, Jev at 0.8 | 0.868 | 0.3327 | 23.6 | 84% | 100% / 98% | 0.955 | 0.1270 | 52% | 94% / 77% |
| Router A, the routing rule, Jev at 0.5 | 0.868 | 0.3274 | 23.1 | 74% | 100% / 96% | 0.955 | 0.1182 | 36% | 94% / 69% |
| Router B (quality not measurable; cost estimated from per-role costs) | | ≈ 0.288 | | 74% | | | | | |
| **Answer check at 0.5** | **0.833** | **0.1079** | 22.3 | 25% | **78% / 20%** | 0.930 | 0.0889 | 14% | 67% / 42% |
| Answer check at 0.7 | 0.833 | 0.3204 | 28.2 | 44% | 78% / 94% | 0.955 | 0.1163 | 21% | 94% / 67% |
| Answer check at 0.5, large evidence: mini first, always rerun | 0.860 | 0.2797 | 28.6 | 51% | 95% / 80% | 0.930 | 0.1303 | 35% | 67% / 80% |
| Answer check at 0.5, large evidence straight to `gpt-5.4` | 0.860 | 0.2518 | 23.6 | 51% | 95% / 70% | 0.930 | 0.1115 | 35% | 67% / 63% |
| Escalate on the evidence notice | 0.772 | 0.1494 | 22.5 | 30% | 39% / 34% | 0.910 | 0.0821 | 13% | 44% / 36% |
| Perfect router (hindsight bound) | 0.904 | 0.1029 | 17.9 | 25% | 123% / 18% | 0.965 | 0.0717 | 14% | 106% / 26% |

**Reading.**

- **For full `gpt-5.4` quality,** the routing rule through Jev is the safe choice: no loss on
  GT, 0.005 on validation, and a saving of 2–4% on GT and 17–22% on validation.
- **For the best trade-off,** the answer check at 0.5 keeps 78% of the GT gain for 20% of
  the extra cost; no router comes close on GT.
- **Between the two,** sending large evidence straight to `gpt-5.4` buys the remaining
  GT quality (0.860) for 70% of the extra cost; on validation it adds nothing.
- **GT09 sits under every row.** Whichever option escalates it pays $3.44 for a partial
  answer mini gets right, which is why the cost jumps between thresholds 0.5 and 0.7. A cap
  on the strong path (O2) would lower every row that sends GT09 to `gpt-5.4`.
- **Router B's cost** is estimated per GT question from the measured per-role costs:
  decomposer, TOC reviewer, and planner from the mini runs, assessor and answer from the
  `gpt-5.4` run, weighted by how often mini flagged a table. That gives $0.288 per
  question against $0.299 for the type router with the same trigger, $0.377 against $0.403
  on a routed question, and $3.38 for GT09: B keeps on `gpt-5.4` the two roles whose
  prompts crossed the 272K tier. Without GT09, B costs $0.116 and the type router $0.125.
- **Every row except the two "All" rows is a prediction.** The thresholds were read off
  the same data, and the `gpt-5.4` outcomes come from one run per set.

# Live GT runs: three routing strategies

**Status:** complete (2026-10-04, 12:56–13:31): `wizardly_yao` (type), `suspicious_liskov`
(B), `gifted_yao` (answer check), one run each; $13.2 billed, including one failed attempt
(below).

**Why.** The decision recorded in the options section: the three strategies the saved runs
could not settle, run live on GT before any further combination is chosen.

## How the routing was built

**One mechanism for all three** ([`../wiki_agents/model_routing.py`](../wiki_agents/model_routing.py)):

- **A model switch.** The graph's nodes build their model call at the moment they run, so
  a `TierSwitchModel` standing in for a chat model forwards each call to `gpt-5.4-mini` or
  `gpt-5.4`, whichever the current question's tier says.
- **A routing node after the TOC review** (`route_model`, an optional node in
  `agent_graph.build_retrieval_benchmark_graph`) sets the tier and records the decision in
  the state (`routing`), which the cost harness writes to the results CSV (`route`,
  `route_reason`, and for the answer check `check_p_complete`, `escalated`,
  `router_cost_usd`). The decomposer and the TOC reviewer always run on mini: the route
  is decided from their output.
- **The answer check** wraps two graphs: the routed one, and an all-`gpt-5.4` one. After
  mini answers, Jev asks "does the answer fully answer every part of the question?"; below
  0.5, or when the check fails or the evidence is too large for Jev, the whole question is
  answered again on the all-`gpt-5.4` graph and both are paid.

| Run (experiment name suffix) | Routed to `gpt-5.4` when | Roles on `gpt-5.4` when routed |
| --- | --- | --- |
| `route_type` | the TOC review flagged a table | assessor, table planner, answer |
| `route_b` | the TOC review flagged a table | assessor, answer |
| `route_check_0.5` | a text question's kept articles exceed 80,000 characters (Jev's window); or, after mini answered, Jev's p(complete) < 0.5, the check fails, or the answer context exceeds the window | after the review: assessor, table planner, answer; on escalation: every role, the question answered again |

- **Builder and harness:** `survivor_agent_final.build_survivor_routed` and
  `cost_test_starter.py --routing {type,b,check}` (`--strong-model`, `--check-threshold`).
  Every new option defaults to off; the 6.1 and 7.1 builds are unchanged.
- **Jev's cost** is invisible to the LangChain telemetry, so the routing records it
  (`router_cost_usd`) and the efficiency analyzer adds it to each question's cost.
- **Tests:** `tests/test_model_routing.py` (the switch, both routing nodes, the escalation
  with fake graphs); 195 tests pass. An offline build of each strategy confirmed the
  routing node sits between the TOC review and section loading.
- **Smoke tests** (2026-10-04, one question each, outputs kept out of the run folders):

  | Strategy, question | What the telemetry shows |
  | --- | --- |
  | type, GT04 | decomposer and TOC reviewer on mini; assessor, planner, answer on `gpt-5.4`; pass |
  | b, GT04 | the same, with the planner on mini; pass |
  | check, GT06 | kept articles 94,907 characters, so routed to `gpt-5.4` after the review; pass |
  | check, GT04, threshold forced to 1.01 | six mini calls, Jev p(complete) 0.97, escalation, seven `gpt-5.4` calls; all 13 calls and Jev's cost recorded; pass |

**Commands** (from `rag_and_context_engineering/`; each run also needs `--gt-set` and
`--output-dir` as in the GT baseline):

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_test_final.py" --routing type
python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_test_final.py" --routing b
python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/cost_test_final.py" --routing check --check-threshold 0.5
```

## Predictions (recorded before the results)

From the options section, with three differences between the simulation and these runs:
the simulation gave a routed question the whole `gpt-5.4` run's outcome, while here its
decomposer and TOC reviewer stay on mini; each strategy runs once (the 6.1 mini runs spread
from 0.737 to 0.816); and these runs are hours after the baselines, so seconds compare
only per call and role (the analyzer's comparability section).

| Run | Quality | List $/q | Note |
| --- | ---: | ---: | --- |
| `route_type` | about 0.825 | about 0.30 | GT09 alone about $3.4 of the run |
| `route_b` | close to `route_type` | about 0.29 | 6.1: `gpt-5.4` on the planner alone changed nothing |
| `route_check_0.5` | about 0.86 | about 0.25 | GT09 is a large-evidence question if its kept articles exceed the window |

## A failed first attempt of the answer check

The first answer-check run (`keen_perlis`, 13:11–13:21) answered and judged all 19 questions
and then failed when RAGAS wrote the results CSV: the CSV takes its columns from the first
row, and a question routed to `gpt-5.4` after the review carried no check fields while a
checked question did. The answers, the verdicts, and the telemetry were lost (about $4.90
billed); the AgentState logs remain, and the one-row fragment is kept in
`cost_efficiency/failed_runs/`. Every routing record now carries the same fields
(`model_routing.ROUTING_FIELDS`, filled with empty values where a step did not apply), a
test checks that every routing path writes identical columns, and a two-question smoke test
mixing both paths saved its CSV before the run was repeated (`gifted_yao`). The
single-question smoke tests could not have caught it: the failure needs two kinds of row.

## Results (2026-10-04)

Report: `cost_efficiency/reports/gt_routing_runs.pdf` (efficiency analyzer, baseline the
7.1 safeguarded configuration on mini; its saved experiment label is `7.1 final`).

| GT, 19 questions | Runs | Quality | List $/q | Billed $/q | Seconds/q | Without GT09: quality, list $/q | Gain kept / extra cost | p (quality, against mini) |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 7.1 safeguarded baseline, `gpt-5.4-mini` | 3 | 0.711 | 0.0502 | 0.0348 | 13.8 | 0.694, 0.0460 | 0% / 0% | |
| Safeguarded graph, `gpt-5.4` in all roles | 1 | 0.868 | 0.3387 | 0.2787 | 24.2 | 0.889, 0.1663 | 100% / 100% | 0.074 |
| Router by question type | 1 | 0.816 | 0.3009 | 0.2451 | 22.0 | 0.833, 0.1282 | 67% / 87% | 0.133 |
| **Router B (assessor and answer)** | 1 | **0.868** | **0.1417** | 0.1013 | 20.8 | 0.889, 0.1069 | **100% / 32%** | 0.074 |
| **Answer check 0.5, large evidence to `gpt-5.4`** | 1 | **0.842** | **0.1275** | 0.0816 | 22.8 | 0.833, 0.1327 | **83% / 27%** | **0.031** |

Seconds were measured hours after the mini baselines; the decomposer's median call varied
0.93–1.80 s across the session, so the time column compares only roughly.

**Router B: the planner is where `gpt-5.4` overspends.** *(One run; the three-run comparison
below refines this: a mini planner lowers the risk of GT09's large prompts but does not
remove it.)*

- Router B scored what all `gpt-5.4` scored (0.868) for 42% of its cost; against the type
  router, which differs only in running the table planner on `gpt-5.4`, it scored 0.05
  higher for half the cost.
- GT09 shows the mechanism: with the planner on `gpt-5.4` (type router, all `gpt-5.4`) it
  made 5–6 planner calls, read 767–773K input tokens, and its largest prompt (the assessor's)
  reached 294K tokens, above the 272K price tier: $3.41–3.44. With the planner on mini
  (Router B): 4 planner calls, 307K input tokens, a largest prompt of 100K: $0.77. A
  `gpt-5.4` planner requests more table data, and every later call reads it again.
- Without GT09, Router B costs $0.107 per question against $0.128 for the type router and
  $0.166 for all `gpt-5.4`, still the cheapest of the three at the highest quality.

**The answer check: cheapest of the routed runs, and the only one separable from mini.**

| Path | Questions |
| --- | --- |
| Stayed on mini (Jev: complete) | 11: GT01, GT02, GT04, GT07, GT09, GT10, GT11, GT12, GT13, GT14, GT15 |
| `gpt-5.4` after the review (kept articles above 80,000 characters) | 4: GT06, GT16, GT17, GT18, all pass (GT16 was the Joe Biden question on mini) |
| Answered again on `gpt-5.4` | 4: GT05 (p 0.09) and GT08 (p 0.33) pass; GT03 and GT19 (check failed or evidence too large) fail and pass |

- 0.842 at $0.128 per question, the lowest cost of the three; quality +0.132 over mini with
  p = 0.031. Jev cost $0.007 for the run.
- **It avoided the tail:** Jev judged mini's GT09 answer complete (0.73), so GT09 stayed on
  mini and passed for $0.034.
- **Its misses are the known limit:** GT07 and GT11 stayed on mini (Jev 0.68 and 0.92) and
  failed: their answers read as complete, but their computed counts were wrong, which a
  check of the answer's form cannot see.
- **Escalation is slow:** an escalated question pays two passes, 27–79 s.

**Predictions against results:**

| Run | Predicted | Result |
| --- | --- | --- |
| Type router | about 0.825 at about $0.30; GT09 about $3.4 | 0.816 at $0.301; GT09 $3.41. Held |
| Router B | close to the type router's quality at about $0.29 | 0.868 at $0.142. Quality higher and cost half: the estimate assumed GT09's assessor and answer prompts would be as large as in the `gpt-5.4` run; with the planner on mini they were a third of it |
| Answer check | about 0.86 at about $0.25 | 0.842 at $0.128. Cheaper than predicted: GT09 stayed on mini |

**Reading.**

- **Two strategies dominated the other live configurations in this GT run:** Router B
  matched the observed all-`gpt-5.4` score while using 32% of its extra cost, and the
  answer check kept 83% of the observed gain for 27% of the extra cost. These were
  single-run results at this stage; the repeated comparison below made the final choice.
- **Heterogeneous roles beat a whole-question switch.** The roles that judge evidence and
  write the answer gain from `gpt-5.4`; the role that requests table data does not, and
  costs more there. This matches 6.1, where `gpt-5.4` on the planner alone changed nothing.
- **One run each:** Router B and the answer check differ by 0.026 in quality and $0.014 in
  cost, inside the run-to-run spread (the three mini runs of the safeguarded baseline ranged 0.658 to
  0.763). Which of the two is better is not settled by these runs.


## The pipeline, step by step, in each configuration

What each configuration changes, in pipeline order. "Mini" is `gpt-5.4-mini`, "5.4" is
`gpt-5.4`. At this stage the last column was a proposed combination estimated from the
runs above; it was subsequently implemented and evaluated in the three-run comparison.

| Pipeline step | All mini | All 5.4 | Router by question type | Router B | Answer check 0.5 | Proposed: Router B + answer check |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Input sanitizer (code, no model) | on | on | on | on | on | on |
| 2. Decomposer: one search per named person, place, or work | mini | 5.4 | mini | mini | mini; 5.4 on a rerun | mini |
| 3. Article selection (TOC reviewer): keep articles, pick sections and tables, set the table flag | mini | 5.4 | mini | mini | mini; 5.4 on a rerun | mini |
| 4. **Routing step** (new, after step 3) | none | none | table flag → 5.4 for steps 6, 7, 9 | table flag → 5.4 for steps 6 and 9 | text question with kept articles over 80,000 characters → 5.4 for steps 6, 7, 9; every other question stays on mini, checked at step 11 | as the answer check, with 5.4 for steps 6 and 9 only |
| 5. Load sections and tables (code) | same | same | same | same | same | same |
| 6. Assessor: is the evidence enough; request tables or more evidence (loop) | mini | 5.4 | 5.4 when routed | 5.4 when routed | 5.4 when routed; 5.4 on a rerun | 5.4 when routed or rerun |
| 7. Table planner, then the deterministic executor | mini | 5.4 | 5.4 when routed | **always mini** | 5.4 when routed; 5.4 on a rerun | **always mini** |
| 8. Widen: whole articles, then graph neighbours (code) | same | same | same | same | same | same |
| 9. Answer | mini | 5.4 | 5.4 when routed | 5.4 when routed | 5.4 when routed; 5.4 on a rerun | 5.4 when routed or rerun |
| 10. Grounding check (code) | on | on | on | on | on | on |
| 11. **Jev "complete?" check** (new) | none | none | none | none | after a mini answer; below 0.5, a failed check, or evidence over Jev's window → step 12 | as the answer check |
| 12. **Rerun** (new) | none | none | none | none | the whole question on an all-5.4 graph; both runs paid | the whole question with Router B's models (steps 6 and 9 on 5.4) |
| **GT quality** | 0.711 (3 runs) | 0.868 | 0.816 | **0.868** | **0.842** | about 0.82 (estimate) |
| **GT list $ per question** | 0.0502 | 0.3387 | 0.3009 | **0.1417** | **0.1275** | about 0.105 (estimate) |
| **GT seconds per question** | 13.8 | 24.2 | 22.0 | 20.8 | 22.8 | |
| Questions on 5.4 (any step) | 0 of 19 | 19 | 14 | 14 | 8 (4 after step 4, 4 rerun) | 8 |

- **Code for steps 4, 11, and 12:** `wiki_agents/model_routing.py` (the model switch, both
  routing steps, the Jev check, the rerun), an optional `route_model` node in
  `agent_graph.py`, and `cost_test_starter.py --routing {type,b,check}`. Steps 1–3, 5, 8,
  and 10 are unchanged in every configuration.
- **The grounding check (step 10)** is the corrected version in every run after the
  name-extraction fix; the three mini baseline runs used the earlier version. It only
  labels a flagged answer and never changes its content; whether the label moves the
  judge's verdict was not measured.
- **The proposed combination's estimate:** the answer-check run with its four reruns
  priced and judged as Router B ran those questions (GT03, GT05, GT08, GT19). It costs
  less per rerun ($0.07–0.27 against $0.13–0.67) and loses GT19 (0.5 under Router B, 1.0
  on the full 5.4 rerun), so the quality estimate rests on one question's single verdict.

# Three-run comparison on GT

**Status:** complete (2026-10-04, 14:30–15:30); report
`cost_efficiency/reports/gt_three_run_comparison.pdf`.

**Why.** One run of 19 questions cannot separate differences of a few points (the three
mini runs of the 7.1 safeguarded baseline spread from 0.658 to 0.763). Every configuration in the
comparison gets the same number of runs: three.

**Runs added** (in this order, one at a time):

- Router B + answer check (`b_check`, new): the answer check with Router B's models: on
  large evidence, and on a rerun, only the assessor and the answer use `gpt-5.4`; the table
  planner stays on mini. Runs `reverent_bezos`, `brave_liskov`, `vigilant_page`.
- Router B, two more runs: `reverent_diffie`, `focused_huffman`.
- All `gpt-5.4`, two more runs: `pedantic_neumann`, `hardcore_turing`.

The two strategies run only once (the type router, the answer check alone) stay outside
this comparison as exploratory results.

**Before the runs:** a two-question smoke test of `b_check` confirmed the rerun's models
(decomposer, TOC reviewer, and planner on mini; assessor and answer on `gpt-5.4`). The
combination was estimated at about 0.82 and $0.105 per question from the answer-check run
(its reruns priced as Router B ran those questions).

## Results

| GT, 3 runs each | Quality (run range) | List $/q (run range) | Seconds/q | List $ per passing answer | Most expensive question-run |
| --- | --- | --- | ---: | ---: | ---: |
| 7.1 safeguarded baseline, `gpt-5.4-mini` | 0.711 (0.658–0.763) | 0.0502 (0.0459–0.0539) | 13.8 | | 0.236 |
| Safeguarded graph, `gpt-5.4` in all roles | **0.886** (0.842–0.947) | 0.3457 (0.3387–0.3516) | 24.7 | 0.402 | 3.442 |
| **Router B** | **0.868** (0.868 in all three) | **0.1725** (0.1417–0.1924) | 21.3 | **0.209** | 1.356 |
| Router B + answer check | 0.798 (0.763–0.842) | 0.2260 (0.1485–0.3145) | 26.4 | 0.322 | 3.530 |

**Paired by question** (each question's mean over its three runs; Wilcoxon signed-rank):

| Comparison | Quality | List $/q | Seconds/q |
| --- | --- | --- | --- |
| `gpt-5.4` against mini | +0.175 (9 better, 1 worse; p = 0.055) | +$0.296 (p < 0.001) | +10.9 |
| Router B against mini | +0.158 (8 better, 1 worse; **p = 0.047**) | +$0.122 (p < 0.001) | +7.5 |
| **Router B against `gpt-5.4`** | **−0.018 (2 better, 3 worse; p = 0.81)** | **−$0.173, −50% (p = 0.001)** | −3.4 |
| Router B + check against `gpt-5.4` | −0.088 (2 better, 4 worse; p = 0.25) | −$0.120, −35% (p = 0.045) | +1.7 |

**Reading.**

- **Router B delivered the best measured quality-cost trade-off.** Against all-`gpt-5.4`,
  its observed quality was 0.018 lower and the difference was not statistically detected
  (p = 0.81); this is not a formal equivalence result. Its list cost was 50% lower
  (p = 0.001). It was the only routed configuration statistically higher than mini in
  this comparison (p = 0.047), and it scored 0.868 in all three runs. Each passing answer
  cost $0.21, compared with $0.40 on all-`gpt-5.4`.
- **Router B + answer check fell short of its estimate.** Jev sent 6–8 questions per run to
  a rerun (4 in the single answer-check run), every rerun pays two passes, and quality
  dropped to 0.798 at $0.226. The estimate rested on one run's four reruns.
- **GT09 is a property of the question on `gpt-5.4`,** not a chance event: $3.42–3.44 in all
  three runs, scored 0.5, 0, and 0.5 (mini answers it for $0.04–0.24 and scores 1.0 in all
  three of its runs).
- **The planner, corrected.** One run suggested that the table planner alone explained
  GT09's cost. Across the runs: with the planner on `gpt-5.4`, GT09's largest prompt reached
  294K tokens (above the 272K price tier) in all three `gpt-5.4` runs and the type-router
  run; with the planner on mini, the largest prompt was 100–220K in Router B's three runs,
  but one Router B + check rerun reached 294K too (951K input tokens). A mini planner makes
  the large evidence less likely; only a cap on prompt size would rule it out.
- **The single runs stay exploratory:** the type router (0.816 at $0.301) and the answer
  check alone (0.842 at $0.128) were not repeated. The answer check's one run suggests a
  cheaper point than Router B; the combination's three runs did not reproduce it.


# Final validation: 5.1, 6.1, and 7.1 survivors

**Status:** complete (2026-10-04, 15:41–16:26).

**Why.** GT was the working set for every 7.1 choice; validation was reserved for one
final comparison campaign, with three runs per survivor. The operational selection goal
was for Router B to score at least as well as the 6.1 survivor in these held-out runs.

**Runs** (`cost_efficiency/wikipedia_GT_validation_set/`, its own manifest, logs, and
console; interleaved, one at a time): the three Router B runs (`xenodochial_tarjan`,
`thirsty_stallman`, `sweet_dijkstra`) are the **7.1 Final Survivor**. The three mini-only
7.1 runs are retained in the recorded run folder but omitted from this final survivor
comparison: they reproduced the 6.1 mean (0.860) at effectively the same cost and add no
new lineage step. No further all-`gpt-5.4` run: its only validation run (6.1, 0.960) stays
a reference outside the comparison.

**The comparison folder** (`final_validation/`, built by
[`analyzers/build_final_validation.py`](analyzers/build_final_validation.py)): copies of
three runs per survivor in `runs/experiments/` and `runs/telemetry/`, each copy's
`experiment_name` set to one label per survivor (only on the copies; the recorded files are
unchanged), file times preserved, and `provenance.csv` listing every copy's source and
original name. The 5.1 survivor is represented by `quirky_adleman` (its one validation run
with cost telemetry) and the two most recent of its four 2026-09-23 runs, `eager_rossum`
and `objective_hopper`; their mean, 0.880, equals the four-run mean recorded in 5.1.

**Final outputs:**

- `final_validation/ragas_validation_5_1_6_1_7_1.pdf`: recall and accuracy (the original
  analyzer);
- `final_validation/efficiency_validation_5_1_6_1_7_1.pdf`: accuracy against cost and
  latency (the efficiency analyzer, baseline the 6.1 survivor), with its tables in
  `efficiency_validation_5_1_6_1_7_1_tables/`.

Rebuild the three-survivor comparison without changing the recorded source runs:

```bash
python "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/analyzers/build_final_validation.py"
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments.py \
  --experiments-dir "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/final_validation/runs" \
  --output "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/final_validation/ragas_validation_5_1_6_1_7_1.pdf" \
  --title "Final validation: survivor progression from 5.1 to 7.1"
python wikipedia_retrieval_engine/utils/analyze_ragas_experiments_efficiency.py \
  --experiments-dir "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/final_validation/runs" \
  --baseline "6.1 survivor" \
  --output "wikipedia_retrieval_engine/Capstone Checkpoint 7.1/final_validation/efficiency_validation_5_1_6_1_7_1.pdf" \
  --title "Survivor quality, cost, and latency"
```

## Results

| Validation, 25 questions, 3 runs each | Quality (runs) | Pass / partial / fail | Article recall | List $/q | Billed $/q | Seconds/q | List $ per passing answer |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5.1 survivor | 0.880 (0.860, 0.900, 0.880) | 82.7% / 10.7% / 6.7% | 100.0% | 0.0431 (one run with telemetry) | 0.0356 | 16.1 | 0.054 |
| 6.1 survivor | 0.860 (0.880, 0.800, 0.900) | 80.0% / 12.0% / 8.0% | 100.0% | 0.0422 | 0.0296 | 12.8 | 0.053 |
| **7.1 Final Survivor** | **0.933** (0.940, 0.920, 0.940) | **89.3% / 8.0% / 2.7%** | 99.3% | 0.1068 | 0.0751 | 18.7 | 0.120 |

**Paired against the 6.1 survivor:**

- **7.1 Final Survivor: +0.073** (6 questions better, 1 worse; p = 0.094), for +$0.065 per question at
  list price and +5.9 s. Gains on VAL24 (0.33 → 1.00), VAL06 (0.33 → 1.00), VAL08 and VAL14
  (0.83 → 1.00), VAL02 and VAL05; the one loss is VAL10 (0.67 → 0.50), the question where
  one Router B run missed an article (recall 99.3%).
- 5.1: +0.020 (p = 0.69).

**Reading.**

- **The 7.1 Final Survivor met the operational selection goal in these runs.** It scored
  above the 6.1 survivor in all three held-out runs (0.920–0.940 against 0.800–0.900),
  with the lowest observed fail rate of any survivor (2.7%). The mean improvement over
  6.1 was +0.073 with p = 0.094, so this small comparison does not establish a statistically
  significant general improvement. On GT, Router B was 0.018 below all-`gpt-5.4`
  (p = 0.81) at half its list cost.
- **The price is 2.5x the mini survivors** ($0.107 against $0.042–0.044 at list price) and
  6 s per question; a passing answer costs $0.12 against $0.05. That is the price of
  `gpt-5.4` in the two roles that judge the evidence and write the answer, on the questions
  the TOC review routes to the table path.
- **The 7.1 Final Survivor is Router B:** the safeguarded graph (input sanitizer, guarded answer prompt,
  corrected grounding check) with the routing step, `gpt-5.4-mini` by default, and the
  assessor and the answer on `gpt-5.4` when the TOC review flags a table.

**Why recall dipped to 99.3%.** This is one miss on VAL10 in one of 75 question-runs.
Initial top-4 retrieval found the historical life-expectancy
article but not the exact UN population-list article. After two incomplete table rounds,
the assessor put the still-missing population source into `table_requests` with no table
ID and emitted no `retrieval_request`. The bounded router gives table requests priority;
with the table budget exhausted and no retrieval request left, it terminated before the
graph-seeded retrieval stage. The other two 7.1 Final Survivor runs kept a retrieval
request alive, found both required articles, and recorded 1.000 recall. The evidence
points to a request-typing and termination edge case between the assessor and router;
additional runs would be needed to determine how often it recurs.

# Final technical conclusion

Router B is the selected architecture because it concentrates the stronger model in the
two roles with the clearest measured benefit while leaving the table planner on the
smaller model. The decision is supported by three repeated GT runs and three held-out
validation runs, not by the earlier one-run routing simulations. The results support a
practical cost-quality choice for these datasets; they do not establish equivalence to
all-`gpt-5.4` or guarantee the same behavior on a different workload.

The first follow-up improvements should be:

1. Add deterministic limits to table-request loops, prompt size, and accumulated
   evidence so repeated table work cannot create extreme tail cost.
2. Replace the current name-oriented grounding heuristic with evidence-linked claim
   verification, then tune it on a larger labeled set to reduce false quarantines without
   weakening protection against fabricated claims.
3. Monitor routing decisions, article recall, and per-question tail cost on a larger and
   more varied evaluation set.

## Supporting material

- [`cost_efficiency/reports/gt_three_run_comparison.pdf`](cost_efficiency/reports/gt_three_run_comparison.pdf): repeated GT comparison used for the routing decision.
- [`final_validation/ragas_validation_5_1_6_1_7_1.pdf`](final_validation/ragas_validation_5_1_6_1_7_1.pdf): final survivor accuracy and recall.
- [`final_validation/efficiency_validation_5_1_6_1_7_1.pdf`](final_validation/efficiency_validation_5_1_6_1_7_1.pdf): final survivor quality, cost, and latency.
- [`final_validation/provenance.csv`](final_validation/provenance.csv): source run for every copied final-validation result.
- [`cost_efficiency/run_manifest.csv`](cost_efficiency/run_manifest.csv): GT experiment order and run locations.

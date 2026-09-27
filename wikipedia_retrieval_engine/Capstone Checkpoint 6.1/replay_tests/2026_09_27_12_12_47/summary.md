# Answer replay summary: 2026_09_27_12_12_47

Replayed question-runs: 84. Judge: openai/gpt-5.4-mini. Unchanged question-runs keep their 5.1 verdicts in the projections.

## Quality on the replayed question-runs

| Arm | n | Quality | Pass | Partial | Fail | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sections|openai/gpt-5.4-mini | 84 | 0.929 | 74 | 8 | 2 | 0 |
| whole_per_question|openai/gpt-5.4-mini | 84 | 0.964 | 80 | 2 | 2 | 0 |
| whole_per_article|openai/gpt-5.4-mini | 84 | 0.958 | 79 | 3 | 2 | 0 |

## Paired differences (same question-run, one factor changed)

| Arm | Against | Pairs | Mean difference | Better | Worse | Same | Wilcoxon p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| whole_per_question|openai/gpt-5.4-mini | sections|openai/gpt-5.4-mini | 84 | +0.036 | 8 | 2 | 74 | 0.217 |
| whole_per_article|openai/gpt-5.4-mini | sections|openai/gpt-5.4-mini | 84 | +0.030 | 8 | 3 | 73 | 0.340 |

## Noise floor

The control (sections|openai/gpt-5.4-mini) re-answers the exact 5.1 contexts. Its verdict differs from the original 5.1 verdict on 6 of 84 question-runs (mean difference -0.036): the run-to-run variation of the answer model and the judge on identical input.

## Projected quality on the selected runs

Replayed verdicts on the replayed question-runs, 5.1 verdicts on the rest. Only arms that use the 5.1 answer model (openai/gpt-5.4-mini) or replayed every question-run are projected.

| Arm | validation (4 runs) | gt (3 runs) |
| --- | ---: | ---: |
| 5.1 as recorded | 0.880 | 0.754 |
| sections|openai/gpt-5.4-mini | 0.875 | 0.711 |
| whole_per_question|openai/gpt-5.4-mini | 0.885 | 0.746 |
| whole_per_article|openai/gpt-5.4-mini | 0.880 | 0.746 |

## Cost and latency per answer call (replayed question-runs)

List price charges every input token at the full rate (no caching): the fair comparison, because repeated runs of the same prompt get cache hits that distinct user questions would not.

| Arm | Context chars | Input tokens | Cached share | Output tokens | List $ | Billed $ | Provider $ | Latency median | Latency p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sections|openai/gpt-5.4-mini | 44,239 | 10,700 | 19% | 192 | 0.00889 | 0.00751 | 0.00751 | 1.9s | 2.7s |
| whole_per_question|openai/gpt-5.4-mini | 100,211 | 26,761 | 64% | 188 | 0.02091 | 0.00944 | 0.00944 | 1.9s | 2.7s |
| whole_per_article|openai/gpt-5.4-mini | 118,355 | 31,811 | 62% | 188 | 0.02470 | 0.01141 | 0.01141 | 1.9s | 2.7s |

## Answer cost per question-run over the selected runs

Change against the control, spread over all 157 question-runs of the selected runs (unchanged question-runs add 0), and as a share of a whole 5.1 question-run ($0.0415 at list price, $0.0313 billed, from OpenRouter analytics).

| Arm | Change, list | Share of question, list | Change, billed | Share of question, billed |
| --- | ---: | ---: | ---: | ---: |
| whole_per_question|openai/gpt-5.4-mini | +0.00644 | +15.5% | +0.00103 | +3.3% |
| whole_per_article|openai/gpt-5.4-mini | +0.00846 | +20.4% | +0.00209 | +6.7% |

**Spend of this replay:** 168 answer calls, $2.8217 at list price, $1.5898 billed estimate, $1.5898 reported by OpenRouter; plus 168 judge calls (not metered here; OpenRouter origin .../judge).

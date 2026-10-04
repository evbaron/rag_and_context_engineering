# Prompt replay: legacy against guarded answer prompt (2026_10_04_09_34_37)

96 answer calls over 48 saved question-runs (8 GT questions); 96 judged.

## Quality: prompt by evidence source

| Evidence from | Legacy prompt | Guarded prompt | Recorded in the run |
| --- | ---: | ---: | ---: |
| 6.1 survivor runs | 0.688 | 0.688 | 0.708 |
| 7.1 final runs | 0.688 | 0.688 | 0.521 |
| Both | 0.688 | 0.688 | |

## Paired: the same context under both prompts

- Contexts with both answers judged: 48
- Guarded minus legacy: +0.000 on average
- Guarded better on 8, worse on 9, the same on 31; Wilcoxon p = 0.942

## Noise floor

The arm that matches each context's own run re-answers the recorded condition: 22 of 48 verdicts differ from the recorded ones (recorded 0.615, replayed 0.688). On 7.1 contexts the recorded answers carried the grounding label when the check acted; the replay judges the raw answer.

## Per question

| Question | Legacy | Guarded | Legacy hedges | Guarded hedges | Note |
| --- | ---: | ---: | ---: | ---: | --- |
| GT05 | 0.83 | 1.00 | 1/6 | 4/6 | 'Totals' row mentioned: legacy 1/6, guarded 0/6 |
| GT07 | 0.33 | 0.33 | 0/6 | 0/6 |  |
| GT09 | 0.92 | 0.83 | 2/6 | 5/6 |  |
| GT10 | 0.83 | 0.83 | 0/6 | 0/6 |  |
| GT11 | 0.00 | 0.17 | 0/6 | 0/6 |  |
| GT15 | 1.00 | 1.00 | 2/6 | 3/6 |  |
| GT16 | 0.83 | 0.58 | 0/6 | 1/6 | Joe Biden: legacy 4/6, guarded 2/6; Hillary: legacy 5/6, guarded 5/6 |
| GT19 | 0.75 | 0.75 | 3/6 | 4/6 |  |

## Grounding check on the replayed answers (not applied; recorded only)

| Arm | Flagged | Flagged and passed by the judge |
| --- | ---: | ---: |
| legacy | 9/48 | 6 |
| guarded | 8/48 | 6 |

## Cost

- Answer calls: $1.83 at list price, $1.26 billed estimate, $1.26 reported by OpenRouter.
- Judge calls: about $0.08 (not in the telemetry; `…/judge` origin).

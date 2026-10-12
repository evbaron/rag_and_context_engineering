# Log analysis: what every run cost, and how long it took

Every question answered since Checkpoint 1 is in the logs, with every model call's
role, tokens, and time. This folder adds the analysis that turns those logs into cost
and latency, next to quality, across the whole project, in preparation for the
performance and cost work.

## New in this folder

| File | What it does |
|---|---|
| `ragkit/reports/performance.py` | Cost and time per run and per role; quality against cost; the slowest questions; CSV files for charts |
| `samples/analyze_logs.py` | Prints the headline numbers and writes the performance report |

## How to use it

```
python samples/analyze_logs.py                       # every run since Checkpoint 1
python samples/analyze_logs.py --checkpoint 3 4 5    # the evaluated runs
python samples/analyze_logs.py --since 2026-10-01
python -m ragkit.reports.performance --experiment cp3_hybrid
```

The report has four parts:

| Part | What it answers |
|---|---|
| Runs | Per run: questions, errors, quality, recall, calls, tokens, cost, and time per question (median and 95th percentile) |
| Quality against cost and time | The scored runs, best quality first: is the best run worth its extra cost and time? |
| Where the money goes | Tokens and cost by role (answer, plan, decompose, embedding, judge, ...) and each role's share of the system's cost |
| Slowest questions | The ten slowest questions and their runs; read their log lines to see why |

The judge's cost is shown but kept out of the system's cost: it is the price of
measuring, not of answering. Two CSV files (runs and roles) are written next to the
report, for charts in Excel or Google Sheets.

## Questions to ask of the logs

1. Which role spends the most, and does it have to? (Planning calls see shortened
   passages; does the answer call need every passage it gets?)
2. Is the most accurate configuration worth its cost and time, given the spread
   between repeated runs in the quality report?
3. Which questions are slow, and what did the system do on them?

## A note on the numbers

Costs are estimates at list prices from `ragkit/pricing.json` (dated in the file). The
provider's bill can be lower when it serves repeated prompt text from its cache; the
logs record cached tokens per call, and the estimate prices them at the cached rate.

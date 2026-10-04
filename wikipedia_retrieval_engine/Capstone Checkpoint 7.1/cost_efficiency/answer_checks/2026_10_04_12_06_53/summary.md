# Jev answer check (2026_10_04_12_06_53)

214 answers, 213 checked; 57 with excerpted evidence; cost $0.1479; median latency 0.33 s.

## Does Jev's score separate the judge's non-pass answers from its passes?

AUC: the chance a non-pass answer scores lower than a pass answer (0.5 = no signal, 1.0 = perfect).

| Answers | Non-pass | Grounded AUC | Complete AUC | min(both) AUC |
| --- | ---: | ---: | ---: | ---: |
| GT | 36 of 113 | 0.68 | 0.76 | 0.71 |
| Validation | 18 of 100 | 0.83 | 0.93 | 0.91 |
| All | 54 of 213 | 0.73 | 0.83 | 0.79 |
| Whole evidence only | 35 of 156 | 0.70 | 0.80 | 0.76 |

## Escalate when min(grounded, complete) is below the threshold

| Threshold | Non-pass caught | Passes escalated (false alarms) |
| ---: | ---: | ---: |
| 0.3 | 25/54 | 12/159 |
| 0.5 | 35/54 | 17/159 |
| 0.7 | 43/54 | 38/159 |
| 0.8 | 43/54 | 65/159 |
| 0.9 | 46/54 | 119/159 |

## Simulated: mini, then Jev, then gpt-5.4 when Jev says no

**GT test set** (cheap: 7.1 final, 3 runs; strong: 7.1 final, gpt-5.4)

| Policy | Quality | List $/q | Seconds/q | Escalated |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.711 | 0.0502 | 13.8 | 0% |
| All gpt-5.4 | 0.868 | 0.3387 | 24.2 | 100% |
| Jev check at 0.3 (excerpts for large evidence) | 0.798 | 0.1514 | 21.0 | 23% |
| Jev check at 0.5 (excerpts for large evidence) | 0.842 | 0.1891 | 25.2 | 35% |
| Jev check at 0.7 (excerpts for large evidence) | 0.833 | 0.3262 | 29.2 | 51% |
| Jev check at 0.8 (excerpts for large evidence) | 0.833 | 0.3428 | 31.9 | 63% |
| Jev check at 0.9 (excerpts for large evidence) | 0.877 | 0.3679 | 35.3 | 81% |
| Jev check at 0.5, large evidence always escalated | 0.860 | 0.2813 | 28.9 | 53% |
| Jev check at 0.8, large evidence always escalated | 0.860 | 0.3651 | 33.4 | 72% |

**Validation set** (cheap: 6.1 survivor, 7.1 final, 4 runs; strong: 6.1 survivor, gpt-5.4)

| Policy | Quality | List $/q | Seconds/q | Escalated |
| --- | ---: | ---: | ---: | ---: |
| All mini | 0.870 | 0.0431 | 12.4 | 0% |
| All gpt-5.4 | 0.960 | 0.1524 | 21.6 | 100% |
| Jev check at 0.3 (excerpts for large evidence) | 0.920 | 0.0908 | 18.3 | 15% |
| Jev check at 0.5 (excerpts for large evidence) | 0.940 | 0.1057 | 19.7 | 19% |
| Jev check at 0.7 (excerpts for large evidence) | 0.955 | 0.1267 | 22.1 | 30% |
| Jev check at 0.8 (excerpts for large evidence) | 0.955 | 0.1367 | 24.0 | 42% |
| Jev check at 0.9 (excerpts for large evidence) | 0.955 | 0.1700 | 30.0 | 75% |
| Jev check at 0.5, large evidence always escalated | 0.940 | 0.1349 | 22.9 | 36% |
| Jev check at 0.8, large evidence always escalated | 0.955 | 0.1544 | 26.0 | 52% |


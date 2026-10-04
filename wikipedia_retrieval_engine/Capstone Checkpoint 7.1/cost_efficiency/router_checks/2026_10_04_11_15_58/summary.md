# Jev route check (2026_10_04_11_15_58)

132 calls (132 ok) over 44 questions; model typesafe/jev-1.13; total cost $0.0023; median latency 0.20 s.

Stability across repeats: same choice on 43/44 questions; largest spread of p(simple) 0.090.

## Agreement with the answer key, by threshold

The key routes a question to mini when it is a text question (fewer than half of the mini runs flagged a table) and has one source article. Route from the mean p(simple) over the repeats.

| Threshold | Correct | Complex sent to mini (dangerous) | Simple sent to gpt-5.4 (costly) | Sent to mini |
| ---: | ---: | ---: | ---: | ---: |
| 0.5 | 34/44 | 10 GT01, GT04, VAL11, VAL12, VAL13, VAL14, VAL18, VAL19, VAL20, VAL21 | 0  | 21 |
| 0.6 | 34/44 | 9 GT01, GT04, VAL11, VAL12, VAL13, VAL14, VAL19, VAL20, VAL21 | 1 GT18 | 19 |
| 0.7 | 33/44 | 8 GT01, GT04, VAL11, VAL12, VAL13, VAL14, VAL19, VAL20 | 3 GT02, GT18, VAL23 | 16 |
| 0.8 | 32/44 | 8 GT01, GT04, VAL11, VAL12, VAL13, VAL14, VAL19, VAL20 | 4 GT02, GT18, VAL04, VAL23 | 15 |
| 0.9 | 32/44 | 5 GT01, GT04, VAL11, VAL12, VAL19 | 7 GT02, GT18, VAL01, VAL04, VAL22, VAL23, VAL25 | 9 |

## Per question

| Question | Category | Source articles | Mini runs flagging a table | Key | Mean p(simple) | Route at 0.8 |
| --- | --- | ---: | ---: | --- | ---: | --- |
| GT01 | Direct fact and quotation | 1 | 100% | complex | 0.963 | cheap |
| GT02 | Open-list question and quotations | 1 | 0% | simple | 0.673 | strong |
| GT03 | Cross-article exhaustive intersection and winner classification | 3 | 100% | complex | 0.000 | strong |
| GT04 | Direct fact | 1 | 100% | complex | 1.000 | cheap |
| GT05 | Table lookup | 1 | 100% | complex | 0.123 | strong |
| GT06 | Process explanation | 1 | 0% | simple | 0.990 | cheap |
| GT07 | Temporal aggregation | 1 | 100% | complex | 0.000 | strong |
| GT08 | Uncertainty and conflicting estimates | 1 | 100% | complex | 0.000 | strong |
| GT09 | Cross-table comparison | 2 | 100% | complex | 0.000 | strong |
| GT10 | Program-history filter | 1 | 100% | complex | 0.000 | strong |
| GT11 | Program-history filter | 1 | 100% | complex | 0.000 | strong |
| GT12 | Historical entity resolution | 3 | 100% | complex | 0.010 | strong |
| GT13 | Historical identity timeline | 1 | 100% | complex | 0.053 | strong |
| GT14 | People connection: shared work and awards | 4 | 100% | complex | 0.127 | strong |
| GT15 | People connection: repeated collaboration | 2 | 100% | complex | 0.297 | strong |
| GT16 | People connection: intermediary person | 2 | 0% | complex | 0.323 | strong |
| GT17 | Geopolitical state-formation timeline | 2 | 17% | complex | 0.010 | strong |
| GT18 | Geopolitical entity relationships | 1 | 0% | simple | 0.513 | strong |
| GT19 | Geopolitical cross-table calculation | 2 | 100% | complex | 0.000 | strong |
| VAL01 | Direct fact and quotation | 1 | 25% | simple | 0.853 | cheap |
| VAL02 | Cross-article exhaustive intersection and winner classification | 3 | 75% | complex | 0.000 | strong |
| VAL03 | Table lookup | 1 | 100% | complex | 0.057 | strong |
| VAL04 | Process explanation | 1 | 0% | simple | 0.707 | strong |
| VAL05 | Temporal aggregation | 1 | 100% | complex | 0.000 | strong |
| VAL06 | Uncertainty and conflicting estimates | 1 | 100% | complex | 0.000 | strong |
| VAL07 | Program-history filter | 1 | 100% | complex | 0.000 | strong |
| VAL08 | Historical identity timeline | 1 | 100% | complex | 0.197 | strong |
| VAL09 | People connection: intermediary person | 2 | 0% | complex | 0.023 | strong |
| VAL10 | Geopolitical cross-table calculation | 2 | 100% | complex | 0.000 | strong |
| VAL11 | Process explanation | 2 | 0% | complex | 0.957 | cheap |
| VAL12 | Process explanation | 2 | 0% | complex | 0.973 | cheap |
| VAL13 | Inference limitation | 2 | 0% | complex | 0.823 | cheap |
| VAL14 | Direct fact | 1 | 75% | complex | 0.870 | cheap |
| VAL15 | Process explanation | 1 | 0% | simple | 0.940 | cheap |
| VAL16 | Diagnostic reasoning and limitations | 1 | 0% | simple | 0.940 | cheap |
| VAL17 | Uncertainty and conflicting estimates | 1 | 0% | simple | 0.923 | cheap |
| VAL18 | Uncertainty and conflicting estimates | 1 | 100% | complex | 0.560 | strong |
| VAL19 | Process explanation | 1 | 50% | complex | 0.953 | cheap |
| VAL20 | Direct fact | 1 | 50% | complex | 0.800 | cheap |
| VAL21 | People connection: shared work and roles | 1 | 100% | complex | 0.667 | strong |
| VAL22 | Temporal aggregation | 1 | 0% | simple | 0.823 | cheap |
| VAL23 | Process explanation | 1 | 25% | simple | 0.680 | strong |
| VAL24 | Cross-article comparison | 2 | 75% | complex | 0.000 | strong |
| VAL25 | Process explanation | 1 | 0% | simple | 0.807 | cheap |

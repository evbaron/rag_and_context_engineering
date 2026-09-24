# Sample AgentState — GT10 (deterministic table computation)

*Run `logs/2026_09_22_14_03_17` · one question's full agent state, annotated. Shows how the graph coordinates retrieval, self-assessment, and a deterministic tool call.*

## Question
> Using the Sport/Years table in the Wikipedia article on the Winter Olympic Games, which listed sports first entered the official Winter Olympic program in 1950 or later? Give the first year for each.

## 1 · Initial retrieval — entity decomposition
The question is decomposed into canonical-entity queries (plus the full question), each run against the section index:
- `Winter Olympic Games`
- `Using the Sport/Years table in the Wikipedia article on the Winter Olympic Games, which listed sports first entered the official Winter Olympic program in 1950 or later? Give the first year for each.`

## 2 · TOC review — keep the right article, select sections, flag the table
One fused call judges each candidate by its **table of contents** (not a snippet), then selects the sections to read and the exact table artifact to compute over:

- **KEEP · Winter_Olympic_Games.html** — "the target article… contains the Winter Olympic sports table needed to identify first official program years." → sections `["Sports", "Current sports"]`, `needs_table_reader=True`, table `a555de5b320201e3f6f2a6d0`
- reject · List_of_Olympic_Games_host_cities.html — about host cities, not the sports-program table
- reject · Summer_Olympic_Games.html — Summer, not the Winter source needed
- reject · 1992_Winter_Olympics.html — one edition, not the cross-year program table
- reject · 1988_Winter_Olympics.html — one edition, not the cross-year program table

→ **selected_articles**: `["Winter_Olympic_Games.html"]` (4 distractors correctly dropped)

## 3 · Evidence assembled (additive)
- `toc_selected_section` — Winter_Olympic_Games.html#section-013-00
- `toc_selected_section` — Winter_Olympic_Games.html#section-014-00
- `toc_selected_table` — Winter_Olympic_Games.html#table-001-688d334e5c
- `table_computation` — Winter_Olympic_Games.html#table-001-688d334e5c#computed-table-r1-1-78303d04ed0f

## 4 · Assessment loop — the agent reasons about its own evidence
**Round 1** · `ready_to_answer=False` · table_requests=1
> The evidence includes the relevant table and several rows with post-1950 start years, but only 9 of 16 rows are displayed in the excerpt. Because the question requires an exhaustive list of all qualifying sports, we need table computation on the full table artifact to ensure no qualifying sport is missed.

**Round 2** · `ready_to_answer=True` · table_requests=0
> The supplied deterministic table-computation result directly answers the question by filtering the Winter Olympic Games Sports/Years table for sports with first official program year >= 1950 and returning each sport with its first year. No additional retrieval or table work is needed.

## 5 · Deterministic table computation (the tool call)
Instead of letting the model read rows by eye, a planner emits a validated plan and **Python** executes it over the normalized table:
```json
{
  "operation": "filter",
  "selected_columns": [
    "Sport",
    "Years"
  ],
  "predicates": [
    {
      "column": "Years",
      "op": "year_min_gte",
      "value": 1950,
      "value2": null
    }
  ]
}
```
**Computed result — the rows that satisfy `first year ≥ 1950`:**

| Sport | Years |
| --- | --- |
| Biathlon | Since 1960 |
| Freestyle skiing | Since 1992 |
| Luge | Since 1964 |
| Short track speed skating | Since 1992 |
| Ski mountaineering | Since 2026 |
| Snowboarding | Since 1998 |

**Source cells (provenance):** `table-001-688d334e5c:r3:c1, table-001-688d334e5c:r3:c2, table-001-688d334e5c:r8:c1, table-001-688d334e5c:r8:c2, table-001-688d334e5c:r10:c1, table-001-688d334e5c:r10:c2, table-001-688d334e5c:r12:c1, table-001-688d334e5c:r12:c2` …

## 6 · Final answer (grounded in the computed rows)
Biathlon — 1960; Luge — 1964; Freestyle skiing — 1992; Short-track speed skating — 1992; Snowboarding — 1998; Ski mountaineering — 2026.

*On a clean run this scores **PASS** — it matches the ground-truth reference exactly. The point of interest is **how** it got there: the agent declined to answer from raw rows (Round 1), requested a deterministic computation, and answered from the exact filtered cells with provenance (Round 2).*

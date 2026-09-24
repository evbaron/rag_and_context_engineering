# Sample AgentState — VAL25 (the breadth refinement in action)

*Run `logs/2026_09_23_10_14_16` (held-out validation) · a **synthesis** question with no tables. Shows the readiness **nudge** overriding a premature 'ready' so the answer is built on fuller context.*

## Question
> Why do stratovolcanoes tend to have steep profiles and explosive eruptions? Connect their layered structure and magma properties to eruption behavior, and name two hazards emphasized in the article that are more immediately deadly than a typical slow lava flow.

## 1 · Initial retrieval — decomposition
- `Why do stratovolcanoes tend to have steep profiles and explosive eruptions? Connect their layered structure and magma properties to eruption behavior, and name two hazards emphasized in the article that are more immediately deadly than a typical slow lava flow.`

## 2 · TOC review — one article, many sections, **no table**
- **KEEP · Stratovolcano.html** → `needs_table_reader=False`, table_ids=[]
  sections: ['Formation', 'Hazards', 'Ash', 'Lava', 'Volcanic bombs', 'Lahar', 'Volcanic gas', 'Eruptions that affected global climate']

## 3 · Assessment loop — the nudge earns its keep
**Round 1** · `ready_to_answer=False`
> The supplied evidence is sufficient. The Formation section supports the magma explanation: magma rises, incorporates silica-rich crust, and accumulates volatiles/pressure before eruption; the Hazards 

**Round 2** · `ready_to_answer=True`
> The supplied evidence is sufficient. The lead section supports the structural and magma-property explanation for steep profiles and explosivity, and the Hazards section names two deadly hazards (pyroc

Note **Round 1**: the assessor's own words say the evidence is *sufficient*, yet `ready_to_answer=False`. That is the **breadth nudge** refusing a first-pass answer for a non-table question — forcing one escalation into `article_broaden` before answering.

## 4 · Breadth route fires
Evidence stages: {'toc_selected_section': 8, 'broadened_article_sections': 2} — the initial TOC sections **plus** `broadened_article_sections` (more of the same article, additive). `retrieval_attempts=2`, `table_attempts=0`.

## 5 · Final answer — verdict: **PASS**
Grounded in the widened context, with direct quotes from the article:
> Stratovolcanoes are described as “a typically conical volcano built up by many alternating layers (strata) of hardened lava and tephra,” and they are “characterized by a steep profile with a summit crater and explosive eruptions.” The article links this behavior to magma properties: the lava is “typically cool[ing] and …

**Why it matters (Step 3/4):** single-section evidence was starving synthesis questions like this on the held-out set. The nudge + breadth route recovered them — validation quality 0.845 → 0.880 — without touching the table path or recall.

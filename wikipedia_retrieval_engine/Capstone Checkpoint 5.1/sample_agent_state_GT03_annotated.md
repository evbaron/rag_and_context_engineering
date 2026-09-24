# Sample AgentState — GT03 (multi-table orchestration + an honest limitation)

*Run `logs/2026_09_22_13_20_23` · shows the agent orchestrating **three** table computations in one pass — and where the pipeline hits a real wall: presentation ('layout') tables.*

## Question
> Considering the complete winners-and-nominees lists for the 68th, 70th, and 74th Academy Awards, identify every person who was nominated at all three ceremonies. For each person, give at least one nominated work from each ceremony. Also determine whether each person won at any of those three ceremonies; if so, identify the ceremony, work, and award.

## 1 · Initial retrieval — decomposition into the three ceremonies
- `74th Academy Awards`
- `68th Academy Awards`
- `70th Academy Awards`
- `Considering the complete winners-and-nominees lists for the 68th, 70th, and 74th Academy Awards, identify every person who was nominated at all three ceremonies. For each person, give at least one nominated work from each ceremony. Also determine whether each person won at any of those three ceremonies; if so, identify the ceremony, work, and award.`

## 2 · TOC review — keeps all three ceremony articles
- **KEEP · 74th_Academy_Awards.html** → section `['Winners and nominees']`, table `['table-001-908aa46185']`
- **KEEP · 68th_Academy_Awards.html** → section `['Winners and nominees']`, table `['table-001-5ee67d5c31']`
- **KEEP · 70th_Academy_Awards.html** → section `['Winners and nominees']`, table `['table-001-26584ccd78']`

→ **selected_articles**: ['74th_Academy_Awards.html', '68th_Academy_Awards.html', '70th_Academy_Awards.html'] — a genuine multi-article question.

## 3 · Assessment loop
**Round 1** · `ready_to_answer=False` · table_requests=3
> The supplied evidence only provides introductory prose for each ceremony page and does not expose the actual nominees by category. The user’s question requires a cross-ceremony intersection of nominees, plus award-winning status and the ass

**Round 2** · `ready_to_answer=True` · table_requests=0
> The table-computation excerpts for the 68th, 70th, and 74th Academy Awards each provide the full nominee lists by category, with winners marked. That is enough to identify people nominated at all three ceremonies, name at least one nominate

## 4 · Three deterministic lookups fire (one per ceremony)
The gateway routes **all three** tables through the executor — `table_computation` evidence x3. This is real multistep tool orchestration.

## 5 · …but the tables are *layout* tables — the wall
The executor flags it: **warning = ['No explicit header row detected; generated positional columns.']**. The 'rows' are not per-nominee; each cell is an entire award category mashed into one string:
```
column_1: Best Picture Braveheart – Mel Gibson , Bruce Davey and Alan Ladd Jr. , producers Apollo 13 – Brian Grazer , producer Babe – George Miller , Doug Mitch…
column_2: Best Directing Mel Gibson – Braveheart Chris Noonan – Babe Tim Robbins – Dead Man Walking Mike Figgis – Leaving Las Vegas Michael Radford – Il Postino…
```
There are no per-nominee rows to intersect, so deterministic extraction returns blobs and the model must parse names out of prose — exactly what determinism was meant to avoid.

## 6 · Final answer — verdict: **FAIL**
The model hedges, unable to verify nominees across the blob cells:
> From the provided winners-and-nominees lists, the people I can identify as being nominated at all three ceremonies are:  - **Denzel Washington**   - 68th: **The Preacher's Wife** (not in the provided 68th table excerpt, so I can’t verify from the given context)   - 70th: **no nomination shown in the …

**Limitation (Step 5):** the fix is upstream of routing — a *parser* that explodes layout tables into per-nominee rows. The agent orchestrated correctly; the representation defeated it.

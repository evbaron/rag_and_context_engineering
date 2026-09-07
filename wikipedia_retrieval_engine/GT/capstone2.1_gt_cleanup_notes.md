# Ground Truth Evolution from Checkpoint 2.1 to Checkpoint 3.1

## Current ground-truth artifact

Ground truth location: `GT/wikipedia_GT.csv`

The CSV is based on the ground-truth questions from Capstone Checkpoint 2.1. The questions and reference answers were revised so that they are precise, gradeable, and supported by articles in the local Wikipedia corpus. Additional questions broaden the evaluation from direct fact and quotation retrieval to multi-article synthesis, entity resolution, calculation, uncertainty handling, and inference.

The cleanup was completed with assistance from ChatGPT. I reviewed the CSV structure, source-file coverage, reference answers, grading notes, and scope assumptions against the local corpus and made the final decisions about the evaluation set.

## CSV contents

The CSV contains 19 evaluation cases with consecutive IDs from GT01 through GT19. It
is intentionally stored as a CSV so both the evaluation scripts and pandas can load a
single canonical artifact without requiring Excel.

The dataset uses nine fields for every test case:

1. **ID:** stable identifier used to join questions to evaluation results.
2. **Category:** type of retrieval or reasoning task.
3. **Question:** prompt presented to the retrieval-augmented system.
4. **Reference answer:** expected answer supported by the corpus.
5. **Grading notes:** minimum requirements for a passing answer and acceptable variants.
6. **Source articles:** local article files that contain the required evidence.
7. **Scope and assumptions:** boundaries needed to prevent ambiguous grading.
8. **Evaluation role:** capability or failure mode tested by the question.
9. **Complexity:** approximate number of sources and reasoning steps required.

Definitions that were previously considered for a separate worksheet are now captured
directly in the `Grading notes` and `Scope and assumptions` fields. These include
Russia-related identities, official Olympic program debuts, time bounds, quotation
fidelity, open-list grading, and limits on correlation or causal inference.

## Evaluation coverage

The current set includes:

- Direct fact retrieval, table lookup, process explanation, and quotation fidelity.
- Open-list questions where multiple supported answers may be valid.
- Temporal filtering, aggregation, and historical-name normalization.
- Cross-article intersections and multi-hop relationships among people, works, awards, and political roles.
- Geopolitical state formation and distinctions among related legal or geographic entities.
- Cross-table joining and arithmetic using population and life-expectancy data.
- Conflicting estimates, uncertainty preservation, date mismatches, and limits on causal inference.

## New questions added after the original audit

- **GT14:** connects Damien Chazelle and Emma Stone through *La La Land* and the 89th Academy Awards.
- **GT15:** connects Chris Columbus and Daniel Radcliffe through the first two Harry Potter films while testing name and title disambiguation.
- **GT16:** identifies Hillary Clinton as the intermediary connecting Bill Clinton and Barack Obama through family, election, and administration relationships.
- **GT17:** constructs the state-formation sequence from British India to India and Pakistan in 1947 and from East Pakistan to Bangladesh in 1971.
- **GT18:** distinguishes Vatican City, Rome, Italy, and the Holy See and identifies the Lateran Treaty as the basis for Vatican City independence.
- **GT19:** compares India and mainland China using 2023 population estimates and 2010–2015 life expectancy, requiring a table join, arithmetic, and an explicit warning about the date mismatch and causal inference.

## Verification status

- The CSV contains 19 questions and nine populated evaluation fields for each question.
- IDs are unique and consecutive from GT01 through GT19.
- The CSV contains no blank evaluation cells.
- All 31 article references listed in the CSV resolve to files in `retrievers/db/article_text/wikipedia_plain_text`.
- The reference answers and grading notes define required facts, acceptable alternatives, exclusions, and uncertainty where needed.
- The local corpus is the evidence boundary for evaluation; outside model knowledge should not be required for a passing response.

## Audit of previous GT

Historical source workbook: `Capstone Checkpoint 2.1/wikipedia Q-A GT.xlsx`

The historical workbook now remains inside the Checkpoint 2.1 folder. It is preserved
only as evidence for that checkpoint and should not be used as the current evaluation
input.

Corpus reviewed: `retrievers/db/article_text/wikipedia_plain_text`

## Summary

- Keep as written: 3 questions
- Revise wording or grading criteria: 5 questions
- Replace because the current question is ambiguous or not fully supported: 5 questions
- Remove as a duplicate: 1 question

The audit found that workbook cleanup was needed: add column headers, assign unique question IDs, remove the duplicated Best Actor question, and move the continuation of Q13's answer into the same row as Q13. These changes have now been incorporated into `GT/wikipedia_GT.csv`.

## Question-by-question findings

### Q1 — Keep

**Question:** Current men's 100 metres world record.

**Best source:** `100_metres.html.txt`

The answer is correct and directly supported. The grading criteria should require 9.58 seconds, Usain Bolt of Jamaica, Berlin, and 16 August 2009. Because the question requests a quotation, the response should also reproduce the relevant article wording accurately.

### Q2 — Revise

**Question:** Three significant events recorded for 1580.

**Best source:** `1580.html.txt`

The proposed events are supported, but the answer supplies seven possibilities instead of three and does not actually quote the article. Select exactly three dated events and include a short supporting excerpt for each. The grading notes should allow multiple valid combinations.

### Q3 — Revise

**Question:** A person nominated at the 68th, 70th, and 74th Academy Awards.

**Best sources:** `68th_Academy_Awards.html.txt`, `70th_Academy_Awards.html.txt`, and `74th_Academy_Awards.html.txt`

John Williams is correct. The answer should begin with “Yes,” rather than calling him a counterexample. Supporting nominations are *Nixon* and *Sabrina* at the 68th ceremony, *Amistad* at the 70th, and *A.I. Artificial Intelligence* and *Harry Potter and the Sorcerer's Stone* at the 74th.

### Q4 — Keep

**Question:** Location of the 1972 Winter Olympics.

**Best source:** `1972_Winter_Olympics.html.txt`

The answer is correct: Sapporo, Hokkaido Prefecture, Japan.

### Q5 — Keep

**Question:** Country with the most medals at the 1972 Winter Olympics.

**Best source:** `1972_Winter_Olympics.html.txt`

The answer is correct: the Soviet Union won 16 total medals—8 gold, 5 silver, and 3 bronze.

### Q6 — Replace

**Question:** How the Academy Awards nomination process works.

**Closest corpus sources:** `Academy_Award_for_Best_Actor.html.txt`, `Academy_Award_for_Best_Director.html.txt`, and `Academy_Award_for_Best_Picture.html.txt`

The existing answer uses external web sources and includes claims that cannot be reproduced from the retrieval corpus. Replace it with a category-specific question:

> How are nominees and winners selected for the Academy Award for Best Actor?

Expected answer: nominees are determined by single transferable vote within the actors branch of AMPAS; the winner is selected by plurality vote among all eligible Academy voters.

### Q7 — Revise

**Question:** Actor with the most Academy Awards from 2000 through 2020.

**Best source:** `Academy_Award_for_Best_Actor.html.txt`

The answer is correct only if “Academy Awards” means the Best Actor category and the dates refer to film years. Reword it as:

> Between the films of 2000 and 2020 inclusive, who won the Academy Award for Best Actor most often?

Expected answer: Sean Penn and Daniel Day-Lewis, with two wins each.

### Q8 — Remove duplicate

This row repeats Q7 exactly and adds no evaluation coverage. Delete it or replace it with a different question.

### Duplicate Q8 — Replace

**Question:** Most devastating earthquakes in the last 50 years.

**Best sources:** `Lists_of_earthquakes.html.txt` and, for event-level detail, `2011_Tōhoku_earthquake_and_tsunami.html.txt`

The identifier Q8 is reused. The question also does not define “most devastating,” the number of results to return, or how disputed fatality estimates should be handled. Replace it with:

> According to the deadliest-earthquakes table, which earthquakes since 1976 have reported fatality estimates exceeding 100,000?

The answer should identify the Tangshan, Indian Ocean, and Haiti earthquakes and preserve the uncertainty and attribution attached to their fatality figures.

### Q9 — Revise

**Question:** Correlation between country population and life expectancy.

**Best sources:** `List_of_countries_by_past_life_expectancy.html.txt` and `List_of_countries_by_population_(United_Nations).html.txt`

The source choice and qualitative conclusion are reasonable. The exact coefficients are not stable unless the evaluation specifies country-name normalization, territory and region exclusions, selected years, missing-value treatment, and the correlation formula. Document these decisions before treating an exact coefficient as ground truth. Otherwise, grade the qualitative conclusion: population size has little useful relationship with life expectancy in the selected data.

### Q10 — Replace

**Question:** Winter Olympic events added during the last 100 years.

**Closest sources:** `Winter_Olympic_Games.html.txt`, `1936_Winter_Olympics.html.txt`, and `1992_Winter_Olympics.html.txt`

“Events” could mean sports, disciplines, or individual medal events. The answer also mixes Olympic debuts with sports returning to the program. The corpus does not contain every edition article needed to verify the proposed chronology consistently. Narrow the question to information explicitly stated in one available article.

### Q11 — Replace

**Question:** Summer Olympic events added during the last 100 years.

**Closest sources:** `Summer_Olympic_Games.html.txt`, `1936_Summer_Olympics.html.txt`, and `2020_Summer_Olympics.html.txt`

This question has the same sports-versus-disciplines ambiguity and inconsistent treatment of returning sports. A safer replacement is:

> Which sports debuted at the Tokyo 2020 Summer Olympics, and in which country were the Games held?

### Q12 — Revise

**Question:** Olympic Games hosted by Russia.

**Best sources:** `List_of_Olympic_Games_host_cities.html.txt`, `Summer_Olympic_Games.html.txt`, and `Winter_Olympic_Games.html.txt`

The answer is supported, but the question must say whether the Soviet Union counts as a historical form of Russia. If it does, the expected answer is the 1980 Summer Olympics in Moscow, Soviet Union, and the 2014 Winter Olympics in Sochi, Russia.

### Q13 — Replace

**Question:** Olympic Games in which Russia did not participate.

**Closest sources:** `1984_Summer_Olympics.html.txt`, `Summer_Olympic_Games.html.txt`, and `Unified_Team_at_the_Olympics.html.txt`

The question is ambiguous across the Russian Empire, Soviet Union, Russian Federation, ROC, and neutral athletes. The workbook also splits the answer across two rows. The corpus lacks a single complete source for the proposed historical list. Replace it with:

> Why did the Soviet Union not participate in the 1984 Summer Olympics?

## Suggested additional questions

1. **Single-article fact:** What distinction made the 1972 Winter Olympics geographically historic?  
   Source: `1972_Winter_Olympics.html.txt`  
   Expected answer: They were the first Winter Olympics held outside Europe and North America.

2. **Multi-article comparison:** Compare the host countries and dates of the 1932 and 1936 Winter Olympics.  
   Sources: `1932_Winter_Olympics.html.txt` and `1936_Winter_Olympics.html.txt`

3. **Category rule:** How are Best Actor nominees selected, and how is the winner selected?  
   Source: `Academy_Award_for_Best_Actor.html.txt`

4. **Uncertainty handling:** What fatality estimates does the earthquake list give for the 2010 Haiti earthquake?  
   Source: `Lists_of_earthquakes.html.txt`  
   The grading notes should require the answer to preserve the range and source attribution rather than present one certain number.

## Checkpoint 3.1 use

The 19 cases were used for the oracle-context, vector, and hybrid RAGAS experiments in
Checkpoint 3.1. Each saved run preserves the question ID, generated answer, score,
model settings, and evaluation mode. Retriever runs also preserve selected articles,
designated-source recall, and context size. This makes it possible to distinguish
retrieval failures from response-generation failures.

## Future use

Keep GT01-GT19 unchanged as a development and regression set so later results remain
comparable. Use the Lab 3.2 workflow to create controlled question variants, and add a
separate held-out set that is not used to tune prompts, grading notes, or retrieval
settings.

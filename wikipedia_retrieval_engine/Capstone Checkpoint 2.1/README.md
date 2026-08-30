# Capstone Checkpoint 2.1: Wikipedia Retrieval Engine

## Technical report and experimental findings

This checkpoint extends the Wikipedia question-answering work from Capstone
Checkpoint 1.1 by adding retrieval-augmented generation (RAG). The purpose of the
work was not only to make the language model produce an answer, but to determine:

1. whether the system retrieved the correct Wikipedia article or articles;
2. whether the retrieved context contained enough information to answer the question;
3. whether the language model correctly synthesized the evidence it received.

The experiments compare BM25 keyword retrieval, Chroma vector retrieval, and hybrid
BM25/vector retrieval across three context-construction strategies: fixed character
chunks, HTML section chunks, and full extracted articles.

Every question is processed independently. The system does not maintain conversation
history or use prior questions as context.

## Evidence and project artifacts

The following files contain the implementation, experiment evidence, and analysis used
for this checkpoint.

- [Initial retrieval analysis](<logs/Checkpoint 2.1 Retrieval Analysis.xlsx>) records
  the no-RAG comparison and the first character-chunk experiments.
- [Expanded retrieval analysis](<logs/Checkpoint 2.1 Retrieval Analysis_Expanded.xlsx>)
  extends the comparison to section and full-article context strategies. This is the
  primary results matrix referenced in this report.
- [Ground-truth answers](<../GT/wikipedia Q-A GT.xlsx>) contains the expected answers
  used during manual review.
- [Baseline character-chunk experiment](capstone_checkpoint_2_1_baseline_retrieval_starter.py)
  runs BM25, vector, and multiple hybrid weighting configurations.
- [HTML section experiment](capstone_checkpoint_2_1_chunk_by_article_headers.py)
  retrieves complete article sections defined by Wikipedia headings.
- [Full-article experiment](<capstone_checkpoint_2_1_full articles_sent.py>) uses
  retrieved chunks to identify articles and then sends each selected article's
  complete extracted text to the language model.
- [Retriever implementation guide](../retrievers/_README_RETRIEVERS.md) documents the
  reusable retriever classes and configuration options.
- [Corpus preprocessing guide](../retrievers/_README_ARTCILE_CORPUS.md) documents HTML
  extraction, character chunking, section chunking, Chroma indexes, and the persistent
  plain-text article collection.
- [Submitted checkpoint report](ElenaBaron_Capstone_Checkpoint_2_1.pdf) contains the
  assignment-formatted summary.
- The [`logs/`](logs/) directory contains one timestamped evidence log per retriever
  configuration.

The Excel workbooks contain qualitative assessments rather than automated exact-match
scores. Labels such as `Correct`, `Partial`, `Not enough information`, and `Wrong
articles retrieved` were assigned after manually comparing the retrieved articles,
retrieved text, generated answer, and ground truth.

## System architecture

The implementation separates corpus preparation, retrieval, context construction,
language-model calls, and evidence logging.

```text
Wikipedia HTML corpus
        |
        +--> character chunks (1,600 characters, 200 overlap)
        |         |--> BM25 in-memory index
        |         +--> persistent Chroma vector index
        |
        +--> HTML section chunks (h2-h6 hierarchy, max 10,000 characters)
        |         |--> BM25 in-memory index
        |         +--> separate persistent Chroma vector index
        |
        +--> one persistent plain-text file per complete extracted article

Question
  --> BM25, vector, or hybrid retrieval
  --> retrieved chunks or unique article expansion
  --> grounded LLM call
  --> timestamped evidence log
```

The shared implementation is under [`../retrievers/`](../retrievers/):

- `corpus.py` extracts article text and creates the three corpus representations.
- `bm25.py` builds an in-memory `BM25Okapi` index and performs keyword retrieval.
- `vector.py` builds or loads a named persistent Chroma index and performs semantic
  retrieval.
- `hybrid.py` composes the BM25 and vector retrievers, normalizes their scores, and
  fuses their rankings.
- `base.py` defines the common retrieval interface and configurable `RetrieverSpec`.
- `expansion.py` converts retrieved chunk IDs into unique article names and loads each
  selected full article once.
- `llm.py` owns the chat model, embedding client, and the single grounding system
  prompt. Retrieval classes do not call the chat model.
- `evidence.py` writes configuration headers, retrieved article names, chunk-level
  evidence, expanded full-article evidence, and generated answers.

## Corpus and preprocessing

The source corpus contains 2,417 local Wikipedia HTML files in `../Wikipedia/`.
Preprocessing isolates the main `mw-content-text` article body, removes non-content
elements such as scripts and styles, stops before References or Notes, converts useful
HTML boundaries into text boundaries, removes `[edit]` labels, and normalizes
whitespace.

### Character-window corpus

The original baseline divides extracted article text into approximately 1,600-character
windows with 200 characters of overlap. It attempts to end a chunk on a paragraph,
sentence, or line boundary when possible.

The overlap protects meaning near arbitrary boundaries, but it also duplicates text.
The initial analysis workbook records 59,298 chunks for the first experiment family.
Later full-article logs record 58,263 current character chunks after preprocessing code
changes; this difference is discussed under reproducibility limitations.

The corresponding persistent vector index is:

```text
../retrievers/db/wikipedia_chars1600_overlap200/
```

### HTML section corpus

The section experiment uses Wikipedia's `h2` through `h6` hierarchy as natural text
boundaries. A section path such as the following is included in the indexed text and
metadata:

```text
Article: 1580
Section: Events > April-June
```

Text directly under a parent heading is kept in the parent section. Child-section text
is not copied into the parent. For example, the `Events` chunk does not automatically
contain `Events > January-March`, `Events > April-June`, or the other children.

A natural section remains intact unless it exceeds 10,000 characters. Oversized
sections are split with no overlap. This produced 41,014 section chunks in the
experiment logs.

The separate Chroma index is:

```text
../retrievers/db/wikipedia_sections_max10000_no_overlap/
```

### Complete extracted article collection

The full-article experiment does not reconstruct articles by concatenating overlapping
chunks. Instead, preprocessing creates one independent UTF-8 text file for every
article:

```text
../retrievers/db/article_text/wikipedia_plain_text/
```

Retrieval still operates on the 1,600/200 character index. The retrieved chunk IDs are
used only as article-selection signals. Duplicate chunk hits from the same article are
collapsed, and each selected article is loaded once from its standalone text file.
Consequently, the language model receives complete, non-overlapping extracted article
text rather than repeated chunk windows.

## Retrieval methods

### BM25 keyword retrieval

BM25 lowercases text, extracts alphanumeric terms, removes a small stopword list, and
builds an in-memory index each time the program starts. It does not use embeddings or a
persistent database. Higher BM25 scores are better.

BM25 was expected to work well for exact article names, ceremony numbers, years, and
other literal terms. In practice, it sometimes retrieved the correct article but often
spent the remaining Top K positions on lexically similar yet irrelevant articles.

### Vector retrieval

Vector retrieval uses `openai/text-embedding-3-small` through OpenRouter and stores
document embeddings in Chroma. Chroma returns distances, so lower raw vector scores are
better.

The named Chroma directories allow the indexes to be loaded after a Python or computer
restart. Existing document embeddings do not need to be regenerated, although each new
question still requires a query embedding.

Vector retrieval was generally more consistent than BM25 for semantic wording and was
the strongest single retriever across the manually reviewed experiments.

### Hybrid retrieval

Hybrid retrieval obtains a candidate pool from both BM25 and vector search. BM25 scores
are min-max normalized directly; Chroma distances are min-max normalized and inverted.
The normalized scores are then combined:

```text
hybrid_score = bm25_weight * normalized_bm25
             + vector_weight * normalized_vector_similarity
```

The initial experiment compared `0.50/0.50`, `0.70/0.30`, and `0.30/0.70`
BM25/vector weights. Later experiments used `0.35/0.65`, favoring semantic retrieval
while retaining exact-term evidence. The candidate pool was 10 per component.

Changing the weights affected some rankings, but the Excel analysis indicates that
context construction usually had a larger effect than the difference among reasonable
hybrid weights.

## Experiment design

Thirteen questions were selected to exercise different retrieval requirements:

- precise single-article facts and quotations;
- broad questions requiring coverage across one long article;
- table or list interpretation;
- aggregation across several articles;
- time-bounded historical questions;
- multi-source comparison and calculation.

The following experiment families were run. The exact configuration for every run is
also recorded at the beginning of its `.log` file.

| Run family | Retriever configurations | Indexed unit | Context sent to LLM |
|---|---|---|---|
| Character baseline, K=4 | BM25; vector; hybrid 50/50, 70/30, and 30/70 | 1,600 characters, 200 overlap | Top 4 retrieved chunks |
| Sections, K=4 | BM25; vector; hybrid 35/65 | Natural HTML sections, max 10,000, no overlap | Top 4 sections |
| Full article, K=4 | BM25; vector; hybrid 35/65 | Character chunks select articles | Every unique selected article once |
| Sections, K=10 | Vector; hybrid 35/65 | Natural HTML sections, max 10,000, no overlap | Top 10 sections |
| Full article, K=7 | BM25; vector; hybrid 35/65 | Character chunks select articles | Every unique selected article once |

The expanded Excel workbook presents selected result columns from these families. The
log directory contains the complete run evidence, including configurations that were
run but not given a separate workbook column.

The model settings recorded in the logs were:

- chat model: `openai/gpt-5.4-mini`;
- temperature: `0.2`;
- embedding model: `openai/text-embedding-3-small`;
- system behavior: answer only from the supplied Wikipedia context, quote when
  possible, and explicitly report insufficient evidence instead of guessing.

## Findings by question

The detailed cell-by-cell observations are preserved in the expanded analysis
workbook. The following is a technical synthesis of those observations.

| Question | Retrieval requirement | Main finding |
|---|---|---|
| Q1: 100 metres world record | Precise fact and quotation from one article | All RAG configurations answered correctly. Small chunks were sufficient because the required sentence was locally self-contained. |
| Q2: significant events in 1580 | Broad coverage within one long article | Character chunks usually found `1580.html` but did not provide enough of the year. Vector/hybrid section retrieval covered multiple quarters, and full-article context consistently produced a complete answer. |
| Q3: nominations at the 68th, 70th, and 74th Academy Awards | Cross-ceremony entity intersection | Most configurations failed. Hybrid section retrieval at K=4 produced the correct answer once, but the result was not robust across later settings. This question requires collecting and intersecting evidence across ceremonies, not merely finding an Academy Awards article. |
| Q4: location of the 1972 Winter Olympics | Precise single-article fact | Every RAG configuration answered correctly. This is the clearest example of a retrieval task for which Top K=4 chunks are adequate. |
| Q5: country with the most 1972 Winter Olympic medals | Table/list fact | Nearly all configurations answered correctly. BM25 section retrieval at K=4 was the notable failure because its selected section did not contain the medal table evidence. |
| Q6: Academy Awards nomination process | Broad procedural explanation | No configuration was consistently complete. Full-article vector retrieval found Best Director and Best Picture process descriptions, but these are category-specific fragments rather than a complete general nomination process. |
| Q7: most Best Actor wins from 2000 through 2020 | Time-bounded aggregation and counting | No configuration reliably returned both Sean Penn and Daniel Day-Lewis. In the full-article vector run, retrieval and context coverage were sufficient, but the LLM contradicted its own evidence while counting. This is an answer-synthesis failure, not only a retrieval failure. |
| Q8: deadliest earthquakes in the last 50 years | Ranked multi-event list with a date constraint | Section vector retrieval and full-article context produced the strongest, most detailed answers. Several chunk and hybrid runs found only the top one or two events, and some section results included events outside the requested time window. |
| Q9: life expectancy versus population | Two-source table join and statistical calculation | Every tested configuration missed at least one required source or retrieved region-specific substitutes. This was the clearest article-recall failure. Even with both articles, the system would still need country-name normalization, a table join, and a correlation calculation. |
| Q10: Winter Olympic events added over time | Long chronological list | Vector character retrieval and section retrieval performed well. Full-article context was generally correct, although irrelevant selected articles sometimes added noise. |
| Q11: Summer Olympic events, years, and host countries | Chronological list plus cross-source host lookup | Character chunks and K=4 sections lacked sufficient coverage. Full-article and K=10 section configurations improved substantially; the strongest hybrid outputs were correct but occasionally added irrelevant details. |
| Q12: Olympic Games hosted by Russia/USSR | Multi-article fact aggregation | Chunk and section runs commonly found either the Winter or Summer Games but not both. Full-article expansion was the first strategy to consistently include both. |
| Q13: Olympic Games without Russian participation | Historical list with changing national status | All answers remained partial. K=10 hybrid section retrieval found the 1984 boycott and was acceptable for the main event, but it did not fully represent early non-participation, bans, ROC participation, or neutral-athlete distinctions. |

## Cross-experiment findings

### 1. Correct article retrieval is not the same as answerability

Several poor answers were produced after the correct article had already been found.
The 1580 question is the clearest example: the article was retrieved, but four short
chunks did not represent the whole year. Evaluation therefore needs three separate
layers:

1. **Article recall:** Were all required articles retrieved?
2. **Context sufficiency:** Did the selected text contain enough evidence?
3. **Answer synthesis:** Did the model correctly interpret, aggregate, and constrain
   the evidence?

Treating all three as one `Correct/Incorrect` answer score hides where the system
actually failed.

### 2. Context construction had more impact than small weight changes

The original hybrid weight sweep changed retrieval order, but it did not solve broad
coverage problems. Moving from arbitrary character windows to natural sections, and
then to full articles, produced larger improvements than changing BM25/vector weights
within the tested range.

### 3. Section chunking improved coherence but did not guarantee coverage

Sections preserve meaningful HTML structure and remove overlap. However, each child
section is still a separate retrieval unit. Retrieving `Events > January-March` does
not automatically include the other `Events` subsections. Increasing section Top K
from 4 to 10 improved broad-question coverage, but it also introduced more irrelevant
sections.

### 4. Full-article expansion improved recall after article selection

Full-article context was especially effective for broad questions whose answer lived
inside one or a small number of articles, including Q2, Q8, Q10, and Q12. The retrieved
chunks served as article locators, while the persistent text collection supplied
complete, non-overlapping context.

The approach is less safe when Top K identifies many unique articles. For example, a
K=7 run can send multiple long articles even when several chunks come from one primary
article. This increases token use and can distract the model. More retrieved context is
therefore not automatically better context.

### 5. Some failures require computation, not more text

Q7 requires filtering years and counting winners. Q9 requires retrieving two tables,
normalizing country names, joining rows, selecting comparable periods, and calculating
correlation. These operations should be implemented as explicit data-processing steps
rather than delegated entirely to a free-form language-model response.

### 6. Flattened HTML can damage structured evidence

The current HTML-to-text conversion preserves useful line boundaries, but tables,
legends, merged headers, and list relationships can still lose structure. Academy
Awards and Olympic questions often depend on exactly those relationships. A table-aware
representation would likely improve Q3, Q5, Q7, Q9, Q10, and Q11.

## Recommended next architecture

The most promising baseline is vector-primary hybrid retrieval with BM25/vector weights
of approximately `0.35/0.65`, combined with adaptive context construction rather than a
single fixed Top K policy.

Recommended improvements are:

1. Retrieve natural sections and deduplicate results by article.
2. Classify each question as a precise fact, broad single-article question,
   multi-article aggregation, or structured-data calculation.
3. For precise facts, send a small number of highly ranked sections.
4. For broad article questions, retrieve a section and expand to its sibling/child
   sections or to the complete article within a context budget.
5. For multi-source questions, decompose the query into explicit source needs before
   retrieval. Q9 should separately retrieve a country population table and a country
   life-expectancy table.
6. Preserve HTML tables as structured rows and columns, including captions and headers.
7. Add a reranking or article-selection step before sending full articles to the LLM.
8. Evaluate article recall, context sufficiency, and answer correctness separately.
9. Use deterministic Python calculations for joins, counts, rankings, date filters, and
   correlations after retrieval.
10. Add automated regression checks for the 13 questions while retaining the detailed
    evidence logs for manual review.

## Reproducibility and persistence

Each checkpoint script defines its experiment list through `RetrieverSpec` objects.
Changing `RETRIEVAL_TOP_K`, hybrid weights, candidate pool, Chroma database name, or
context strategy changes the experiment configuration written into the resulting log.

From the `wikipedia_retrieval_engine` directory, the experiment scripts can be run as:

```bash
python "Capstone Checkpoint 2.1/capstone_checkpoint_2_1_baseline_retrieval_starter.py"
python "Capstone Checkpoint 2.1/capstone_checkpoint_2_1_chunk_by_article_headers.py"
python "Capstone Checkpoint 2.1/capstone_checkpoint_2_1_full articles_sent.py"
```

`OPENROUTER_API_KEY` must be available from the project `.env` file or environment.
BM25 rebuilds its in-memory token index on every process start. Chroma and the extracted
article text collection persist on disk and are reused after restarts.

The logs are append-independent: every retriever configuration receives a new
timestamped filename, and the file begins with the exact retriever, chunking, Chroma,
embedding, LLM, and prompt configuration. Each question entry then records unique
article names, chunk ranks and scores, chunk previews, any full articles sent to the
model, and the grounded answer.

## Reproducibility limitations and data-quality notes

- The evaluation is a carefully documented manual analysis, not a formal benchmark
  with numerical precision, recall, or answer-quality metrics.
- LLM output can vary between runs even with the same retrieved context. The recorded
  temperature was `0.2`, not zero.
- The first character-chunk run recorded 59,298 chunks, while later full-article runs
  recorded 58,263 chunks under the same named character index. The current Chroma load
  logic reuses any non-empty named directory without checking a corpus manifest. This
  creates a possible stale-index mismatch between current BM25 chunks and persisted
  vector chunks. Before formal quantitative comparison, the character index should be
  rebuilt or given a versioned name, and Chroma should validate a manifest containing
  the preprocessing version, file list, chunk count, and content fingerprint.
- The expanded workbook intentionally summarizes selected experiment outputs; the raw
  logs remain the authoritative evidence for exact retrieved articles and chunks.
- The ground-truth workbook contains a duplicated Best Actor question and uses `Q8` for
  both that duplicate and the earthquake question. This README follows the 13-question
  numbering in the analysis workbooks: Q7 is Best Actor and Q8 is earthquakes.
- The life-expectancy and population ground truth compares values from different date
  ranges. It is useful for testing retrieval, joining, and calculation, but its final
  correlation should be described as a cross-source comparison rather than a same-year
  causal analysis.

## Conclusion

The experiments show that the retrieval engine is successful for precise,
single-article factual questions. Its main limitation is not simply choosing BM25
versus vector search. The larger issue is matching context construction and downstream
reasoning to the question type.

Natural section chunking improves coherence, and full-article expansion improves broad
coverage when article selection is precise. However, multi-source questions and
table-based aggregation require query decomposition, structured extraction, and
deterministic computation. The most important design lesson from this checkpoint is to
evaluate article retrieval, context completeness, and answer synthesis as separate
components of the RAG pipeline.

## AI assistance disclosure

I used ChatGPT to assist with organizing my code and developing the testing framework,
including parsing HTML, generating comprehensive logs, and creating a framework for
running multiple experiments.

I also used ChatGPT to organize my observations and refine the wording of my written
analysis. I reviewed the prompts, experimental runs, interpretations, and final
conclusions and made all final decisions regarding their inclusion.

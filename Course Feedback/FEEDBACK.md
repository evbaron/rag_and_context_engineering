# Course Feedback and an Offer to Help

Thank you for the course. Every module gave me something useful that will make me
better at my job. I especially valued the history of AI and LLMs, which gave me a
better framework for understanding models' sometimes surprising behavior; the
references to research papers, which were excellent supporting material; and the use
of graph relationships to discover additional articles, which was a genuinely useful
retrieval technique that I had not used before.

I am sharing the rest of this feedback because I care about the course and would like
to help make it stronger. I am grateful for what I learned, but I am also frustrated
because the part I most wanted to learn was the part I felt was least developed.

## My central concern: context engineering after retrieval

The course is titled *RAG and Context Engineering: Designing and Building
Production-Grade AI Systems*. It taught retrieval well. However, the part I expected
to be context engineering - what to do with evidence after the correct documents have
been found - received much less attention than the title led me to expect. That was
the main reason I enrolled.

Much current industry practice stops at placing a strong model on top of an uncurated
corpus and calling the result AI-enabled. That often produces a more expensive product
without a correspondingly valuable result. To me, context engineering is not only
about retrieving smaller passages or reducing the number of tokens sent to a model.
It is also about preparing, structuring, routing, validating, and sometimes computing
over evidence so that the model can use it reliably.

This distinction matters in my work. For example, I may need to analyze a large body
of highly specialized clinical-trial protocols and research papers to answer questions
such as:

- For a cohort such as non-small-cell lung cancer trials, what is the average number
  of inclusion and exclusion criteria, and what patient burden do those criteria
  create?
- Which eligibility criteria are associated with the largest number of protocol
  amendments?
- What enrollment targets and other distributions appear across the corpus?

These questions cannot be answered by finding one relevant paragraph. They require
structured extraction across many inconsistently written documents, normalization,
aggregation, provenance, and verification. We already decompose protocols, curate and
extract individual values, represent relationships in a graph, generate Cypher, and
build fallbacks when a generated query fails. Even then, we encounter lost-in-the-
middle behavior, needle-in-a-haystack failures, and computational inconsistencies. A
model may identify the correct trend while returning slightly incorrect distribution
buckets - enough for a statistician to reject the result.

I had hoped the course would go further into techniques for these problems: structured
preprocessing, deterministic tools, evidence assembly, map-reduce patterns that
preserve precision, verification of intermediate results, and strategies for reasoning
across evidence that cannot simply be removed from the prompt. The lectures explained
why long context is difficult, but the practical answer was often to send less. In
enterprise work, the full body of evidence frequently cannot be reduced without losing
part of the question.

## What my capstone results showed

The capstone made this gap measurable. By Checkpoint 5.1, my system was retrieving the
designated articles with essentially perfect recall, but some answers were still
wrong. The right article was present, yet the model miscounted, misread a table, missed
an important qualifier, or failed to synthesize evidence across sources.

The improvement came from processing the retrieved evidence. Moving from TOC-selected
sections to aligned table artifacts and deterministic lookup and computation increased
answer quality from **0.579 to 0.789** and strict passes from **40.8% to 75.0%**. In the
final computation runs, article recall was already **1.000**. Retrieval had succeeded;
table representation, calculation, and answer synthesis were the limiting factors.

This was one of my most important lessons from the project, but I had to work out much
of it independently. I believe it could form a valuable part of the course: teach
students to diagnose whether a failure happened in retrieval, evidence preparation,
reasoning, calculation, or answer construction, and then apply the appropriate fix.

## Suggestions for future cohorts
Basic ideas how to improve capstone project experience.

### 1. Give students an extendable architecture

The checkpoints should build one system incrementally. Each checkpoint could add a
small, clearly bounded capability while retaining the corpus, interfaces, evaluation,
logs, and previous work. Students who are on track could add only the new files;
students who fall behind could start from a complete checkpoint snapshot.

This would reinforce the idea that production systems evolve through measured changes,
and it would reduce the time students spend repeatedly rewiring starter code.

### 2. Introduce logging with the first LLM call

Every run should record the model, role, prompt and output token counts, cached tokens,
latency, estimated cost, answer, and relevant configuration. By the time students reach
the performance and cost module, they would already have a history of their own system
to analyze.

Logging early would also give students another debugging tool. They could identify
which questions trigger additional calls, which role consumes the most context, and
whether a quality improvement is worth its additional cost and latency.

### 3. Score retrieval and answer quality separately

Article recall and answer correctness measure different stages of the system. A system
can retrieve every required article and still produce the wrong answer. Reporting both
metrics helps students distinguish a retrieval failure from an evidence-processing or
synthesis failure.

The course datasets already identify source documents for many questions, so the basis
for an article-recall metric is available. A simple diagnostic matrix - source found or
missed, answer correct or incorrect - would make this lesson immediately visible.

### 4. Teach evidence-processing tools after retrieval

Once retrieval recall is high, students should have examples of what to try next:

- normalize tables and other structured content during preprocessing;
- use models to create constrained plans, but use deterministic code for filtering,
  aggregation, comparison, and arithmetic;
- preserve cell- or passage-level provenance through computation;
- assemble evidence from multiple documents before asking the model to synthesize it;
- validate evidence sufficiency and intermediate outputs;
- compare long-context, map-reduce, tool-assisted, and agentic approaches.

This would connect retrieval to the production-grade context-engineering problems that
begin after the correct document has been found.

### 5. Require repeated experimental runs

LLM systems are nondeterministic. A single run can produce 100% accuracy by chance, or
make a sound design appear worse than it is. Students should repeat each important
experiment and report the distribution or run-to-run spread, not only the best run.

This also changes how trade-offs are discussed. A small difference between two
configurations is not meaningful if it is smaller than their ordinary run-to-run
variation.

### 6. Make the quality-cost-latency relationship visible throughout

Students should be able to compare configurations across all three dimensions:

- Did quality improve?
- How much additional time did each question require?
- How many calls and tokens were added, and what did they cost?
- Was the improvement consistent, or did routing make individual questions
  unpredictably expensive?

This would make the final performance lesson a continuation of the capstone rather
than the first time operational data is collected.

### 7. Improve setup and budget guidance

I spent considerable time resolving environment issues. Package versions were not
pinned until later in the course, and the Python version on my Mac caused confusion. A
single setup guide, a supported Python version, pinned dependencies, an `.env.example`,
and a setup-check script at the beginning would remove avoidable friction.

The API budget also deserves clearer planning. I exhausted the course-provided credits
near the beginning of Checkpoint 4.1 and moved to my own OpenRouter account. In my
experience, completing the capstone with repeated evaluation and enough experimentation
to support reliable conclusions required roughly **$100 in model usage**. Some of that
reflects the depth of my investigation, but repeated runs are methodologically
important, not merely optional exploration. Future students should either receive a
budget that supports the expected workload or be given a realistic cost estimate and
lower-cost experimental paths from the beginning.

## A concrete contribution I would be happy to make

I prepared a prototype which is available next to the FEEDBACK.md file 
under `capstone_checkpoint_starters/` showing how these ideas
could work across Checkpoints 1 through 5, followed by a log-analysis checkpoint. It
is not intended as criticism of the instructors' work or as a claim that I know how
to teach the material. It is a practical example based on the obstacles I
encountered.

The prototype includes:

- one cumulative project architecture that grows across checkpoints;
- pinned dependencies, a setup guide, an environment template, and a setup checker;
- support for the actual capstone corpora rather than only a few sample sentences;
- common retriever and pipeline interfaces so later checkpoints extend earlier work;
- logging from Checkpoint 1, including tokens, latency, model role, and estimated cost;
- separate article-recall and answer-quality evaluation;
- repeated-run support and a saved baseline for later comparisons;
- agentic retrieval and tool-using examples with bounded loops;
- cost and latency analysis across the accumulated logs; and
- offline tests plus a maintainer build script so checkpoint copies do not drift.

I would be glad to donate this work, or any other useful parts of my capstone, without
expectation. I can also help adapt it to the course's conventions, strengthen the
documentation and tests, validate it on both capstone scenarios, or build only the
pieces the instructional team finds valuable. Please feel free to contact me; I would
be happy to contribute in whatever form is most useful for the next cohort. 


Thank you again for the ideas, research references, and retrieval techniques the
course gave me. My frustration comes from believing that the course is close to being
something unusually valuable. It already provides a strong RAG and retrieval
foundation. Extending it further into evidence processing, synthesis, measurement, and
operational trade-offs would make it better match the promise of production-grade
context engineering that brought me to the program.


Elena Baron
I can be contacted on linkedin https://www.linkedin.com/in/elena-baron-6abb0620/
As well as through emeritus messaging

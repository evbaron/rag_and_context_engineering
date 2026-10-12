# Checkpoint 4: advanced retrieval with multistep and graph search

Two retrieval ideas for questions that one search handles badly: questions that need
several articles, and questions whose answer sits in an article the question never
names. Each idea is one new file, and each is measured against the baseline saved in
Checkpoint 3.

## New in this checkpoint

| File | What it does |
|---|---|
| `ragkit/retrievers/multistep.py` | The model splits a question into short searches; each search's best passage is kept, so every part of the question is represented |
| `ragkit/retrievers/graph.py` | Adds related articles: Wikipedia links between corpus articles, or, for papers, papers that mention another paper's title |
| `samples/cp4_challengers.py` | Baseline, multistep, and graph on the same questions |

Both retrievers wrap the baseline's own retriever, so each comparison changes one thing.

## How to use it

1. Run the challengers against the baseline:
   ```
   python samples/cp4_challengers.py                                   # the demo questions
   python samples/cp4_challengers.py --questions ~/rag_course_work/my_questions.xlsx
   ```
2. Read recall first. These are retrieval improvements: did the multi-article questions
   get all their sources? Did a gain on one question cost another?
3. Then read quality, on the gt questions and on the validation questions. A challenger
   that wins on gt but not on validation was tuned to the gt questions.
4. The multistep retriever logs the searches it ran, and the graph retriever the
   articles it added (`details` in each log line): read them for the questions that
   changed.

## Adopting a winner

When a challenger beats the baseline on both question sets, it becomes the new
baseline. `ragkit/baseline.py` builds the baseline from the saved settings; extend
`open_baseline` to wrap the retriever (for example in `MultiStepRetriever`) when the
saved settings say so. From here on, the library is the project's own to grow.

## For the Checkpoint 4.1 write-up

The challengers report compares each idea with the baseline on recall and on quality,
per question set, and shows which questions changed.

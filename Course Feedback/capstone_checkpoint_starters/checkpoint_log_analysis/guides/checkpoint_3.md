# Checkpoint 3: measuring with question sets, recall, and answer quality

From here on, every change is measured. This checkpoint adds question sets kept in a
spreadsheet, two independent scores for every question (did retrieval find the source
articles? is the answer right?), and a report that compares runs. It ends with a
baseline: the configuration every later idea has to beat.

## New in this checkpoint

| File | What it does |
|---|---|
| `data/questions_template.xlsx` | An empty question set, with a "How to fill" sheet |
| `data/questions_demo_wikipedia.xlsx` | 10 demo questions over the Wikipedia corpus (6 gt, 4 validation) |
| `ragkit/eval/questions.py` | Reads question sets (.xlsx or .csv) |
| `ragkit/eval/recall.py` | Article recall: the share of a question's source articles that retrieval found |
| `ragkit/eval/judge.py` | A model grades each answer PASS, PARTIAL, or FAIL against the reference and the grading notes |
| `ragkit/eval/run.py` | `run_eval`: every question through a pipeline, scored and logged |
| `ragkit/pipelines/oracle.py` | The oracle: answers with the source articles handed over directly |
| `ragkit/baseline.py` | Saves and reopens the baseline configuration |
| `ragkit/reports/quality.py` | Recall and quality per run, per question, and per category; which half failed |
| `samples/cp3_evaluate.py` | Runs pipelines on a question set, then writes the quality report |
| `samples/cp3_save_baseline.py` | Saves the winning configuration as the baseline |

## Two scores for the two halves of the problem

A RAG system fails in one of two places: retrieval never found the right article, or it
found it and the answer was still wrong (a miscount, a misread table, a missed part).
Scoring every question for recall and for answer quality separately shows which:

| | Answer PASS | Answer PARTIAL or FAIL |
|---|---|---|
| **Every source retrieved** | working | answer problem: a better retriever will not help |
| **A source missed** | suspicious: answered from memory, or the question set lists the wrong sources | retrieval problem |

The oracle shows the best the answer step can do with perfect retrieval: when the
oracle fails a question too, the problem is not retrieval.

Retrieval choices are settings of the system and can be compared like any other: the
passage size and the number of passages per question (k) decide whether the right
section arrives at all, and whether unrelated passages crowd it out.

## How to use it

1. Run the demo question set through keyword, vector, and hybrid retrieval and the oracle:
   ```
   python samples/cp3_evaluate.py
   ```
   Open the report and read "Which half failed" first.
2. Write a question set for the chosen scenario. Copy `data/questions_template.xlsx` to
   `RAG_WORK_DIR` (outside the project folder, so it carries over), then fill in about
   15 to 25 questions: a mix of categories, roughly two thirds gt and one third
   validation. Copy every reference answer from the corpus, and list every source file.
   ```
   python samples/cp3_evaluate.py --questions ~/rag_course_work/my_questions.xlsx
   ```
3. Compare settings, and see how much results move by chance:
   ```
   python samples/cp3_evaluate.py --questions ... --pipelines bm25 hybrid --k 3 5 8
   python samples/cp3_evaluate.py --questions ... --pipelines hybrid --repeat 3
   ```
4. Save the configuration that wins on both the gt and the validation questions:
   ```
   python samples/cp3_save_baseline.py --retriever hybrid --k 5 --note "best recall and quality on gt and validation"
   ```

## Small question sets are noisy

With 20 questions, one question moves quality by 0.05. Run one configuration a few
times (`--repeat 3`): the spread in the report's "Repeated runs" table is the noise. A
difference between two configurations smaller than that spread is not evidence.

## For the Checkpoint 3.1 write-up

The quality report holds the evaluation framework's results: recall and quality per
run, the split between retrieval and answer failures, the per-question detail, and the
noise between repeated runs. The baseline and its note record what was chosen and why.

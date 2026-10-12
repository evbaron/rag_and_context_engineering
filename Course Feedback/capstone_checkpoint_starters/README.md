# Capstone Checkpoint Starters

One capstone project, carried from Checkpoint 1 through Checkpoint 5, plus a log
analysis folder in preparation for the performance work. Each checkpoint adds a few
files to the same project instead of starting over; every answer the system gives is
logged from the first question on.

| Folder | What it adds | Samples |
|---|---|---|
| `checkpoint_1` | Setup guide, pinned requirements, setup check; chat with history on or off; the model on its own; logging and a run report | `cp1_chat.py`, `cp1_probes.py` |
| `checkpoint_2` | Reading the corpus (Wikipedia, papers, emails); keyword, vector, and hybrid retrieval, one file each; the RAG pipeline | `cp2_build_index.py`, `cp2_compare_retrievers.py`, `cp2_chat.py` |
| `checkpoint_3` | Question sets in Excel; retrieval recall and answer quality scored separately; the oracle; the quality report; the baseline | `cp3_evaluate.py`, `cp3_save_baseline.py` |
| `checkpoint_4` | Multistep and graph retrieval, measured against the baseline | `cp4_challengers.py` |
| `checkpoint_5` | An agentic retriever and a tool-using agent on the same retrievers, chat, and evaluation | `cp5_agent.py` |
| `checkpoint_log_analysis` | Cost and latency across every logged run, by run and by role | `analyze_logs.py` |

Each folder's `README.md` says what is included and how to use it; `README_SETUP.md` is
the one-time setup, identical in every folder.

## How students use the folders

1. Start from `checkpoint_1` and follow `README_SETUP.md` until `python check_setup.py`
   reports `Setup complete`. Everything every checkpoint needs is installed then.
2. Each later folder holds everything from the earlier ones plus the files listed under
   "New in this checkpoint" in its README. A student who is on track copies only those
   files into their own project; no earlier file changes. A student who fell behind
   starts from that folder instead, which already contains every earlier piece.
3. Logs, reports, vector indexes, question sets, and the baseline live in `RAG_WORK_DIR`
   (set in `.env`), outside the project folder, so nothing is lost when moving to a
   newer folder.

## Design choices

- **Labs show the homework.** The library reads the lab corpus (emails) as well as both
  capstone corpora (Wikipedia, research papers), so a lab and its checkpoint make the
  same calls on different data.
- **Pieces with one job each.** A retriever only retrieves; a pipeline answers; a chat
  session keeps the history. Every retriever has `retrieve(query, k)`, and every
  pipeline `answer(question, history)`, so the chat, the logs, and the evaluation work
  with all of them unchanged.
- **One way to call a model**, `build_messages` then `ask`, and small classes whose state
  can be printed (`session.history`), with no functions that return functions.
- **History holds questions and answers only**, never retrieved passages, so prompts do
  not grow with every turn and planted text is not replayed.
- **Two scores for every question**: retrieval recall and answer quality, so a failure
  can be traced to retrieval or to the answer step.
- **Offline tests in every folder** (`pytest`): no API calls, no cost.

## For maintainers

Every file lives once, in `_maintainers/source/`; the checkpoint folders are generated
from it, so they cannot drift apart. Edit the source, then rebuild and test:

```
python _maintainers/build_starters.py --test
```

The build assigns each file to the checkpoint that introduces it (the lists at the top
of `build_starters.py`) and stops if a new file has not been assigned. Run it with the
Python of an environment that has `requirements.txt` installed.

Last verified on 2026-10-11:
- a fresh Python 3.12 environment installs `requirements.txt` cleanly;
- every folder passes its own offline tests;
- every sample ran end to end against a 40-article slice of the Wikipedia corpus. The
  live calls cost about $0.13 in total, as measured by the log analysis itself.

# Checkpoint 1: the project, the model on its own, and logs

This folder starts the capstone project. It sets up the environment once, introduces
`ragkit`, the small library the project grows across the checkpoints, and probes the
model without retrieval. Every answer is logged from the first question on, so later
checkpoints can compare runs and work out what they cost.

## What is included

| File | What it does |
|---|---|
| `README_SETUP.md` | One-time setup: editor, Python 3.12, virtual environment, install, `.env` |
| `requirements.txt` | Every package for every checkpoint, at pinned versions |
| `check_setup.py` | Checks the setup and prints the fix for each problem |
| `ragkit/config.py` | Settings from `.env`: API key, scenario, corpus folder, work folder |
| `ragkit/llm.py` | `make_llm`, `build_messages`, `ask`: the one way to call the model |
| `ragkit/pipelines/base.py` | `Answer` and `Pipeline`: the shape every pipeline shares |
| `ragkit/pipelines/llm_only.py` | The no-retrieval pipeline |
| `ragkit/chat.py` | `ChatSession` (history on or off) and the chat loop |
| `ragkit/runlog.py` | One JSON line per answered question, under `RAG_WORK_DIR/logs/` |
| `ragkit/pricing.py`, `ragkit/pricing.json` | Estimated cost from token counts |
| `ragkit/reports/runs.py` | A Markdown report that puts runs side by side |
| `samples/cp1_chat.py` | Chat with the model, history on or off |
| `samples/cp1_probes.py` | Probe prompts on one or more models, logged and reported |
| `tests/` | Offline tests: no API calls, no cost |

## How the pieces fit

Every question takes the same path, in this checkpoint and every later one:

```
ChatSession.ask(question)
  -> pipeline.answer(question, history)       what the pipeline does changes per checkpoint
       -> build_messages(...), ask(llm, ...)  the model call, with its tokens and time
  -> Answer(text, hits, calls, metadata)
  -> RunLog.record(answer)                    one line in the run's log file
```

Later checkpoints add pipelines and retrievers. The chat, the log, and the reports work
with all of them unchanged.

## How to use it

1. Follow `README_SETUP.md` until `python check_setup.py` ends with `Setup complete`.
2. Chat with history on, then off, and try the two-turn test from Lab 1.1
   ("When was the War of 1812?", then "And who won?"):
   ```
   python samples/cp1_chat.py
   python samples/cp1_chat.py --no-history
   ```
   Type `:history` to see exactly what is re-sent with the next question.
3. Compare the two chats: `python -m ragkit.reports.runs` writes a report on the two most
   recent runs. Open it in the editor's Markdown preview.
4. Add probes about the chosen corpus to `MY_PROBES` in `samples/cp1_probes.py`, then:
   ```
   python samples/cp1_probes.py
   python samples/cp1_probes.py --models openai/gpt-5.4-mini openai/gpt-5.4-nano
   python samples/cp1_probes.py --repeat 3
   ```
   Read every answer against the real document: correct, made up, hedged, or generic?
   The repeats show whether the model gives the same answer twice.

## For the Checkpoint 1.1 write-up

The probes report holds the evidence: each prompt, each answer, and how answers differ
between models and between repeats. The log files keep everything else, including
tokens and time, for the log analysis at the end of the project.

## Where output goes

Everything a run produces goes to `RAG_WORK_DIR` (set in `.env`), outside this folder:
`logs/` holds one `.jsonl` file per run, and `reports/` the Markdown reports. Moving to a
later checkpoint's folder keeps all of it.

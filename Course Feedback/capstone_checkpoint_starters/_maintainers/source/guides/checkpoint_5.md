# Checkpoint 5: agents

Until now, every question took a fixed path: retrieve once, then answer. An agent
decides the path itself: search again, read a whole article, ask the user, or answer.
This checkpoint adds two agents, both built on the baseline's retriever and both run
through the same evaluation, so the report shows whether letting the model decide
improves the answers.

## New in this checkpoint

| File | What it does |
|---|---|
| `ragkit/structured.py` | `ask_structured`: the model fills in a form (a Pydantic model) instead of writing free text, so its decisions can be acted on |
| `ragkit/retrievers/agentic.py` | An agentic retriever (Lab 5.1): search, judge whether the evidence is enough, search again with a new query if not; a LangGraph loop |
| `ragkit/pipelines/agent.py` | A tool-using agent (Lab 5.2): on each step the model plans one action: search, read a whole source, answer, or ask a clarifying question |
| `samples/cp5_agent.py` | Baseline vs both agents on the same questions; or a chat with the agent |

The agentic retriever is a retriever, so it plugs into the RAG pipeline unchanged. The
tool-using agent is a pipeline. Its clarifying question is returned as an ordinary
answer, so the chat needs no change: the user's reply arrives as the next turn. Both
agents have a step limit, so a question can never loop forever.

## How to use it

1. Evaluate both agents against the baseline:
   ```
   python samples/cp5_agent.py
   python samples/cp5_agent.py --questions ~/rag_course_work/my_questions.xlsx
   ```
2. Chat with the tool-using agent, and try an ambiguous question ("Who hosted it?"):
   ```
   python samples/cp5_agent.py --chat
   ```
3. Read the agents' decisions: each log line's `details` holds the rounds (agentic
   retriever) or the steps (tool-using agent), with the reason for every action.
4. Agents make several model calls per question, and every call is logged with its role
   (`assess`, `plan`, `answer`, ...). The quality report shows whether the extra calls
   bought better answers; `python -m ragkit.reports.runs --last 3` shows the calls and
   time per question.

## After Checkpoint 5

The structure is complete: corpus, retrievers, pipelines, agents, evaluation, logs, and
reports. Evolving the system from here is the project's own work; the next folder,
`checkpoint_log_analysis`, adds the tools to analyze everything logged so far, in
preparation for the performance work.

## For the Checkpoint 5.1 write-up

The agents report compares the baseline and both agents on recall and quality; the log
details show what each agent decided and why.

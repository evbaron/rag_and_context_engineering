"""A conversation with any pipeline, with history on or off. (Checkpoint 1)

ChatSession keeps the conversation and decides what is re-sent to the model:

    use_history=True    earlier (question, answer) pairs go with each new question
    use_history=False   each question goes alone, as if it were the first

Only questions and answers are kept, never the passages retrieved for them. Re-sending
old passages would make every turn bigger and more expensive, and text planted in one
turn would keep reaching the model in every later turn.

    python samples/cp1_chat.py              # chat with history on
    python samples/cp1_chat.py --no-history
"""

from __future__ import annotations

import time
from collections.abc import Callable

from ragkit.pipelines.base import Answer, Pipeline, Turn
from ragkit.runlog import RunLog

HELP = """Commands:
  :history   show the turns that will be re-sent with the next question
  :forget    clear the history
  :help      show this list
  :quit      stop (also: quit, exit)"""


class ChatSession:
    """Runs a conversation through ``pipeline`` and keeps its history."""

    def __init__(
        self,
        pipeline: Pipeline,
        use_history: bool = True,
        max_turns: int | None = None,
        log: RunLog | None = None,
    ):
        self.pipeline = pipeline
        self.use_history = use_history
        self.max_turns = max_turns  # keep only the most recent N turns; None keeps all
        self.log = log
        self.history: list[Turn] = []

    def turns_to_send(self) -> list[Turn]:
        """The earlier turns that go with the next question."""
        if not self.use_history:
            return []
        if self.max_turns is None:
            return list(self.history)
        return self.history[-self.max_turns :] if self.max_turns > 0 else []

    def ask(self, question: str) -> Answer:
        """Answer one question, remember the turn, and log it."""
        sent = self.turns_to_send()
        started = time.perf_counter()
        try:
            answer = self.pipeline.answer(question, sent)
        except Exception as error:
            if self.log is not None:
                self.log.record_error(question, error, history_turns=len(sent))
            raise
        latency_s = time.perf_counter() - started
        # The question as the pipeline used it, so a cleaned question is what gets replayed.
        self.history.append((answer.question, answer.text))
        if self.log is not None:
            self.log.record(answer, question=question, history_turns=len(sent), latency_s=latency_s)
        return answer

    def forget(self) -> None:
        self.history.clear()

    def describe_history(self) -> str:
        if not self.use_history:
            return "History is off: each question is sent alone."
        sent = self.turns_to_send()
        if not sent:
            return "No earlier turns yet: the next question is sent alone."
        lines = [f"{len(sent)} earlier turn(s) will be re-sent with the next question:"]
        for number, (question, answer) in enumerate(sent, start=1):
            lines.append(f"  {number}. Q: {_short(question)}")
            lines.append(f"     A: {_short(answer)}")
        return "\n".join(lines)


def chat_loop(
    session: ChatSession,
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> None:
    """Read a question, print the answer, repeat. Errors are shown, not fatal."""
    history_state = "on" if session.use_history else "off"
    print_fn(f"Chat with '{session.pipeline.name}', history {history_state}. Type :help for commands.")
    if session.log is not None:
        print_fn(f"Logging to {session.log.path}")
    while True:
        try:
            text = input_fn("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print_fn("\nGoodbye.")
            return
        if not text:
            continue
        if text.lower() in {":quit", "quit", "exit"}:
            print_fn("Goodbye.")
            return
        if text == ":help":
            print_fn(HELP)
            continue
        if text == ":history":
            print_fn(session.describe_history())
            continue
        if text == ":forget":
            session.forget()
            print_fn("History cleared.")
            continue
        try:
            answer = session.ask(text)
        except Exception as error:  # keep the chat alive after one failed turn
            print_fn(f"[error] {type(error).__name__}: {error}")
            continue
        print_fn(f"\nAssistant: {answer.text}")
        sources = sorted({hit.doc.metadata.get("source", "?") for hit in answer.hits})
        if sources:
            print_fn(f"  (sources: {', '.join(sources)})")


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."

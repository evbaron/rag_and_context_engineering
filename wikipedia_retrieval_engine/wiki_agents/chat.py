"""A multi-turn chat session over the guarded graph.

This is the interactive path, for trying the safeguards by hand and for replaying the
Checkpoint 6.1 attacks against the hardened system. It is **not** the measurement path:
quality, cost and the before/after comparison come from the RAGAS runs, as in 6.1.

Multi-turn matters here more than anywhere else, because 6.1's three adoptions were all
multi-turn: a fake source was pasted in one turn and adopted several turns later, when the
system's own evidence had a gap. So the session is built around three rules.

**Retrieval sees the current question only.** Earlier turns reach the answer model as
``(question, answer)`` pairs and nothing else, exactly as the 6.1 ``ConversationSession``
sent them. Earlier *evidence* is never re-sent.

**History stores the sanitised question, not the raw one.** The graph's
``sanitize_question`` node cleans the question before retrieval; this session then reads
the cleaned text back out of the final state and stores *that*. Storing the raw text would
let a forged source block survive in history for every later turn, which is precisely the
attack 6.1 recorded.

**The grounding check never sees history.** It is built from the answer's evidence items
alone (``evidence_haystack``). That is what makes it able to catch a planted fact: the
plant is in the prompt, so the model can use it, but it is not in the evidence, so the
check cannot be fooled by it.

    python "Capstone Checkpoint 7.1/survivor_agent_final.py" --chat
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from wikipedia_retrieval_engine.wiki_agents.agentic_models import AgentState, initial_agent_state

EXIT_WORDS = {"exit", "quit", ":q"}

BANNER = """Wikipedia retrieval engine - guarded chat.
Type a question, or 'exit' to stop. Commands:
  :state     what the last turn did (sanitising, evidence, guardrail)
  :history   the turns being re-sent to the answer model
  :forget    clear the history
"""


@dataclass
class TurnResult:
    """One turn: what was asked, what was delivered, and what the safeguards did."""

    question_raw: str
    question_sanitized: str
    answer: str
    state: AgentState
    guarded: bool = False

    @property
    def sanitizing(self) -> dict[str, Any]:
        return dict(self.state.get("input_sanitization") or {})

    @property
    def grounding(self) -> dict[str, Any]:
        return dict(self.state.get("grounding") or {})

    @property
    def evidence_count(self) -> int:
        return len(self.state.get("answer_evidence") or [])

    @property
    def context_characters(self) -> int:
        return len(self.state.get("answer_context") or "")

    def summary(self) -> str:
        lines = [
            f"  question changed by input filters: {self.question_sanitized != self.question_raw}",
            f"  evidence items sent to the answer: {self.evidence_count}",
            f"  answer context characters:         {self.context_characters:,}",
        ]
        sanitizing = self.sanitizing
        if sanitizing:
            lines.append(
                f"  input layers: escaped={sanitizing.get('input_escaped')}"
                f" forged_blocks={sanitizing.get('input_evidence_blocks_removed')}"
                f" injection_pattern={sanitizing.get('input_injection_pattern_hit')}"
                f" model_filter_changed={sanitizing.get('input_model_filter_changed')}"
                f" model_filter_failed_open={sanitizing.get('input_model_filter_failed_open')}"
            )
        grounding = self.grounding
        if grounding:
            lines.append(
                f"  grounding: policy={grounding.get('grounding_policy')}"
                f" ok={grounding.get('grounding_ok')}"
                f" acted={grounding.get('grounding_acted')}"
                f" ungrounded_spans={grounding.get('ungrounded_span_count')}"
            )
            for key, label in (("ungrounded_entities", "entities"), ("ungrounded_quotations", "quotations")):
                spans = grounding.get(key)
                if spans:
                    lines.append(f"    unsupported {label}: {spans}")
        return "\n".join(lines)


@dataclass
class ChatSession:
    """Drives the compiled graph across turns and keeps the conversation history."""

    graph: Any
    max_history_turns: int | None = None
    recursion_limit: int = 30
    call_with_backoff: Callable[[Callable[[], Any], str], Any] | None = None
    history: list[tuple[str, str]] = field(default_factory=list)
    turns: list[TurnResult] = field(default_factory=list)

    def ask(self, question: str) -> TurnResult:
        """Run one turn and record it. Raises nothing the caller cannot see."""

        state: AgentState = initial_agent_state(question)
        state["history"] = list(self.history)
        if self.max_history_turns is not None:
            state["max_history_turns"] = self.max_history_turns

        def invoke() -> AgentState:
            return self.graph.invoke(state, config={"recursion_limit": self.recursion_limit})

        final = self.call_with_backoff(invoke, "agent graph") if self.call_with_backoff else invoke()

        # The sanitised question, read back from the state the graph returned. Storing the
        # raw question instead would keep a forged source block alive in history.
        sanitized = final.get("question", question)
        answer = final.get("answer", "")
        grounding = final.get("grounding") or {}
        result = TurnResult(
            question_raw=question,
            question_sanitized=sanitized,
            answer=answer,
            state=final,
            guarded=bool(grounding.get("grounding_acted")),
        )
        self.history.append((sanitized, answer))
        self.turns.append(result)
        return result

    def forget(self) -> None:
        self.history.clear()

    def describe_history(self) -> str:
        if not self.history:
            return "  (no history; the next question is a first turn)"
        sent = self.history
        if self.max_history_turns is not None and self.max_history_turns >= 0:
            sent = self.history[-self.max_history_turns:] if self.max_history_turns else []
        lines = [f"  {len(self.history)} turn(s) stored, {len(sent)} re-sent to the answer model:"]
        for index, (question, answer) in enumerate(sent, start=1):
            lines.append(f"    {index}. Q: {question[:88]}")
            lines.append(f"       A: {answer[:88]}")
        return "\n".join(lines)


def chat(
    session: ChatSession,
    *,
    banner: str = BANNER,
    show_state: bool = False,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> None:
    """A read-eval-print loop over ``session``.

    ``input_fn`` and ``print_fn`` are injectable so the loop can be exercised offline
    without a terminal; ``tests/test_chat.py`` drives it that way.
    """

    print_fn(banner)
    while True:
        try:
            raw = input_fn("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print_fn("\nGoodbye.")
            return
        if not raw:
            continue
        if raw.lower() in EXIT_WORDS:
            print_fn("Goodbye.")
            return
        if raw == ":forget":
            session.forget()
            print_fn("  history cleared.")
            continue
        if raw == ":history":
            print_fn(session.describe_history())
            continue
        if raw == ":state":
            print_fn(session.turns[-1].summary() if session.turns else "  (no turns yet)")
            continue

        try:
            result = session.ask(raw)
        except Exception as error:  # a chat loop must survive a failed turn
            print_fn(f"  [error] {type(error).__name__}: {error}")
            continue

        if result.question_sanitized != result.question_raw:
            print_fn(f"  [input filter] question rewritten to: {result.question_sanitized}")
        print_fn(f"\nAssistant: {result.answer}\n")
        if show_state:
            print_fn(result.summary())

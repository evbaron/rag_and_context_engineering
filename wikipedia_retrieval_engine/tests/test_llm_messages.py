from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from wikipedia_retrieval_engine.retrievers.llm import (
    OPENROUTER_REFERER,
    SYSTEM_PROMPT,
    answer,
    build_answer_messages,
    openrouter_headers,
)

CONTEXT = "[Evidence ID: X.html#section-000-00]\nSource article: X.html\nBody text."
QUESTION = "Where were the 1972 Winter Olympics held?"

# The single-turn message pair sent by every checkpoint since 2.1, written out
# literally so a change to the prompt layout fails here.
SINGLE_TURN = [
    (SystemMessage, SYSTEM_PROMPT),
    (HumanMessage, f"Context (Wikipedia articles):\n{CONTEXT}\n\nQuestion: {QUESTION}"),
]


def _shape(messages: list[BaseMessage]) -> list[tuple[type, str]]:
    return [(type(message), message.content) for message in messages]


class _RecordingLLM:
    """Chat-model stand-in that records the messages it receives."""

    def __init__(self) -> None:
        self.messages: list[BaseMessage] = []

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        self.messages = list(messages)
        return AIMessage(content="ok")


class AnswerMessageTests(unittest.TestCase):
    def test_without_history_matches_the_single_turn_prompt(self) -> None:
        self.assertEqual(_shape(build_answer_messages(QUESTION, CONTEXT)), SINGLE_TURN)

    def test_answer_still_sends_the_single_turn_prompt(self) -> None:
        llm = _RecordingLLM()

        self.assertEqual(answer(QUESTION, CONTEXT, llm=llm), "ok")
        self.assertEqual(_shape(llm.messages), SINGLE_TURN)

    def test_history_turns_precede_the_current_message(self) -> None:
        messages = build_answer_messages(
            QUESTION,
            CONTEXT,
            history=[("first question", "first answer"), ("second question", "second answer")],
        )

        self.assertEqual(
            _shape(messages),
            [
                SINGLE_TURN[0],
                (HumanMessage, "first question"),
                (AIMessage, "first answer"),
                (HumanMessage, "second question"),
                (AIMessage, "second answer"),
                SINGLE_TURN[1],
            ],
        )

    def test_max_history_turns_keeps_the_most_recent_turns(self) -> None:
        history = [("q1", "a1"), ("q2", "a2"), ("q3", "a3")]

        last_two = build_answer_messages(QUESTION, CONTEXT, history=history, max_history_turns=2)
        none_kept = build_answer_messages(QUESTION, CONTEXT, history=history, max_history_turns=0)

        self.assertEqual([m.content for m in last_two[1:-1]], ["q2", "a2", "q3", "a3"])
        self.assertEqual(_shape(none_kept), SINGLE_TURN)

    def test_custom_system_prompt_is_used(self) -> None:
        messages = build_answer_messages(QUESTION, CONTEXT, system_prompt="Custom rules.")

        self.assertEqual(_shape(messages[:1]), [(SystemMessage, "Custom rules.")])


class OpenRouterHeaderTests(unittest.TestCase):
    def test_each_role_gets_its_own_origin(self) -> None:
        referers = {
            title: openrouter_headers(title)["HTTP-Referer"]
            for title in ("WRE retriever", "WRE judge", "WRE embedding", "WRE replay answer")
        }

        self.assertEqual(referers["WRE judge"], f"{OPENROUTER_REFERER}/judge")
        self.assertEqual(referers["WRE replay answer"], f"{OPENROUTER_REFERER}/replay-answer")
        self.assertEqual(len(set(referers.values())), 4)

    def test_title_and_hidden_visibility_are_sent(self) -> None:
        headers = openrouter_headers("WRE judge")

        self.assertEqual(headers["X-OpenRouter-Title"], "WRE judge")
        self.assertEqual(headers["X-Title"], "WRE judge")
        self.assertEqual(headers["X-OpenRouter-App-Visibility"], "hidden")


if __name__ == "__main__":
    unittest.main()

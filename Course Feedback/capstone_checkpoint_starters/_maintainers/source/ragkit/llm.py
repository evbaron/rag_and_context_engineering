"""Calling the chat model. (Checkpoint 1)

Three functions, used by every pipeline:

    make_llm()        creates the chat model client (through OpenRouter)
    build_messages()  puts the system prompt, earlier turns, context, and question in order
    ask()             sends the messages; returns the reply and a record of the call

The model keeps no memory between calls. A conversation's "memory" is the earlier
turns, re-sent with every new question by build_messages(). Without them, a follow-up
such as "And who won?" has nothing to refer to.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ragkit import config
from ragkit.pipelines.base import LLMCall, Turn

# The longest reply allowed, in tokens. OpenRouter reserves credit for the longest
# possible reply before every call; without a cap, a key with little credit left fails
# even on short questions (error 402). Real answers in this project stay far below it.
DEFAULT_MAX_TOKENS = 4000

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question accurately and concisely. "
    "When you quote a source, quote it exactly. If you are not sure, say so instead of guessing."
)


def make_llm(
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = DEFAULT_MAX_TOKENS,
) -> ChatOpenAI:
    """Create a chat model client. Retries rate-limit and connection errors 3 times."""
    return ChatOpenAI(
        model=model or config.model(),
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=config.api_key(),
        base_url=config.OPENROUTER_BASE_URL,
        max_retries=3,
        timeout=180,
    )


def build_messages(
    question: str,
    *,
    context: str | None = None,
    history: Sequence[Turn] = (),
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> list[BaseMessage]:
    """Return the messages for one model call, in the order the model reads them:

    1. the system prompt (the rules)
    2. each earlier turn as a question/answer pair (empty when history is off)
    3. the new question, with the retrieved context in front of it when there is any
    """
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for earlier_question, earlier_answer in history:
        messages.append(HumanMessage(content=earlier_question))
        messages.append(AIMessage(content=earlier_answer))
    if context:
        messages.append(HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"))
    else:
        messages.append(HumanMessage(content=question))
    return messages


def ask(llm: Any, messages: list[BaseMessage], role: str = "answer") -> tuple[str, LLMCall]:
    """Send ``messages`` to ``llm``. Return the reply text and a record of the call."""
    started = time.perf_counter()
    response = llm.invoke(messages)
    latency_s = time.perf_counter() - started
    return message_text(response), call_record(response, llm, role, latency_s)


def call_record(response: Any, llm: Any, role: str, latency_s: float) -> LLMCall:
    """Read the token counts the provider reported for one call."""
    usage = getattr(response, "usage_metadata", None) or {}
    details = usage.get("input_token_details") or {}
    reported_model = (getattr(response, "response_metadata", None) or {}).get("model_name")
    return LLMCall(
        role=role,
        model=reported_model or getattr(llm, "model_name", None) or "unknown",
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        latency_s=round(latency_s, 3),
        cached_tokens=int(details.get("cache_read") or 0),
    )


def message_text(response: Any) -> str:
    """The text of a model reply. Some providers return a list of content blocks."""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return str(content)

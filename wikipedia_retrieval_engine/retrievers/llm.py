"""LLM and embedding clients. Kept separate from retriever ranking logic."""
from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "openai/gpt-5.4-mini"
EMBEDDING_MODEL = "openai/text-embedding-3-small"
TEMPERATURE = 0.2

# OpenRouter app attribution. These two HTTP headers are surfaced by OpenRouter
# analytics as the `app` (X-Title) and `origin` (HTTP-Referer) dimensions, so
# retriever, embedding, and judge calls can be told apart even though they all
# use the same model. A localhost referer keeps this project out of OpenRouter's
# public app rankings.
OPENROUTER_REFERER = "http://localhost/wikipedia-retrieval-engine"


def openrouter_headers(app_title: str) -> dict[str, str]:
    """Tag every OpenRouter call with an app name so usage can be split per role."""
    return {"HTTP-Referer": OPENROUTER_REFERER, "X-Title": app_title}


SYSTEM_PROMPT = """You are a helpful assistant for a Wikipedia retrieval engine. \
You answer questions by drawing information exclusively from the Wikipedia articles \
provided to you as context in each message.

Rules:
- If the answer can be found in the provided articles, answer clearly and concisely, \
and quote from them where you can.
- If the provided articles do not contain enough information to answer the question, \
say so explicitly and do not speculate or use outside knowledge.
- Do not answer questions that are unrelated to the content of the provided articles."""


def load_api_key() -> str | None:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / ".env",
        here.parents[3] / ".env",
        Path.cwd() / ".env",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
    load_dotenv(override=False)
    return os.environ.get("OPENROUTER_API_KEY")


def require_api_key() -> str:
    key = load_api_key()
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Put it in a .env file "
            "(rag_and_context_engineering/.env) and rerun."
        )
    return key


def make_llm(
    model: str = LLM_MODEL,
    temperature: float = TEMPERATURE,
    app_title: str = "WRE retriever",
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=require_api_key(),
        base_url=OPENROUTER_BASE_URL,
        default_headers=openrouter_headers(app_title),
    )


def get_embeddings(model: str = EMBEDDING_MODEL) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=model,
        api_key=require_api_key(),
        base_url=OPENROUTER_BASE_URL,
        default_headers=openrouter_headers("WRE embedding"),
    )


def build_answer_messages(
    query: str,
    context: str,
    *,
    history: Sequence[tuple[str, str]] | None = None,
    max_history_turns: int | None = None,
    system_prompt: str = SYSTEM_PROMPT,
) -> list[BaseMessage]:
    """Build the answer model's message list, optionally with conversation history.

    The chat model keeps no memory between calls, so earlier turns must be re-sent
    on every call. ``history`` holds them oldest first as ``(user_message,
    answer)`` pairs; each becomes a ``HumanMessage``/``AIMessage`` pair between the
    system prompt and the current message. Only the text of earlier questions and
    answers is sent, not the context retrieved for them.

    ``max_history_turns`` keeps the most recent N turns (``None`` keeps all, ``0``
    keeps none). Without history the result is the single-turn message pair every
    checkpoint has sent through ``answer()``.
    """
    turns = list(history or [])
    if max_history_turns is not None:
        turns = turns[-max_history_turns:] if max_history_turns > 0 else []
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for user_message, previous_answer in turns:
        messages.append(HumanMessage(content=user_message))
        messages.append(AIMessage(content=previous_answer))
    messages.append(
        HumanMessage(content=f"Context (Wikipedia articles):\n{context}\n\nQuestion: {query}")
    )
    return messages


def answer(
    query: str,
    context: str,
    llm: ChatOpenAI | None = None,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    """Answer ``query`` from ``context`` using an explicit system prompt.

    Retrieval is intentionally outside this function so callers can log and reuse
    the exact same hits that are sent to the model.
    """
    if not context.strip():
        raise ValueError("Cannot ask the LLM to answer without retrieved context.")
    client = llm or make_llm()
    messages = build_answer_messages(query, context, system_prompt=system_prompt)
    response = client.invoke(messages)
    content = response.content if hasattr(response, "content") else response
    return content if isinstance(content, str) else str(content)


def decompose_query(query: str, system_prompt, original_query: str, llm: ChatOpenAI | None = None) -> str:
    """Decompose the query into a list of sub-queries and reasoning instructions."""
    client = llm or make_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ]
    response = client.invoke(messages)
    return response.content if hasattr(response, "content") else str(response)

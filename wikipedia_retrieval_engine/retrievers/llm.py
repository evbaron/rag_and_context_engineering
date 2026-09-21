"""LLM and embedding clients. Kept separate from retriever ranking logic."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "openai/gpt-5.4-mini"
EMBEDDING_MODEL = "openai/text-embedding-3-small"
TEMPERATURE = 0.2

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


def make_llm(model: str = LLM_MODEL, temperature: float = TEMPERATURE) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=require_api_key(),
        base_url=OPENROUTER_BASE_URL,
    )


def get_embeddings(model: str = EMBEDDING_MODEL) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=model,
        api_key=require_api_key(),
        base_url=OPENROUTER_BASE_URL,
    )


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
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Context (Wikipedia articles):\n{context}\n\nQuestion: {query}"),
    ]
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

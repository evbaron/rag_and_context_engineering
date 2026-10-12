"""Embedding text, and estimating what embedding will cost. (Checkpoint 2)

An embedding turns text into a list of numbers so that texts with similar meaning get
similar numbers. The vector retriever compares the question's numbers with every
passage's numbers. Embedding a corpus costs money once (when the index is built);
each question then costs one small embedding call.
"""

from __future__ import annotations

from collections.abc import Iterable

from langchain_openai import OpenAIEmbeddings

from ragkit import config
from ragkit.pricing import load_prices, price_for


def make_embeddings(model: str | None = None) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=model or config.embedding_model(),
        api_key=config.api_key(),
        base_url=config.OPENROUTER_BASE_URL,
        max_retries=3,
    )


def count_tokens(texts: Iterable[str]) -> int:
    """Tokens in ``texts`` as OpenAI models count them (an estimate for other models).

    The tokenizer table is downloaded on first use; without a network connection the
    count falls back to the usual rule of thumb of about 4 characters per token.
    """
    texts = list(texts)
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return sum(len(text) for text in texts) // 4
    return sum(len(encoding.encode(text, disallowed_special=())) for text in texts)


def estimate_embedding_cost(texts: Iterable[str], model: str | None = None) -> tuple[int, float | None]:
    """(tokens, USD) for embedding ``texts`` once; USD is None for an unknown model."""
    tokens = count_tokens(texts)
    row = price_for(model or config.embedding_model(), load_prices())
    return tokens, (tokens * row["input"] / 1_000_000 if row else None)

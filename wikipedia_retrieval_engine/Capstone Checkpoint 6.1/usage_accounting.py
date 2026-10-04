"""Token usage and cost accounting shared by the Checkpoint 6.1 cost starters.

Both ``cost_test_starter.py`` (live agent runs) and ``answer_replay_starter.py``
(re-answering saved runs) answer two questions the same way:

1. What did one chat-model call use? ``usage_from_message`` reads the reply's
   ``usage_metadata`` (input, cached input, output, and reasoning tokens) and its
   ``response_metadata`` (model name, and the cost OpenRouter reports).
2. What does that usage cost? ``call_cost`` prices it twice:

   list     every input token at the full input rate, as if nothing were cached.
            This is the fair comparison between context variants: repeat runs of
            the same prompt get cache hits that a stream of distinct user
            questions would not (70.5% of the 4.1 graph's input was cached for
            that reason).
   billed   cached input tokens at the cached rate, as OpenRouter bills them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PRICES_PATH = Path(__file__).resolve().parent / "pricing" / "model_prices.json"

Price = dict[str, Any]  # rates in USD per 1M tokens, plus an optional "long_context" tier
Prices = dict[str, Price]

FREE_PRICE: Price = {"input": 0.0, "cached_input": 0.0, "output": 0.0}


def load_prices(path: Path = PRICES_PATH) -> Prices:
    """USD per 1M tokens by model id; a missing file means no estimates."""

    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("usd_per_million_tokens", {})


def price_for(model: str | None, prices: Prices) -> Price | None:
    """The price entry for ``model``: exact id, else the longest matching id prefix.

    The longest prefix matters because replies name a dated snapshot, such as
    ``openai/gpt-5.4-mini-20260317``, which also starts with ``openai/gpt-5.4``.
    Free models (id ends in ``:free``) cost nothing.
    """

    if not model:
        return None
    if model.endswith(":free"):
        return FREE_PRICE
    if model in prices:
        return prices[model]
    matches = [key for key in prices if model.startswith(key)]
    return prices[max(matches, key=len)] if matches else None


def call_cost(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    price: Price | None,
) -> dict[str, float | None]:
    """List and billed cost in USD for one call's token counts (None without a price).

    A price may carry a ``long_context`` tier: above ``min_prompt_tokens`` the whole call
    is charged at the tier's rates. ``gpt-5.4`` doubles its input price above 272K prompt
    tokens; the 7.1 GT run sent two 293K-token prompts (GT09), and only the tier reproduces
    what OpenRouter billed for them ($0.798 and $1.473).
    """

    if not price or price.get("input") is None or price.get("output") is None:
        return {"list": None, "billed": None}
    tier = price.get("long_context")
    if isinstance(tier, dict) and input_tokens > tier.get("min_prompt_tokens", float("inf")):
        price = {**price, **{key: value for key, value in tier.items() if key != "min_prompt_tokens"}}
    cached_rate = price["input"] if price.get("cached_input") is None else price["cached_input"]
    cached = min(cached_input_tokens, input_tokens)
    output = output_tokens * price["output"]
    return {
        "list": (input_tokens * price["input"] + output) / 1_000_000,
        "billed": ((input_tokens - cached) * price["input"] + cached * cached_rate + output) / 1_000_000,
    }


def _count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def usage_from_message(message: Any) -> dict[str, Any]:
    """Token counts, model, and provider-reported cost of one chat-model reply.

    Missing or malformed fields become 0 or None. This never raises: LangChain
    swallows callback exceptions, so an error here would only show up as missing
    records.
    """

    usage = getattr(message, "usage_metadata", None) or {}
    metadata = getattr(message, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage") or {}
    cost = token_usage.get("cost")
    return {
        "model": metadata.get("model_name") or metadata.get("model"),
        "input_tokens": _count(usage.get("input_tokens")),
        "output_tokens": _count(usage.get("output_tokens")),
        "total_tokens": _count(usage.get("total_tokens")),
        "cached_input_tokens": _count((usage.get("input_token_details") or {}).get("cache_read")),
        "reasoning_tokens": _count((usage.get("output_token_details") or {}).get("reasoning")),
        "provider_cost_usd": float(cost) if isinstance(cost, (int, float)) else None,
    }

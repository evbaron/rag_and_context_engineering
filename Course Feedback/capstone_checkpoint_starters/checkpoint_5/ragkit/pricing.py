"""Estimated cost of model calls, from a price table. (Checkpoint 1)

Prices are USD per million tokens, copied from OpenRouter's model list on the date in
pricing.json. They change, so pricing.json carries its date; update it when they do.
A model missing from the table gets no estimate (None), never a guess. The estimate is
the list price; the provider's bill can be lower when it serves cached input.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

PRICES_FILE = Path(__file__).with_name("pricing.json")


def load_prices(path: Path | None = None) -> dict[str, dict[str, Any]]:
    with (path or PRICES_FILE).open(encoding="utf-8") as handle:
        return json.load(handle)["usd_per_million_tokens"]


def price_for(model: str, prices: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The price row for ``model``: the longest table id that the model id starts with."""
    if model.endswith(":free"):
        return {"input": 0.0, "cached_input": 0.0, "output": 0.0}
    matches = [model_id for model_id in prices if model.startswith(model_id)]
    return prices[max(matches, key=len)] if matches else None


def call_cost(call: Any, prices: dict[str, dict[str, Any]] | None = None) -> float | None:
    """USD for one logged call (a dict from a log line, or an LLMCall)."""
    if is_dataclass(call):
        call = asdict(call)
    row = price_for(call.get("model") or "", prices or load_prices())
    if row is None:
        return None
    cached = int(call.get("cached_tokens") or 0)
    fresh = max(int(call.get("input_tokens") or 0) - cached, 0)
    cached_price = row.get("cached_input")
    if cached_price is None:
        cached_price = row["input"]
    usd = fresh * row["input"] + cached * cached_price + int(call.get("output_tokens") or 0) * row["output"]
    return usd / 1_000_000


def record_cost(
    record: dict[str, Any],
    prices: dict[str, dict[str, Any]] | None = None,
    *,
    roles: set[str] | None = None,
    exclude_roles: set[str] = frozenset(),
) -> float | None:
    """USD for every call in one log line. ``roles`` keeps only those roles;
    ``exclude_roles`` leaves some out (for example the evaluation judge)."""
    prices = prices or load_prices()
    total = 0.0
    for call in record.get("calls", []):
        role = call.get("role", "")
        if (roles is not None and role not in roles) or role in exclude_roles:
            continue
        usd = call_cost(call, prices)
        if usd is None:
            return None
        total += usd
    return total

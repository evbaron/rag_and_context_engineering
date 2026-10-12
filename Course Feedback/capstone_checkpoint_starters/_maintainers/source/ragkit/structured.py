"""Asking the model to fill in a form instead of writing free text. (Checkpoint 5)

An agent needs decisions it can act on: "search again for X", "answer now". Free text
is hard to act on reliably, so the model fills in a Pydantic model instead: a form with
named, typed fields. The call is recorded like any other, so its tokens and time reach
the log.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from ragkit.llm import call_record
from ragkit.pipelines.base import LLMCall

Form = TypeVar("Form", bound=BaseModel)


def ask_structured(llm: Any, messages: list[BaseMessage], schema: type[Form], role: str) -> tuple[Form, LLMCall]:
    """Send ``messages``; return the filled-in ``schema`` and a record of the call."""
    started = time.perf_counter()
    result = llm.with_structured_output(schema, method="function_calling", include_raw=True).invoke(messages)
    call = call_record(result["raw"], llm, role, time.perf_counter() - started)
    parsed = result.get("parsed")
    if parsed is None:
        raise ValueError(f"The model's reply did not fit the {schema.__name__} form: {result.get('parsing_error')}")
    return parsed, call

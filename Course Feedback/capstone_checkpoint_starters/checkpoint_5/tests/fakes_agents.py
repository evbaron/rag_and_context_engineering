"""A stand-in model that fills in forms, for the agent tests (Checkpoint 5)."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from tests.fakes import FakeLLM


class FakeFormLLM(FakeLLM):
    """``with_structured_output`` returns the scripted forms in order; ``invoke`` returns text replies."""

    def __init__(self, forms=None, replies=None):
        super().__init__(replies)
        self.forms = list(forms or [])

    def with_structured_output(self, schema, **kwargs):
        outer = self

        class Runner:
            def invoke(self, messages):
                outer.sent.append(messages)
                usage = {"input_tokens": 20, "output_tokens": 4, "total_tokens": 24}
                return {"raw": AIMessage(content="", usage_metadata=usage), "parsed": outer.forms.pop(0), "parsing_error": None}

        return Runner()

"""Stand-ins for the model, so tests run offline and cost nothing."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from ragkit.pipelines.base import Answer, LLMCall, Pipeline


class FakeLLM:
    """Behaves like ChatOpenAI for ``invoke``: returns scripted replies, records inputs."""

    model_name = "fake/model"

    def __init__(self, replies=None, input_tokens=10, output_tokens=5):
        self.replies = list(replies or ["ok"])
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.sent = []

    def invoke(self, messages):
        self.sent.append(messages)
        text = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return AIMessage(
            content=text,
            usage_metadata={
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
            response_metadata={"model_name": self.model_name},
        )


class EchoPipeline(Pipeline):
    """Answers 'answer N' and remembers the history it received."""

    name = "echo"

    def __init__(self):
        self.received = []

    def answer(self, question, history=()):
        self.received.append(list(history))
        number = len(self.received)
        call = LLMCall(role="answer", model="fake/model", input_tokens=10, output_tokens=5, latency_s=0.01)
        return Answer(text=f"answer {number}", question=question, calls=[call])


class FailingPipeline(Pipeline):
    name = "failing"

    def answer(self, question, history=()):
        raise RuntimeError("model unavailable")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ragkit.llm import ask, build_messages, call_record, message_text
from ragkit.pipelines.llm_only import LLMOnlyPipeline
from tests.fakes import FakeLLM


def test_messages_without_history_are_system_then_question():
    messages = build_messages("When was the War of 1812?", system_prompt="rules")
    assert [type(m) for m in messages] == [SystemMessage, HumanMessage]
    assert messages[0].content == "rules"
    assert messages[1].content == "When was the War of 1812?"


def test_history_turns_sit_between_system_prompt_and_new_question():
    history = [("When was the War of 1812?", "1812 to 1815.")]
    messages = build_messages("And who won?", history=history)
    assert [type(m) for m in messages] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert messages[1].content == "When was the War of 1812?"
    assert messages[2].content == "1812 to 1815."
    assert messages[3].content == "And who won?"


def test_context_goes_in_front_of_the_question():
    messages = build_messages("Who holds the record?", context="[1] Usain Bolt ran 9.58 s.")
    assert messages[-1].content.startswith("Context:\n[1] Usain Bolt")
    assert messages[-1].content.endswith("Question: Who holds the record?")


def test_ask_returns_text_and_a_call_record():
    llm = FakeLLM(["hello"], input_tokens=12, output_tokens=3)
    text, call = ask(llm, build_messages("hi"), role="answer")
    assert text == "hello"
    assert (call.role, call.model, call.input_tokens, call.output_tokens) == ("answer", "fake/model", 12, 3)
    assert call.latency_s >= 0


def test_call_record_reads_cached_tokens():
    response = AIMessage(
        content="x",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "input_token_details": {"cache_read": 60},
        },
    )
    call = call_record(response, FakeLLM(), "answer", 0.5)
    assert call.cached_tokens == 60


def test_message_text_joins_content_blocks():
    assert message_text(AIMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])) == "ab"


def test_llm_only_pipeline_answers_and_records_its_call():
    llm = FakeLLM(["1812 to 1815."])
    pipeline = LLMOnlyPipeline(model="fake/model", llm=llm)
    answer = pipeline.answer("When was the War of 1812?")
    assert answer.text == "1812 to 1815."
    assert answer.question == "When was the War of 1812?"
    assert len(answer.calls) == 1 and answer.calls[0].role == "answer"
    assert pipeline.settings() == {"name": "llm_only", "model": "fake/model", "temperature": 0.2}

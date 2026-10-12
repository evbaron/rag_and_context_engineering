import pytest

from ragkit.chat import ChatSession, chat_loop
from ragkit.runlog import RunLog, read_records
from tests.fakes import EchoPipeline, FailingPipeline


def test_history_on_sends_earlier_turns():
    pipeline = EchoPipeline()
    session = ChatSession(pipeline, use_history=True)
    session.ask("first")
    session.ask("second")
    assert pipeline.received[0] == []
    assert pipeline.received[1] == [("first", "answer 1")]


def test_history_off_sends_each_question_alone():
    pipeline = EchoPipeline()
    session = ChatSession(pipeline, use_history=False)
    session.ask("first")
    session.ask("second")
    assert pipeline.received == [[], []]
    assert session.history == [("first", "answer 1"), ("second", "answer 2")]
    assert "History is off" in session.describe_history()


def test_max_turns_keeps_only_the_most_recent_turns():
    pipeline = EchoPipeline()
    session = ChatSession(pipeline, max_turns=1)
    for question in ["a", "b", "c"]:
        session.ask(question)
    assert pipeline.received[2] == [("b", "answer 2")]


def test_forget_clears_the_history():
    session = ChatSession(EchoPipeline())
    session.ask("first")
    session.forget()
    assert session.history == []
    assert "No earlier turns" in session.describe_history()


def test_each_turn_is_logged_with_the_turns_sent():
    log = RunLog("test", checkpoint="1", settings={"name": "echo"})
    session = ChatSession(EchoPipeline(), log=log)
    session.ask("first")
    session.ask("second")
    records = read_records([log.path])
    assert [r["question"] for r in records] == ["first", "second"]
    assert [r["history_turns"] for r in records] == [0, 1]
    assert records[1]["calls"][0]["role"] == "answer"


def test_a_failed_turn_is_logged_and_raised():
    log = RunLog("test", settings={"name": "failing"})
    session = ChatSession(FailingPipeline(), log=log)
    with pytest.raises(RuntimeError):
        session.ask("hello")
    assert read_records([log.path])[0]["error"] == "RuntimeError: model unavailable"
    assert session.history == []


def test_chat_loop_runs_commands_and_survives_errors():
    inputs = iter(["hello", ":history", ":forget", "", ":quit"])
    printed = []
    chat_loop(ChatSession(EchoPipeline()), input_fn=lambda _: next(inputs), print_fn=printed.append)
    text = "\n".join(printed)
    assert "Assistant: answer 1" in text
    assert "1 earlier turn(s) will be re-sent" in text
    assert "History cleared." in text
    assert text.endswith("Goodbye.")

    inputs = iter(["hello", "quit"])
    printed = []
    chat_loop(ChatSession(FailingPipeline()), input_fn=lambda _: next(inputs), print_fn=printed.append)
    assert any("[error] RuntimeError" in line for line in printed)

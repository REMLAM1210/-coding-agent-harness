import pytest
from harness.models import Action, Context, Message
from harness.llm.mock_client import MockLLMClient


def test_mock_queue_mode():
    client = MockLLMClient(actions=[
        Action(type="WriteFile", args={"path": "foo.py", "content": "x"}),
        Action(type="Done", args={"summary": "done"}),
    ])
    ctx = Context(system_prompt="test")
    a1 = client.propose_action(ctx)
    assert a1.type == "WriteFile"
    a2 = client.propose_action(ctx)
    assert a2.type == "Done"


def test_mock_queue_exhausted():
    client = MockLLMClient(actions=[Action(type="Done", args={})])
    client.propose_action(Context(system_prompt=""))
    with pytest.raises(Exception, match="MockExhausted"):
        client.propose_action(Context(system_prompt=""))


def test_mock_responder_mode():
    def responder(ctx: Context) -> Action:
        if ctx.feedback_signals:
            return Action(type="Done", args={"summary": "fixed"})
        return Action(type="RunTests", args={})

    client = MockLLMClient(responder=responder)
    ctx = Context(system_prompt="test")
    a1 = client.propose_action(ctx)
    assert a1.type == "RunTests"
    ctx.feedback_signals = ["some_signal"]
    a2 = client.propose_action(ctx)
    assert a2.type == "Done"

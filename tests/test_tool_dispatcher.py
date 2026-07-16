import pytest
from harness.models import Action, ActionResult, Decision, DecisionType, Workspace
from harness.tools.base import Tool, ToolDispatcher


class FakeTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "ReadFile"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        return ActionResult(success=True, output="file content")


class FakeGuardrail:
    def check(self, action: Action) -> Decision:
        if action.type == "RunShell" and "rm -rf" in action.args.get("command", ""):
            return Decision(verdict=DecisionType.DENY, reason="guardrail_denied")
        return Decision(verdict=DecisionType.ALLOW)


class FakeSandbox:
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        return ActionResult(success=True, output="executed")


def test_dispatch_allow():
    td = ToolDispatcher(tools=[FakeTool()], guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="ReadFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    assert result.success
    assert result.output == "file content"


def test_dispatch_deny_returns_rejected_feedback():
    from harness.feedback.models import FeedbackSignal
    td = ToolDispatcher(tools=[FakeTool()], guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="RunShell", args={"command": "rm -rf /"}), Workspace(cwd="/tmp"))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "guardrail_denied"


def test_dispatch_no_tool_handles():
    td = ToolDispatcher(tools=[FakeTool()], guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="ListFiles", args={}), Workspace(cwd="/tmp"))
    assert result.success is False
    assert "no tool" in result.error.lower()

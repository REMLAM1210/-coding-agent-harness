import pytest
from harness.models import Action, ActionResult, Decision, DecisionType, Workspace
from harness.tools.base import Tool, ToolDispatcher
from harness.feedback.models import FeedbackSignal


class FakeTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "ReadFile"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        return ActionResult(success=True, output="file content")


class FakeDeleteTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "DeleteFile"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        return ActionResult(success=True, output="deleted")


class FakeGuardrail:
    def check(self, action: Action) -> Decision:
        if action.type == "RunShell" and "rm -rf" in action.args.get("command", ""):
            return Decision(verdict=DecisionType.DENY, reason="guardrail_denied")
        if action.type == "DeleteFile":
            return Decision(verdict=DecisionType.REQUIRE_APPROVAL, reason="needs human approval")
        return Decision(verdict=DecisionType.ALLOW)


class FakeSandbox:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools = tools or []

    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        for tool in self._tools:
            if tool.can_handle(action):
                return tool.execute(action, workspace)
        return ActionResult(success=False, error=f"No tool can handle action type '{action.type}'")


class FakeApprovalResolver:
    def __init__(self, verdict: DecisionType = DecisionType.ALLOW, reason: str = ""):
        self._verdict = verdict
        self._reason = reason

    def request_approval(self, action: Action) -> Decision:
        return Decision(verdict=self._verdict, reason=self._reason)


def test_dispatch_allow():
    tool = FakeTool()
    td = ToolDispatcher(guardrail=FakeGuardrail(), sandbox=FakeSandbox(tools=[tool]))
    result = td.dispatch(Action(type="ReadFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    assert result.success
    assert result.output == "file content"


def test_dispatch_deny_returns_rejected_feedback():
    td = ToolDispatcher(guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="RunShell", args={"command": "rm -rf /"}), Workspace(cwd="/tmp"))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "guardrail_denied"


def test_dispatch_no_tool_handles():
    td = ToolDispatcher(guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="ListFiles", args={}), Workspace(cwd="/tmp"))
    assert result.success is False
    assert "no tool" in result.error.lower()


def test_dispatch_require_approval_no_resolver():
    td = ToolDispatcher(guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="DeleteFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "no_approval_resolver"


def test_dispatch_require_approval_resolver_allows():
    tool = FakeDeleteTool()
    resolver = FakeApprovalResolver(verdict=DecisionType.ALLOW)
    td = ToolDispatcher(
        guardrail=FakeGuardrail(),
        sandbox=FakeSandbox(tools=[tool]),
        approval_resolver=resolver,
    )
    result = td.dispatch(Action(type="DeleteFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    assert result.success
    assert result.output == "deleted"


def test_dispatch_require_approval_resolver_denies():
    resolver = FakeApprovalResolver(verdict=DecisionType.DENY)
    td = ToolDispatcher(
        guardrail=FakeGuardrail(),
        sandbox=FakeSandbox(),
        approval_resolver=resolver,
    )
    result = td.dispatch(Action(type="DeleteFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    assert isinstance(result, FeedbackSignal)
    assert result.source == "hitl"
    assert result.reason == "approval_denied"

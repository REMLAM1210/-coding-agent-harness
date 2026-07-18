from harness.models import Action, Decision, DecisionType
from harness.feedback.models import FeedbackSignal
from harness.governance.hitl import HitlStateMachine, ApprovalResolver


class StubApprovalResolver(ApprovalResolver):
    def __init__(self, decision: Decision):
        self._decision = decision
    def request_approval(self, action: Action) -> Decision:
        return self._decision


def test_hitl_approve():
    sm = HitlStateMachine(resolver=StubApprovalResolver(Decision(verdict=DecisionType.ALLOW)))
    result = sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert sm.state == "IDLE"
    assert result.verdict == DecisionType.ALLOW


def test_hitl_deny_returns_rejected_signal():
    sm = HitlStateMachine(resolver=StubApprovalResolver(Decision(verdict=DecisionType.DENY, reason="approval_denied")))
    result = sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "approval_denied"
    assert sm.state == "IDLE"


def test_hitl_timeout_returns_rejected_signal():
    class TimeoutResolver(ApprovalResolver):
        def request_approval(self, action: Action) -> Decision:
            return Decision(verdict=DecisionType.DENY, reason="approval_timeout")
    sm = HitlStateMachine(resolver=TimeoutResolver(), timeout=0)
    result = sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "approval_timeout"
    assert sm.state == "IDLE"


def test_hitl_state_transitions():
    sm = HitlStateMachine(resolver=StubApprovalResolver(Decision(verdict=DecisionType.ALLOW)))
    assert sm.state == "IDLE"
    sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert sm.state == "IDLE"

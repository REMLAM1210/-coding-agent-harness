from __future__ import annotations
from harness.models import Action, Decision, DecisionType
from harness.feedback.models import FeedbackSignal


class ApprovalResolver:
    def request_approval(self, action: Action) -> Decision:
        raise NotImplementedError


class HitlStateMachine:
    def __init__(self, resolver: ApprovalResolver, timeout: int = 300):
        self._resolver = resolver
        self._timeout = timeout
        self.state = "IDLE"

    def handle(self, action: Action) -> Decision | FeedbackSignal:
        self.state = "PENDING_APPROVAL"
        decision = self._resolver.request_approval(action)
        if decision.verdict == DecisionType.ALLOW:
            self.state = "APPROVED"
            self.state = "IDLE"
            return decision
        elif decision.verdict == DecisionType.DENY:
            self.state = "DENIED"
            self.state = "IDLE"
            return FeedbackSignal(
                source="hitl", passed=False, failures=[],
                summary="", raw="", reason=decision.reason or "approval_denied",
            )

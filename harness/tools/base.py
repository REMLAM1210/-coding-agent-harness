from __future__ import annotations
from abc import ABC, abstractmethod
from harness.models import Action, ActionResult, Decision, DecisionType, Workspace
from harness.feedback.models import FeedbackSignal


class Tool(ABC):
    @abstractmethod
    def can_handle(self, action: Action) -> bool: ...
    @abstractmethod
    def execute(self, action: Action, workspace: Workspace) -> ActionResult: ...


class GuardrailProtocol(ABC):
    @abstractmethod
    def check(self, action: Action) -> Decision: ...


class SandboxProtocol(ABC):
    @abstractmethod
    def execute(self, action: Action, workspace: Workspace) -> ActionResult: ...


class ApprovalResolverProtocol(ABC):
    @abstractmethod
    def request_approval(self, action: Action) -> Decision: ...


class ToolDispatcher:
    def __init__(
        self,
        guardrail: GuardrailProtocol,
        sandbox: SandboxProtocol,
        approval_resolver: ApprovalResolverProtocol | None = None,
    ):
        self._guardrail = guardrail
        self._sandbox = sandbox
        self._approval_resolver = approval_resolver

    @property
    def guardrail(self) -> GuardrailProtocol:
        return self._guardrail

    def dispatch(self, action: Action, workspace: Workspace) -> ActionResult | FeedbackSignal:
        decision = self._guardrail.check(action)
        if decision.verdict == DecisionType.ALLOW:
            return self._sandbox.execute(action, workspace)
        elif decision.verdict == DecisionType.DENY:
            return FeedbackSignal(
                source="guardrail", passed=False, failures=[],
                summary="", raw="", reason=decision.reason or "guardrail_denied",
            )
        elif decision.verdict == DecisionType.REQUIRE_APPROVAL:
            if self._approval_resolver is None:
                return FeedbackSignal(
                    source="guardrail", passed=False, failures=[],
                    summary="", raw="", reason="no_approval_resolver",
                )
            approval = self._approval_resolver.request_approval(action)
            if approval.verdict == DecisionType.ALLOW:
                return self._sandbox.execute(action, workspace)
            else:
                return FeedbackSignal(
                    source="hitl", passed=False, failures=[],
                    summary="", raw="", reason=approval.reason or "approval_denied",
                )
        return ActionResult(success=False, error="unknown verdict")


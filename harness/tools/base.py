from __future__ import annotations
from abc import ABC, abstractmethod
from harness.models import Action, ActionResult, Decision, DecisionType, Workspace, HitlApprovalRequired, RawExecutionResult
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


class EventSinkProtocol:
    def emit(self, event) -> None: ...


class ToolDispatcher:
    def __init__(
        self,
        guardrail: GuardrailProtocol,
        sandbox: SandboxProtocol,
        approval_resolver: ApprovalResolverProtocol | None = None,
        event_sink: EventSinkProtocol | None = None,
    ):
        self._guardrail = guardrail
        self._sandbox = sandbox
        self._approval_resolver = approval_resolver
        self._event_sink = event_sink
        self._hitl_sm = None
        if approval_resolver is not None:
            from harness.governance.hitl import HitlStateMachine
            self._hitl_sm = HitlStateMachine(resolver=approval_resolver)

    @property
    def guardrail(self) -> GuardrailProtocol:
        return self._guardrail

    def set_event_sink(self, sink: EventSinkProtocol | None) -> None:
        self._event_sink = sink

    def dispatch_with_decision(
        self, action: Action, workspace: Workspace
    ) -> tuple[ActionResult | RawExecutionResult | FeedbackSignal, Decision]:
        decision = self._guardrail.check(action)
        if decision.verdict == DecisionType.ALLOW:
            return self._sandbox.execute(action, workspace), decision
        elif decision.verdict == DecisionType.DENY:
            return FeedbackSignal(
                source="guardrail", passed=False, failures=[],
                summary="", raw="", reason=decision.reason or "guardrail_denied",
            ), decision
        elif decision.verdict == DecisionType.REQUIRE_APPROVAL:
            if self._hitl_sm is None:
                return FeedbackSignal(
                    source="guardrail", passed=False, failures=[],
                    summary="", raw="", reason="no_approval_resolver",
                ), decision
            if self._event_sink is not None:
                self._event_sink.emit(HitlApprovalRequired(action=action))
            result = self._hitl_sm.handle(action)
            if isinstance(result, Decision) and result.verdict == DecisionType.ALLOW:
                return self._sandbox.execute(action, workspace), decision
            else:
                return result, decision
        return ActionResult(success=False, error="unknown verdict"), decision

    def dispatch(self, action: Action, workspace: Workspace) -> ActionResult | RawExecutionResult | FeedbackSignal:
        result, _ = self.dispatch_with_decision(action, workspace)
        return result


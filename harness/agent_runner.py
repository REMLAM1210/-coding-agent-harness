from __future__ import annotations
from typing import Protocol
from harness.models import (
    Action, ActionResult, RawExecutionResult, Context, Message,
    Workspace, Config, MemoryItem, WorkspaceInfo,
    LoopStarted, ContextBuilt, LLMProposed, GuardrailDecision,
    ToolCallStarted, ToolCallResult, FeedbackSignalEmitted,
    FailureClassified, RetryDecisionEvent, HitlApprovalRequired,
    LoopStep, LoopFinished,
)
from harness.feedback.models import FeedbackSignal, FailureClassification, RetryDecision, RetryStrategy
from harness.llm.base import LLMClient
from harness.tools.base import ToolDispatcher
from harness.feedback.validators import PytestValidator
from harness.feedback.classifier import Classifier
from harness.feedback.feedback_loop import FeedbackLoop


class EventSink(Protocol):
    def emit(self, event) -> None: ...


class RecordingEventSink:
    def __init__(self):
        self.events: list = []
    def emit(self, event) -> None:
        self.events.append(event)


class AgentRunner:
    def __init__(
        self,
        llm_client: LLMClient,
        dispatcher: ToolDispatcher,
        validator: PytestValidator,
        classifier: Classifier,
        feedback_loop: FeedbackLoop,
        config: Config,
        event_sink: EventSink,
    ):
        self._llm = llm_client
        self._dispatcher = dispatcher
        self._validator = validator
        self._classifier = classifier
        self._feedback_loop = feedback_loop
        self._config = config
        self._sink = event_sink
        self._history: list[Message] = []
        self._feedback_history: list[FeedbackSignal] = []
        self._consecutive_passes = 0

    def _build_context(self, task: str, workspace: Workspace) -> Context:
        ws_info = WorkspaceInfo(cwd=workspace.cwd)
        return Context(
            system_prompt=f"You are a coding agent. Task: {task}",
            history=self._history[-20:],
            memory_items=[],
            feedback_signals=self._feedback_history[-5:],
            workspace_info=ws_info,
        )

    def _format_feedback(self, signal: FeedbackSignal, fc: FailureClassification, rd: RetryDecision) -> str:
        lines = [f"[FEEDBACK] source={signal.source}, passed={signal.passed}"]
        if signal.failures:
            lines.append("  Failures:")
            for f in signal.failures:
                lines.append(f"    - {f.loc}: {f.message} ({f.category})")
        lines.append(f"  Classification: {fc.category}")
        if fc.hint:
            lines.append(f"  Hint: {fc.hint}")
        lines.append(f"  RetryDecision: {rd.strategy.value} (attempt {rd.attempt_count}/{rd.max})")
        return "\n".join(lines)

    def _should_auto_stop(self) -> bool:
        return self._consecutive_passes >= 2

    def run(self, task: str, workspace: Workspace) -> None:
        self._sink.emit(LoopStarted(session_id="", task=task))
        attempt = 0
        while attempt < self._config.max_iterations:
            attempt += 1
            ctx = self._build_context(task, workspace)
            self._sink.emit(ContextBuilt(context=ctx))

            action = self._llm.propose_action(ctx)
            self._sink.emit(LLMProposed(action=action))

            if action.type == "Done":
                self._sink.emit(LoopFinished(session_id="", reason=f"Done: {action.args.get('summary', '')}"))
                return

            result = self._dispatcher.dispatch(action, workspace)

            if isinstance(result, FeedbackSignal) and result.reason:
                # Rejected signal from guardrail/HITL
                self._feedback_history.append(result)
                self._sink.emit(FeedbackSignalEmitted(signal=result))
                self._history.append(Message(role="tool", content=f"Action rejected: {result.reason}"))
                self._consecutive_passes = 0
                continue

            self._sink.emit(ToolCallStarted(action=action))
            self._sink.emit(ToolCallResult(action=action, result=result if isinstance(result, ActionResult) else ActionResult(success=True)))

            # Check if result is a RawExecutionResult (from feedback tools)
            if isinstance(result, RawExecutionResult):
                signal = self._validator.parse(result)
                self._sink.emit(FeedbackSignalEmitted(signal=signal))

                if signal.passed:
                    self._consecutive_passes += 1
                else:
                    self._consecutive_passes = 0
                    fc = self._classifier.classify(signal)
                    self._sink.emit(FailureClassified(classification=fc))
                    rd = self._feedback_loop.decide(signal, fc, attempt, self._feedback_history)
                    self._sink.emit(RetryDecisionEvent(strategy=rd.strategy.value, attempt_count=rd.attempt_count))
                    feedback_text = self._format_feedback(signal, fc, rd)
                    self._history.append(Message(role="tool", content=feedback_text))

                    if rd.strategy == RetryStrategy.ABORT:
                        self._sink.emit(LoopFinished(session_id="", reason="ABORT: max iterations reached"))
                        return
                    if rd.strategy == RetryStrategy.ESCALATE:
                        self._history.append(Message(role="system", content="ESCALATION: agent appears stuck. Try a different approach."))

                self._feedback_history.append(signal)
            else:
                self._history.append(Message(role="tool", content=result.output if result.success else f"Error: {result.error}"))
                self._consecutive_passes = 0

            self._sink.emit(LoopStep(step=attempt))

            if self._should_auto_stop():
                self._sink.emit(LoopFinished(session_id="", reason="Auto-stop: consecutive passes"))
                return

        self._sink.emit(LoopFinished(session_id="", reason="ABORT: max iterations reached"))

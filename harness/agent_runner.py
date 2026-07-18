from __future__ import annotations
from typing import Any, Protocol
from harness.models import (
    Action, ActionResult, RawExecutionResult, Context, Message,
    Workspace, Config, MemoryItem, WorkspaceInfo,
    LoopStarted, ContextBuilt, LLMProposed, GuardrailDecision,
    ToolCallStarted, ToolCallResult, FeedbackSignalEmitted,
    FailureClassified, RetryDecisionEvent, HitlApprovalRequired,
    LoopStep, LoopFinished,
)
from harness.feedback.models import FeedbackSignal, FailureClassification, RetryDecision, RetryStrategy
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator
from harness.llm.base import LLMClient
from harness.tools.base import ToolDispatcher
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
        validator: Any = None,
        classifier: Classifier = None,
        feedback_loop: FeedbackLoop = None,
        config: Config = None,
        event_sink: EventSink = None,
        validators: dict[str, Any] | None = None,
        memory_store: Any = None,
    ):
        self._llm = llm_client
        self._dispatcher = dispatcher
        self._validator = validator if validator is not None else PytestValidator()
        self._validators = validators or {}
        self._classifier = classifier
        self._feedback_loop = feedback_loop
        self._config = config
        self._sink = event_sink
        self._memory_store = memory_store
        self._history: list[Message] = []
        self._feedback_history: list[FeedbackSignal] = []
        self._consecutive_passes = 0
        if hasattr(self._dispatcher, "set_event_sink"):
            self._dispatcher.set_event_sink(event_sink)

    def _build_context(self, task: str, workspace: Workspace) -> Context:
        ws_info = WorkspaceInfo(cwd=workspace.cwd)
        memory_items: list[MemoryItem] = []
        if self._memory_store is not None:
            task_words = task.lower().split()
            for key in self._memory_store.list_keys():
                key_lower = key.lower()
                if any(word in key_lower for word in task_words):
                    value = self._memory_store.retrieve(key)
                    if value is not None:
                        memory_items.append(MemoryItem(key=key, value=value))
        return Context(
            system_prompt=f"You are a coding agent. Task: {task}",
            history=self._history[-20:],
            memory_items=memory_items,
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

    def _select_validator(self, action: Action) -> Any:
        return self._validators.get(action.type, self._validator)

    def run(self, task: str, workspace: Workspace) -> None:
        self._sink.emit(LoopStarted(session_id="", task=task))
        final_reason = "ABORT: max iterations reached"
        attempt = 0
        while attempt < self._config.max_iterations:
            try:
                attempt += 1
                ctx = self._build_context(task, workspace)
                self._sink.emit(ContextBuilt(context=ctx))

                action = self._llm.propose_action(ctx)
                self._sink.emit(LLMProposed(action=action))

                if action.type == "Done":
                    final_reason = f"Done: {action.args.get('summary', '')}"
                    break

                result, g_decision = self._dispatcher.dispatch_with_decision(action, workspace)
                self._sink.emit(GuardrailDecision(action=action, verdict=g_decision.verdict, reason=g_decision.reason))

                if isinstance(result, FeedbackSignal) and result.reason:
                    self._feedback_history.append(result)
                    self._sink.emit(FeedbackSignalEmitted(signal=result))
                    self._history.append(Message(role="tool", content=f"Action rejected: {result.reason}"))
                    self._consecutive_passes = 0
                    continue

                self._sink.emit(ToolCallStarted(action=action))
                self._sink.emit(ToolCallResult(action=action, result=result))

                if isinstance(result, RawExecutionResult):
                    validator = self._select_validator(action)
                    signal = validator.parse(result)
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
                            final_reason = "ABORT: max iterations reached"
                            break
                        if rd.strategy == RetryStrategy.ESCALATE:
                            self._history.append(Message(role="system", content="ESCALATION: agent appears stuck. Try a different approach."))

                    self._feedback_history.append(signal)
                else:
                    self._history.append(Message(role="tool", content=result.output if result.success else f"Error: {result.error}"))
                    self._consecutive_passes = 0

                self._sink.emit(LoopStep(step=attempt))

                if self._should_auto_stop():
                    final_reason = "Auto-stop: consecutive passes"
                    break
            except Exception as e:
                final_reason = f"ERROR: {e}"
                break

        self._sink.emit(LoopFinished(session_id="", reason=final_reason))
        if self._memory_store is not None:
            self._memory_store.store("last_task", task)
            self._memory_store.store("last_result", final_reason)

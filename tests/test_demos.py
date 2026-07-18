# tests/test_demos.py
"""Mechanism demos (A.6) — deterministic reproduction under mock LLM.

Run: pytest tests/test_demos.py -v -k demo
"""
import tempfile
import pytest
from harness.models import Action, Workspace, RawExecutionResult, Config, DecisionType, GuardrailRule
from harness.agent_runner import AgentRunner, RecordingEventSink
from harness.llm.mock_client import MockLLMClient
from harness.tools.base import ToolDispatcher
from harness.tools.file_tools import WriteFileTool, ReadFileTool
from harness.tools.feedback_tools import RunTestsTool
from harness.governance.guardrail import Guardrail
from harness.governance.sandbox import Sandbox
from harness.feedback.validators import PytestValidator
from harness.feedback.classifier import Classifier
from harness.feedback.feedback_loop import FeedbackLoop
from harness.feedback.models import FeedbackSignal, FailureItem


def _make_runner(actions, tmpdir, cfg=None, validator=None):
    cfg = cfg or Config()
    tools = [ReadFileTool(), WriteFileTool(), RunTestsTool(timeout=10)]
    rules = cfg.guardrail_rules or [
        GuardrailRule(name="block_rm_rf", pattern=r"rm\s+-rf", action_type="RunShell", verdict=DecisionType.DENY, reason="guardrail_denied"),
    ]
    guardrail = Guardrail(rules=rules)
    sandbox = Sandbox(tools=tools, timeout=cfg.sandbox_timeout, env_whitelist=cfg.sandbox_env_whitelist)
    td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
    llm = MockLLMClient(actions=actions)
    fl = FeedbackLoop(max_iterations=cfg.max_iterations, escalation_threshold=cfg.feedback_thresholds["escalation_threshold"])
    sink = RecordingEventSink()
    runner = AgentRunner(
        llm_client=llm, dispatcher=td, validator=validator or PytestValidator(),
        classifier=Classifier(hints=cfg.hints), feedback_loop=fl,
        config=cfg, event_sink=sink,
    )
    return runner, sink


# === Demo 1: Guardrail intercepts dangerous action ===

def test_demo_guardrail_intercept():
    """MockLLM proposes rm -rf / -> guardrail DENY -> rejected FeedbackSignal -> LLM re-proposes safe action."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner, sink = _make_runner([
            Action(type="RunShell", args={"command": "rm -rf /"}),
            Action(type="Done", args={"summary": "switched to safe action"}),
        ], tmpdir)
        runner.run("demo", Workspace(cwd=tmpdir))

        # Assert guardrail decision event
        decisions = [e for e in sink.events if e.__class__.__name__ == "GuardrailDecision"]
        assert len(decisions) >= 1
        assert decisions[0].verdict == DecisionType.DENY

        # Assert rejected feedback signal was emitted
        signals = [e for e in sink.events if e.__class__.__name__ == "FeedbackSignalEmitted"]
        rejected = [s for s in signals if s.signal.reason == "guardrail_denied"]
        assert len(rejected) >= 1

        # Assert loop finished (LLM re-proposed safe action -> Done)
        finished = [e for e in sink.events if e.__class__.__name__ == "LoopFinished"]
        assert len(finished) == 1


# === Demo 2: Inject failure -> feedback loop self-correction ===

class FakeFailThenPassValidator:
    """Returns failure on first call, pass on second."""
    _call_count = 0
    @staticmethod
    def parse(raw):
        FakeFailThenPassValidator._call_count += 1
        if FakeFailThenPassValidator._call_count == 1:
            return FeedbackSignal(
                source="pytest", passed=False,
                failures=[FailureItem(loc="test_foo.py::test_bar", message="assert 1==2", category="ASSERTION_FAILURE")],
                summary="1 failed", raw="",
            )
        return FeedbackSignal(source="pytest", passed=True, failures=[])


def test_demo_feedback_self_correction():
    """WriteFile(buggy) -> RunTests -> fail -> feedback -> fix -> RunTests -> pass -> Done."""
    with tempfile.TemporaryDirectory() as tmpdir:
        FakeFailThenPassValidator._call_count = 0
        runner, sink = _make_runner([
            Action(type="WriteFile", args={"path": "foo.py", "content": "def foo(): return 1"}),
            Action(type="RunTests", args={}),
            Action(type="WriteFile", args={"path": "foo.py", "content": "def foo(): return 2"}),
            Action(type="RunTests", args={}),
            Action(type="Done", args={"summary": "fixed"}),
        ], tmpdir, validator=FakeFailThenPassValidator())
        runner.run("fix the failing test", Workspace(cwd=tmpdir))

        # Assert feedback signal was emitted with failure
        signals = [e for e in sink.events if e.__class__.__name__ == "FeedbackSignalEmitted"]
        fail_signals = [s for s in signals if not s.signal.passed]
        assert len(fail_signals) >= 1
        assert fail_signals[0].signal.failures[0].loc == "test_foo.py::test_bar"

        # Assert classification was emitted
        classified = [e for e in sink.events if e.__class__.__name__ == "FailureClassified"]
        assert len(classified) >= 1
        assert classified[0].classification.category == "ASSERTION_FAILURE"

        # Assert retry decision was RETRY_SAME
        decisions = [e for e in sink.events if e.__class__.__name__ == "RetryDecisionEvent"]
        assert any(d.strategy == "RETRY_SAME" for d in decisions)

        # Assert loop finished successfully
        finished = [e for e in sink.events if e.__class__.__name__ == "LoopFinished"]
        assert len(finished) == 1


# === Demo 3: Stagnation detection -> early ESCALATE ===

class AlwaysFailValidator:
    """Always returns the same failure."""
    @staticmethod
    def parse(raw):
        return FeedbackSignal(
            source="pytest", passed=False,
            failures=[FailureItem(loc="test_foo.py::test_bar", message="assert 1==2", category="ASSERTION_FAILURE")],
            summary="1 failed", raw="",
        )


def test_demo_stagnation_detection():
    """Inject same failure repeatedly -> FeedbackLoop detects stagnation -> ESCALATE before fixed threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config(max_iterations=10)
        cfg.feedback_thresholds = {"max_retries_per_class": 5, "escalation_threshold": 10}  # high threshold so stagnation triggers first

        def responder(ctx):
            return Action(type="RunTests", args={})

        tools = [RunTestsTool(timeout=10)]
        guardrail = Guardrail()
        sandbox = Sandbox(tools=tools, timeout=10)
        td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
        llm = MockLLMClient(responder=responder)
        fl = FeedbackLoop(max_iterations=10, escalation_threshold=10)
        sink = RecordingEventSink()
        runner = AgentRunner(
            llm_client=llm, dispatcher=td, validator=AlwaysFailValidator(),
            classifier=Classifier(hints={}), feedback_loop=fl,
            config=cfg, event_sink=sink,
        )
        runner.run("stuck task", Workspace(cwd=tmpdir))

        # Assert ESCALATE was triggered
        decisions = [e for e in sink.events if e.__class__.__name__ == "RetryDecisionEvent"]
        escalations = [d for d in decisions if d.strategy == "ESCALATE"]
        assert len(escalations) >= 1

        # Assert escalation happened before the fixed threshold (10)
        first_escalation = escalations[0]
        assert first_escalation.attempt_count < 10

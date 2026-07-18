from harness.models import (
    Action, ActionResult, RawExecutionResult, Decision, DecisionType,
    Context, Session, GuardrailRule, Config,
)
from harness.feedback.models import (
    FeedbackSignal, FailureItem, FailureClassification, RetryDecision, RetryStrategy,
)


def test_action_read_file():
    a = Action(type="ReadFile", args={"path": "foo.py"})
    assert a.type == "ReadFile"
    assert a.args["path"] == "foo.py"


def test_action_done():
    a = Action(type="Done", args={"summary": "fixed"})
    assert a.type == "Done"


def test_raw_execution_result():
    r = RawExecutionResult(exit_code=1, stdout="FAIL", stderr="")
    assert r.exit_code == 1
    assert r.stdout == "FAIL"


def test_decision_allow():
    d = Decision(verdict=DecisionType.ALLOW)
    assert d.verdict == DecisionType.ALLOW
    assert d.reason == ""


def test_decision_deny():
    d = Decision(verdict=DecisionType.DENY, reason="dangerous")
    assert d.verdict == DecisionType.DENY
    assert d.reason == "dangerous"


def test_feedback_signal():
    sig = FeedbackSignal(
        source="pytest", passed=False,
        failures=[FailureItem(loc="test_foo.py::test_bar", message="assert 1==2", category="ASSERTION_FAILURE")],
        summary="1 failed", raw="...", reason="",
    )
    assert sig.passed is False
    assert sig.failures[0].loc == "test_foo.py::test_bar"


def test_feedback_signal_rejected():
    sig = FeedbackSignal(
        source="guardrail", passed=False, failures=[], summary="", raw="", reason="guardrail_denied",
    )
    assert sig.reason == "guardrail_denied"


def test_retry_decision():
    rd = RetryDecision(strategy=RetryStrategy.RETRY_SAME, attempt_count=1, max=20)
    assert rd.strategy == RetryStrategy.RETRY_SAME
    assert rd.attempt_count == 1


def test_failure_classification_priority():
    fc = FailureClassification(category="ASSERTION_FAILURE", hint="check logic", priority=4)
    assert fc.category == "ASSERTION_FAILURE"
    assert fc.priority == 4


def test_guardrail_rule():
    rule = GuardrailRule(name="block_rm_rf", pattern=r"rm\s+-rf", action_type="RunShell", verdict=DecisionType.DENY, reason="destructive")
    assert rule.name == "block_rm_rf"
    assert rule.verdict == DecisionType.DENY


def test_config_defaults():
    cfg = Config()
    assert cfg.max_iterations == 20
    assert cfg.sandbox_timeout == 30

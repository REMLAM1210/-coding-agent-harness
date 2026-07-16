from harness.feedback.models import FeedbackSignal, FailureItem, FailureClassification, RetryDecision, RetryStrategy
from harness.feedback.feedback_loop import FeedbackLoop


def make_signal(locs: list[str]) -> FeedbackSignal:
    return FeedbackSignal(
        source="pytest", passed=False,
        failures=[FailureItem(loc=l, message="assert", category="ASSERTION_FAILURE") for l in locs],
    )


def test_converging_retries_same():
    fl = FeedbackLoop(max_iterations=20, escalation_threshold=3)
    sig = make_signal(["a", "b"])
    fc = FailureClassification(category="ASSERTION_FAILURE", hint="", priority=3)
    history = [make_signal(["a", "b", "c"])]  # previous had more failures
    rd = fl.decide(sig, fc, attempt_count=1, failure_history=history)
    assert rd.strategy == RetryStrategy.RETRY_SAME


def test_stagnation_triggers_escalate():
    fl = FeedbackLoop(max_iterations=20, escalation_threshold=3)
    sig = make_signal(["a", "b"])
    fc = FailureClassification(category="ASSERTION_FAILURE", hint="", priority=3)
    history = [make_signal(["a", "b"]), make_signal(["a", "b"])]  # same failures
    rd = fl.decide(sig, fc, attempt_count=3, failure_history=history)
    assert rd.strategy == RetryStrategy.ESCALATE


def test_oscillation_triggers_escalate():
    fl = FeedbackLoop(max_iterations=20, escalation_threshold=3)
    sig = make_signal(["a"])  # "a" reappears
    fc = FailureClassification(category="ASSERTION_FAILURE", hint="", priority=3)
    history = [make_signal(["a"]), make_signal([])]  # a appeared, disappeared, now reappears
    rd = fl.decide(sig, fc, attempt_count=3, failure_history=history)
    assert rd.strategy == RetryStrategy.ESCALATE


def test_max_iterations_abort():
    fl = FeedbackLoop(max_iterations=3, escalation_threshold=5)
    sig = make_signal(["a"])
    fc = FailureClassification(category="ASSERTION_FAILURE", hint="", priority=3)
    rd = fl.decide(sig, fc, attempt_count=3, failure_history=[])
    assert rd.strategy == RetryStrategy.ABORT


def test_passed_signal_retries_same():
    fl = FeedbackLoop(max_iterations=20, escalation_threshold=3)
    sig = FeedbackSignal(source="pytest", passed=True, failures=[])
    fc = FailureClassification(category="PASSED", hint="", priority=99)
    rd = fl.decide(sig, fc, attempt_count=1, failure_history=[])
    assert rd.strategy == RetryStrategy.RETRY_SAME


def test_category_threshold_triggers_escalate():
    fl = FeedbackLoop(max_iterations=20, escalation_threshold=3)
    sig = make_signal(["a"])
    fc = FailureClassification(category="ASSERTION_FAILURE", hint="", priority=3)
    history = [make_signal(["b"]), make_signal(["c"]), make_signal(["d"])]
    rd = fl.decide(sig, fc, attempt_count=4, failure_history=history)
    assert rd.strategy == RetryStrategy.ESCALATE

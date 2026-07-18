from harness.feedback.models import FeedbackSignal, FailureItem, FailureClassification
from harness.feedback.classifier import Classifier, CATEGORY_PRIORITY


def test_classify_single_assertion_failure():
    sig = FeedbackSignal(
        source="pytest", passed=False,
        failures=[FailureItem(loc="t.py::test_a", message="assert", category="ASSERTION_FAILURE")],
    )
    fc = Classifier(hints={}).classify(sig)
    assert fc.category == "ASSERTION_FAILURE"


def test_classify_priority_collection_over_assertion():
    sig = FeedbackSignal(
        source="pytest", passed=False,
        failures=[
            FailureItem(loc="t.py::test_a", message="assert", category="ASSERTION_FAILURE"),
            FailureItem(loc="t.py", message="import error", category="IMPORT_ERROR"),
        ],
    )
    fc = Classifier(hints={}).classify(sig)
    assert fc.category == "IMPORT_ERROR"


def test_classify_priority_syntax_over_type():
    sig = FeedbackSignal(
        source="mypy", passed=False,
        failures=[
            FailureItem(loc="foo.py:10", message="type error", category="TYPE_ERROR"),
            FailureItem(loc="foo.py", message="syntax error", category="SYNTAX_ERROR"),
        ],
    )
    fc = Classifier(hints={}).classify(sig)
    assert fc.category == "SYNTAX_ERROR"


def test_classify_hint_from_config():
    hints = {"ASSERTION_FAILURE": "Check the logic in the failing test."}
    sig = FeedbackSignal(
        source="pytest", passed=False,
        failures=[FailureItem(loc="t.py::test_a", message="assert", category="ASSERTION_FAILURE")],
    )
    fc = Classifier(hints=hints).classify(sig)
    assert fc.hint == "Check the logic in the failing test."


def test_classify_passed_signal():
    sig = FeedbackSignal(source="pytest", passed=True, failures=[])
    fc = Classifier(hints={}).classify(sig)
    assert fc.category == "PASSED"


def test_priority_ordering():
    assert CATEGORY_PRIORITY["COLLECTION_ERROR"] < CATEGORY_PRIORITY["TIMEOUT"]
    assert CATEGORY_PRIORITY["TIMEOUT"] < CATEGORY_PRIORITY["TYPE_ERROR"]
    assert CATEGORY_PRIORITY["TYPE_ERROR"] < CATEGORY_PRIORITY["ASSERTION_FAILURE"]
    assert CATEGORY_PRIORITY["ASSERTION_FAILURE"] < CATEGORY_PRIORITY["LINT_VIOLATION"]

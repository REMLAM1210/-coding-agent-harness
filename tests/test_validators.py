from harness.models import RawExecutionResult
from harness.feedback.models import FeedbackSignal
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator


def test_pytest_pass():
    raw = RawExecutionResult(exit_code=0, stdout="1 passed", stderr="")
    sig = PytestValidator.parse(raw)
    assert sig.passed is True
    assert sig.source == "pytest"
    assert len(sig.failures) == 0


def test_pytest_fail():
    raw = RawExecutionResult(
        exit_code=1,
        stdout="FAILED test_foo.py::test_bar - assert 1 == 2\n1 failed",
        stderr="",
    )
    sig = PytestValidator.parse(raw)
    assert sig.passed is False
    assert len(sig.failures) == 1
    assert sig.failures[0].loc == "test_foo.py::test_bar"
    assert "assert 1 == 2" in sig.failures[0].message


def test_pytest_collection_error():
    raw = RawExecutionResult(
        exit_code=2,
        stdout="ERROR collecting test_foo.py\nImportError: No module named 'foo'",
        stderr="",
    )
    sig = PytestValidator.parse(raw)
    assert sig.passed is False
    assert any(f.category == "COLLECTION_ERROR" or f.category == "IMPORT_ERROR" for f in sig.failures)


def test_ruff_pass():
    raw = RawExecutionResult(exit_code=0, stdout="[]", stderr="")
    sig = RuffValidator.parse(raw)
    assert sig.passed is True


def test_ruff_fail():
    raw = RawExecutionResult(
        exit_code=1,
        stdout='[{"filename": "foo.py", "message": "unused import", "code": "F401"}]',
        stderr="",
    )
    sig = RuffValidator.parse(raw)
    assert sig.passed is False
    assert len(sig.failures) == 1
    assert sig.failures[0].category == "LINT_VIOLATION"


def test_mypy_pass():
    raw = RawExecutionResult(exit_code=0, stdout="", stderr="")
    sig = MypyValidator.parse(raw)
    assert sig.passed is True


def test_mypy_fail():
    raw = RawExecutionResult(
        exit_code=1,
        stdout="foo.py:10: error: Incompatible types  [assignment]",
        stderr="",
    )
    sig = MypyValidator.parse(raw)
    assert sig.passed is False
    assert len(sig.failures) == 1
    assert sig.failures[0].category == "TYPE_ERROR"
    assert sig.failures[0].loc == "foo.py:10"

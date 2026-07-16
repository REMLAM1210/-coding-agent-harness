from __future__ import annotations
import json
import re
from harness.models import RawExecutionResult
from harness.feedback.models import FeedbackSignal, FailureItem


class PytestValidator:
    @staticmethod
    def parse(raw: RawExecutionResult) -> FeedbackSignal:
        if raw.exit_code == 0:
            return FeedbackSignal(source="pytest", passed=True, failures=[], summary=raw.stdout, raw=raw.stdout)
        failures: list[FailureItem] = []
        for m in re.finditer(r"FAILED\s+(\S+)\s+-\s+(.+)", raw.stdout):
            loc = m.group(1)
            msg = m.group(2).strip()
            failures.append(FailureItem(loc=loc, message=msg, category="ASSERTION_FAILURE"))
        if not failures:
            for m in re.finditer(r"ERROR collecting\s+(\S+)", raw.stdout):
                failures.append(FailureItem(loc=m.group(1), message="Collection error", category="COLLECTION_ERROR"))
            for m in re.finditer(r"ImportError:\s*(.+)", raw.stdout):
                failures.append(FailureItem(loc="import", message=m.group(1).strip(), category="IMPORT_ERROR"))
        if not failures:
            for m in re.finditer(r"SyntaxError:\s*(.+)", raw.stdout):
                failures.append(FailureItem(loc="syntax", message=m.group(1).strip(), category="SYNTAX_ERROR"))
        if not failures:
            failures.append(FailureItem(loc="unknown", message=raw.stdout[:200], category="UNKNOWN"))
        return FeedbackSignal(source="pytest", passed=False, failures=failures, summary=raw.stdout, raw=raw.stdout)


class RuffValidator:
    @staticmethod
    def parse(raw: RawExecutionResult) -> FeedbackSignal:
        if raw.exit_code == 0:
            return FeedbackSignal(source="ruff", passed=True, failures=[], summary="clean", raw=raw.stdout)
        failures: list[FailureItem] = []
        try:
            items = json.loads(raw.stdout)
            for item in items:
                loc = item.get("filename", "unknown")
                msg = item.get("message", "")
                failures.append(FailureItem(loc=loc, message=msg, category="LINT_VIOLATION"))
        except (json.JSONDecodeError, TypeError):
            failures.append(FailureItem(loc="unknown", message=raw.stdout[:200], category="UNKNOWN"))
        return FeedbackSignal(source="ruff", passed=False, failures=failures, summary=raw.stdout, raw=raw.stdout)


class MypyValidator:
    @staticmethod
    def parse(raw: RawExecutionResult) -> FeedbackSignal:
        if raw.exit_code == 0:
            return FeedbackSignal(source="mypy", passed=True, failures=[], summary="clean", raw=raw.stdout)
        failures: list[FailureItem] = []
        for m in re.finditer(r"(\S+:\d+):\s*error:\s*(.+)", raw.stdout):
            loc = m.group(1)
            msg = m.group(2).strip()
            failures.append(FailureItem(loc=loc, message=msg, category="TYPE_ERROR"))
        if not failures:
            failures.append(FailureItem(loc="unknown", message=raw.stdout[:200], category="UNKNOWN"))
        return FeedbackSignal(source="mypy", passed=False, failures=failures, summary=raw.stdout, raw=raw.stdout)

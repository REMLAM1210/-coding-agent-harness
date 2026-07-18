from __future__ import annotations
from harness.feedback.models import FeedbackSignal, FailureClassification


CATEGORY_PRIORITY: dict[str, int] = {
    "COLLECTION_ERROR": 0,
    "IMPORT_ERROR": 0,
    "SYNTAX_ERROR": 0,
    "TIMEOUT": 1,
    "TYPE_ERROR": 2,
    "ASSERTION_FAILURE": 3,
    "LINT_VIOLATION": 4,
    "UNKNOWN": 5,
    "PASSED": 99,
}


class Classifier:
    def __init__(self, hints: dict[str, str] | None = None):
        self._hints = hints or {}

    def classify(self, signal: FeedbackSignal) -> FailureClassification:
        if signal.passed:
            return FailureClassification(category="PASSED", hint="", priority=CATEGORY_PRIORITY["PASSED"])
        if not signal.failures:
            return FailureClassification(category="UNKNOWN", hint=self._hints.get("UNKNOWN", ""), priority=CATEGORY_PRIORITY["UNKNOWN"])
        best_category = "UNKNOWN"
        best_priority = CATEGORY_PRIORITY["UNKNOWN"]
        for item in signal.failures:
            p = CATEGORY_PRIORITY.get(item.category, CATEGORY_PRIORITY["UNKNOWN"])
            if p < best_priority:
                best_priority = p
                best_category = item.category
        hint = self._hints.get(best_category, "")
        return FailureClassification(category=best_category, hint=hint, priority=best_priority)

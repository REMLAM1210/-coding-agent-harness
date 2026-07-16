from __future__ import annotations
from harness.feedback.models import FeedbackSignal, FailureClassification, RetryDecision, RetryStrategy


class FeedbackLoop:
    def __init__(self, max_iterations: int = 20, escalation_threshold: int = 3):
        self._max_iterations = max_iterations
        self._escalation_threshold = escalation_threshold

    def decide(
        self,
        signal: FeedbackSignal,
        classification: FailureClassification,
        attempt_count: int,
        failure_history: list[FeedbackSignal],
    ) -> RetryDecision:
        if attempt_count >= self._max_iterations:
            return RetryDecision(strategy=RetryStrategy.ABORT, attempt_count=attempt_count, max=self._max_iterations)

        if signal.passed:
            return RetryDecision(strategy=RetryStrategy.RETRY_SAME, attempt_count=attempt_count, max=self._max_iterations)

        current_locs = {f.loc for f in signal.failures}

        # Check stagnation: same failures across recent rounds
        if len(failure_history) >= 2:
            recent = failure_history[-2:]
            prev_locs = {f.loc for f in recent[-1].failures}
            if current_locs == prev_locs:
                return RetryDecision(strategy=RetryStrategy.ESCALATE, attempt_count=attempt_count, max=self._max_iterations)

        # Check oscillation: a loc that disappeared then reappeared
        if len(failure_history) >= 2:
            older_locs = {f.loc for f in failure_history[-2].failures}
            newer_locs = {f.loc for f in failure_history[-1].failures}
            disappeared = older_locs - newer_locs
            reappeared = disappeared & current_locs
            if reappeared:
                return RetryDecision(strategy=RetryStrategy.ESCALATE, attempt_count=attempt_count, max=self._max_iterations)

        # Check threshold: same category too many times
        same_category_count = sum(
            1 for h in failure_history
            if h.failures and h.failures[0].category == classification.category
        )
        if same_category_count >= self._escalation_threshold:
            return RetryDecision(strategy=RetryStrategy.ESCALATE, attempt_count=attempt_count, max=self._max_iterations)

        return RetryDecision(strategy=RetryStrategy.RETRY_SAME, attempt_count=attempt_count, max=self._max_iterations)

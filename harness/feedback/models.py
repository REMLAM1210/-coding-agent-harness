from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class RetryStrategy(str, Enum):
    RETRY_SAME = "RETRY_SAME"
    ESCALATE = "ESCALATE"
    ABORT = "ABORT"
    REVERT = "REVERT"


@dataclass
class FailureItem:
    loc: str
    message: str
    category: str


@dataclass
class FeedbackSignal:
    source: str
    passed: bool
    failures: list[FailureItem] = field(default_factory=list)
    summary: str = ""
    raw: str = ""
    reason: str = ""


@dataclass
class FailureClassification:
    category: str
    hint: str
    priority: int


@dataclass
class RetryDecision:
    strategy: RetryStrategy
    attempt_count: int
    max: int

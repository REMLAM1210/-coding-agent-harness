from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class DecisionType(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass
class Action:
    type: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    success: bool
    output: str = ""
    error: str | None = None


@dataclass
class RawExecutionResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class Decision:
    verdict: DecisionType
    reason: str = ""


@dataclass
class Message:
    role: str
    content: str


@dataclass
class MemoryItem:
    key: str
    value: str


@dataclass
class WorkspaceInfo:
    cwd: str
    files: list[str] = field(default_factory=list)


@dataclass
class Context:
    system_prompt: str
    history: list[Message] = field(default_factory=list)
    memory_items: list[MemoryItem] = field(default_factory=list)
    feedback_signals: list[Any] = field(default_factory=list)
    workspace_info: WorkspaceInfo | None = None


@dataclass
class Workspace:
    cwd: str


@dataclass
class Session:
    id: str
    task: str
    workspace: Workspace
    state: str = "running"


@dataclass
class GuardrailRule:
    name: str
    pattern: str
    action_type: str
    verdict: DecisionType
    reason: str = ""


@dataclass
class Config:
    max_iterations: int = 20
    sandbox_timeout: int = 30
    sandbox_env_whitelist: list[str] = field(default_factory=lambda: ["PATH", "HOME", "LANG"])
    hitl_timeout: int = 300
    max_concurrent_sessions: int = 5
    workspace_retention_seconds: int = 3600
    guardrail_rules: list[GuardrailRule] = field(default_factory=list)
    feedback_thresholds: dict[str, int] = field(default_factory=lambda: {"max_retries_per_class": 3, "escalation_threshold": 2})
    llm_settings: dict[str, Any] = field(default_factory=lambda: {"model": "gpt-4o-mini", "temperature": 0.0})
    hints: dict[str, str] = field(default_factory=dict)


class AgentEvent(Protocol):
    """Base protocol for all agent events."""
    pass


# Concrete event types as simple dataclasses
@dataclass
class LoopStarted:
    session_id: str
    task: str

@dataclass
class ContextBuilt:
    context: Context

@dataclass
class LLMProposed:
    action: Action

@dataclass
class GuardrailDecision:
    action: Action
    verdict: DecisionType
    reason: str

@dataclass
class ToolCallStarted:
    action: Action

@dataclass
class ToolCallResult:
    action: Action
    result: ActionResult

@dataclass
class FeedbackSignalEmitted:
    signal: Any  # FeedbackSignal, avoid circular import

@dataclass
class FailureClassified:
    classification: Any  # FailureClassification

@dataclass
class RetryDecisionEvent:
    strategy: str
    attempt_count: int

@dataclass
class HitlApprovalRequired:
    action: Action

@dataclass
class LoopStep:
    step: int

@dataclass
class LoopFinished:
    session_id: str
    reason: str

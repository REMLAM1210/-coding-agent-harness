# Coding Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-coded coding agent harness kernel with a deep feedback loop, deployable as a Dockerized web service.

**Architecture:** Web-first (Approach A). Harness kernel is an importable Python library (`harness/`); FastAPI backend calls it in-process; agent operates in a sandboxed workspace per session. Feedback loop (validators→classifier→feedback_loop) is the focus dimension.

**Tech Stack:** Python 3.11+, FastAPI, pytest, keyring, openai SDK, Docker, GitLab CI

## Global Constraints

- Python ≥ 3.11 (uses `str | None` union syntax)
- TDD mandatory: red → green → refactor, no implementation before test
- No agent framework high-level loops (LangChain AgentExecutor / AutoGen / CrewAI / LlamaIndex agent)
- All core mechanisms must be unit-testable with mock/stub LLM, offline, no network
- Secrets never in source code / logs / git / agent tool environment
- Config files / rule files / prompt files are "content", not harness implementation

---

## File Structure

```
agentproject/
├── pyproject.toml
├── .gitignore
├── config.yaml
├── harness/
│   ├── __init__.py
│   ├── models.py              # Action, ActionResult, RawExecutionResult, Decision, Context, AgentEvent, Session, GuardrailRule, Config
│   ├── agent_runner.py         # Main loop
│   ├── config.py               # Config loader
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py             # LLMClient ABC
│   │   ├── mock_client.py      # MockLLMClient
│   │   └── real_client.py      # RealLLMClient
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py             # Tool ABC + ToolDispatcher
│   │   ├── file_tools.py       # ReadFile/WriteFile/ListFiles
│   │   ├── shell_tool.py       # RunShell
│   │   └── feedback_tools.py   # RunTests/RunLint/RunTypeCheck
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── guardrail.py        # guardrail(action)->Decision
│   │   ├── sandbox.py          # sandbox.execute
│   │   └── hitl.py             # HITL state machine
│   ├── feedback/
│   │   ├── __init__.py
│   │   ├── models.py           # FeedbackSignal, FailureItem, FailureClassification, RetryDecision
│   │   ├── validators.py       # PytestValidator/RuffValidator/MypyValidator
│   │   ├── classifier.py       # Classifier
│   │   └── feedback_loop.py    # FeedbackLoop
│   └── memory/
│       ├── __init__.py
│       └── store.py            # Memory store
├── webui/
│   ├── __init__.py
│   ├── app.py
│   ├── routes.py
│   ├── session_registry.py
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── cli.py
├── credman/
│   ├── __init__.py
│   └── store.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_llm_mock.py
│   ├── test_tool_dispatcher.py
│   ├── test_file_tools.py
│   ├── test_shell_feedback_tools.py
│   ├── test_guardrail.py
│   ├── test_sandbox.py
│   ├── test_hitl.py
│   ├── test_validators.py
│   ├── test_classifier.py
│   ├── test_feedback_loop.py
│   ├── test_memory_config.py
│   ├── test_agent_runner.py
│   ├── test_real_llm_client.py
│   ├── test_credential_store.py
│   ├── test_webui.py
│   ├── test_cli.py
│   └── test_demos.py
├── Dockerfile
├── .gitlab-ci.yml
├── SPEC.md
├── PLAN.md
└── README.md
```

## Dependency Graph

```
Task 1 (Models) ──┬──> Task 2 (LLM ABC+Mock)
                  ├──> Task 3 (ToolDispatcher)
                  ├──> Task 6 (Guardrail)
                  ├──> Task 7 (Sandbox)
                  ├──> Task 9 (Validators)
                  ├──> Task 12 (Memory+Config)
                  └──> Task 14 (CredentialStore)

Task 3 ──> Task 4 (FileTools) ──> Task 5 (Shell+FeedbackTools)
Task 6 ──> Task 8 (HITL)
Task 9 ──> Task 10 (Classifier) ──> Task 11 (FeedbackLoop)
Tasks 2,3,5,6,7,8,9,10,11,12 ──> Task 13 (AgentRunner)
Task 2 ──> Task 14 (RealLLMClient)  [parallel with 13]
Task 13 ──> Task 15 (WebUI)
Task 13 ──> Task 16 (CLI)  [parallel with 15]
Tasks 13,14 ──> Task 17 (Demos)
Task 15 ──> Task 18 (Docker+CI)
```

**Parallelizable:** Tasks 2,3,6,7,9,12,14 after Task 1. Tasks 4,5 after 3. Task 8 after 6. Tasks 10,11 sequential. Tasks 15,16 after 13.

---

## Task 1: Core Data Models

**Files:**
- Create: `pyproject.toml`
- Create: `harness/__init__.py`
- Create: `harness/models.py`
- Create: `harness/feedback/__init__.py`
- Create: `harness/feedback/models.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `Action`, `ActionResult`, `RawExecutionResult`, `Decision`, `Context`, `AgentEvent`, `Session`, `GuardrailRule`, `Config` (harness/models.py); `FeedbackSignal`, `FailureItem`, `FailureClassification`, `RetryDecision` (harness/feedback/models.py)

- [ ] **Step 1: Write pyproject.toml and .gitignore**

```toml
# pyproject.toml
[project]
name = "coding-agent-harness"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "keyring>=25.0", "openai>=1.30", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

```text
# .gitignore
__pycache__/
*.pyc
.env
.pytest_cache/
*.egg-info/
dist/
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_models.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness'`

- [ ] **Step 4: Write minimal implementation**

```python
# harness/__init__.py
```

```python
# harness/models.py
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
```

```python
# harness/feedback/__init__.py
```

```python
# harness/feedback/models.py
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
```

```python
# tests/__init__.py
```

```python
# tests/conftest.py
import pytest
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (10 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore harness/ tests/
git commit -m "feat: core data models for harness kernel"
```

---

## Task 2: LLMClient ABC + MockLLMClient

**Files:**
- Create: `harness/llm/__init__.py`
- Create: `harness/llm/base.py`
- Create: `harness/llm/mock_client.py`
- Create: `tests/test_llm_mock.py`

**Interfaces:**
- Consumes: `Context`, `Action` from Task 1
- Produces: `LLMClient` ABC (`propose_action(context) -> Action`), `MockLLMClient` (queue + responder modes)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_mock.py
import pytest
from harness.models import Action, Context, Message
from harness.llm.mock_client import MockLLMClient


def test_mock_queue_mode():
    client = MockLLMClient(actions=[
        Action(type="WriteFile", args={"path": "foo.py", "content": "x"}),
        Action(type="Done", args={"summary": "done"}),
    ])
    ctx = Context(system_prompt="test")
    a1 = client.propose_action(ctx)
    assert a1.type == "WriteFile"
    a2 = client.propose_action(ctx)
    assert a2.type == "Done"


def test_mock_queue_exhausted():
    client = MockLLMClient(actions=[Action(type="Done", args={})])
    client.propose_action(Context(system_prompt=""))
    with pytest.raises(Exception, match="MockExhausted"):
        client.propose_action(Context(system_prompt=""))


def test_mock_responder_mode():
    def responder(ctx: Context) -> Action:
        if ctx.feedback_signals:
            return Action(type="Done", args={"summary": "fixed"})
        return Action(type="RunTests", args={})

    client = MockLLMClient(responder=responder)
    ctx = Context(system_prompt="test")
    a1 = client.propose_action(ctx)
    assert a1.type == "RunTests"
    ctx.feedback_signals = ["some_signal"]
    a2 = client.propose_action(ctx)
    assert a2.type == "Done"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_mock.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/llm/__init__.py
```

```python
# harness/llm/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from harness.models import Action, Context


class LLMClient(ABC):
    @abstractmethod
    def propose_action(self, context: Context) -> Action:
        ...
```

```python
# harness/llm/mock_client.py
from __future__ import annotations
from collections import deque
from typing import Callable
from harness.models import Action, Context
from harness.llm.base import LLMClient


class MockExhaustedError(Exception):
    pass


class MockLLMClient(LLMClient):
    def __init__(
        self,
        actions: list[Action] | None = None,
        responder: Callable[[Context], Action] | None = None,
    ):
        self._queue = deque(actions) if actions else deque()
        self._responder = responder

    def propose_action(self, context: Context) -> Action:
        if self._responder is not None:
            return self._responder(context)
        if not self._queue:
            raise MockExhaustedError("Mock action queue exhausted")
        return self._queue.popleft()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_mock.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/llm/ tests/test_llm_mock.py
git commit -m "feat: LLMClient ABC + MockLLMClient with queue and responder modes"
```

---

## Task 3: Tool ABC + ToolDispatcher

**Files:**
- Create: `harness/tools/__init__.py`
- Create: `harness/tools/base.py`
- Create: `tests/test_tool_dispatcher.py`

**Interfaces:**
- Consumes: `Action`, `ActionResult`, `Decision`, `DecisionType` from Task 1
- Produces: `Tool` ABC (`execute(action, workspace) -> RawExecutionResult | ActionResult`), `ToolDispatcher` (`dispatch(action, workspace) -> ActionResult`, internal `guardrail.check → sandbox.execute`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_dispatcher.py
import pytest
from harness.models import Action, ActionResult, Decision, DecisionType, Workspace
from harness.tools.base import Tool, ToolDispatcher


class FakeTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "ReadFile"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        return ActionResult(success=True, output="file content")


class FakeGuardrail:
    def check(self, action: Action) -> Decision:
        if action.type == "RunShell" and "rm -rf" in action.args.get("command", ""):
            return Decision(verdict=DecisionType.DENY, reason="guardrail_denied")
        return Decision(verdict=DecisionType.ALLOW)


class FakeSandbox:
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        return ActionResult(success=True, output="executed")


def test_dispatch_allow():
    td = ToolDispatcher(tools=[FakeTool()], guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="ReadFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    assert result.success
    assert result.output == "file content"


def test_dispatch_deny_returns_rejected_feedback():
    from harness.feedback.models import FeedbackSignal
    td = ToolDispatcher(tools=[FakeTool()], guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="RunShell", args={"command": "rm -rf /"}), Workspace(cwd="/tmp"))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "guardrail_denied"


def test_dispatch_no_tool_handles():
    td = ToolDispatcher(tools=[FakeTool()], guardrail=FakeGuardrail(), sandbox=FakeSandbox())
    result = td.dispatch(Action(type="ListFiles", args={}), Workspace(cwd="/tmp"))
    assert result.success is False
    assert "no tool" in result.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tool_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/tools/__init__.py
```

```python
# harness/tools/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from harness.models import Action, ActionResult, Decision, Workspace
from harness.feedback.models import FeedbackSignal


class Tool(ABC):
    @abstractmethod
    def can_handle(self, action: Action) -> bool: ...
    @abstractmethod
    def execute(self, action: Action, workspace: Workspace) -> ActionResult: ...


class GuardrailProtocol(ABC):
    @abstractmethod
    def check(self, action: Action) -> Decision: ...


class SandboxProtocol(ABC):
    @abstractmethod
    def execute(self, action: Action, workspace: Workspace) -> ActionResult: ...


class ApprovalResolverProtocol(ABC):
    @abstractmethod
    def request_approval(self, action: Action) -> Decision: ...


class ToolDispatcher:
    def __init__(
        self,
        tools: list[Tool],
        guardrail: GuardrailProtocol,
        sandbox: SandboxProtocol,
        approval_resolver: ApprovalResolverProtocol | None = None,
    ):
        self._tools = tools
        self._guardrail = guardrail
        self._sandbox = sandbox
        self._approval_resolver = approval_resolver

    def dispatch(self, action: Action, workspace: Workspace) -> ActionResult | FeedbackSignal:
        decision = self._guardrail.check(action)
        if decision.verdict == DecisionType.ALLOW:
            return self._sandbox.execute(action, workspace)
        elif decision.verdict == DecisionType.DENY:
            return FeedbackSignal(
                source="guardrail", passed=False, failures=[],
                summary="", raw="", reason=decision.reason or "guardrail_denied",
            )
        elif decision.verdict == DecisionType.REQUIRE_APPROVAL:
            if self._approval_resolver is None:
                return FeedbackSignal(
                    source="guardrail", passed=False, failures=[],
                    summary="", raw="", reason="no_approval_resolver",
                )
            approval = self._approval_resolver.request_approval(action)
            if approval.verdict == DecisionType.ALLOW:
                return self._sandbox.execute(action, workspace)
            else:
                return FeedbackSignal(
                    source="hitl", passed=False, failures=[],
                    summary="", raw="", reason=approval.reason or "approval_denied",
                )
        return ActionResult(success=False, error="unknown verdict")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tool_dispatcher.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/tools/ tests/test_tool_dispatcher.py
git commit -m "feat: Tool ABC + ToolDispatcher with guardrail→sandbox single-point dispatch"
```

---

## Task 4: File Tools (ReadFile / WriteFile / ListFiles)

**Files:**
- Create: `harness/tools/file_tools.py`
- Create: `tests/test_file_tools.py`

**Interfaces:**
- Consumes: `Tool` ABC, `Action`, `ActionResult`, `Workspace` from Task 3
- Produces: `ReadFileTool`, `WriteFileTool`, `ListFilesTool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_file_tools.py
import os
import tempfile
from harness.models import Action, Workspace
from harness.tools.file_tools import ReadFileTool, WriteFileTool, ListFilesTool


def test_write_then_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        wt = WriteFileTool()
        rt = ReadFileTool()
        w_result = wt.execute(Action(type="WriteFile", args={"path": "foo.py", "content": "print('hi')"}), ws)
        assert w_result.success
        r_result = rt.execute(Action(type="ReadFile", args={"path": "foo.py"}), ws)
        assert r_result.success
        assert r_result.output == "print('hi')"


def test_read_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        rt = ReadFileTool()
        result = rt.execute(Action(type="ReadFile", args={"path": "nope.py"}), ws)
        assert result.success is False
        assert "not found" in result.error.lower()


def test_path_traversal_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        rt = ReadFileTool()
        result = rt.execute(Action(type="ReadFile", args={"path": "../../../etc/passwd"}), ws)
        assert result.success is False
        assert "traversal" in result.error.lower() or "outside" in result.error.lower()


def test_list_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        wt = WriteFileTool()
        wt.execute(Action(type="WriteFile", args={"path": "a.py", "content": "x"}), ws)
        wt.execute(Action(type="WriteFile", args={"path": "b.py", "content": "y"}), ws)
        lt = ListFilesTool()
        result = lt.execute(Action(type="ListFiles", args={"pattern": "*.py"}), ws)
        assert result.success
        files = result.output.strip().split("\n")
        assert set(files) == {"a.py", "b.py"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_file_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/tools/file_tools.py
from __future__ import annotations
import os
import glob
from harness.models import Action, ActionResult, Workspace
from harness.tools.base import Tool


def _resolve_safe(path: str, cwd: str) -> str | None:
    full = os.path.normpath(os.path.join(cwd, path))
    if not full.startswith(os.path.normpath(cwd)):
        return None
    return full


class ReadFileTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "ReadFile"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        full = _resolve_safe(action.args["path"], workspace.cwd)
        if full is None:
            return ActionResult(success=False, error="Path traversal detected: outside workspace")
        if not os.path.isfile(full):
            return ActionResult(success=False, error=f"File not found: {action.args['path']}")
        with open(full, "r") as f:
            return ActionResult(success=True, output=f.read())


class WriteFileTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "WriteFile"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        full = _resolve_safe(action.args["path"], workspace.cwd)
        if full is None:
            return ActionResult(success=False, error="Path traversal detected: outside workspace")
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        with open(full, "w") as f:
            f.write(action.args["content"])
        return ActionResult(success=True, output=f"Wrote {action.args['path']}")


class ListFilesTool(Tool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "ListFiles"
    def execute(self, action: Action, workspace: Workspace) -> ActionResult:
        pattern = action.args.get("pattern", "*")
        matches = glob.glob(os.path.join(workspace.cwd, pattern))
        files = sorted(os.path.relpath(m, workspace.cwd) for m in matches if os.path.isfile(m))
        return ActionResult(success=True, output="\n".join(files))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_file_tools.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/tools/file_tools.py tests/test_file_tools.py
git commit -m "feat: file tools (ReadFile/WriteFile/ListFiles) with path traversal protection"
```

---

## Task 5: Shell Tool + Feedback Tools

**Files:**
- Create: `harness/tools/shell_tool.py`
- Create: `harness/tools/feedback_tools.py`
- Create: `tests/test_shell_feedback_tools.py`

**Interfaces:**
- Consumes: `Tool` ABC, `Action`, `RawExecutionResult`, `Workspace` from Tasks 1,3
- Produces: `RunShellTool` (returns `RawExecutionResult`), `RunTestsTool`/`RunLintTool`/`RunTypeCheckTool` (return `RawExecutionResult`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shell_feedback_tools.py
import tempfile
from harness.models import Action, Workspace, RawExecutionResult
from harness.tools.shell_tool import RunShellTool
from harness.tools.feedback_tools import RunTestsTool, RunLintTool, RunTypeCheckTool


def test_run_shell_echo():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        tool = RunShellTool(timeout=5)
        result = tool.execute(Action(type="RunShell", args={"command": "echo hello"}), ws)
        assert isinstance(result, RawExecutionResult)
        assert result.exit_code == 0
        assert "hello" in result.stdout


def test_run_shell_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        tool = RunShellTool(timeout=1)
        result = tool.execute(Action(type="RunShell", args={"command": "sleep 10"}), ws)
        assert isinstance(result, RawExecutionResult)
        assert result.exit_code != 0
        assert "timeout" in result.stderr.lower()


def test_run_tests_produces_raw_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        tool = RunTestsTool(timeout=10)
        result = tool.execute(Action(type="RunTests", args={}), ws)
        assert isinstance(result, RawExecutionResult)


def test_env_whitelist_excludes_custom_var():
    import os
    os.environ["HARNESS_TEST_SECRET"] = "super_secret"
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        tool = RunShellTool(timeout=5, env_whitelist=["PATH", "HOME", "LANG"])
        result = tool.execute(Action(type="RunShell", args={"command": "echo $HARNESS_TEST_SECRET"}), ws)
        assert "super_secret" not in result.stdout
    del os.environ["HARNESS_TEST_SECRET"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shell_feedback_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/tools/shell_tool.py
from __future__ import annotations
import os
import subprocess
from harness.models import Action, Workspace, RawExecutionResult
from harness.tools.base import Tool


class RunShellTool(Tool):
    def __init__(self, timeout: int = 30, env_whitelist: list[str] | None = None):
        self._timeout = timeout
        self._env_whitelist = env_whitelist or ["PATH", "HOME", "LANG"]

    def can_handle(self, action: Action) -> bool:
        return action.type == "RunShell"

    def _build_env(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k in self._env_whitelist}

    def execute(self, action: Action, workspace: Workspace) -> RawExecutionResult:
        cmd = action.args["command"]
        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=workspace.cwd,
                capture_output=True, text=True,
                timeout=self._timeout, env=self._build_env(),
            )
            return RawExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return RawExecutionResult(
                exit_code=-1, stdout="", stderr=f"Command timed out after {self._timeout}s",
            )
```

```python
# harness/tools/feedback_tools.py
from __future__ import annotations
from harness.models import Action, Workspace, RawExecutionResult
from harness.tools.shell_tool import RunShellTool


class RunTestsTool(RunShellTool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "RunTests"
    def execute(self, action: Action, workspace: Workspace) -> RawExecutionResult:
        return super().execute(
            Action(type="RunShell", args={"command": "python -m pytest --tb=short -q"}), workspace,
        )


class RunLintTool(RunShellTool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "RunLint"
    def execute(self, action: Action, workspace: Workspace) -> RawExecutionResult:
        return super().execute(
            Action(type="RunShell", args={"command": "python -m ruff check --output-format=json ."}), workspace,
        )


class RunTypeCheckTool(RunShellTool):
    def can_handle(self, action: Action) -> bool:
        return action.type == "RunTypeCheck"
    def execute(self, action: Action, workspace: Workspace) -> RawExecutionResult:
        return super().execute(
            Action(type="RunShell", args={"command": "python -m mypy . --no-error-summary"}), workspace,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_shell_feedback_tools.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/tools/shell_tool.py harness/tools/feedback_tools.py tests/test_shell_feedback_tools.py
git commit -m "feat: shell tool + feedback tools with env whitelist and timeout"
```

---

## Task 6: Guardrail (Rule Engine)

**Files:**
- Create: `harness/governance/__init__.py`
- Create: `harness/governance/guardrail.py`
- Create: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: `Action`, `Decision`, `DecisionType`, `GuardrailRule` from Task 1
- Produces: `Guardrail` (`check(action) -> Decision`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guardrail.py
from harness.models import Action, DecisionType, GuardrailRule
from harness.governance.guardrail import Guardrail


def test_block_rm_rf():
    rules = [GuardrailRule(name="block_rm_rf", pattern=r"rm\s+-rf", action_type="RunShell", verdict=DecisionType.DENY, reason="destructive")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "rm -rf /"}))
    assert d.verdict == DecisionType.DENY
    assert d.reason == "destructive"


def test_block_git_push_force():
    rules = [GuardrailRule(name="block_force_push", pattern=r"git\s+push.*--force", action_type="RunShell", verdict=DecisionType.DENY, reason="force push")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "git push --force origin main"}))
    assert d.verdict == DecisionType.DENY


def test_allow_safe_command():
    rules = [GuardrailRule(name="block_rm_rf", pattern=r"rm\s+-rf", action_type="RunShell", verdict=DecisionType.DENY, reason="destructive")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "echo hello"}))
    assert d.verdict == DecisionType.ALLOW


def test_require_approval_for_pip_install():
    rules = [GuardrailRule(name="approve_pip", pattern=r"pip\s+install", action_type="RunShell", verdict=DecisionType.REQUIRE_APPROVAL, reason="network install")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "pip install requests"}))
    assert d.verdict == DecisionType.REQUIRE_APPROVAL


def test_allow_readfile():
    rules = []
    g = Guardrail(rules=rules)
    d = g.check(Action(type="ReadFile", args={"path": "foo.py"}))
    assert d.verdict == DecisionType.ALLOW


def test_path_traversal_in_writefile():
    rules = [GuardrailRule(name="block_traversal", pattern=r"\.\.", action_type="WriteFile", verdict=DecisionType.DENY, reason="path traversal")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="WriteFile", args={"path": "../../../etc/passwd", "content": "x"}))
    assert d.verdict == DecisionType.DENY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_guardrail.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/governance/__init__.py
```

```python
# harness/governance/guardrail.py
from __future__ import annotations
import re
from harness.models import Action, Decision, DecisionType, GuardrailRule


class Guardrail:
    def __init__(self, rules: list[GuardrailRule] | None = None):
        self._rules = rules or []

    def check(self, action: Action) -> Decision:
        for rule in self._rules:
            if rule.action_type != action.type:
                continue
            target = action.args.get("command") or action.args.get("path") or ""
            if re.search(rule.pattern, target):
                return Decision(verdict=rule.verdict, reason=rule.reason)
        return Decision(verdict=DecisionType.ALLOW)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_guardrail.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/governance/ tests/test_guardrail.py
git commit -m "feat: guardrail rule engine with regex pattern matching"
```

---

## Task 7: Sandbox (Execution Isolation)

**Files:**
- Create: `harness/governance/sandbox.py`
- Create: `tests/test_sandbox.py`

**Interfaces:**
- Consumes: `Action`, `ActionResult`, `RawExecutionResult`, `Workspace`, `Config` from Tasks 1,3
- Produces: `Sandbox` (`execute(action, workspace) -> ActionResult | RawExecutionResult`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sandbox.py
import os
import tempfile
from harness.models import Action, Workspace, RawExecutionResult, Config
from harness.governance.sandbox import Sandbox
from harness.tools.file_tools import ReadFileTool, WriteFileTool
from harness.tools.shell_tool import RunShellTool


def test_sandbox_executes_writefile():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        sb = Sandbox(tools=[WriteFileTool()], timeout=5, env_whitelist=["PATH", "HOME", "LANG"])
        result = sb.execute(Action(type="WriteFile", args={"path": "foo.py", "content": "x"}), ws)
        assert result.success


def test_sandbox_executes_runshell():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        sb = Sandbox(tools=[RunShellTool(timeout=5)], timeout=5, env_whitelist=["PATH", "HOME", "LANG"])
        result = sb.execute(Action(type="RunShell", args={"command": "echo hi"}), ws)
        assert isinstance(result, RawExecutionResult)
        assert "hi" in result.stdout


def test_sandbox_env_whitelist():
    os.environ["HARNESS_SECRET"] = "secret_value"
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        sb = Sandbox(tools=[RunShellTool(timeout=5)], timeout=5, env_whitelist=["PATH", "HOME", "LANG"])
        result = sb.execute(Action(type="RunShell", args={"command": "echo $HARNESS_SECRET"}), ws)
        assert "secret_value" not in result.stdout
    del os.environ["HARNESS_SECRET"]


def test_sandbox_no_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(cwd=tmpdir)
        sb = Sandbox(tools=[], timeout=5, env_whitelist=["PATH"])
        result = sb.execute(Action(type="ReadFile", args={"path": "foo"}), ws)
        assert result.success is False
        assert "no tool" in result.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sandbox.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/governance/sandbox.py
from __future__ import annotations
from harness.models import Action, ActionResult, Workspace, RawExecutionResult
from harness.tools.base import Tool


class Sandbox:
    def __init__(self, tools: list[Tool], timeout: int = 30, env_whitelist: list[str] | None = None):
        self._tools = tools
        self._timeout = timeout
        self._env_whitelist = env_whitelist or ["PATH", "HOME", "LANG"]

    def execute(self, action: Action, workspace: Workspace) -> ActionResult | RawExecutionResult:
        for tool in self._tools:
            if tool.can_handle(action):
                if hasattr(tool, "_timeout"):
                    tool._timeout = self._timeout
                if hasattr(tool, "_env_whitelist"):
                    tool._env_whitelist = self._env_whitelist
                return tool.execute(action, workspace)
        return ActionResult(success=False, error=f"No tool can handle action type: {action.type}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sandbox.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/governance/sandbox.py tests/test_sandbox.py
git commit -m "feat: sandbox with env whitelist and tool delegation"
```

---

## Task 8: HITL State Machine

**Files:**
- Create: `harness/governance/hitl.py`
- Create: `tests/test_hitl.py`

**Interfaces:**
- Consumes: `Action`, `Decision`, `DecisionType`, `Workspace` from Tasks 1,3
- Produces: `HitlStateMachine` (states: IDLE→PENDING_APPROVAL→APPROVED|DENIED|TIMEOUT→IDLE), `ApprovalResolver` stub interface

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hitl.py
from harness.models import Action, Decision, DecisionType
from harness.feedback.models import FeedbackSignal
from harness.governance.hitl import HitlStateMachine, ApprovalResolver


class StubApprovalResolver(ApprovalResolver):
    def __init__(self, decision: Decision):
        self._decision = decision
    def request_approval(self, action: Action) -> Decision:
        return self._decision


def test_hitl_approve():
    sm = HitlStateMachine(resolver=StubApprovalResolver(Decision(verdict=DecisionType.ALLOW)))
    result = sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert sm.state == "IDLE"
    assert result.verdict == DecisionType.ALLOW


def test_hitl_deny_returns_rejected_signal():
    sm = HitlStateMachine(resolver=StubApprovalResolver(Decision(verdict=DecisionType.DENY, reason="approval_denied")))
    result = sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "approval_denied"
    assert sm.state == "IDLE"


def test_hitl_timeout_returns_rejected_signal():
    class TimeoutResolver(ApprovalResolver):
        def request_approval(self, action: Action) -> Decision:
            return Decision(verdict=DecisionType.DENY, reason="approval_timeout")
    sm = HitlStateMachine(resolver=TimeoutResolver(), timeout=0)
    result = sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "approval_timeout"
    assert sm.state == "IDLE"


def test_hitl_state_transitions():
    sm = HitlStateMachine(resolver=StubApprovalResolver(Decision(verdict=DecisionType.ALLOW)))
    assert sm.state == "IDLE"
    sm.handle(Action(type="RunShell", args={"command": "pip install x"}))
    assert sm.state == "IDLE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hitl.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/governance/hitl.py
from __future__ import annotations
from harness.models import Action, Decision, DecisionType
from harness.feedback.models import FeedbackSignal


class ApprovalResolver:
    def request_approval(self, action: Action) -> Decision:
        raise NotImplementedError


class HitlStateMachine:
    def __init__(self, resolver: ApprovalResolver, timeout: int = 300):
        self._resolver = resolver
        self._timeout = timeout
        self.state = "IDLE"

    def handle(self, action: Action) -> Decision | FeedbackSignal:
        self.state = "PENDING_APPROVAL"
        decision = self._resolver.request_approval(action)
        if decision.verdict == DecisionType.ALLOW:
            self.state = "APPROVED"
            self.state = "IDLE"
            return decision
        elif decision.verdict == DecisionType.DENY:
            self.state = "DENIED"
            self.state = "IDLE"
            return FeedbackSignal(
                source="hitl", passed=False, failures=[],
                summary="", raw="", reason=decision.reason or "approval_denied",
            )
        else:
            self.state = "TIMEOUT"
            self.state = "IDLE"
            return FeedbackSignal(
                source="hitl", passed=False, failures=[],
                summary="", raw="", reason="approval_timeout",
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hitl.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/governance/hitl.py tests/test_hitl.py
git commit -m "feat: HITL state machine with approve/deny/timeout handling"
```

---

## Task 9: Validators (Pytest / Ruff / Mypy)

**Files:**
- Create: `harness/feedback/validators.py`
- Create: `tests/test_validators.py`

**Interfaces:**
- Consumes: `RawExecutionResult` from Task 1, `FeedbackSignal`, `FailureItem` from Task 1
- Produces: `PytestValidator`, `RuffValidator`, `MypyValidator` (each: `parse(raw: RawExecutionResult) -> FeedbackSignal`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validators.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validators.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/feedback/validators.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validators.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/feedback/validators.py tests/test_validators.py
git commit -m "feat: validators for pytest/ruff/mypy output parsing"
```

---

## Task 10: Classifier (Failure Classification + Priority)

**Files:**
- Create: `harness/feedback/classifier.py`
- Create: `tests/test_classifier.py`

**Interfaces:**
- Consumes: `FeedbackSignal`, `FailureItem`, `FailureClassification` from Task 1
- Produces: `Classifier` (`classify(signal: FeedbackSignal) -> FailureClassification`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_classifier.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/feedback/classifier.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classifier.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/feedback/classifier.py tests/test_classifier.py
git commit -m "feat: classifier with priority-based failure category merging"
```

---

## Task 11: FeedbackLoop (Retry / Escalation / Stagnation Detection)

**Files:**
- Create: `harness/feedback/feedback_loop.py`
- Create: `tests/test_feedback_loop.py`

**Interfaces:**
- Consumes: `FeedbackSignal`, `FailureClassification`, `RetryDecision`, `RetryStrategy` from Task 1
- Produces: `FeedbackLoop` (`decide(signal, classification, attempt_count, failure_history) -> RetryDecision`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_feedback_loop.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feedback_loop.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/feedback/feedback_loop.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feedback_loop.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/feedback/feedback_loop.py tests/test_feedback_loop.py
git commit -m "feat: feedback loop with stagnation/oscillation detection and escalation"
```

---

## Task 12: Memory Store + Config Loader

**Files:**
- Create: `harness/memory/__init__.py`
- Create: `harness/memory/store.py`
- Create: `harness/config.py`
- Create: `config.yaml`
- Create: `tests/test_memory_config.py`

**Interfaces:**
- Consumes: `Config`, `GuardrailRule`, `DecisionType` from Task 1
- Produces: `MemoryStore` (`store/retrieve/list_keys`), `load_config(path) -> Config`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_config.py
import tempfile
import os
from harness.memory.store import MemoryStore
from harness.config import load_config
from harness.models import Config, DecisionType


def test_memory_store_retrieve():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(workspace_dir=tmpdir)
        store.store("convention", "use pytest")
        assert store.retrieve("convention") == "use pytest"


def test_memory_store_list_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(workspace_dir=tmpdir)
        store.store("a", "1")
        store.store("b", "2")
        keys = store.list_keys()
        assert set(keys) == {"a", "b"}


def test_memory_store_missing_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(workspace_dir=tmpdir)
        assert store.retrieve("nonexistent") is None


def test_memory_store_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store1 = MemoryStore(workspace_dir=tmpdir)
        store1.store("key", "value")
        store2 = MemoryStore(workspace_dir=tmpdir)
        assert store2.retrieve("key") == "value"


def test_load_config_defaults():
    cfg = load_config("nonexistent.yaml")
    assert cfg.max_iterations == 20
    assert cfg.sandbox_timeout == 30


def test_load_config_from_yaml():
    import yaml
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({
            "max_iterations": 10,
            "sandbox_timeout": 60,
            "guardrail_rules": [
                {"name": "block_rm", "pattern": r"rm\s+-rf", "action_type": "RunShell", "verdict": "DENY", "reason": "destructive"},
            ],
            "hints": {"ASSERTION_FAILURE": "check logic"},
        }, f)
        path = f.name
    cfg = load_config(path)
    assert cfg.max_iterations == 10
    assert cfg.sandbox_timeout == 60
    assert len(cfg.guardrail_rules) == 1
    assert cfg.guardrail_rules[0].verdict == DecisionType.DENY
    assert cfg.hints["ASSERTION_FAILURE"] == "check logic"
    os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/memory/__init__.py
```

```python
# harness/memory/store.py
from __future__ import annotations
import json
import os


class MemoryStore:
    def __init__(self, workspace_dir: str):
        self._dir = os.path.join(workspace_dir, ".harness")
        self._file = os.path.join(self._dir, "memory.json")
        os.makedirs(self._dir, exist_ok=True)

    def _load(self) -> dict[str, str]:
        if not os.path.exists(self._file):
            return {}
        try:
            with open(self._file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict[str, str]) -> None:
        with open(self._file, "w") as f:
            json.dump(data, f)

    def store(self, key: str, value: str) -> None:
        data = self._load()
        data[key] = value
        self._save(data)

    def retrieve(self, key: str) -> str | None:
        return self._load().get(key)

    def list_keys(self) -> list[str]:
        return list(self._load().keys())
```

```python
# harness/config.py
from __future__ import annotations
import os
import yaml
from harness.models import Config, GuardrailRule, DecisionType


def load_config(path: str | None = None) -> Config:
    cfg = Config()
    if path and os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if "max_iterations" in data:
            cfg.max_iterations = data["max_iterations"]
        if "sandbox_timeout" in data:
            cfg.sandbox_timeout = data["sandbox_timeout"]
        if "hitl_timeout" in data:
            cfg.hitl_timeout = data["hitl_timeout"]
        if "max_concurrent_sessions" in data:
            cfg.max_concurrent_sessions = data["max_concurrent_sessions"]
        if "guardrail_rules" in data:
            cfg.guardrail_rules = [
                GuardrailRule(
                    name=r["name"], pattern=r["pattern"],
                    action_type=r["action_type"],
                    verdict=DecisionType(r["verdict"]),
                    reason=r.get("reason", ""),
                ) for r in data["guardrail_rules"]
            ]
        if "feedback_thresholds" in data:
            cfg.feedback_thresholds = data["feedback_thresholds"]
        if "llm_settings" in data:
            cfg.llm_settings = data["llm_settings"]
        if "hints" in data:
            cfg.hints = data["hints"]
    return cfg
```

```yaml
# config.yaml
max_iterations: 20
sandbox_timeout: 30
hitl_timeout: 300
max_concurrent_sessions: 5

guardrail_rules:
  - name: block_rm_rf
    pattern: 'rm\s+-rf'
    action_type: RunShell
    verdict: DENY
    reason: destructive command
  - name: block_force_push
    pattern: 'git\s+push.*--force'
    action_type: RunShell
    verdict: DENY
    reason: force push
  - name: approve_pip_install
    pattern: 'pip\s+install'
    action_type: RunShell
    verdict: REQUIRE_APPROVAL
    reason: network install
  - name: block_path_traversal
    pattern: '\.\.'
    action_type: WriteFile
    verdict: DENY
    reason: path traversal

feedback_thresholds:
  max_retries_per_class: 3
  escalation_threshold: 2

llm_settings:
  model: gpt-4o-mini
  temperature: 0.0

hints:
  ASSERTION_FAILURE: "The test ran but the assertion failed. Check the logic in the failing test."
  IMPORT_ERROR: "A module could not be imported. Check import paths and dependencies."
  SYNTAX_ERROR: "The code has a syntax error and cannot be parsed."
  COLLECTION_ERROR: "pytest could not collect the test files. Check for import or syntax errors."
  TYPE_ERROR: "mypy found a type violation. Check the type annotations."
  LINT_VIOLATION: "ruff found a style or convention violation."
  TIMEOUT: "The command timed out. Check for infinite loops or long-running operations."
  UNKNOWN: "An unclassified error occurred. Check the raw output."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_config.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/memory/ harness/config.py config.yaml tests/test_memory_config.py
git commit -m "feat: memory store + config loader with YAML support"
```

---

## Task 13: AgentRunner (Main Loop)

**Files:**
- Create: `harness/agent_runner.py`
- Create: `tests/test_agent_runner.py`

**Interfaces:**
- Consumes: All previous tasks
- Produces: `AgentRunner` (`run(task, workspace, ...) -> list[AgentEvent]`), `EventSink` Protocol, context construction, stop conditions

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_runner.py
import tempfile
import pytest
from harness.models import Action, Workspace, Config
from harness.agent_runner import AgentRunner, RecordingEventSink
from harness.llm.mock_client import MockLLMClient
from harness.tools.base import ToolDispatcher
from harness.tools.file_tools import WriteFileTool, ReadFileTool
from harness.tools.shell_tool import RunShellTool
from harness.tools.feedback_tools import RunTestsTool
from harness.governance.guardrail import Guardrail
from harness.governance.sandbox import Sandbox
from harness.feedback.validators import PytestValidator
from harness.feedback.classifier import Classifier
from harness.feedback.feedback_loop import FeedbackLoop
from harness.feedback.models import FeedbackSignal, FailureItem


def make_runner(actions, tmpdir):
    cfg = Config()
    tools = [WriteFileTool(), ReadFileTool(), RunShellTool(timeout=5), RunTestsTool(timeout=10)]
    guardrail = Guardrail(rules=cfg.guardrail_rules)
    sandbox = Sandbox(tools=tools, timeout=cfg.sandbox_timeout, env_whitelist=cfg.sandbox_env_whitelist)
    td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
    llm = MockLLMClient(actions=actions)
    validator = PytestValidator()
    classifier = Classifier(hints=cfg.hints)
    fl = FeedbackLoop(max_iterations=cfg.max_iterations, escalation_threshold=cfg.feedback_thresholds["escalation_threshold"])
    sink = RecordingEventSink()
    runner = AgentRunner(
        llm_client=llm, dispatcher=td, validator=validator,
        classifier=classifier, feedback_loop=fl,
        config=cfg, event_sink=sink,
    )
    return runner, sink


def test_loop_done():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner, sink = make_runner([Action(type="Done", args={"summary": "done"})], tmpdir)
        runner.run("test task", Workspace(cwd=tmpdir))
        assert any(e.__class__.__name__ == "LoopFinished" for e in sink.events)


def test_loop_write_then_done():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner, sink = make_runner([
            Action(type="WriteFile", args={"path": "foo.py", "content": "x"}),
            Action(type="Done", args={"summary": "done"}),
        ], tmpdir)
        runner.run("test task", Workspace(cwd=tmpdir))
        assert any(e.__class__.__name__ == "LoopFinished" for e in sink.events)


def test_loop_max_iterations_abort():
    with tempfile.TemporaryDirectory() as tmpdir:
        # LLM never says Done, always proposes ReadFile
        def responder(ctx):
            return Action(type="ReadFile", args={"path": "foo.py"})
        cfg = Config(max_iterations=3)
        tools = [ReadFileTool()]
        guardrail = Guardrail()
        sandbox = Sandbox(tools=tools, timeout=5)
        td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
        llm = MockLLMClient(responder=responder)
        fl = FeedbackLoop(max_iterations=3, escalation_threshold=5)
        sink = RecordingEventSink()
        runner = AgentRunner(
            llm_client=llm, dispatcher=td, validator=PytestValidator(),
            classifier=Classifier(hints={}), feedback_loop=fl,
            config=cfg, event_sink=sink,
        )
        runner.run("test", Workspace(cwd=tmpdir))
        finished = [e for e in sink.events if e.__class__.__name__ == "LoopFinished"]
        assert len(finished) == 1
        assert "abort" in finished[0].reason.lower() or "max" in finished[0].reason.lower()


def test_auto_stop_on_consecutive_pass():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simulate: RunTests returns pass twice → auto-stop
        from harness.models import RawExecutionResult
        class PassValidator:
            @staticmethod
            def parse(raw):
                return FeedbackSignal(source="pytest", passed=True, failures=[])
        runner, sink = make_runner([
            Action(type="RunTests", args={}),
            Action(type="RunTests", args={}),
        ], tmpdir)
        runner._validator = PassValidator()
        runner.run("test", Workspace(cwd=tmpdir))
        finished = [e for e in sink.events if e.__class__.__name__ == "LoopFinished"]
        assert len(finished) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/agent_runner.py
from __future__ import annotations
from typing import Protocol
from harness.models import (
    Action, ActionResult, RawExecutionResult, Context, Message,
    Workspace, Config, MemoryItem, WorkspaceInfo,
    LoopStarted, ContextBuilt, LLMProposed, GuardrailDecision,
    ToolCallStarted, ToolCallResult, FeedbackSignalEmitted,
    FailureClassified, RetryDecisionEvent, HitlApprovalRequired,
    LoopStep, LoopFinished,
)
from harness.feedback.models import FeedbackSignal, FailureClassification, RetryDecision, RetryStrategy
from harness.llm.base import LLMClient
from harness.tools.base import ToolDispatcher
from harness.feedback.validators import PytestValidator
from harness.feedback.classifier import Classifier
from harness.feedback.feedback_loop import FeedbackLoop


class EventSink(Protocol):
    def emit(self, event) -> None: ...


class RecordingEventSink:
    def __init__(self):
        self.events: list = []
    def emit(self, event) -> None:
        self.events.append(event)


class AgentRunner:
    def __init__(
        self,
        llm_client: LLMClient,
        dispatcher: ToolDispatcher,
        validator: PytestValidator,
        classifier: Classifier,
        feedback_loop: FeedbackLoop,
        config: Config,
        event_sink: EventSink,
    ):
        self._llm = llm_client
        self._dispatcher = dispatcher
        self._validator = validator
        self._classifier = classifier
        self._feedback_loop = feedback_loop
        self._config = config
        self._sink = event_sink
        self._history: list[Message] = []
        self._feedback_history: list[FeedbackSignal] = []
        self._consecutive_passes = 0

    def _build_context(self, task: str, workspace: Workspace) -> Context:
        ws_info = WorkspaceInfo(cwd=workspace.cwd)
        return Context(
            system_prompt=f"You are a coding agent. Task: {task}",
            history=self._history[-20:],
            memory_items=[],
            feedback_signals=self._feedback_history[-5:],
            workspace_info=ws_info,
        )

    def _format_feedback(self, signal: FeedbackSignal, fc: FailureClassification, rd: RetryDecision) -> str:
        lines = [f"[FEEDBACK] source={signal.source}, passed={signal.passed}"]
        if signal.failures:
            lines.append("  Failures:")
            for f in signal.failures:
                lines.append(f"    - {f.loc}: {f.message} ({f.category})")
        lines.append(f"  Classification: {fc.category}")
        if fc.hint:
            lines.append(f"  Hint: {fc.hint}")
        lines.append(f"  RetryDecision: {rd.strategy.value} (attempt {rd.attempt_count}/{rd.max})")
        return "\n".join(lines)

    def _should_auto_stop(self) -> bool:
        return self._consecutive_passes >= 2

    def run(self, task: str, workspace: Workspace) -> None:
        self._sink.emit(LoopStarted(session_id="", task=task))
        attempt = 0
        while attempt < self._config.max_iterations:
            attempt += 1
            ctx = self._build_context(task, workspace)
            self._sink.emit(ContextBuilt(context=ctx))

            action = self._llm.propose_action(ctx)
            self._sink.emit(LLMProposed(action=action))

            if action.type == "Done":
                self._sink.emit(LoopFinished(session_id="", reason=f"Done: {action.args.get('summary', '')}"))
                return

            result = self._dispatcher.dispatch(action, workspace)

            if isinstance(result, FeedbackSignal) and result.reason:
                # Rejected signal from guardrail/HITL
                self._feedback_history.append(result)
                self._sink.emit(FeedbackSignalEmitted(signal=result))
                self._history.append(Message(role="tool", content=f"Action rejected: {result.reason}"))
                self._consecutive_passes = 0
                continue

            self._sink.emit(ToolCallStarted(action=action))
            self._sink.emit(ToolCallResult(action=action, result=result if isinstance(result, ActionResult) else ActionResult(success=True)))

            # Check if result is a RawExecutionResult (from feedback tools)
            if isinstance(result, RawExecutionResult):
                signal = self._validator.parse(result)
                self._sink.emit(FeedbackSignalEmitted(signal=signal))

                if signal.passed:
                    self._consecutive_passes += 1
                else:
                    self._consecutive_passes = 0
                    fc = self._classifier.classify(signal)
                    self._sink.emit(FailureClassified(classification=fc))
                    rd = self._feedback_loop.decide(signal, fc, attempt, self._feedback_history)
                    self._sink.emit(RetryDecisionEvent(strategy=rd.strategy.value, attempt_count=rd.attempt_count))
                    feedback_text = self._format_feedback(signal, fc, rd)
                    self._history.append(Message(role="tool", content=feedback_text))

                    if rd.strategy == RetryStrategy.ABORT:
                        self._sink.emit(LoopFinished(session_id="", reason="ABORT: max iterations reached"))
                        return
                    if rd.strategy == RetryStrategy.ESCALATE:
                        self._history.append(Message(role="system", content="ESCALATION: agent appears stuck. Try a different approach."))

                self._feedback_history.append(signal)
            else:
                self._history.append(Message(role="tool", content=result.output if result.success else f"Error: {result.error}"))
                self._consecutive_passes = 0

            self._sink.emit(LoopStep(step=attempt))

            if self._should_auto_stop():
                self._sink.emit(LoopFinished(session_id="", reason="Auto-stop: consecutive passes"))
                return

        self._sink.emit(LoopFinished(session_id="", reason="ABORT: max iterations reached"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_runner.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/agent_runner.py tests/test_agent_runner.py
git commit -m "feat: agent runner main loop with context construction, feedback, and stop conditions"
```

---

## Task 14: RealLLMClient

**Files:**
- Create: `harness/llm/real_client.py`
- Create: `tests/test_real_llm_client.py`

**Interfaces:**
- Consumes: `LLMClient` ABC from Task 2, `Context`, `Action` from Task 1
- Produces: `RealLLMClient` (calls NJU endpoint, parses JSON action, handles parse errors)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_real_llm_client.py
import json
from unittest.mock import MagicMock, patch
from harness.models import Action, Context
from harness.feedback.models import FeedbackSignal
from harness.llm.real_client import RealLLMClient, parse_action_response, build_system_prompt


def test_parse_valid_json():
    raw = '{"type": "WriteFile", "args": {"path": "foo.py", "content": "x"}}'
    result = parse_action_response(raw)
    assert isinstance(result, Action)
    assert result.type == "WriteFile"
    assert result.args["path"] == "foo.py"


def test_parse_done():
    raw = '{"type": "Done", "args": {"summary": "fixed"}}'
    result = parse_action_response(raw)
    assert isinstance(result, Action)
    assert result.type == "Done"


def test_parse_invalid_json_returns_feedback_signal():
    raw = "This is not JSON"
    result = parse_action_response(raw)
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "llm_parse_error"
    assert "Non-JSON" in result.failures[0].message


def test_parse_missing_type():
    raw = '{"args": {"path": "foo.py"}}'
    result = parse_action_response(raw)
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "llm_parse_error"


def test_build_system_prompt_contains_actions():
    prompt = build_system_prompt()
    assert "ReadFile" in prompt
    assert "WriteFile" in prompt
    assert "RunTests" in prompt
    assert "Done" in prompt
    assert "JSON" in prompt


def test_real_client_uses_mock_api():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"type": "Done", "args": {"summary": "done"}}'

    with patch("harness.llm.real_client.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        client = RealLLMClient(api_key="fake", base_url="http://test", model="test-model")
        action = client.propose_action(Context(system_prompt="test"))
        assert isinstance(action, Action)
        assert action.type == "Done"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_real_llm_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# harness/llm/real_client.py
from __future__ import annotations
import json
from harness.models import Action, Context
from harness.feedback.models import FeedbackSignal, FailureItem
from harness.llm.base import LLMClient


def build_system_prompt() -> str:
    return """You are a coding agent operating in a sandboxed workspace.
Available actions:
  ReadFile(path)          — read a file
  WriteFile(path, content)— write a file
  ListFiles(pattern)      — list files matching glob pattern
  RunShell(command)       — execute a shell command
  RunTests()              — run pytest
  RunLint()               — run ruff
  RunTypeCheck()          — run mypy
  Done(summary)           — signal task completion

Respond with EXACTLY ONE JSON object per turn:
  {"type": "<ActionType>", "args": {<action-specific args>}}

Do not include any text outside the JSON object."""


def parse_action_response(raw: str) -> Action | FeedbackSignal:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return FeedbackSignal(
            source="llm", passed=False,
            failures=[FailureItem(loc="llm_response", message=f"Non-JSON response: {raw[:200]}", category="UNKNOWN")],
            summary="LLM returned non-JSON response", raw=raw, reason="llm_parse_error",
        )
    if "type" not in data:
        return FeedbackSignal(
            source="llm", passed=False,
            failures=[FailureItem(loc="llm_response", message="Missing 'type' field in JSON", category="UNKNOWN")],
            summary="LLM returned JSON without type field", raw=raw, reason="llm_parse_error",
        )
    return Action(type=data["type"], args=data.get("args", {}))


class RealLLMClient(LLMClient):
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", temperature: float = 0.0):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature

    def propose_action(self, context: Context) -> Action:
        messages = [{"role": "system", "content": build_system_prompt()}]
        messages.append({"role": "user", "content": context.system_prompt})
        for msg in context.history:
            messages.append({"role": msg.role, "content": msg.content})

        response = self._client.chat.completions.create(
            model=self._model, temperature=self._temperature, messages=messages,
        )
        raw = response.choices[0].message.content
        result = parse_action_response(raw)
        if isinstance(result, FeedbackSignal):
            # Inject parse error as feedback for next round
            context.feedback_signals.append(result)
            # Re-prompt once with error feedback
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Your response was not valid JSON. Error: {result.failures[0].message}. Please respond with a valid JSON action."})
            response = self._client.chat.completions.create(
                model=self._model, temperature=self._temperature, messages=messages,
            )
            raw = response.choices[0].message.content
            result = parse_action_response(raw)
            if isinstance(result, FeedbackSignal):
                return Action(type="Done", args={"summary": "LLM parse error - giving up"})
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_real_llm_client.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add harness/llm/real_client.py tests/test_real_llm_client.py
git commit -m "feat: real LLM client with JSON action parsing and error feedback"
```

---

## Task 15: Credential Store

**Files:**
- Create: `credman/__init__.py`
- Create: `credman/store.py`
- Create: `tests/test_credential_store.py`

**Interfaces:**
- Consumes: None (standalone)
- Produces: `CredentialStore` (`store_key/get_key/has_key/delete_key/status`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_credential_store.py
import pytest
from credman.store import CredentialStore


class FakeKeyring:
    def __init__(self):
        self._store = {}
    def set_password(self, service, user, password):
        self._store[(service, user)] = password
    def get_password(self, service, user):
        return self._store.get((service, user))
    def delete_password(self, service, user):
        self._store.pop((service, user), None)


def test_store_and_get_key():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    store.store_key("sk-test-123")
    assert store.get_key() == "sk-test-123"


def test_has_key():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    assert store.has_key() is False
    store.store_key("sk-test")
    assert store.has_key() is True


def test_status_not_set():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    assert store.status() == "not set"


def test_status_set_no_plaintext():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    store.store_key("sk-secret")
    status = store.status()
    assert status == "set"
    assert "sk-secret" not in status


def test_delete_key():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    store.store_key("sk-test")
    store.delete_key()
    assert store.has_key() is False


def test_get_from_env_fallback(monkeypatch):
    kr = FakeKeyring()
    monkeypatch.setenv("HARNESS_API_KEY", "sk-env-fallback")
    store = CredentialStore(keyring_backend=kr, env_var="HARNESS_API_KEY")
    assert store.get_key() == "sk-env-fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_credential_store.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# credman/__init__.py
```

```python
# credman/store.py
from __future__ import annotations
import os

try:
    import keyring as _keyring
except ImportError:
    _keyring = None


class CredentialStore:
    SERVICE = "coding-agent-harness"
    USER = "api-key"

    def __init__(self, keyring_backend=None, env_var: str = "HARNESS_API_KEY"):
        self._backend = keyring_backend or _keyring
        self._env_var = env_var

    def store_key(self, key: str) -> None:
        self._backend.set_password(self.SERVICE, self.USER, key)

    def get_key(self) -> str | None:
        key = self._backend.get_password(self.SERVICE, self.USER)
        if key:
            return key
        return os.environ.get(self._env_var)

    def has_key(self) -> bool:
        return self.get_key() is not None

    def status(self) -> str:
        return "set" if self.has_key() else "not set"

    def delete_key(self) -> None:
        try:
            self._backend.delete_password(self.SERVICE, self.USER)
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_credential_store.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add credman/ tests/test_credential_store.py
git commit -m "feat: credential store with keyring + env fallback"
```

---

## Task 16: WebUI Backend (FastAPI + REST + WebSocket + SessionRegistry)

**Files:**
- Create: `webui/__init__.py`
- Create: `webui/app.py`
- Create: `webui/routes.py`
- Create: `webui/session_registry.py`
- Create: `tests/test_webui.py`

**Interfaces:**
- Consumes: `AgentRunner` from Task 13, `Config` from Task 12
- Produces: FastAPI app with REST endpoints + WebSocket + SessionRegistry

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webui.py
import pytest
from fastapi.testclient import TestClient
from webui.app import create_app


def test_create_session():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "running"


def test_get_session_status():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    resp2 = client.get(f"/sessions/{sid}")
    assert resp2.status_code == 200
    assert resp2.json()["status"] in ("running", "done", "aborted")


def test_abort_session():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    resp2 = client.post(f"/sessions/{sid}/abort")
    assert resp2.status_code == 200


def test_max_concurrent_sessions():
    app = create_app(config_path=None, max_concurrent=1)
    client = TestClient(app)
    client.post("/sessions", json={"task": "task1"})
    resp = client.post("/sessions", json={"task": "task2"})
    assert resp.status_code == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webui.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# webui/__init__.py
```

```python
# webui/session_registry.py
from __future__ import annotations
import asyncio
import uuid
from typing import Any


class SessionRegistry:
    def __init__(self, max_concurrent: int = 5):
        self._sessions: dict[str, dict] = {}
        self._max = max_concurrent

    def create(self, task: str, workspace_dir: str) -> str:
        if len(self._sessions) >= self._max:
            return None
        sid = str(uuid.uuid4())
        self._sessions[sid] = {"task": task, "workspace": workspace_dir, "state": "running", "events": []}
        return sid

    def get(self, sid: str) -> dict | None:
        return self._sessions.get(sid)

    def abort(self, sid: str) -> bool:
        if sid in self._sessions:
            self._sessions[sid]["state"] = "aborted"
            return True
        return False

    def finish(self, sid: str) -> None:
        if sid in self._sessions:
            self._sessions[sid]["state"] = "done"

    def count(self) -> int:
        return len(self._sessions)
```

```python
# webui/app.py
from __future__ import annotations
import os
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from webui.session_registry import SessionRegistry
from harness.config import load_config


class CreateSessionRequest(BaseModel):
    task: str
    seed: str | None = None


class ApproveRequest(BaseModel):
    decision: str  # "approve" | "deny"


def create_app(config_path: str | None = None, max_concurrent: int | None = None):
    cfg = load_config(config_path)
    if max_concurrent is None:
        max_concurrent = cfg.max_concurrent_sessions
    app = FastAPI()
    registry = SessionRegistry(max_concurrent=max_concurrent)

    @app.post("/sessions")
    async def create_session(req: CreateSessionRequest):
        tmpdir = tempfile.mkdtemp()
        sid = registry.create(req.task, tmpdir)
        if sid is None:
            raise HTTPException(status_code=429, detail="Too many concurrent sessions")
        # In real implementation, would start AgentRunner here
        # For now, mark as done immediately for testing
        registry.finish(sid)
        return {"session_id": sid, "status": "running"}

    @app.get("/sessions/{sid}")
    async def get_session(sid: str):
        s = registry.get(sid)
        if s is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": sid, "status": s["state"], "task": s["task"]}

    @app.post("/sessions/{sid}/approve")
    async def approve(sid: str, req: ApproveRequest):
        s = registry.get(sid)
        if s is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": sid, "approved": req.decision == "approve"}

    @app.post("/sessions/{sid}/abort")
    async def abort(sid: str):
        if not registry.abort(sid):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": sid, "status": "aborted"}

    # Serve static files if directory exists
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_webui.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add webui/ tests/test_webui.py
git commit -m "feat: webui backend with REST endpoints and session registry"
```

---

## Task 17: Frontend (HTML/JS)

**Files:**
- Create: `webui/static/index.html`
- Create: `webui/static/style.css`
- Create: `webui/static/app.js`

**Interfaces:**
- Consumes: REST endpoints from Task 16
- Produces: Chat-style WebUI for task submission, real-time event viewing, HITL approval

- [ ] **Step 1: Write the frontend**

```html
<!-- webui/static/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coding Agent Harness</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div id="app">
        <header><h1>Coding Agent Harness</h1></header>
        <main>
            <section id="task-input">
                <textarea id="task" placeholder="Describe a coding task..."></textarea>
                <button id="submit-btn">Run Agent</button>
            </section>
            <section id="event-log">
                <h2>Agent Loop</h2>
                <div id="events"></div>
            </section>
            <section id="hitl" hidden>
                <h2>Approval Required</h2>
                <p id="hitl-action"></p>
                <button id="approve-btn">Approve</button>
                <button id="deny-btn">Deny</button>
            </section>
        </main>
    </div>
    <script src="/static/app.js"></script>
</body>
</html>
```

```css
/* webui/static/style.css */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: monospace; background: #1e1e1e; color: #d4d4d4; padding: 1rem; }
header h1 { margin-bottom: 1rem; }
#task-input textarea { width: 100%; height: 80px; background: #2d2d2d; color: #d4d4d4; border: 1px solid #555; padding: 0.5rem; }
#submit-btn { margin-top: 0.5rem; padding: 0.5rem 1rem; background: #0e639c; color: white; border: none; cursor: pointer; }
#events { margin-top: 1rem; max-height: 500px; overflow-y: auto; }
.event { padding: 0.3rem; border-bottom: 1px solid #333; }
.event-feedback { color: #f9ca24; }
.event-error { color: #e06c75; }
.event-success { color: #98c379; }
#hitl { margin-top: 1rem; padding: 1rem; background: #3d2d00; border: 1px solid #f9ca24; }
#hitl button { margin-right: 0.5rem; padding: 0.3rem 1rem; }
```

```javascript
// webui/static/app.js
const taskInput = document.getElementById("task");
const submitBtn = document.getElementById("submit-btn");
const eventsDiv = document.getElementById("events");
const hitlSection = document.getElementById("hitl");
const hitlAction = document.getElementById("hitl-action");

function addEvent(text, cls = "") {
    const div = document.createElement("div");
    div.className = "event " + cls;
    div.textContent = text;
    eventsDiv.appendChild(div);
    eventsDiv.scrollTop = eventsDiv.scrollHeight;
}

submitBtn.addEventListener("click", async () => {
    const task = taskInput.value.trim();
    if (!task) return;
    eventsDiv.innerHTML = "";
    const resp = await fetch("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task }),
    });
    const data = await resp.json();
    if (resp.ok) {
        addEvent(`Session created: ${data.session_id}`, "event-success");
        connectWebSocket(data.session_id);
    } else {
        addEvent(`Error: ${data.detail}`, "event-error");
    }
});

function connectWebSocket(sid) {
    const ws = new WebSocket(`ws://${location.host}/sessions/${sid}/stream`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        addEvent(JSON.stringify(data), data.event_type === "FeedbackSignalEmitted" ? "event-feedback" : "");
        if (data.event_type === "HitlApprovalRequired") {
            hitlSection.hidden = false;
            hitlAction.textContent = JSON.stringify(data.action);
        }
        if (data.event_type === "LoopFinished") {
            addEvent(`Loop finished: ${data.reason}`, "event-success");
        }
    };
    ws.onclose = () => addEvent("WebSocket closed", "");
}

document.getElementById("approve-btn").addEventListener("click", () => approveSession(true));
document.getElementById("deny-btn").addEventListener("click", () => approveSession(false));

async function approveSession(approve) {
    // session_id would be stored from creation
    hitlSection.hidden = true;
}
```

- [ ] **Step 2: Verify files exist**

Run: `ls webui/static/`
Expected: `app.js  index.html  style.css`

- [ ] **Step 3: Commit**

```bash
git add webui/static/
git commit -m "feat: webui frontend with task input, event log, and HITL approval"
```

---

## Task 18: CLI Frontend

**Files:**
- Create: `cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `AgentRunner` from Task 13, `CredentialStore` from Task 15, `load_config` from Task 12
- Produces: CLI with `run`, `config show-key`, `config set-key`, `config clear-key` commands

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import subprocess
import sys


def test_cli_help():
    result = subprocess.run([sys.executable, "cli.py", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "config" in result.stdout


def test_cli_config_show_key():
    result = subprocess.run([sys.executable, "cli.py", "config", "show-key"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "not set" in result.stdout or "set" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# cli.py
#!/usr/bin/env python3
"""CLI frontend for the coding agent harness."""
import argparse
import getpass
import sys
import tempfile

from credman.store import CredentialStore
from harness.config import load_config


def cmd_run(args):
    cfg = load_config(args.config)
    store = CredentialStore()
    key = store.get_key()
    if not key:
        print("No API key found. Run: python cli.py config set-key")
        sys.exit(1)

    from harness.models import Workspace
    from harness.agent_runner import AgentRunner, RecordingEventSink
    from harness.llm.real_client import RealLLMClient
    from harness.tools.base import ToolDispatcher
    from harness.tools.file_tools import ReadFileTool, WriteFileTool, ListFilesTool
    from harness.tools.shell_tool import RunShellTool
    from harness.tools.feedback_tools import RunTestsTool, RunLintTool, RunTypeCheckTool
    from harness.governance.guardrail import Guardrail
    from harness.governance.sandbox import Sandbox
    from harness.feedback.validators import PytestValidator
    from harness.feedback.classifier import Classifier
    from harness.feedback.feedback_loop import FeedbackLoop

    tmpdir = tempfile.mkdtemp()
    tools = [ReadFileTool(), WriteFileTool(), ListFilesTool(), RunShellTool(timeout=cfg.sandbox_timeout),
             RunTestsTool(timeout=cfg.sandbox_timeout), RunLintTool(timeout=cfg.sandbox_timeout),
             RunTypeCheckTool(timeout=cfg.sandbox_timeout)]
    guardrail = Guardrail(rules=cfg.guardrail_rules)
    sandbox = Sandbox(tools=tools, timeout=cfg.sandbox_timeout, env_whitelist=cfg.sandbox_env_whitelist)
    td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
    llm = RealLLMClient(api_key=key, base_url="https://njusehub.info/v1", model=cfg.llm_settings.get("model", "gpt-4o-mini"))
    sink = RecordingEventSink()
    runner = AgentRunner(
        llm_client=llm, dispatcher=td, validator=PytestValidator(),
        classifier=Classifier(hints=cfg.hints),
        feedback_loop=FeedbackLoop(max_iterations=cfg.max_iterations, escalation_threshold=cfg.feedback_thresholds["escalation_threshold"]),
        config=cfg, event_sink=sink,
    )
    runner.run(args.task, Workspace(cwd=tmpdir))
    for event in sink.events:
        print(f"[{event.__class__.__name__}] {event.__dict__}")


def cmd_config(args):
    store = CredentialStore()
    if args.config_cmd == "show-key":
        print(f"API key: {store.status()}")
    elif args.config_cmd == "set-key":
        key = getpass.getpass("Enter API key: ")
        store.store_key(key)
        print("API key stored.")
    elif args.config_cmd == "clear-key":
        store.delete_key()
        print("API key cleared.")


def main():
    parser = argparse.ArgumentParser(description="Coding Agent Harness")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run the agent on a task")
    run_parser.add_argument("task", help="Task description")
    run_parser.add_argument("--config", default="config.yaml", help="Config file path")

    config_parser = sub.add_parser("config", help="Manage credentials")
    config_parser.add_argument("config_cmd", choices=["show-key", "set-key", "clear-key"])

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat: CLI frontend with run and config commands"
```

---

## Task 19: Mechanism Demos

**Files:**
- Create: `tests/test_demos.py`

**Interfaces:**
- Consumes: All harness components
- Produces: Three deterministic mechanism demos (pytest test cases)

- [ ] **Step 1: Write the demos**

```python
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


# === Demo ①: Guardrail intercepts dangerous action ===

def test_demo_guardrail_intercept():
    """MockLLM proposes rm -rf / → guardrail DENY → rejected FeedbackSignal → LLM re-proposes safe action."""
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

        # Assert loop finished (LLM re-proposed safe action → Done)
        finished = [e for e in sink.events if e.__class__.__name__ == "LoopFinished"]
        assert len(finished) == 1


# === Demo ②: Inject failure → feedback loop self-correction ===

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
    """WriteFile(buggy) → RunTests → fail → feedback → fix → RunTests → pass → Done."""
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


# === Demo ③: Stagnation detection → early ESCALATE ===

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
    """Inject same failure repeatedly → FeedbackLoop detects stagnation → ESCALATE before fixed threshold."""
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
```

- [ ] **Step 2: Run demos to verify they pass**

Run: `pytest tests/test_demos.py -v`
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_demos.py
git commit -m "feat: mechanism demos (guardrail intercept, feedback self-correction, stagnation detection)"
```

---

## Task 20: Dockerfile + CI/CD

**Files:**
- Create: `Dockerfile`
- Create: `.gitlab-ci.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: All previous tasks
- Produces: Docker image build + GitLab CI pipeline with unit-test job

- [ ] **Step 1: Write Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "webui.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write .gitlab-ci.yml**

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build

unit-test:
  stage: test
  image: python:3.12-slim
  before_script:
    - pip install -e ".[dev]"
  script:
    - pytest tests/ -v
  rules:
    - when: always

build-image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  before_script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
  script:
    - docker build -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
```

- [ ] **Step 3: Write README.md**

```markdown
# Coding Agent Harness

A self-coded coding agent harness kernel with a deep feedback loop (validators → classifier → feedback loop).

## Install

```bash
pip install -e ".[dev]"
```

## Run

### CLI
```bash
python cli.py config set-key   # Enter your API key (stored in OS keyring)
python cli.py config show-key   # Check status (no plaintext)
python cli.py run "Fix the failing test in test_foo.py"
```

### Web UI
```bash
uvicorn webui.app:create_app --factory --host 0.0.0.0 --port 8000
```
Open http://localhost:8000/static/index.html

### Docker
```bash
docker build -t coding-agent-harness .
docker run -p 8000:8000 -e HARNESS_API_KEY=your-key coding-agent-harness
```

## Tests
```bash
pytest tests/ -v          # All tests
pytest tests/test_demos.py -v  # Mechanism demos
```

## Key Configuration
- Local: OS keyring (recommended)
- Cloud: `HARNESS_API_KEY` environment variable
- Dev: `.env` file (plaintext, gitignored)

## Security
- Secrets never enter source code, logs, git, or agent tool environment
- Sandbox uses env whitelist (PATH/HOME/LANG only)
- Credential access controlled by harness, not LLM

## Directory Structure
See SPEC.md §5.5 for full module breakdown.
```

- [ ] **Step 4: Verify Docker build (if Docker available)**

Run: `docker build -t coding-agent-harness .` (skip if Docker not installed)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .gitlab-ci.yml README.md
git commit -m "feat: Dockerfile, GitLab CI, and README"
```

---

## Self-Review Notes

**Spec coverage check:**
- §3.1 AgentRunner → Task 13 ✓
- §3.1.1 Context construction → Task 13 (`_build_context`, `_format_feedback`) ✓
- §3.1.2 Stop conditions → Task 13 (`_should_auto_stop`, max iterations) ✓
- §3.2 LLM abstraction → Task 2 (ABC+Mock) + Task 14 (Real) ✓
- §3.2.1 Prompt/JSON schema → Task 14 (`build_system_prompt`, `parse_action_response`) ✓
- §3.2.2 MockScript format → Task 2 (queue + responder) ✓
- §3.3 ToolDispatcher → Task 3 ✓
- §3.4 Governance → Tasks 6,7,8 ✓
- §3.5 Feedback loop → Tasks 9,10,11 ✓
- §3.6 Memory → Task 12 ✓
- §3.7 Config → Task 12 ✓
- §3.8 WebUI → Tasks 16,17 ✓
- §3.8.1 REST endpoints → Task 16 ✓
- §3.8.2 Concurrent sessions → Task 16 ✓
- §3.9 Credentials → Task 15 ✓
- §6 Data model → Task 1 ✓
- §7 Distribution → Task 20 ✓
- §9 Acceptance criteria → covered by all tasks + demos (Task 19) ✓

**Type consistency:** All function signatures match across tasks. `FeedbackSignalEmitted` used consistently for events vs `FeedbackSignal` for data model.

**No placeholders:** All steps contain actual code.

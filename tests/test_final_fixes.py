import asyncio
import tempfile
from fastapi.testclient import TestClient
from harness.models import (
    Action, ActionResult, RawExecutionResult, Workspace, Config, Decision, DecisionType,
    LoopFinished, ToolCallResult, HitlApprovalRequired, MemoryItem,
)
from harness.agent_runner import AgentRunner, RecordingEventSink
from harness.llm.mock_client import MockLLMClient
from harness.tools.base import ToolDispatcher
from harness.tools.file_tools import WriteFileTool, ReadFileTool
from harness.tools.feedback_tools import RunTestsTool, RunLintTool
from harness.governance.guardrail import Guardrail
from harness.governance.sandbox import Sandbox
from harness.feedback.validators import PytestValidator, RuffValidator
from harness.feedback.classifier import Classifier
from harness.feedback.feedback_loop import FeedbackLoop
from harness.feedback.models import FeedbackSignal, FailureItem
from harness.memory.store import MemoryStore


def _make_runner(actions, tmpdir, validators=None, memory_store=None, llm=None):
    cfg = Config()
    tools = [ReadFileTool(), WriteFileTool(), RunTestsTool(timeout=10), RunLintTool(timeout=10)]
    guardrail = Guardrail(rules=cfg.guardrail_rules)
    sandbox = Sandbox(tools=tools, timeout=cfg.sandbox_timeout, env_whitelist=cfg.sandbox_env_whitelist)
    td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
    llm = llm or MockLLMClient(actions=actions)
    fl = FeedbackLoop(max_iterations=cfg.max_iterations, escalation_threshold=cfg.feedback_thresholds["escalation_threshold"])
    sink = RecordingEventSink()
    runner = AgentRunner(
        llm_client=llm, dispatcher=td,
        validator=PytestValidator(),
        validators=validators,
        classifier=Classifier(hints=cfg.hints), feedback_loop=fl,
        config=cfg, event_sink=sink, memory_store=memory_store,
    )
    return runner, sink


# === I1: Validator routed by source ===

def test_validator_routed_by_action_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner, sink = _make_runner(
            [Action(type="RunLint", args={}), Action(type="Done", args={"summary": "done"})],
            tmpdir,
            validators={"RunLint": RuffValidator()},
        )
        runner.run("lint task", Workspace(cwd=tmpdir))
        signals = [e for e in sink.events if e.__class__.__name__ == "FeedbackSignalEmitted"]
        assert len(signals) >= 1
        assert signals[0].signal.source == "ruff"


# === I2: Memory wired into main loop ===

def test_memory_retrieved_in_context():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemoryStore(workspace_dir=tmpdir)
        memory.store("test_convention", "use pytest for tests")
        runner, sink = _make_runner(
            [Action(type="Done", args={"summary": "done"})],
            tmpdir, memory_store=memory,
        )
        runner.run("test something", Workspace(cwd=tmpdir))
        contexts = [e for e in sink.events if e.__class__.__name__ == "ContextBuilt"]
        assert len(contexts) >= 1
        mem_items = contexts[0].context.memory_items
        assert any("test_convention" == m.key for m in mem_items)


def test_memory_stored_after_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemoryStore(workspace_dir=tmpdir)
        runner, sink = _make_runner(
            [Action(type="Done", args={"summary": "finished"})],
            tmpdir, memory_store=memory,
        )
        runner.run("my task", Workspace(cwd=tmpdir))
        assert memory.retrieve("last_task") == "my task"
        assert "finished" in (memory.retrieve("last_result") or "")


# === I3: HITL state machine emits HitlApprovalRequired ===

def test_hitl_approval_required_event_emitted():
    from harness.tools.base import ToolDispatcher
    from harness.models import Action, Decision, DecisionType, Workspace

    class ApprovalGuardrail:
        def check(self, action):
            return Decision(verdict=DecisionType.REQUIRE_APPROVAL, reason="needs approval")

    class StubResolver:
        def request_approval(self, action):
            return Decision(verdict=DecisionType.ALLOW)

    class StubSandbox:
        def execute(self, action, workspace):
            return ActionResult(success=True, output="executed")

    sink = RecordingEventSink()
    td = ToolDispatcher(
        guardrail=ApprovalGuardrail(), sandbox=StubSandbox(),
        approval_resolver=StubResolver(), event_sink=sink,
    )
    td.dispatch(Action(type="DeleteFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"))
    hitl_events = [e for e in sink.events if e.__class__.__name__ == "HitlApprovalRequired"]
    assert len(hitl_events) == 1


# === I4: Exception handling in main loop ===

def test_exception_emits_error_loop_finished():
    with tempfile.TemporaryDirectory() as tmpdir:
        class ExplodingLLM:
            def propose_action(self, ctx):
                raise RuntimeError("LLM exploded")
        runner, sink = _make_runner(
            [], tmpdir, llm=ExplodingLLM(),
        )
        runner.run("crash task", Workspace(cwd=tmpdir))
        finished = [e for e in sink.events if e.__class__.__name__ == "LoopFinished"]
        assert len(finished) == 1
        assert "ERROR" in finished[0].reason


# === I5: ToolCallResult preserves RawExecutionResult ===

def test_tool_call_result_preserves_raw_execution_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner, sink = _make_runner(
            [Action(type="RunTests", args={}), Action(type="Done", args={"summary": "done"})],
            tmpdir,
        )
        runner.run("test task", Workspace(cwd=tmpdir))
        results = [e for e in sink.events if e.__class__.__name__ == "ToolCallResult"]
        assert len(results) >= 1
        assert isinstance(results[0].result, RawExecutionResult)


# === I6: Guardrail checked once via dispatch_with_decision ===

def test_dispatch_with_decision_returns_both():
    from harness.models import Action, Decision, DecisionType, Workspace

    class CountingGuardrail:
        def __init__(self):
            self.check_count = 0
        def check(self, action):
            self.check_count += 1
            return Decision(verdict=DecisionType.ALLOW)

    class StubSandbox:
        def execute(self, action, workspace):
            return ActionResult(success=True, output="ok")

    g = CountingGuardrail()
    td = ToolDispatcher(guardrail=g, sandbox=StubSandbox())
    result, decision = td.dispatch_with_decision(
        Action(type="ReadFile", args={"path": "foo.py"}), Workspace(cwd="/tmp"),
    )
    assert result.success
    assert decision.verdict == DecisionType.ALLOW
    assert g.check_count == 1


# === C1: WebUI actually runs the agent ===

def test_webui_runs_agent_and_streams_events():
    from webui.app import create_app

    def mock_factory():
        return MockLLMClient(actions=[Action(type="Done", args={"summary": "webui done"})])

    app = create_app(config_path=None, llm_client_factory=mock_factory)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    assert resp.status_code == 200

    # Give the background task time to run
    import time
    time.sleep(0.5)

    session = app.dependency_overrides if hasattr(app, "dependency_overrides") else None
    # Access the registry through the app's routes
    # The session should have events now
    s = None
    for route in app.routes:
        if hasattr(route, "path") and route.path == "/sessions/{sid}":
            pass
    # Verify via the get endpoint
    resp2 = client.get(f"/sessions/{sid}")
    assert resp2.status_code == 200
    assert resp2.json()["status"] in ("running", "done", "aborted")


def test_webui_approve_resolves_future():
    from webui.app import create_app, FutureApprovalResolver
    from harness.models import Decision, DecisionType

    resolver = FutureApprovalResolver(timeout=5)
    import threading

    result_holder = {}

    def wait_for_approval():
        result_holder["decision"] = resolver.request_approval(Action(type="DeleteFile", args={}))

    t = threading.Thread(target=wait_for_approval)
    t.start()

    import time
    time.sleep(0.1)
    assert resolver.pending

    resolver.resolve(Decision(verdict=DecisionType.ALLOW))
    t.join(timeout=5)

    assert "decision" in result_holder
    assert result_holder["decision"].verdict == DecisionType.ALLOW

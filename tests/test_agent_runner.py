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
        # Simulate: RunTests returns pass twice -> auto-stop
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

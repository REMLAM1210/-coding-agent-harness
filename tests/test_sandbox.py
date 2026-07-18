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

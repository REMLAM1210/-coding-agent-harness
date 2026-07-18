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

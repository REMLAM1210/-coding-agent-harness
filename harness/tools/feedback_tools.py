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

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

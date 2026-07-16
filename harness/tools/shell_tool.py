from __future__ import annotations
import os
import shutil
import subprocess
from harness.models import Action, Workspace, RawExecutionResult
from harness.tools.base import Tool


def _find_shell() -> str | None:
    """Locate a POSIX shell so $VAR expansion and coreutils (sleep) work cross-platform.

    On POSIX, /bin/sh is always available. On Windows, prefer Git-Bash if present.
    Returns None to fall back to the platform default (shell=True).
    """
    for name in ("bash", "sh"):
        path = shutil.which(name)
        if path:
            return path
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\sh.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


class RunShellTool(Tool):
    def __init__(self, timeout: int = 30, env_whitelist: list[str] | None = None):
        self._timeout = timeout
        self._env_whitelist = env_whitelist or ["PATH", "HOME", "LANG"]
        self._shell = _find_shell()

    def can_handle(self, action: Action) -> bool:
        return action.type == "RunShell"

    def _build_env(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k in self._env_whitelist}

    def execute(self, action: Action, workspace: Workspace) -> RawExecutionResult:
        cmd = action.args["command"]
        try:
            if self._shell is not None:
                proc = subprocess.run(
                    [self._shell, "-c", cmd], cwd=workspace.cwd,
                    capture_output=True, text=True,
                    timeout=self._timeout, env=self._build_env(),
                )
            else:
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
                exit_code=-1, stdout="", stderr=f"Command timeout after {self._timeout}s",
            )

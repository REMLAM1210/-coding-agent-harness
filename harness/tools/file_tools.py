from __future__ import annotations
import os
import glob
from harness.models import Action, ActionResult, Workspace
from harness.tools.base import Tool


def _resolve_safe(path: str, cwd: str) -> str | None:
    full = os.path.normpath(os.path.join(cwd, path))
    norm_cwd = os.path.normpath(cwd)
    try:
        if os.path.commonpath([full, norm_cwd]) != norm_cwd:
            return None
    except ValueError:
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
        safe_files = []
        for m in matches:
            if not os.path.isfile(m):
                continue
            full = _resolve_safe(os.path.relpath(m, workspace.cwd), workspace.cwd)
            if full is None:
                continue
            safe_files.append(os.path.relpath(m, workspace.cwd))
        files = sorted(safe_files)
        return ActionResult(success=True, output="\n".join(files))

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

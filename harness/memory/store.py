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

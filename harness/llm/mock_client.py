from __future__ import annotations
from collections import deque
from typing import Callable
from harness.models import Action, Context
from harness.llm.base import LLMClient


class MockExhaustedError(Exception):
    pass


class MockLLMClient(LLMClient):
    def __init__(
        self,
        actions: list[Action] | None = None,
        responder: Callable[[Context], Action] | None = None,
    ):
        self._queue = deque(actions) if actions else deque()
        self._responder = responder

    def propose_action(self, context: Context) -> Action:
        if self._responder is not None:
            return self._responder(context)
        if not self._queue:
            raise MockExhaustedError("MockExhausted: action queue exhausted")
        return self._queue.popleft()

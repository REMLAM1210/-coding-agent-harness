from __future__ import annotations
from abc import ABC, abstractmethod
from harness.models import Action, Context


class LLMClient(ABC):
    @abstractmethod
    def propose_action(self, context: Context) -> Action:
        ...

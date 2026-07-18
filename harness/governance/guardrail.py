from __future__ import annotations
import re
from harness.models import Action, Decision, DecisionType, GuardrailRule


class Guardrail:
    def __init__(self, rules: list[GuardrailRule] | None = None):
        self._rules = rules or []

    def check(self, action: Action) -> Decision:
        for rule in self._rules:
            if rule.action_type != action.type:
                continue
            target = action.args.get("command") or action.args.get("path") or ""
            if re.search(rule.pattern, target):
                return Decision(verdict=rule.verdict, reason=rule.reason)
        return Decision(verdict=DecisionType.ALLOW)

from __future__ import annotations
import os
import yaml
from harness.models import Config, GuardrailRule, DecisionType


def load_config(path: str | None = None) -> Config:
    cfg = Config()
    if path and os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if "max_iterations" in data:
            cfg.max_iterations = data["max_iterations"]
        if "sandbox_timeout" in data:
            cfg.sandbox_timeout = data["sandbox_timeout"]
        if "hitl_timeout" in data:
            cfg.hitl_timeout = data["hitl_timeout"]
        if "max_concurrent_sessions" in data:
            cfg.max_concurrent_sessions = data["max_concurrent_sessions"]
        if "guardrail_rules" in data:
            cfg.guardrail_rules = [
                GuardrailRule(
                    name=r["name"], pattern=r["pattern"],
                    action_type=r["action_type"],
                    verdict=DecisionType(r["verdict"]),
                    reason=r.get("reason", ""),
                ) for r in data["guardrail_rules"]
            ]
        if "feedback_thresholds" in data:
            cfg.feedback_thresholds = data["feedback_thresholds"]
        if "llm_settings" in data:
            cfg.llm_settings = data["llm_settings"]
        if "hints" in data:
            cfg.hints = data["hints"]
    return cfg

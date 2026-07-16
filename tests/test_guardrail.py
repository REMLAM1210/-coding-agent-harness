from harness.models import Action, DecisionType, GuardrailRule
from harness.governance.guardrail import Guardrail


def test_block_rm_rf():
    rules = [GuardrailRule(name="block_rm_rf", pattern=r"rm\s+-rf", action_type="RunShell", verdict=DecisionType.DENY, reason="destructive")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "rm -rf /"}))
    assert d.verdict == DecisionType.DENY
    assert d.reason == "destructive"


def test_block_git_push_force():
    rules = [GuardrailRule(name="block_force_push", pattern=r"git\s+push.*--force", action_type="RunShell", verdict=DecisionType.DENY, reason="force push")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "git push --force origin main"}))
    assert d.verdict == DecisionType.DENY


def test_allow_safe_command():
    rules = [GuardrailRule(name="block_rm_rf", pattern=r"rm\s+-rf", action_type="RunShell", verdict=DecisionType.DENY, reason="destructive")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "echo hello"}))
    assert d.verdict == DecisionType.ALLOW


def test_require_approval_for_pip_install():
    rules = [GuardrailRule(name="approve_pip", pattern=r"pip\s+install", action_type="RunShell", verdict=DecisionType.REQUIRE_APPROVAL, reason="network install")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="RunShell", args={"command": "pip install requests"}))
    assert d.verdict == DecisionType.REQUIRE_APPROVAL


def test_allow_readfile():
    rules = []
    g = Guardrail(rules=rules)
    d = g.check(Action(type="ReadFile", args={"path": "foo.py"}))
    assert d.verdict == DecisionType.ALLOW


def test_path_traversal_in_writefile():
    rules = [GuardrailRule(name="block_traversal", pattern=r"\.\.", action_type="WriteFile", verdict=DecisionType.DENY, reason="path traversal")]
    g = Guardrail(rules=rules)
    d = g.check(Action(type="WriteFile", args={"path": "../../../etc/passwd", "content": "x"}))
    assert d.verdict == DecisionType.DENY

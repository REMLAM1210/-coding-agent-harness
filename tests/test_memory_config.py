import tempfile
import os
from harness.memory.store import MemoryStore
from harness.config import load_config
from harness.models import Config, DecisionType


def test_memory_store_retrieve():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(workspace_dir=tmpdir)
        store.store("convention", "use pytest")
        assert store.retrieve("convention") == "use pytest"


def test_memory_store_list_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(workspace_dir=tmpdir)
        store.store("a", "1")
        store.store("b", "2")
        keys = store.list_keys()
        assert set(keys) == {"a", "b"}


def test_memory_store_missing_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(workspace_dir=tmpdir)
        assert store.retrieve("nonexistent") is None


def test_memory_store_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store1 = MemoryStore(workspace_dir=tmpdir)
        store1.store("key", "value")
        store2 = MemoryStore(workspace_dir=tmpdir)
        assert store2.retrieve("key") == "value"


def test_load_config_defaults():
    cfg = load_config("nonexistent.yaml")
    assert cfg.max_iterations == 20
    assert cfg.sandbox_timeout == 30


def test_load_config_from_yaml():
    import yaml
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({
            "max_iterations": 10,
            "sandbox_timeout": 60,
            "guardrail_rules": [
                {"name": "block_rm", "pattern": r"rm\s+-rf", "action_type": "RunShell", "verdict": "DENY", "reason": "destructive"},
            ],
            "hints": {"ASSERTION_FAILURE": "check logic"},
        }, f)
        path = f.name
    cfg = load_config(path)
    assert cfg.max_iterations == 10
    assert cfg.sandbox_timeout == 60
    assert len(cfg.guardrail_rules) == 1
    assert cfg.guardrail_rules[0].verdict == DecisionType.DENY
    assert cfg.hints["ASSERTION_FAILURE"] == "check logic"
    os.unlink(path)

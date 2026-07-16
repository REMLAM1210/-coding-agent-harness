import pytest
import credman.store
from credman.store import CredentialStore


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, user, password):
        self._store[(service, user)] = password

    def get_password(self, service, user):
        return self._store.get((service, user))

    def delete_password(self, service, user):
        self._store.pop((service, user), None)


def test_store_and_get_key():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    store.store_key("sk-test-123")
    assert store.get_key() == "sk-test-123"


def test_has_key():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    assert store.has_key() is False
    store.store_key("sk-test")
    assert store.has_key() is True


def test_status_not_set():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    assert store.status() == "not set"


def test_status_set_no_plaintext():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    store.store_key("sk-secret")
    status = store.status()
    assert status == "set"
    assert "sk-secret" not in status


def test_delete_key():
    kr = FakeKeyring()
    store = CredentialStore(keyring_backend=kr)
    store.store_key("sk-test")
    store.delete_key()
    assert store.has_key() is False


def test_get_from_env_fallback(monkeypatch):
    kr = FakeKeyring()
    monkeypatch.setenv("HARNESS_API_KEY", "sk-env-fallback")
    store = CredentialStore(keyring_backend=kr, env_var="HARNESS_API_KEY")
    assert store.get_key() == "sk-env-fallback"


# --- Issue 1: None-backend must not crash ---

def test_none_backend_get_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(credman.store, "_keyring", None)
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    monkeypatch.setenv("HARNESS_API_KEY", "sk-env-none-backend")
    store = CredentialStore(env_var="HARNESS_API_KEY", dotenv_path="nonexistent.env")
    assert store.get_key() == "sk-env-none-backend"


def test_none_backend_status_not_set(monkeypatch):
    monkeypatch.setattr(credman.store, "_keyring", None)
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    store = CredentialStore(env_var="HARNESS_API_KEY", dotenv_path="nonexistent.env")
    assert store.status() == "not set"
    assert store.has_key() is False


def test_none_backend_store_key_raises(monkeypatch):
    monkeypatch.setattr(credman.store, "_keyring", None)
    store = CredentialStore(dotenv_path="nonexistent.env")
    with pytest.raises(RuntimeError):
        store.store_key("sk-test")


def test_none_backend_delete_key_no_crash(monkeypatch):
    monkeypatch.setattr(credman.store, "_keyring", None)
    store = CredentialStore(dotenv_path="nonexistent.env")
    store.delete_key()  # must not raise


# --- Issue 2: .env file fallback ---

def test_get_from_dotenv_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-dotenv-fallback\n", encoding="utf-8")
    kr = FakeKeyring()
    store = CredentialStore(
        keyring_backend=kr, env_var="HARNESS_API_KEY", dotenv_path=str(env_file)
    )
    assert store.get_key() == "sk-dotenv-fallback"


def test_dotenv_fallback_when_backend_none(tmp_path, monkeypatch):
    monkeypatch.setattr(credman.store, "_keyring", None)
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-dotenv-none\n", encoding="utf-8")
    store = CredentialStore(env_var="HARNESS_API_KEY", dotenv_path=str(env_file))
    assert store.get_key() == "sk-dotenv-none"


def test_dotenv_warning_printed(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-warn\n", encoding="utf-8")
    kr = FakeKeyring()
    store = CredentialStore(
        keyring_backend=kr, env_var="HARNESS_API_KEY", dotenv_path=str(env_file)
    )
    assert store.get_key() == "sk-warn"
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert ".env" in captured.err
    assert "insecure" in captured.err


def test_dotenv_parsing_comments_quotes_and_other_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# a comment\n'
        'OTHER_KEY=ignore-me\n'
        '\n'
        'HARNESS_API_KEY="sk-quoted"\n',
        encoding="utf-8",
    )
    kr = FakeKeyring()
    store = CredentialStore(
        keyring_backend=kr, env_var="HARNESS_API_KEY", dotenv_path=str(env_file)
    )
    assert store.get_key() == "sk-quoted"


def test_dotenv_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_API_KEY", raising=False)
    kr = FakeKeyring()
    store = CredentialStore(
        keyring_backend=kr, env_var="HARNESS_API_KEY", dotenv_path=str(tmp_path / ".env")
    )
    assert store.get_key() is None
    assert store.status() == "not set"


def test_priority_keyring_beats_env_and_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_API_KEY", "sk-env")
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-dotenv\n", encoding="utf-8")
    kr = FakeKeyring()
    store = CredentialStore(
        keyring_backend=kr, env_var="HARNESS_API_KEY", dotenv_path=str(env_file)
    )
    store.store_key("sk-keyring")
    assert store.get_key() == "sk-keyring"


def test_priority_env_beats_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_API_KEY", "sk-env")
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-dotenv\n", encoding="utf-8")
    kr = FakeKeyring()
    store = CredentialStore(
        keyring_backend=kr, env_var="HARNESS_API_KEY", dotenv_path=str(env_file)
    )
    assert store.get_key() == "sk-env"

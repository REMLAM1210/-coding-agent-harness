import pytest
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

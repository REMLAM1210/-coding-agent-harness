from __future__ import annotations
import os

try:
    import keyring as _keyring
except ImportError:
    _keyring = None


class CredentialStore:
    SERVICE = "coding-agent-harness"
    USER = "api-key"

    def __init__(self, keyring_backend=None, env_var: str = "HARNESS_API_KEY"):
        self._backend = keyring_backend or _keyring
        self._env_var = env_var

    def store_key(self, key: str) -> None:
        self._backend.set_password(self.SERVICE, self.USER, key)

    def get_key(self) -> str | None:
        key = self._backend.get_password(self.SERVICE, self.USER)
        if key:
            return key
        return os.environ.get(self._env_var)

    def has_key(self) -> bool:
        return self.get_key() is not None

    def status(self) -> str:
        return "set" if self.has_key() else "not set"

    def delete_key(self) -> None:
        try:
            self._backend.delete_password(self.SERVICE, self.USER)
        except Exception:
            pass

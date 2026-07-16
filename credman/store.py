from __future__ import annotations
import os
import sys

try:
    import keyring as _keyring
except ImportError:
    _keyring = None


class CredentialStore:
    SERVICE = "coding-agent-harness"
    USER = "api-key"

    def __init__(
        self,
        keyring_backend=None,
        env_var: str = "HARNESS_API_KEY",
        dotenv_path: str = ".env",
    ):
        self._backend = keyring_backend or _keyring
        self._env_var = env_var
        self._dotenv_path = dotenv_path

    def store_key(self, key: str) -> None:
        if self._backend is None:
            raise RuntimeError(
                "No keyring backend available; cannot store key. "
                "Set the key via the %s env var or a .env file instead."
                % self._env_var
            )
        self._backend.set_password(self.SERVICE, self.USER, key)

    def get_key(self) -> str | None:
        # Priority 1: keyring
        if self._backend is not None:
            key = self._backend.get_password(self.SERVICE, self.USER)
            if key:
                return key
        # Priority 2: env var
        key = os.environ.get(self._env_var)
        if key:
            return key
        # Priority 3: .env file (dev only, plaintext)
        return self._load_from_dotenv()

    def _load_from_dotenv(self) -> str | None:
        if not os.path.exists(self._dotenv_path):
            return None
        try:
            with open(self._dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    name, _, value = line.partition("=")
                    name = name.strip()
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                        value = value[1:-1]
                    if name == self._env_var:
                        print(
                            "WARNING: Loading API key from .env file (plaintext). "
                            "This is insecure for production use.",
                            file=sys.stderr,
                        )
                        return value
        except OSError:
            pass
        return None

    def has_key(self) -> bool:
        return self.get_key() is not None

    def status(self) -> str:
        return "set" if self.has_key() else "not set"

    def delete_key(self) -> None:
        if self._backend is None:
            return
        try:
            self._backend.delete_password(self.SERVICE, self.USER)
        except Exception:
            pass

"""Secrets adapter: a .env file plus the process environment.

.env is gitignored and never leaves this machine. At handoff the OS keyring adapter goes
here beside this one and nothing else changes.
"""

from __future__ import annotations

import os
from pathlib import Path

from ports.secrets import Secret
from registries.errors import MISSING_CREDENTIAL, RegistryError, diagnose

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


def _parse(text: str) -> dict[str, str]:
    from ports import env_file_values  # noqa: PLC0415 - the one parser

    return env_file_values(text)


class DotenvSecrets:
    """Reads .env, with the real environment taking precedence.

    That order matters: a value exported in the shell or injected by a container is a
    deliberate override, and a file on disk should not silently win over it.
    """

    name = "dotenv"

    def __init__(self, env_file: Path | str | None = None) -> None:
        self.env_file = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
        self._file_values = (
            _parse(self.env_file.read_text(encoding="utf-8")) if self.env_file.is_file() else {}
        )

    def __repr__(self) -> str:
        # The file path, never a value and never a count that hints at contents.
        return f"DotenvSecrets(env_file={self.env_file.name})"

    def has(self, key: str) -> bool:
        return bool(self._raw(key))

    def get(self, key: str) -> Secret:
        value = self._raw(key)
        if not value:
            raise RegistryError(
                diagnose(MISSING_CREDENTIAL, f"{key} is not set", locator=self.env_file.name)
            )
        return Secret(value)

    def names(self) -> tuple[str, ...]:
        from_env = {k for k in os.environ if k.startswith("AA_") or k.startswith("ANTHROPIC_")}
        return tuple(sorted(set(self._file_values) | from_env))

    def _raw(self, key: str) -> str:
        return os.environ.get(key) or self._file_values.get(key, "")


def build() -> DotenvSecrets:
    return DotenvSecrets()

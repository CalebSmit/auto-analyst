"""Where a refresh token lives between sessions.

ShareFile's refresh token is the one credential in this system that the system itself
produces. Everything else in `.env` was put there by a person and stays put; this one
arrives from a login, may be replaced by ShareFile at any refresh, and is worth exactly as
much as the password that created it. So it needs somewhere to live that is not `.env`,
not `knowledge/`, and not anywhere `git add -A` could reach.

**Encrypted, under a key derived from the one already there.** `AA_VAULT_KEY` exists for
the mask vault. Deriving a second key from it rather than asking for a second key is a
deliberate trade: one more secret to generate is one more secret to lose, and losing this
one only costs a re-login while losing the vault key costs every token it protects. The
derivation is domain-separated, so the bytes that encrypt a refresh token are not the
bytes that encrypt a client's name - the same practice `privacy/vault.py` already follows
for its HMAC key.

That is not a claim of strong separation. Anyone who can read `.env` on this machine can
derive this key, and the honest statement of what the encryption buys is: a refresh token
does not sit in plaintext in a file that a backup, a sync client or a support person could
copy without noticing. The trust boundary is the machine, and it always was.

**Written where the repo cannot commit it.** `vault/` is already in `.gitignore`, which
makes it the safest place available - a new directory would need a new ignore rule, and a
new ignore rule is a thing somebody can forget while the file is already written.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from registries.errors import (
    CREDENTIAL_REFUSED,
    MISSING_CREDENTIAL,
    RegistryError,
    diagnose,
)

__all__ = ["NEVER", "PRESENT", "PATH_VAR", "StoredToken", "TokenStore"]

KEY_NAME = "AA_VAULT_KEY"
PATH_VAR = "AA_TOKEN_STORE"
DEFAULT_PATH = "vault/refresh-tokens.enc"
DOMAIN = b"automated-analyst/refresh-token/v1"
"""Domain separation. The key that encrypts a refresh token is derived from the vault key
and is not the vault key, so a token file and a vault entry are never encrypted with the
same bytes even though they come from the same secret."""

NEVER = "never"
"""Nobody has signed in. Not an error - it is the state of a machine on day one, and a
report that called it a failure would be read as something being broken."""

PRESENT = "present"


@dataclass(frozen=True)
class StoredToken:
    """What a completed login leaves behind."""

    service: str
    refresh_token: str
    subdomain: str
    obtained_at: str
    """When the login happened, ISO 8601. Shown to a person so "I signed in ages ago" has
    a date attached, and never used to decide whether the token is still good - only
    ShareFile knows that, and guessing from a date is how a working token gets thrown
    away."""

    def __repr__(self) -> str:
        # The whole point. This object ends up in tracebacks and log lines.
        return (
            f"StoredToken(service={self.service!r}, subdomain={self.subdomain!r}, "
            f"obtained_at={self.obtained_at!r}, refresh_token=<redacted>)"
        )


class TokenStore:
    """Read, write and forget one service's refresh token."""

    def __init__(self, secrets: Any, path: Path | str | None = None) -> None:
        self._secrets = secrets
        self.path = Path(path or os.environ.get(PATH_VAR) or DEFAULT_PATH)

    def __repr__(self) -> str:
        return f"TokenStore(path={str(self.path)!r})"

    def state(self, service: str) -> str:
        """`never` or `present`. Asked without decrypting anything it does not need to."""
        return PRESENT if self.read(service) is not None else NEVER

    def read(self, service: str) -> StoredToken | None:
        if not self.path.exists():
            return None
        held = self._all()
        found = held.get(service)
        return StoredToken(**found) if found else None

    def write(self, token: StoredToken) -> None:
        """Store it, replacing whatever was there for that service.

        Replacing rather than appending is the whole reason this method exists: ShareFile
        rotates the refresh token on some refreshes, and a store that kept the old one
        would hand back a token that has already been spent - a login that works once and
        then does not, which reads as an intermittent fault.
        """
        held = self._all()
        held[token.service] = {
            "service": token.service,
            "refresh_token": token.refresh_token,
            "subdomain": token.subdomain,
            "obtained_at": token.obtained_at,
        }
        self._put(held)

    def forget(self, service: str) -> bool:
        """Drop it. True if there was one.

        Needed because a token can be revoked at the other end, and a person who knows
        that should be able to say so rather than waiting for a confusing refusal.
        """
        held = self._all()
        if service not in held:
            return False
        del held[service]
        self._put(held)
        return True

    # ------------------------------------------------------------------ the file

    def _all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        raw = self.path.read_bytes()
        if not raw:
            return {}
        try:
            body = self._fernet().decrypt(raw)
        except InvalidToken as bad:
            # The key changed, or the file did. Either way this is not something to
            # recover from by guessing: refusing sends a person to sign in again, which
            # is a minute, rather than leaving a run reading a token that is not there.
            raise RegistryError(
                diagnose(
                    CREDENTIAL_REFUSED,
                    f"{self.path} cannot be decrypted with the current {KEY_NAME}. If the "
                    f"key was regenerated, delete the file and sign in again - the tokens "
                    f"in it are unrecoverable and were only ever a convenience.",
                    locator=str(self.path),
                )
            ) from bad
        loaded = json.loads(body)
        return dict(loaded) if isinstance(loaded, dict) else {}

    def _put(self, held: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = self._fernet().encrypt(json.dumps(held).encode("utf-8"))
        # Written whole and moved into place: a process that died halfway through would
        # otherwise leave a file that decrypts to nothing, and the repair for that is the
        # same login it was trying to avoid.
        beside = self.path.with_suffix(self.path.suffix + ".tmp")
        beside.write_bytes(data)
        beside.replace(self.path)
        self._restrict(self.path)

    @staticmethod
    def _restrict(path: Path) -> None:
        """Owner-only, where the platform has such a thing.

        On Windows this does nothing useful and is not pretended otherwise - NTFS
        permissions are not chmod, and the protection there is the encryption plus the
        fact that the file is under the user's own profile.
        """
        with contextlib.suppress(OSError):
            path.chmod(0o600)

    def _fernet(self) -> Fernet:
        if not self._secrets.has(KEY_NAME):
            raise RegistryError(
                diagnose(
                    MISSING_CREDENTIAL,
                    f"{KEY_NAME} is not set, so a refresh token cannot be encrypted and "
                    f'will not be stored in plain text. Generate one with `python -c '
                    f'"from cryptography.fernet import Fernet; '
                    f'print(Fernet.generate_key().decode())"` and put it in .env.',
                    locator=KEY_NAME,
                )
            )
        root = str(self._secrets.get(KEY_NAME)).encode("utf-8")
        derived = hashlib.sha256(DOMAIN + root).digest()
        return Fernet(base64.urlsafe_b64encode(derived))


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")

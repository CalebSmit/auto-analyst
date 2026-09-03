"""The Mask Vault: the only store in the system that can re-identify anything.

Scoped per engagement and encrypted at rest, with the key from the Secrets Port. Two
edges only: the Masking Engine writes it, the Unmasking Engine reads it. It is not
exposed as a tool to any agent - there is no `lookup_real_name` registered anywhere, and
`graph/architecture_assertions.py` invariant 1 proves no model node has an edge to it.

The strongest isolation available is absence, not permission.

**Tokens are stable.** The same value under the same engagement gets the same token
across every file and every run, for as long as the entry is retained. That is not a
convenience: period alignment across runs weeks apart depends on it, and so does
precedent portability. It is achieved by looking up a keyed hash of the plaintext before
issuing, so the lookup never decrypts anything.

**Retention is a field, not a policy.** Setting the retention period is Risk / IT's
decision in the blueprint, to be made before phase 1. The column and the purge exist so
that decision has somewhere to land; the default here is a placeholder and says so.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Engine, Table, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from ops.models import VaultEntry, now_iso
from ops.run_store import backend_of, store_url
from ports.secrets import SecretsPort
from registries.errors import MISSING_CREDENTIAL, VAULT_UNAVAILABLE, RegistryError, diagnose

KEY_NAME = "AA_VAULT_KEY"
RETENTION_VAR = "AA_VAULT_RETENTION_DAYS"
# A placeholder until Risk / IT set the policy. Long enough that a repeat engagement a
# year later still resolves; short enough to be a number somebody has to confirm.
DEFAULT_RETENTION_DAYS = 730

__all__ = ["KEY_NAME", "MaskVault", "TOKEN_KINDS", "open_vault", "token_for"]

# The kinds a token can carry. The masker names one per identifier; the scan recognises
# the shape `[[KIND_n]]` and nothing else.
TOKEN_KINDS = ("CLIENT", "PERSON", "ACCOUNT", "ENTITY", "ADDRESS", "NUMBER")


def token_for(kind: str, n: int) -> str:
    return f"[[{kind}_{n}]]"


class MaskVault:
    """Issue tokens for values, and resolve tokens back - for one engagement at a time."""

    def __init__(self, engine: Engine, key: bytes, retention_days: int) -> None:
        self._engine = engine
        self._fernet = Fernet(key)
        self._hmac_key = hashlib.sha256(key).digest()
        self._sessions = sessionmaker(bind=engine, expire_on_commit=False)
        self.retention_days = retention_days
        self.backend = backend_of(str(engine.url))
        # Only the vault's own table. The run tables belong to the run store, and a vault
        # that created them in its own database would be two stores pretending to be one.
        cast(Table, VaultEntry.__table__).create(engine, checkfirst=True)

    # -- writing: the masker's edge

    def issue(self, engagement_id: str, kind: str, value: str, run_id: str | None = None) -> str:
        """The token for this value under this engagement. The same one every time.

        Looked up by keyed hash first, so an account seen in March gets in June the
        token it got in March. Issued fresh only when the vault has never seen the value
        for this engagement, numbered within its kind.
        """
        if kind not in TOKEN_KINDS:
            raise ValueError(f"{kind!r} is not a token kind (have: {', '.join(TOKEN_KINDS)})")
        digest = self._hash(engagement_id, value)
        with self._session() as session:
            existing = session.scalars(
                select(VaultEntry).where(
                    VaultEntry.engagement_id == engagement_id, VaultEntry.value_hash == digest
                )
            ).one_or_none()
            if existing is not None:
                return existing.token
            count = session.scalar(
                select(func.count()).select_from(VaultEntry).where(
                    VaultEntry.engagement_id == engagement_id, VaultEntry.kind == kind
                )
            ) or 0
            token = token_for(kind, count + 1)
            session.add(
                VaultEntry(
                    engagement_id=engagement_id,
                    token=token,
                    kind=kind,
                    value_hash=digest,
                    ciphertext=self._fernet.encrypt(value.encode("utf-8")).decode("ascii"),
                    issued_at=now_iso(),
                    retention_until=_plus_days(self.retention_days),
                    first_run_id=run_id,
                )
            )
            return token

    # -- reading: the unmasker's edge

    def resolve(self, engagement_id: str, token: str) -> str | None:
        """The value behind a token - for this engagement only.

        A token issued under another engagement is not found, because the query is
        scoped before the token is looked at. That is the cross-client boundary, and it
        is a WHERE clause rather than a check somebody has to remember.
        """
        with self._session() as session:
            entry = session.get(VaultEntry, (engagement_id, token))
            if entry is None:
                return None
            try:
                return self._fernet.decrypt(entry.ciphertext.encode("ascii")).decode("utf-8")
            except InvalidToken as exc:
                raise RegistryError(
                    diagnose(
                        VAULT_UNAVAILABLE,
                        f"{token} for {engagement_id} cannot be decrypted with the current "
                        f"key. The key has changed under a live vault, and nothing in it "
                        f"can be re-identified until the right key is back.",
                        locator=engagement_id,
                    )
                ) from exc

    def issued(self, engagement_id: str) -> frozenset[str]:
        """Every token this engagement has ever been issued. What the integrity check
        compares against."""
        with self._session() as session:
            rows = session.scalars(
                select(VaultEntry.token).where(VaultEntry.engagement_id == engagement_id)
            )
            return frozenset(rows)

    def kinds_issued(self, engagement_id: str) -> dict[str, int]:
        with self._session() as session:
            rows = session.execute(
                select(VaultEntry.kind, func.count())
                .where(VaultEntry.engagement_id == engagement_id)
                .group_by(VaultEntry.kind)
            )
            return {kind: int(n) for kind, n in rows}

    # -- retention

    def purge_expired(self, now: datetime | None = None) -> int:
        """Delete every entry past its retention. Returns how many.

        The one delete in the privacy package, and it is by policy rather than by
        request: a token purged here can no longer be resolved, and the integrity check
        will say so if one turns up.
        """
        stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="microseconds")
        stamp = stamp.replace("+00:00", "Z")
        with self._session() as session:
            expired = session.scalars(
                select(VaultEntry).where(VaultEntry.retention_until < stamp)
            ).all()
            for entry in expired:
                session.delete(entry)
            return len(expired)

    def close(self) -> None:
        self._engine.dispose()

    # -- internals

    def _hash(self, engagement_id: str, value: str) -> str:
        """Keyed, and salted with the engagement, so the same value under two
        engagements has two hashes and one vault dump reveals no cross-engagement
        equalities."""
        material = f"{engagement_id}\x1f{value.strip().casefold()}".encode()
        return "hmac:" + hmac.new(self._hmac_key, material, hashlib.sha256).hexdigest()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        """Commit on a clean exit, roll back on an exception. A bare Session context
        manager does neither - it closes and discards, and the first version of this
        vault issued tokens that were never written."""
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def __repr__(self) -> str:
        return f"<MaskVault {self.backend} retention={self.retention_days}d>"


def open_vault(
    secrets: SecretsPort,
    url: str | None = None,
    retention_days: int | None = None,
) -> MaskVault:
    """Open the vault with the key from the Secrets Port. No key, no vault, no masking."""
    if not secrets.has(KEY_NAME):
        raise RegistryError(
            diagnose(
                VAULT_UNAVAILABLE,
                f"{KEY_NAME} is not set. Generate one with "
                f"`python -c \"from cryptography.fernet import Fernet; "
                f"print(Fernet.generate_key().decode())\"` and put it in .env. "
                f"It never leaves this machine, and losing it loses every token it "
                f"protects.",
                locator=KEY_NAME,
            )
        )
    key = str(secrets.get(KEY_NAME)).encode("ascii")
    try:
        Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RegistryError(
            diagnose(MISSING_CREDENTIAL, f"{KEY_NAME} is not a valid Fernet key: {exc}")
        ) from exc
    resolved = store_url(url)
    if resolved.startswith("sqlite") and ":memory:" not in resolved:
        Path(resolved.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    days = retention_days or int(os.environ.get(RETENTION_VAR) or DEFAULT_RETENTION_DAYS)
    return MaskVault(create_engine(resolved, future=True), key, days)


def _plus_days(days: int) -> str:
    until = datetime.now(tz=UTC) + timedelta(days=days)
    return until.isoformat(timespec="microseconds").replace("+00:00", "Z")

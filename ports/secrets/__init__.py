"""The Secrets Port: one interface for every credential.

ShareFile key, Box credentials, database URL, model API key, mask vault encryption key.
No credential is ever read directly from the environment by feature code - the point is
that at handoff, moving to the firm's Anthropic account is a .env change and nothing
else.

The one behaviour worth stating: `has()` answers whether a credential is present without
producing it, so a preflight check can report "the Box credential is missing" without
any code path that could print one that is not.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class Secret(str):
    """A credential that will not appear in a log, a traceback or a repr.

    Subclassing str keeps it usable everywhere a credential is needed, while repr - the
    thing that ends up in exception output, f-strings during debugging, and structlog's
    fallback rendering - shows nothing. Reading the value is deliberate: str(secret).
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "Secret(<redacted>)"

    def __format__(self, spec: str) -> str:
        # An f-string is exactly where a credential leaks into a log line by accident.
        return "<redacted>"


@runtime_checkable
class SecretsPort(Protocol):
    name: str

    def has(self, key: str) -> bool:
        """Whether a credential is set. Never produces the value, so preflight and
        config-audit code can report presence without being able to leak it."""
        ...

    def get(self, key: str) -> Secret:
        """The credential. Missing is SCOPE.MISSING_CREDENTIAL - never an empty string,
        which would be indistinguishable from a credential set to nothing."""
        ...

    def names(self) -> tuple[str, ...]:
        """Which credentials this adapter can see. Names only."""
        ...

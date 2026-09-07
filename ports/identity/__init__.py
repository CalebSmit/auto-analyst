"""The Identity Port: who is asking, as something the system decides rather than accepts.

Every change this system records carries a name - who paused the engagement, who cleared
the methodology, who approved the workflow, who decided the review item. Until this port
existed, that name was a string the caller sent, which meant the change log was an
unverified list of claims in exactly the place it is meant to be evidence.

**One port, like every other deployment choice.** On a laptop bound to loopback the
identity is the operating-system user and there are no accounts, because a machine with
one person on it does not need them and inventing a login there would be ceremony that
teaches people to click through. Off loopback there has to be a real answer, and which
provider gives it - Entra ID, most likely, if the firm confirms Azure - is an adapter
behind this interface rather than a decision baked into the admin surface.

**A client-supplied name is refused, not trusted.** Not ignored: refused. A request that
sends a `who` different from the identity the system resolved is either a bug or somebody
trying, and silently overwriting it would hide both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from registries.errors import MISSING_CREDENTIAL, RegistryError, diagnose

__all__ = ["Identity", "IdentityPort", "NotAuthenticated", "loopback"]

LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
"""What counts as this machine. `testclient` is Starlette's in-process client: a test
exercising the surface is not reaching it over a network, and treating it as remote would
make every test authenticate against a provider that does not exist yet."""


@dataclass(frozen=True)
class Identity:
    """Who the system decided is asking."""

    name: str
    """What goes in the record. A person, never a service account with a person's job."""

    method: str
    """`operating_system`, or the name of the provider that vouched for it. Recorded so
    "who approved this" can be answered with how the system knows."""

    verified: bool
    """False for an identity the system took on trust - the OS user on a laptop is a fact
    about the machine rather than a proof of anything, and saying so is cheaper than
    pretending otherwise."""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("an identity has a name")


class NotAuthenticated(RegistryError):
    """The request reached a surface that needs an identity, and there was none."""


def loopback(host: str | None) -> bool:
    """Whether a request came from this machine.

    A host of None is treated as remote. An unknown origin is not the local user, and the
    safe reading of "I could not tell" is the one that asks for proof.
    """
    if not host:
        return False
    return host.split("%")[0].strip("[]").lower() in LOOPBACK


@runtime_checkable
class IdentityPort(Protocol):
    """Resolve who is asking, or refuse."""

    name: str

    def resolve(self, host: str | None) -> Identity:
        """The identity behind a request from `host`.

        Raises `NotAuthenticated` rather than returning an anonymous identity: a surface
        that cannot say who is asking must not record a change, and a caller that has to
        remember to check a flag is a caller that will not.
        """
        ...


def unauthenticated(detail: str, *, found: str = "no identity") -> NotAuthenticated:
    """The one refusal shape, so every adapter says it the same way."""
    return NotAuthenticated(
        diagnose(
            MISSING_CREDENTIAL,
            detail,
            locator="identity",
            expected="an authenticated identity",
            found=found,
        )
    )

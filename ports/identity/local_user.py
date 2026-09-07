"""The operating-system user, and only from this machine.

The right answer on a laptop: one person, no accounts, and the name in the change log is
the name they log in as. Off loopback it refuses, because the OS user of the process is a
fact about the server rather than about whoever sent the request - and answering with it
there would put one name on every change anybody made.

That refusal is the whole safety of this adapter. It is why binding the surface to a
network address without a real provider does not quietly work.
"""

from __future__ import annotations

import getpass
import os

from ports.identity import Identity, loopback, unauthenticated

__all__ = ["LocalUserIdentity", "build"]

OVERRIDE = "AA_IDENTITY_NAME"
"""What to call the local user, when the OS answer is not the one a firm would recognise -
a container running as `analyst`, most often. Not a way to be somebody else: it is only
consulted for a request that already came from this machine."""


class LocalUserIdentity:
    """The person at the keyboard, taken on trust because they are at the keyboard."""

    name = "local_user"

    def resolve(self, host: str | None) -> Identity:
        if not loopback(host):
            raise unauthenticated(
                "this surface is reachable from somewhere other than the machine it runs "
                "on, and the local-user adapter cannot say who sent the request. Bind it "
                "to 127.0.0.1, or select an identity adapter that authenticates.",
                found=str(host),
            )
        return Identity(name=self._who(), method="operating_system", verified=False)

    def _who(self) -> str:
        override = os.environ.get(OVERRIDE, "").strip()
        if override:
            return override
        try:
            return getpass.getuser()
        except Exception:  # noqa: BLE001 - a container with no passwd entry
            return "unknown local user"


def build() -> LocalUserIdentity:
    return LocalUserIdentity()

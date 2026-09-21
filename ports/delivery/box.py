"""Delivery adapter: Box. The port contract for the connector that exists at work.

**This is a contract, not an implementation.** Chartwell already has a Box connector,
using client-credentials auth; at handoff it becomes the body of the three methods below.
The name is registered so `AA_DELIVERY_ADAPTER=box` is a choice the system understands
and refuses loudly - a deliverable written somewhere nobody chose is the failure the
whole port arrangement exists to prevent.

What the connector has to satisfy:

* **`ensure_folder(path)`** makes the destination exist and is **idempotent**. Called
  before every write, including the ones that turn out to be repeats.
* **`put(path, data)`** writes bytes and returns what was written. It **never silently
  overwrites**. Identical bytes at the same path come back as `already_present=True`
  rather than as a second copy, which is what makes a keyed retry after a transport
  failure safe. Different bytes at the same path take a **new version** - immutability of
  the record comes from the destination rather than from everyone remembering not to
  overwrite. Box's own versioning satisfies this; do not implement a parallel scheme.
* **`version(path)`** returns how many versions exist there, zero for nothing written.

And what it must not do:

* no reading of client folders - delivery is the write side, and the Storage Port is the
  read side. There is no method here that lists or fetches;
* no path invention. The Release Gate decides where a deliverable goes and hands over the
  path; an adapter that appends a date or a suffix breaks the idempotency ledger, which
  keys on exactly that path;
* no credential reads of its own. The Secrets Port holds `BOX_CLIENT_ID`,
  `BOX_CLIENT_SECRET` and `BOX_USER_ID`.

**The third credential was wrong until P87, and the correction is a finding rather than a
tidy-up.** This said `BOX_ENTERPRISE_ID`, which was a guess made before anyone had
authenticated against this firm's Box. An enterprise id authenticates as the *service
account*: a real Box user that is a member of almost nothing. Writes would have been
accepted into a folder nobody reads, or refused for a reason that reads like a bad path.
What actually works - proved by the analyst's own `box.sharefile.automation` harness - is
client credentials with **user impersonation**: `box_subject_type=user`, `box_subject_id`,
and "Generate User Access Tokens" enabled on the Box app. So the credential is the id of
the person whose folders are being written to. `ports/storage/box.py` carries the same
three and the working implementation of the token exchange.

The blueprint lists two Box routes - a Box MCP server and client-credentials auth. This
adapter is the second: one library, one credential set, no server to keep alive. If the
MCP route is ever wanted it is another adapter beside this one, not a change to this one.

Until then, `build()` refuses. See HANDOFF.md.
"""

from __future__ import annotations

import os
from typing import NoReturn

from ports.delivery import PutResult
from registries.errors import (
    ADAPTER_NOT_WIRED,
    MISSING_CREDENTIAL,
    RegistryError,
    diagnose,
)

__all__ = ["CREDENTIALS", "ENV_ROOT", "BoxDelivery", "build"]

CREDENTIALS = ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_USER_ID")
ENV_ROOT = "AA_BOX_ROOT_FOLDER_ID"
CONNECTOR = "the firm's Box connector (client credentials with user impersonation)"


class BoxDelivery:
    """The shape the connector fills in. Every method refuses until it is wired."""

    name = "box"

    def __init__(self, root_folder_id: str = "") -> None:
        self.root_folder_id = root_folder_id or os.environ.get(ENV_ROOT, "")

    def __repr__(self) -> str:
        return f"BoxDelivery(root={self.root_folder_id!r}, wired=False)"

    def ensure_folder(self, path: str) -> None:
        _not_wired("ensure_folder")

    def put(self, path: str, data: bytes) -> PutResult:
        _not_wired("put")

    def version(self, path: str) -> int:
        _not_wired("version")


def missing_credentials() -> tuple[str, ...]:
    return tuple(name for name in CREDENTIALS if not os.environ.get(name))


def _not_wired(method: str) -> NoReturn:
    raise RegistryError(
        diagnose(
            ADAPTER_NOT_WIRED,
            f"BoxDelivery.{method} is a port contract, not an implementation. "
            f"{CONNECTOR} is the body of it; until that is wired in, this adapter "
            f"refuses rather than reporting a write that did not happen. See HANDOFF.md.",
            locator="ports/delivery/box.py",
            expected="a connector that satisfies ensure_folder, put and version",
            found="the contract only",
        )
    )


def build() -> BoxDelivery:
    missing = missing_credentials()
    if missing:
        raise RegistryError(
            diagnose(
                MISSING_CREDENTIAL,
                f"the Box adapter needs {', '.join(missing)}, which the environment "
                f"does not set",
                locator="ports/delivery/box.py",
            )
        )
    _not_wired("build")
    raise AssertionError  # unreachable; _not_wired always raises

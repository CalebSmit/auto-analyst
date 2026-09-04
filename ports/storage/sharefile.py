"""Storage adapter: ShareFile. The port contract for the connector that exists at work.

**This is a contract, not an implementation.** Chartwell already has a ShareFile
connector; at handoff it becomes the body of the three methods below. Registering the
name now means `AA_STORAGE_ADAPTER=sharefile` is a choice the system understands and
refuses loudly, rather than an unknown name or - far worse - a silent fallback to the
local folder, which would be a run reading from somewhere nobody chose.

What the connector has to satisfy, and nothing more:

* **`list(prefix)`** returns every file under the prefix **in a stable order**. Sorted by
  path, not by whatever the API returns: a sweep that returns files in server order
  produces a different run from the same inputs. Folders are not files; do not return
  them. Paths are relative to the configured root and never absolute - an absolute path
  is a fact about one machine, and downstream code holds no such facts.
* **`read(ref)`** returns bytes, or raises `INTAKE.UNREADABLE_FILE`. Never an empty
  result for a file that could not be read: an empty trial balance is indistinguishable
  from a missing one at every point downstream.
* **`stat(ref)`** returns size, modified time and a **sha256 content hash**, without
  reading the file into the caller. If ShareFile's own hash is not sha256, compute one -
  every figure the pipeline produces cites this id, and two sources cannot share it.

Three things the connector must *not* do, each of which the local adapter also does not:

* no writing - this is the read side of intake, and the Delivery Port is the other one;
* no caching that outlives a sweep - a re-uploaded file must appear as new bytes and a
  new hash, because `source_version` is how the Intake Window notices;
* no credential reads of its own - the Secrets Port holds `SHAREFILE_CLIENT_ID`,
  `SHAREFILE_CLIENT_SECRET` and `SHAREFILE_SUBDOMAIN`, and it hands them over rather
  than the adapter going to the environment.

Until then, `build()` refuses. See HANDOFF.md.
"""

from __future__ import annotations

import os
from typing import NoReturn

from ports.storage import FileRef, FileStat
from registries.errors import (
    ADAPTER_NOT_WIRED,
    MISSING_CREDENTIAL,
    RegistryError,
    diagnose,
)

__all__ = ["CREDENTIALS", "ENV_ROOT", "ShareFileStorage", "build"]

CREDENTIALS = ("SHAREFILE_SUBDOMAIN", "SHAREFILE_CLIENT_ID", "SHAREFILE_CLIENT_SECRET")
ENV_ROOT = "AA_SHAREFILE_ROOT"
CONNECTOR = "the firm's ShareFile connector"


class ShareFileStorage:
    """The shape the connector fills in. Every method refuses until it is wired."""

    name = "sharefile"

    def __init__(self, root: str = "") -> None:
        self.root = root or os.environ.get(ENV_ROOT, "")

    def __repr__(self) -> str:
        return f"ShareFileStorage(root={self.root!r}, wired=False)"

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        _not_wired("list")

    def read(self, ref: FileRef) -> bytes:
        _not_wired("read")

    def stat(self, ref: FileRef) -> FileStat:
        _not_wired("stat")


def missing_credentials() -> tuple[str, ...]:
    """Which of the three are not set. Presence only - the value is never read here."""
    return tuple(name for name in CREDENTIALS if not os.environ.get(name))


def _not_wired(method: str) -> NoReturn:
    raise RegistryError(
        diagnose(
            ADAPTER_NOT_WIRED,
            f"ShareFileStorage.{method} is a port contract, not an implementation. "
            f"{CONNECTOR} is the body of it; until that is wired in, this adapter "
            f"refuses rather than returning something. See HANDOFF.md.",
            locator="ports/storage/sharefile.py",
            expected="a connector that satisfies list, read and stat",
            found="the contract only",
        )
    )


def build() -> ShareFileStorage:
    missing = missing_credentials()
    if missing:
        raise RegistryError(
            diagnose(
                MISSING_CREDENTIAL,
                f"the ShareFile adapter needs {', '.join(missing)}, which the "
                f"environment does not set",
                locator="ports/storage/sharefile.py",
            )
        )
    _not_wired("build")
    raise AssertionError  # unreachable; _not_wired always raises

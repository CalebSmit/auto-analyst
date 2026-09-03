"""Content-addressed storage for step results.

Steps pass refs, never values. That is one of P08's exit criteria and it is not a style
preference - three later guarantees rest on it:

**The idempotency key can be computed.** A step's key is a hash over its *inputs*, and
inputs that are refs are already hashed. Inputs that were values would have to be hashed
at every call site, and one call site doing it differently is a key that silently stops
matching.

**A resumed run costs nothing for work already done.** The ledger stores a ref. Satisfying
a completed step from the ledger is a lookup, not a re-materialisation.

**The manifest can name what a step actually saw.** "Which bytes were the input to the
EBITDA step on Tuesday" is a hash, and the hash resolves.

The store is write-once by construction: the address *is* the hash of the content, so
writing the same bytes twice is the same address, and writing different bytes cannot
land on an existing one. There is no update operation because there is nothing an update
could mean.

Local files through P24, behind a Protocol so that stays true without costing anything
later. Not the Storage Port: that one is the read side of client intake and answers a
different question - `list()`, `read()`, `stat()` over documents somebody sent us. This
is the system's own intermediate results, addressed by content rather than by path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from registries.errors import UNREADABLE_FILE, WRITE_FAILED, RegistryError, diagnose

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "runs" / "blobs"

__all__ = [
    "ContentRef",
    "ContentStore",
    "LocalContentStore",
    "content_hash",
]


def content_hash(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class ContentRef:
    """A pointer to bytes, by their hash. What travels between steps.

    Carries the size and media type so a reader can decide whether to fetch before
    fetching - a step that needs to know "is this a 400MB workbook or a 2KB JSON object"
    should not have to read it to find out.
    """

    content_hash: str
    media_type: str = "application/json"
    size_bytes: int = 0
    name: str = ""

    def __str__(self) -> str:
        short = self.content_hash[7:15]
        return f"{self.name or 'ref'}@{short} ({self.size_bytes}B {self.media_type})"

    def __post_init__(self) -> None:
        if not self.content_hash.startswith("sha256:") or len(self.content_hash) != 71:
            raise ValueError(
                f"{self.content_hash!r} is not a content hash. A ref that cannot be "
                f"resolved is a value that lost its provenance on the way."
            )


@runtime_checkable
class ContentStore(Protocol):
    """Put bytes in, get a ref; give a ref, get the bytes back.

    No delete and no overwrite. The address is the content, so there is nothing an
    overwrite could mean, and a run's inputs must still resolve when somebody asks about
    it in eighteen months.
    """

    def put(self, data: bytes, media_type: str = ..., name: str = ...) -> ContentRef: ...
    def get(self, ref: ContentRef) -> bytes: ...
    def has(self, ref: ContentRef) -> bool: ...


class LocalContentStore:
    """Files under a root, two hex characters of fan-out. Good enough to P24."""

    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)

    def __repr__(self) -> str:
        return f"LocalContentStore(root={self.root})"

    def put(self, data: bytes, media_type: str = "application/json", name: str = "") -> ContentRef:
        digest = content_hash(data)
        target = self._path(digest)
        if not target.exists():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Written to a neighbour and moved, so a reader never sees a half-written
                # blob at an address that claims to be its hash.
                staging = target.with_suffix(".partial")
                staging.write_bytes(data)
                staging.replace(target)
            except OSError as exc:
                raise RegistryError(diagnose(WRITE_FAILED, str(exc), locator=digest)) from exc
        return ContentRef(
            content_hash=digest, media_type=media_type, size_bytes=len(data), name=name
        )

    def get(self, ref: ContentRef) -> bytes:
        try:
            data = self._path(ref.content_hash).read_bytes()
        except OSError as exc:
            raise RegistryError(
                diagnose(
                    UNREADABLE_FILE,
                    f"{ref.content_hash} is not in the content store. A ref that does "
                    f"not resolve means a step's input is gone, and the run cannot be "
                    f"reconstructed - which is the thing content addressing is for.",
                    locator=str(self.root),
                )
            ) from exc
        found = content_hash(data)
        if found != ref.content_hash:
            raise RegistryError(
                diagnose(
                    UNREADABLE_FILE,
                    f"the bytes at {ref.content_hash} hash to {found}. Content addressing "
                    f"is only a guarantee if it is checked on the way out.",
                    locator=str(self.root),
                )
            )
        return data

    def has(self, ref: ContentRef) -> bool:
        return self._path(ref.content_hash).is_file()

    # -- convenience for the common case

    def put_json(self, value: Any, name: str = "") -> ContentRef:
        """Canonical JSON: sorted keys, no incidental whitespace.

        Canonical because the hash is an identity. Two structurally identical results
        that hashed differently because a dict happened to iterate in another order would
        make a resumed run pay for work it had already done.
        """
        body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self.put(body, media_type="application/json", name=name)

    def get_json(self, ref: ContentRef) -> Any:
        return json.loads(self.get(ref).decode("utf-8"))

    def _path(self, digest: str) -> Path:
        stem = digest.removeprefix("sha256:")
        return self.root / stem[:2] / stem

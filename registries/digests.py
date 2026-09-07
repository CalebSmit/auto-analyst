"""What a text file's bytes are, decided once.

P31 found this the hard way. Methodology was hashed with `read_bytes`, so the same file
gave one digest on a Windows checkout and another inside a Linux image - a byte per line.
A file cleared at the firm on a laptop read as *edited* the moment the same repo ran in a
container, and the assembled context differed byte for byte between the two, which is two
idempotency keys for one question.

Every registry that identifies a file by its content has that problem, so the answer lives
in one place rather than being remembered separately each time. Decoded as text, encoded
back as UTF-8 with newlines as `\\n` - which is also the byte sequence a model is shown,
so a digest keeps describing what was actually sent rather than what happened to be on
disk on one operating system.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["digest_of", "text_bytes"]


def text_bytes(path: Path) -> bytes:
    """The bytes of a text file, with line endings normalised to `\\n`."""
    return path.read_text(encoding="utf-8").encode("utf-8")


def digest_of(body: bytes) -> str:
    """The one spelling of a content hash in this system, so a digest written by one
    registry is comparable with a digest written by another."""
    return f"sha256:{hashlib.sha256(body).hexdigest()}"

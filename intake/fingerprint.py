"""File Intake & Fingerprint: gives every file a permanent id that every figure will cite.

Computes a SHA-256 content hash as `source_id`, records mime type, size, original path
and a monotonic `source_version`, then routes spreadsheet vs. document. Pure Python;
returns a manifest row. An unreadable file stops the sweep of that engagement rather
than proceeding with a null id - a figure that cites nothing is worse than a figure that
never existed.

`source_version` is per (engagement, filename): the same name arriving with different
bytes is version 2, and the run that consumed version 1 is superseded by the run that
consumes version 2. The same bytes arriving again are not a new version - the id is the
content, and the content did not change.

Provenance is attached at the moment of arrival so it can never be reconstructed
downstream from memory. Arrival is when a sweep first sees the file - the system's
clock, not the client's file system - and that is what the Intake Window counts from.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable
from datetime import UTC, datetime

from intake.bind import Bound
from intake.store import IntakeRow, IntakeStore
from ports.storage import StoragePort

__all__ = [
    "BY_EXTENSION",
    "READ",
    "Fingerprinter",
    "IntakeRecord",
    "kind_of",
    "mime_of",
]

IntakeRecord = IntakeRow

# What each extension means, declared rather than asked of the host.
#
# `mimetypes.guess_type` reads the platform's own table - the Windows registry, or
# /etc/mime.types on Linux, which a slim container image does not install. The same
# spreadsheet was therefore a spreadsheet on one machine and `application/octet-stream`
# on another, which changed `kind`, sent the file past the workbook reader, and put a
# different `mime` in the manifest for identical bytes. A run's record must not depend on
# which host read the file.
BY_EXTENSION: dict[str, str] = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    # Its own type rather than Word's. `mimetypes` calls an .rtf `application/msword` on
    # some hosts, which put it in the same bucket as a .doc - and the two could not be more
    # different to a reader: an RTF is text with its formatting written into it and is read,
    # a .doc is an OLE2 compound file and is refused.
    ".rtf": "application/rtf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

SPREADSHEET = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/vnd.ms-excel",
    "text/csv",
}
DOCUMENT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/rtf",
    "text/plain",
    "text/markdown",
}

# Of the document types above, the ones a reader actually reads. `.doc` is routed and
# refused on purpose: it is an OLE2 compound file, and the reader that met one decoded it as
# UTF-8 and stored the bytes 0 to 255 as lines of a document. Being routed is what gets a
# person the diagnostic that says to save it as a .docx; being read is a different claim and
# this build does not make it.
READ = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/rtf",
    "text/plain",
    "text/markdown",
}


def mime_of(filename: str) -> str:
    """The type of a file, from its extension, the same on every host.

    The declared table first, so the document types this system actually handles are
    decided here. `mimetypes` second, so anything outside the table still gets whatever
    the platform knows, and last `application/octet-stream` - which is honest: unknown.
    """
    import os

    extension = os.path.splitext(filename)[1].lower()
    if extension in BY_EXTENSION:
        return BY_EXTENSION[extension]
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def kind_of(mime: str) -> str:
    if mime in SPREADSHEET:
        return "spreadsheet"
    if mime in DOCUMENT:
        return "document"
    return "other"


class Fingerprinter:
    def __init__(
        self,
        port: StoragePort,
        intake_store: IntakeStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.port = port
        self.intake_store = intake_store
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def take(self, bound: Bound) -> IntakeRecord | None:
        """Fingerprint a bound file. Returns the new intake row, or None when these
        exact bytes are already on the record for this engagement."""
        stat = self.port.stat(bound.ref)
        already = self.intake_store.known(bound.engagement_id, stat.content_hash)
        if already is not None:
            return None
        mime = mime_of(bound.filename)
        prior = self.intake_store.versions_of(bound.engagement_id, bound.filename)
        row = IntakeRow(
            engagement_id=bound.engagement_id,
            source_id=stat.content_hash,
            filename=bound.filename,
            path=bound.ref.path,
            watch_id=bound.watch_id,
            document_type=bound.document_type,
            kind=kind_of(mime),
            mime=mime,
            bytes=stat.size_bytes,
            source_version=(prior[-1].source_version + 1) if prior else 1,
            received_at=_stamp(self._clock()),
            state="held" if bound.document_type is None else "pending",
        )
        return self.intake_store.record(row)


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

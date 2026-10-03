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
    "IMAGE",
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
    # The ones a client sends most and this build read least. A screenshot of a trial
    # balance, a photograph of a page, a scan saved as a TIFF: each is a page with no text
    # layer, which is what a scanned PDF page is, so each is read the same way. Declared
    # here rather than left to `mimetypes` for the reason the whole table exists - the same
    # bytes must get the same type on every host.
    # A client on LibreOffice sends this instead of an .xlsx. Read, through the same
    # conversion seam a .csv goes through.
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    # Excel's binary workbook. Routed so it can be refused by name: a reader for it exists
    # and there is no real one of these on this machine to measure a reader against, and a
    # half-working parser for a binary format produces plausible partial figures.
    ".xlsb": "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
    # What arrives when somebody saves the email instead of the attachment. Read as the
    # message it is, and its attachments named, because that is what has to be asked for.
    ".eml": "message/rfc822",
    # Outlook's own format, which is an OLE2 compound file. Refused like the .xlsb and for
    # the same reason.
    ".msg": "application/vnd.ms-outlook",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

IMAGE = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
}
"""A page with no text layer at all.

Its own set, and also in `DOCUMENT`, because the two say different things. Being a document
is how it reaches a reader; being an image is why that reader hands it to the OCR port
rather than decoding it - and `looks_like` would otherwise refuse the very first bytes of
every one of them, since a PNG signature is exactly what it is built to catch.
"""

SPREADSHEET = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/vnd.ms-excel",
    "text/csv",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
}
DOCUMENT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/rtf",
    "text/plain",
    "text/markdown",
    "message/rfc822",
    "application/vnd.ms-outlook",
    *IMAGE,
}

# Of everything routed above, the ones a reader actually reads - **both kinds**, because the
# distinction is the same one on either side. Three formats are routed and refused on
# purpose:
#
# * `.doc`, an OLE2 compound file, which the reader that met one decoded as UTF-8 and stored
#   as the bytes 0 to 255;
# * `.xlsb`, Excel's binary workbook;
# * `.msg`, Outlook's, which is also OLE2.
#
# Each has a reader somewhere in the world, none has a real example on this machine to
# measure one against, and a half-working parser for a binary format produces plausible
# *partial* content - the failure this repository is most careful about.
#
# Being routed is what gets a person the diagnostic saying to save it as something that is
# read; being read is a different claim and this build does not make it. This set held only
# document types until P159, which made a spreadsheet format nobody reads indistinguishable
# from one that is read - so an `.xlsb` was told it "cannot be opened as a workbook", which
# is true and is the wrong thing to do about it, because nothing is wrong with the file.
READ = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/vnd.ms-excel",
    "text/csv",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/rtf",
    "text/plain",
    "text/markdown",
    "message/rfc822",
    # Read in the sense this set means: a reader takes it and produces a page. What comes
    # back is only as good as the engine configured, and with none it is an empty page
    # reported as scanned - which is the same answer a scanned PDF gets, and is not the same
    # thing as a format nobody tries.
    *IMAGE,
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

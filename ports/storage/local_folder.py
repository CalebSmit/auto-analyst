"""Storage adapter: a watched folder on this machine. How phase 1 runs.

Nothing outside ports/ imports this module. The pipeline holds a reference to the
StoragePort interface, never to a concrete client - which is the property the
import-boundary test in tests/p03 enforces rather than trusts.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from ports.storage import FileRef, FileStat
from registries.errors import UNREADABLE_FILE, RegistryError, diagnose

ENV_ROOT = "AA_INBOX_ROOT"
DEFAULT_ROOT = "./inbox"


class LocalFolderStorage:
    """Reads from a folder. The root comes from config; paths are relative to it."""

    name = "local_folder"

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or os.environ.get(ENV_ROOT, DEFAULT_ROOT)).resolve()

    def __repr__(self) -> str:
        return f"LocalFolderStorage(root={self.root})"

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        base = self._resolve(prefix) if prefix else self.root
        if not base.is_dir():
            return ()
        found = [
            FileRef(p.relative_to(self.root).as_posix())
            for p in base.rglob("*")
            if p.is_file()
        ]
        # Sorted, because a sweep that returns files in whatever order the filesystem
        # offers produces a different run from the same inputs.
        return tuple(sorted(found, key=lambda r: r.path))

    def read(self, ref: FileRef) -> bytes:
        path = self._resolve(ref.path)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise RegistryError(
                diagnose(UNREADABLE_FILE, str(exc), locator=ref.path)
            ) from exc

    def stat(self, ref: FileRef) -> FileStat:
        path = self._resolve(ref.path)
        try:
            info = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise RegistryError(
                diagnose(UNREADABLE_FILE, str(exc), locator=ref.path)
            ) from exc
        return FileStat(
            ref=ref,
            size_bytes=info.st_size,
            modified_at=datetime.fromtimestamp(info.st_mtime, tz=UTC),
            content_hash=f"sha256:{digest}",
        )

    def _resolve(self, relative: str) -> Path:
        """Resolve inside the root, or refuse.

        The Policy Gate checks engagement scope on every proposed action, but a port
        that can be walked out of with '../' would make that check advisory. Cheaper to
        make it impossible here.
        """
        path = (self.root / relative).resolve()
        if path != self.root and self.root not in path.parents:
            raise RegistryError(
                diagnose(UNREADABLE_FILE, "path escapes the storage root", locator=relative)
            )
        return path


def build() -> LocalFolderStorage:
    return LocalFolderStorage()

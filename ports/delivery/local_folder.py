"""Delivery adapter: an output folder on this machine.

Versioning is by suffix - `manifest.json`, `manifest.v2.json` - because the local
filesystem offers none of its own and the manifest has to be immutable in practice, not
only by convention.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ports.delivery import PutResult
from registries.errors import WRITE_FAILED, RegistryError, diagnose

ENV_ROOT = "AA_OUTBOX_ROOT"
DEFAULT_ROOT = "./outbox"


class LocalFolderDelivery:
    name = "local_folder"

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or os.environ.get(ENV_ROOT, DEFAULT_ROOT)).resolve()

    def __repr__(self) -> str:
        return f"LocalFolderDelivery(root={self.root})"

    def ensure_folder(self, path: str) -> None:
        target = self._resolve(path)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RegistryError(diagnose(WRITE_FAILED, str(exc), locator=path)) from exc

    def put(self, path: str, data: bytes) -> PutResult:
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        existing = self._versions(path)

        for candidate in existing:
            if hashlib.sha256(candidate.read_bytes()).hexdigest() == digest.removeprefix("sha256:"):
                return PutResult(
                    path=path,
                    content_hash=digest,
                    version=self._version_of(path, candidate),
                    already_present=True,
                )

        version = len(existing) + 1
        target = self._path_for(path, version)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as exc:
            raise RegistryError(diagnose(WRITE_FAILED, str(exc), locator=path)) from exc
        return PutResult(path=path, content_hash=digest, version=version)

    def version(self, path: str) -> int:
        return len(self._versions(path))

    # ------------------------------------------------------------------ internals

    def _path_for(self, path: str, version: int) -> Path:
        target = self._resolve(path)
        if version == 1:
            return target
        return target.with_name(f"{target.stem}.v{version}{target.suffix}")

    def _versions(self, path: str) -> list[Path]:
        first = self._resolve(path)
        found = [first] if first.is_file() else []
        n = 2
        while (nth := self._path_for(path, n)).is_file():
            found.append(nth)
            n += 1
        return found

    def _version_of(self, path: str, candidate: Path) -> int:
        return next(
            (n for n in range(1, len(self._versions(path)) + 1)
             if self._path_for(path, n) == candidate),
            1,
        )

    def _resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if path != self.root and self.root not in path.parents:
            raise RegistryError(
                diagnose(WRITE_FAILED, "path escapes the delivery root", locator=relative)
            )
        return path


def build() -> LocalFolderDelivery:
    return LocalFolderDelivery()

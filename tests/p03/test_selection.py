"""Switching an adapter is configuration. No pipeline code is touched.

The last exit criterion of the phase, and the one that is easy to believe without
checking. A second storage adapter is registered here purely so the swap can be
demonstrated end to end: with one adapter in the registry, "the port is swappable" is a
claim about code nobody has run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import ports
from ports.storage import FileRef, FileStat, StoragePort


class InMemoryStorage:
    """A second storage adapter, holding bytes in a dict.

    Not registered in ports.PORTS - it is installed into the registry by the test that
    needs it. Real second adapters (ShareFile, email attachments) arrive at handoff.
    """

    name = "in_memory"
    files: dict[str, bytes] = {"MEMO.txt": b"from memory"}

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        return tuple(FileRef(p) for p in sorted(self.files) if p.startswith(prefix))

    def read(self, ref: FileRef) -> bytes:
        return self.files[ref.path]

    def stat(self, ref: FileRef) -> FileStat:
        import hashlib
        from datetime import UTC, datetime

        data = self.files[ref.path]
        return FileStat(
            ref=ref,
            size_bytes=len(data),
            modified_at=datetime(2026, 1, 1, tzinfo=UTC),
            content_hash="sha256:" + hashlib.sha256(data).hexdigest(),
        )


@pytest.fixture
def registered_second_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Install the in-memory adapter as though it had always been in the registry."""
    module = tmp_path / "in_memory_storage.py"
    module.write_text(
        "from tests.p03.test_selection import InMemoryStorage\n"
        "def build():\n    return InMemoryStorage()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    spec = ports.PORTS["storage"]
    monkeypatch.setitem(spec.adapters, "in_memory", "in_memory_storage")


def read_one_file(storage: StoragePort) -> bytes:
    """Stands in for pipeline code.

    It takes the interface, calls three methods, and knows nothing about which adapter
    answered. Nothing below the assertions changes between the two runs, which is the
    property under test.
    """
    first = storage.list()[0]
    storage.stat(first)
    return storage.read(first)


def test_switching_the_adapter_changes_behaviour_with_no_pipeline_change(
    registered_second_adapter: None, inbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (inbox / "TB_FY23.xlsx").write_bytes(b"from the folder")

    monkeypatch.setenv("AA_STORAGE_ADAPTER", "local_folder")
    ports.reset()
    assert read_one_file(ports.get_storage()) == b"from the folder"

    monkeypatch.setenv("AA_STORAGE_ADAPTER", "in_memory")
    ports.reset()
    assert read_one_file(ports.get_storage()) == b"from memory"


def test_the_second_adapter_satisfies_the_same_protocol(
    registered_second_adapter: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AA_STORAGE_ADAPTER", "in_memory")
    ports.reset()
    assert isinstance(ports.get_storage(), StoragePort)


def test_selection_reads_config_every_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AA_STORAGE_ADAPTER", raising=False)
    assert ports.selected("storage") == "local_folder"
    monkeypatch.setenv("AA_STORAGE_ADAPTER", "in_memory")
    assert ports.selected("storage") == "in_memory"


def test_an_unset_adapter_falls_back_to_the_declared_default() -> None:
    """A default is fine. A default reached by silently swallowing an unknown name is
    not - that is the distinction ports.get_port draws."""
    for port, spec in ports.PORTS.items():
        assert spec.default in spec.adapters, f"{port} defaults to an unregistered adapter"


def test_the_llm_default_costs_nothing_and_needs_no_key() -> None:
    """Phases 4 to 10 build the engine against replayed fixtures. A default that reached
    a real model would make the test suite cost money to run, which is how a test suite
    stops being run."""
    assert ports.PORTS["llm"].default == "fake"


def test_adapters_are_cached_until_reset(monkeypatch: pytest.MonkeyPatch, inbox: Path) -> None:
    """A storage client is not free to construct."""
    monkeypatch.setenv("AA_STORAGE_ADAPTER", "local_folder")
    ports.reset()
    first: Any = ports.get_storage()
    assert ports.get_storage() is first
    ports.reset()
    assert ports.get_storage() is not first

"""The whole system against an empty store - which is what P135 is about.

The same fixture `tests/regression/test_serve.py` uses, and deliberately the same: the
point of these tests is the state a real first day is in, so a hand-built double would be
testing something else. It does *not* write a configuration document, because that absence
is the subject.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'serve.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports
    from tools.serve import build

    ports.reset()
    system = build()
    yield system
    system.close()
    ports.reset()

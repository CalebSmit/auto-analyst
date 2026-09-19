"""C28 - Built, and wired to something.

The question this checkpoint asks is not "does each piece work" - every piece worked. It is
whether the pieces are *connected in the system the command builds*, which is a different
question and the one nothing had been asking. Three components were built, registered,
handed to their neighbours and left unread by the one thing that needed them, and all three
survived a full green suite because the tests that came closest either had no store to pass
or passed everything except the argument in question.

So this reaches through `tools.serve.build()` every time, and asks the assembled object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness.context import NoPrecedents
from tools.serve import readiness

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from cryptography.fernet import Fernet

    from tools.serve import build

    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c28.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    built = build()
    yield built
    built.close()
    ports.reset()


def test_the_assembled_system_reads_precedent_and_can_release(system: Any) -> None:
    """Both joins, on one object, built the way the command builds it."""
    from deliver.release import ReleaseGate

    assert system.pool is not None, "the pool did not start; nothing below can be asked"
    wiring = system.pool.passes.wiring

    context = wiring.dispatcher_for("run_c28").context
    assert not isinstance(context.precedents, NoPrecedents)
    assert context.precedents is wiring.precedents, (
        "the dispatcher and the driver read different precedent sources, which is how one "
        "of them came to read none"
    )

    gate = ReleaseGate(wiring.store, wiring.bus, wiring.delivery)
    assert gate.delivery is wiring.delivery


def test_every_seam_is_reported_and_every_one_is_joined(system: Any) -> None:
    seams = {seam.name: seam for seam in readiness()}
    assert "precedent retrieval" in seams
    # `needs_installing` seams are excluded: P74's OCR waits on an engine a person
    # installs, not on a join this build has left unmade, and counting it here would make
    # every machine without one report an unfinished system.
    assert all(seam.ready for seam in seams.values() if not seam.needs_installing), [
        seam.name for seam in seams.values() if not seam.ready and not seam.needs_installing
    ]
    for seam in seams.values():
        assert "NoPrecedents" not in seam.detail, seam.name
        assert "nothing implements" not in seam.detail, seam.name


def test_a_quarantine_is_queryable_by_what_caused_it(system: Any) -> None:
    """`ops/analytics.py` ranks failures by `diagnostic_code`, and the executor put every
    guard, policy, scan and budget failure's code into a message string instead. The column
    it reads is the one that has to carry it."""
    from ops.models import Event

    assert hasattr(Event, "diagnostic_code"), "the column the breakdown is built on"

    import inspect

    from graph.execute import StepExecutor

    source = inspect.getsource(StepExecutor._code_of)
    assert "diagnostic" in source
    assert StepExecutor._code_of(ValueError("no code here")) == {}


def test_what_is_still_not_joined_is_written_down_rather_than_implied() -> None:
    """The release path is built and still cannot be reached: both shipped recipes end at
    `qc-tieout`, which has no mechanical half. That is a real limit and it stays named."""
    open_items = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    assert "qc-tieout" in open_items
    backlog = (ROOT / "knowledge" / "backlog.md").read_text(encoding="utf-8")
    assert "B-004" in backlog, "the procedure that would let a run reach release"

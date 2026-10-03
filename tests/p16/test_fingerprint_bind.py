"""Binding fails closed before anything is read; fingerprinting gives every file its id."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from intake import Intake
from intake.bind import EngagementBinder, bind_document_type
from intake.config import ConfigStore
from intake.fingerprint import Fingerprinter, kind_of
from intake.roster import ProjectRoster, RosterState
from intake.store import IntakeStore
from intake.sweep import SweepTarget
from ports.storage import FileRef
from registries.errors import RegistryError
from tests.p16.conftest import (
    HEND,
    HEND_FOLDER,
    LAUNCH,
    WHO,
    WSTF_FOLDER,
    Clock,
    Spy,
    drop,
    hend,
)

HEND_TARGET = SweepTarget(f"Clients/{HEND_FOLDER}", HEND, "w-val", "monthly-refresh")


# ------------------------------------------------------------------- bind


def test_a_file_outside_the_bound_folder_is_refused_unread(
    inbox: Path, port: Spy, roster: ProjectRoster, config: ConfigStore
) -> None:
    drop(inbox, f"Clients/{WSTF_FOLDER}/TB_FY25.xlsx", "x")
    binder = EngagementBinder(roster, config)
    with pytest.raises(RegistryError) as refused:
        binder.bind(FileRef(f"Clients/{WSTF_FOLDER}/TB_FY25.xlsx"), HEND_TARGET)
    assert refused.value.diagnostic.code == "INTAKE.NO_ENGAGEMENT"
    assert port.touched == []


def test_a_paused_engagement_is_refused_at_binding_even_if_the_planner_said_yes(
    inbox: Path, port: Spy, roster: ProjectRoster, config: ConfigStore
) -> None:
    """The planner's answer is not trusted twice. Binding checks the roster itself."""
    binder = EngagementBinder(roster, config)
    roster.set_state(HEND, RosterState.PAUSED, who=WHO, reason="hold")
    with pytest.raises(RegistryError) as refused:
        binder.bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET)
    assert refused.value.diagnostic.code == "INTAKE.NO_ENGAGEMENT"
    assert "paused" in refused.value.diagnostic.detail


def test_binding_names_exactly_one_engagement(roster: ProjectRoster, config: ConfigStore) -> None:
    bound = EngagementBinder(roster, config).bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET)
    assert bound.engagement_id == HEND and bound.watch_id == "w-val"
    assert bound.document_type == "trial_balance" and bound.filename == "TB_FY25.xlsx"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("TB_FY25.xlsx", "trial_balance"),
        ("Henderson income statement FY25.pdf", "financial_statements"),
        ("DDR response - round 2.pdf", "ddr_response"),
        ("Schedule_C_final(2).pdf", None),
        ("TB_FY25 and income statement.xlsx", None),
    ],
)
def test_document_type_binds_by_convention_or_not_at_all(
    config: ConfigStore, filename: str, expected: str | None
) -> None:
    """Two matching types is an ambiguity, and an ambiguity is not a binding."""
    assert bind_document_type(filename, config.conventions()) == expected


# ------------------------------------------------------------- fingerprint


def test_the_source_id_is_the_sha256_of_the_bytes(
    inbox: Path,
    port: Spy,
    roster: ProjectRoster,
    config: ConfigStore,
    intake_store: IntakeStore,
    clock: Clock,
) -> None:
    expected = drop(inbox, hend("TB_FY25.xlsx"), "trial balance bytes")
    bound = EngagementBinder(roster, config).bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET)
    record = Fingerprinter(port, intake_store, clock=clock).take(bound)

    assert record is not None
    assert (
        record.source_id
        == expected
        == "sha256:" + hashlib.sha256(b"trial balance bytes").hexdigest()
    )
    assert record.bytes == len(b"trial balance bytes")
    assert record.mime.endswith("spreadsheetml.sheet") and record.kind == "spreadsheet"
    assert record.source_version == 1 and record.state == "pending"
    assert record.received_at == "2026-09-03T04:00:00.000000Z"
    assert record.path == hend("TB_FY25.xlsx")


def test_a_reupload_with_different_bytes_is_version_two(
    inbox: Path, port: Spy, roster: ProjectRoster, config: ConfigStore, intake_store: IntakeStore
) -> None:
    binder = EngagementBinder(roster, config)
    printer = Fingerprinter(port, intake_store)
    drop(inbox, hend("TB_FY25.xlsx"), "v1")
    first = printer.take(binder.bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET))
    drop(inbox, hend("TB_FY25.xlsx"), "v2 - corrected")
    second = printer.take(binder.bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET))

    assert first is not None and second is not None
    assert first.source_id != second.source_id
    assert (first.source_version, second.source_version) == (1, 2)
    assert [r.source_version for r in intake_store.versions_of(HEND, "TB_FY25.xlsx")] == [1, 2]


def test_the_same_bytes_again_are_not_a_new_version(
    inbox: Path, port: Spy, roster: ProjectRoster, config: ConfigStore, intake_store: IntakeStore
) -> None:
    binder = EngagementBinder(roster, config)
    printer = Fingerprinter(port, intake_store)
    drop(inbox, hend("TB_FY25.xlsx"), "same")
    assert printer.take(binder.bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET)) is not None
    assert printer.take(binder.bind(FileRef(hend("TB_FY25.xlsx")), HEND_TARGET)) is None
    assert len(intake_store.files(HEND)) == 1


def test_a_file_of_no_declared_type_is_held_not_processed(
    inbox: Path, intake: Intake, intake_store: IntakeStore
) -> None:
    drop(inbox, hend("Schedule_C_final(2).pdf"), "what is this")
    result = intake.sweep(LAUNCH)
    assert [r.filename for r in result.held] == ["Schedule_C_final(2).pdf"]
    assert result.arrived == []
    (held,) = intake_store.held(HEND)
    assert held.document_type is None and held.state == "held"
    assert intake_store.current_set(HEND) == (), "a held file is never in the set"


def test_an_unreadable_file_stops_rather_than_proceeding_with_a_null_id(
    inbox: Path, intake: Intake, port: Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    drop(inbox, hend("TB_FY25.xlsx"), "fine")
    drop(inbox, hend("financials FY25.xlsx"), "also fine")
    from registries.errors import UNREADABLE_FILE, diagnose

    real_stat = port.inner.stat

    def failing_stat(ref: FileRef):  # noqa: ANN202
        if "financials" in ref.path:
            raise RegistryError(diagnose(UNREADABLE_FILE, "disk error", locator=ref.path))
        return real_stat(ref)

    monkeypatch.setattr(port.inner, "stat", failing_stat)
    result = intake.sweep(LAUNCH)
    assert [(p.rsplit("/", 1)[-1], c) for p, c in result.refused] == [
        ("financials FY25.xlsx", "INTAKE.UNREADABLE_FILE")
    ]
    assert [r.filename for r in result.arrived] == ["TB_FY25.xlsx"]
    assert all(r.source_id.startswith("sha256:") for r in result.arrived)


def test_kinds() -> None:
    assert kind_of("application/pdf") == "document"
    assert kind_of("text/csv") == "spreadsheet"
    # An image was `other` and reached no reader at all, which is most of what arrives
    # after a phone call - a screenshot of a trial balance, a photograph of a page. It is a
    # page with no text layer, which is what a scanned PDF page is, so it is a document and
    # goes to the same reader (P155).
    assert kind_of("image/png") == "document"
    assert kind_of("image/tiff") == "document"
    assert kind_of("application/zip") == "other", "and something with no reader still is"


def test_nothing_is_read_before_it_is_bound() -> None:
    """Structural: the local source lists; only the fingerprinter stats or reads, and
    it takes a Bound, not a FileRef."""
    import inspect

    from intake.fingerprint import Fingerprinter
    from intake.local import LocalIntake

    assert "read" not in inspect.getsource(LocalIntake) or "never reads" in inspect.getsource(
        LocalIntake
    )
    assert "bound: Bound" in inspect.getsource(Fingerprinter.take)

"""Two things a generated client engagement taught the driver.

Both found by standing the real process up and putting realistically shaped workbooks
through it, then driving a run twice - which is what a resume is. Neither could be seen by
a test built on fixtures, because a fixture is shaped like a test and a client file is
shaped like an accountant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from graph.execute import StepOutcome
from ops.models import RunState
from tests.p17.conftest import build_xlsx
from tests.p35.test_run_driver import _intake, _replaying, set_up
from workers.driver import RunDriver

STATEMENT = [
    ["Henderson Manufacturing"],
    ["Statement of Income"],
    ["For the fiscal years ended December 31"],
    ["($000s)"],
    [],
    ["Account", "FY2024", "FY2025"],
    ["Revenue", 4_200.0, 4_650.0],
    ["Cost of sales", -2_100.0, -2_310.0],
    ["Officer compensation", -420.0, -455.0],
]


def release_statements(world: dict[str, Any]) -> str:
    from tests.p16.conftest import LAUNCH, drop

    folder = "Clients/Henderson Manufacturing/2026 ESOP"
    drop(world["inbox"], f"{folder}/Henderson Income Statement FY2025.xlsx",
         build_xlsx({"Income Statement": STATEMENT}))
    drop(world["inbox"], f"{folder}/TB_FY25.xlsx", build_xlsx({"TB": [
        ["Henderson Manufacturing - Trial Balance"],
        ["As of December 31, 2025"],
        ["Actual dollars"],
        [],
        ["Account #", "Account name", "Debit", "Credit"],
        [1000, "Cash", 125_000, ""], [6000, "Officer compensation", 455_000, ""],
        [4000, "Product sales", "", 4_650_000],
    ]}))
    intake = _intake(world)
    intake.sweep(LAUNCH)
    world["clock"].advance(minutes=31)
    (launched,) = intake.sweep(LAUNCH).launched
    return str(launched.run_id)


# ------------------------------------------------------------- a resume sees the same file


def test_a_resumed_run_sees_the_scale_the_first_pass_detected(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The first pass read the workbooks and detected `($000s)`. The second pass rebuilt
    the sources from the parse store with no scale at all, and the timing skill escalated
    "has no settled scale" on a file whose header said thousands. A resume that changes
    the answer is not a resume."""
    set_up(world)
    run_id = release_statements(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver: RunDriver = driver_for(_replaying(world))

    first = driver(run_id)
    first_sources = driver._read_sources(run_id, "HEND-2026-04")  # noqa: SLF001
    assert first_sources, "the first pass read something"
    statement = next(s for s in first_sources if "Income" in s.filename)
    assert statement.scale == 1000, "detected on the first pass"

    second = driver(run_id)
    again = driver._read_sources(run_id, "HEND-2026-04")  # noqa: SLF001
    resumed = next(s for s in again if "Income" in s.filename)

    assert resumed.scale == 1000, "and remembered on the second, not re-derived as None"
    assert resumed.document_type == statement.document_type
    assert resumed.period_type == statement.period_type
    assert resumed.ambiguous == statement.ambiguous
    assert first.blocked_on == second.blocked_on, "the same frontier"
    assert not [
        s for s in second.executed if s in first.executed
    ], "and nothing done twice"


def test_the_detection_is_on_the_record_where_a_person_would_read_it(
    world: dict[str, Any], driver_for: Any
) -> None:
    """It comes from the intake.read event rather than a side table, because that event
    is the one a person reads to know what the reader decided about a file."""
    set_up(world)
    run_id = release_statements(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver_for(_replaying(world))(run_id)

    reads = [e for e in world["store"].events(run_id) if e.type == "intake.read"]
    assert reads
    for event in reads:
        for key in (
            "document_type", "scale", "currency", "period_type", "period_ends", "ambiguous",
        ):
            assert key in event.payload, key


# ------------------------------------------------------------- the firm's own people


def test_the_reviewer_is_not_a_client_identifier(world: dict[str, Any], driver_for: Any) -> None:
    """The engagement profile names who reviews this work. The first driver listed that
    address for masking, and since the profile travels to the model verbatim as context,
    the outbound scan found it unmasked and quarantined every run on the firm's own
    metadata. The scan was right and the list was wrong."""
    set_up(world)
    run_id = release_statements(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver: RunDriver = driver_for(_replaying(world))

    entry = world["roster"].get("HEND-2026-04")
    profile = world["config"].profile("HEND-2026-04") or {}
    assert profile.get("checkpoint_policy", {}).get("owner"), "the profile names a reviewer"

    identifiers = driver._identifiers(entry, profile)  # noqa: SLF001
    assert {i.kind for i in identifiers} == {"CLIENT"}, "client identifiers, nothing else"
    assert [i.value for i in identifiers] == ["Henderson Manufacturing", "Henderson"]
    assert all(profile["checkpoint_policy"]["owner"] not in i.value for i in identifiers)

    report = driver(run_id)
    failed = [
        e for e in world["store"].events(run_id)
        if e.type == "guard.payload_scan.fail"
    ]
    assert not failed, "a run is not quarantined by its own reviewer's address"
    assert report.outcomes["intake"] is StepOutcome.EXECUTED


def test_the_client_name_is_still_masked(world: dict[str, Any], driver_for: Any) -> None:
    """What the list is for."""
    set_up(world)
    run_id = release_statements(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    port = _replaying(world)
    driver_for(port)(run_id)

    assert port.requests, "the run reached the model"
    sent = port.requests[0].messages[0].content
    assert "Henderson Manufacturing" not in sent
    # The surname on its own, too. It reaches the payload through the filename - "Henderson
    # Income Statement FY2025.xlsx" - and names the client as surely as the full name does.
    assert "Henderson" not in sent, "the distinctive word of the name is masked on its own"
    assert "[[CLIENT_" in sent


def test_the_files_here_are_shaped_like_an_accountants(world: dict[str, Any]) -> None:
    """The point of the file. A four-line title block with the scale on row four, and a
    trial balance with an account-number column - neither of which any fixture had."""
    folder = Path("Clients/Henderson Manufacturing/2026 ESOP")
    assert STATEMENT[3] == ["($000s)"]
    assert STATEMENT[5][0] == "Account"
    assert folder.parts[0] == "Clients"

"""P88 - A connection test that says which part failed.

The value of this button is not the tick. It is that when there is no tick, the report
names the one screen to open: `.env`, the Box developer console, or the folder's URL.
Every test here is about that distinction surviving.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin.connection import BOX_STEPS, ConnectionReport, Step, probe_box
from ports.storage.box import BoxStorage
from tests.fake_box import ROOT_ID, Credentials, FakeBox, without


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "TB_FY25.xlsx").write_bytes(b"trial balance")
    return tmp_path


def box_for(folder: Path, **kwargs: Any) -> BoxStorage:
    return BoxStorage(
        kwargs.pop("root", ROOT_ID),
        secrets=Credentials(),
        transport=FakeBox(folder, **kwargs).transport(),
    )


def status_of(report: ConnectionReport) -> dict[str, str]:
    return {s.id: s.status for s in report.steps}


# ============================================================ the happy answer


def test_all_four_steps_pass_against_a_box_that_answers(folder: Path) -> None:
    report = probe_box(box_for(folder), Credentials())
    assert report.connected
    assert status_of(report) == {
        "credentials": "pass",
        "token": "pass",
        "folder": "pass",
        "file": "pass",
    }


def test_every_step_is_asked_and_none_is_quietly_dropped(folder: Path) -> None:
    """The four are the contract. A step removed later would make a green report mean
    less without looking any different, which is the failure this whole file is about."""
    report = probe_box(box_for(folder), Credentials())
    assert [s.id for s in report.steps] == [step_id for step_id, _ in BOX_STEPS]
    assert len(BOX_STEPS) == 4


def test_the_report_says_what_it_proves_and_it_is_about_a_moment(folder: Path) -> None:
    """A tick that reads as a standing guarantee is worse than no tick: tokens expire and
    permissions get revoked, and somebody would trust a result from last Tuesday."""
    shown = probe_box(box_for(folder), Credentials()).as_dict()
    assert "when the button was pressed" in shown["proves"]


# ============================================================ which screen to open


def test_a_missing_credential_stops_at_the_first_step(folder: Path) -> None:
    """And the other three say they were not reached. A folder marked failed when the
    credentials were never set would send somebody to Box to fix a folder id that is
    fine."""
    report = probe_box(box_for(folder), without("BOX_USER_ID"))
    assert not report.connected
    assert status_of(report) == {
        "credentials": "fail",
        "token": "not reached",
        "folder": "not reached",
        "file": "not reached",
    }
    assert report.failed is not None and report.failed.id == "credentials"
    assert "BOX_USER_ID" in report.failed.detail


def test_a_refused_token_fails_at_the_token_and_not_at_the_folder(folder: Path) -> None:
    """The distinction the whole module exists for. The credentials are set, so step one
    passes; Box will not issue a token, so step two fails; and the folder - which may be
    perfectly correct - is never blamed."""
    report = probe_box(box_for(folder, refuse_token="unauthorized_client"), Credentials())
    assert status_of(report)["credentials"] == "pass"
    assert status_of(report)["token"] == "fail"
    assert status_of(report)["folder"] == "not reached"
    assert report.failed is not None
    assert "Generate User Access Tokens" in report.failed.detail


def test_a_wrong_folder_id_fails_at_the_folder_with_the_token_already_good(
    folder: Path,
) -> None:
    """A credential problem and a folder problem are different repairs, and this is the
    ordering that tells them apart. The token passing is the evidence that the
    credentials are not what is wrong."""
    report = probe_box(box_for(folder, root="nosuchfolder"), Credentials())
    assert status_of(report)["token"] == "pass"
    assert status_of(report)["folder"] == "fail"
    assert status_of(report)["file"] == "not reached"


def test_each_failure_names_its_own_repair(folder: Path) -> None:
    """Which step failed is already covered above. What this adds is that the *words* are
    different too - each report says what to go and do, rather than three faults that
    differ only by which row is red.

    A person who has to work out the repair from the position of a red dot will stop
    pressing the button.
    """
    missing = probe_box(box_for(folder), without("BOX_CLIENT_ID")).failed
    refused = probe_box(box_for(folder, refuse_token="unauthorized_client"), Credentials()).failed
    wrong_folder = probe_box(box_for(folder, root="nosuchfolder"), Credentials()).failed
    assert missing and refused and wrong_folder

    assert ".env" in missing.detail, "a credential nobody set is fixed in a file"
    assert "Generate User Access Tokens" in refused.detail, "in the Box app's settings"
    where = wrong_folder.diagnostic.locator if wrong_folder.diagnostic else ""
    assert "box:folder/nosuchfolder" in where, "a folder id is fixed by looking at the folder"
    assert len({missing.detail, refused.detail, wrong_folder.detail}) == 3


# ============================================================ what is not a failure


def test_an_empty_folder_is_a_connection(tmp_path: Path) -> None:
    """A Monday morning before anything has arrived is a normal state. A test that called
    it a failure would be ignored by Wednesday."""
    report = probe_box(box_for(tmp_path), Credentials())
    assert report.connected
    assert status_of(report)["folder"] == "pass"
    assert status_of(report)["file"] == "not reached"
    assert "empty" in dict((s.id, s.detail) for s in report.steps)["file"]


def test_not_reached_does_not_make_a_report_disconnected() -> None:
    """The property that makes the empty-folder case work, stated on its own so a change
    to `connected` cannot quietly take it away."""
    report = ConnectionReport(
        service="box",
        ran_at="now",
        steps=(Step("a", "a", "pass", ""), Step("b", "b", "not reached", "")),
    )
    assert report.connected


# ============================================================ what may not leak


def test_testing_a_credential_never_reads_one(folder: Path) -> None:
    """`has()` exists so a check can report 'BOX_USER_ID is missing' without there being a
    code path able to print one that is not."""
    asked: list[str] = []

    class Watched(Credentials):
        def has(self, key: str) -> bool:
            asked.append(f"has:{key}")
            return super().has(key)

        def get(self, key: str) -> Any:
            asked.append(f"get:{key}")
            return super().get(key)

    report = probe_box(box_for(folder), Watched())
    # The adapter reads values to build a token - that is its job. This watches the
    # *connection test's* own secrets object, which must only ever ask presence.
    assert report.connected
    assert [a for a in asked if a.startswith("get:")] == []
    assert "has:BOX_USER_ID" in asked


def test_no_credential_value_appears_in_the_report(folder: Path) -> None:
    secrets = Credentials(BOX_CLIENT_SECRET="hunter2-the-real-one")
    shown = str(probe_box(box_for(folder), secrets).as_dict())
    assert "hunter2" not in shown


def test_the_user_id_is_shown_because_the_wrong_person_looks_like_an_empty_folder(
    folder: Path,
) -> None:
    """An account id is not a credential, and showing it is how somebody notices the token
    is being issued for the wrong person - which otherwise presents as a folder that has
    nothing in it."""
    report = probe_box(box_for(folder), Credentials())
    assert "1234567" in dict((s.id, s.detail) for s in report.steps)["token"]


def test_nothing_the_test_read_is_written_anywhere(folder: Path, tmp_path: Path) -> None:
    """The file step downloads a client's document to prove the call works. It is counted
    and dropped; the report carries a name and a length and not a byte of content."""
    (folder / "TB_FY25.xlsx").write_bytes(b"SECRET-CLIENT-NUMBERS-8675309")
    shown = str(probe_box(box_for(folder), Credentials()).as_dict())
    assert "8675309" not in shown
    assert "TB_FY25.xlsx" in shown


# ============================================================ the trap worth closing


def test_a_green_test_does_not_claim_runs_are_reading_box(folder: Path) -> None:
    """The test builds a Box adapter deliberately, so it passes whether or not
    AA_STORAGE_ADAPTER names box. Four ticks with every sweep still reading the local
    folder is a thing somebody would have no reason to suspect."""
    report = probe_box(box_for(folder), Credentials(), in_use=False)
    assert report.connected and not report.in_use
    assert "AA_STORAGE_ADAPTER=box" in report.report()
    assert report.as_dict()["in_use"] is False


def test_when_it_is_the_adapter_in_use_the_note_is_not_shown(folder: Path) -> None:
    """A warning that is always there is furniture."""
    assert "AA_STORAGE_ADAPTER=box" not in probe_box(box_for(folder), Credentials()).report()


# ============================================================ the route and the button


def test_the_console_refuses_a_service_it_has_no_test_for() -> None:
    """A service nobody wrote a probe for is refused and the ones that exist are named.

    Answering a request for an unknown service with a plausible-looking failure report
    would be worse than refusing: it would read as "that service is broken" rather than
    "there is no such thing here".
    """
    from admin.console import AdminRefused

    console = _console()
    with pytest.raises(AdminRefused) as refused:
        console.test_connection("dropbox")
    detail = refused.value.diagnostic.detail
    assert "dropbox" in detail
    assert "box" in detail and "sharefile" in detail, "it names what does exist"


def test_the_button_on_the_page_reaches_an_action_that_exists() -> None:
    """P81 found a button wired to a name nothing defined, on a fresh install, as the
    first thing anybody would press. This is that check for this button."""
    from admin.page import PAGE as html
    assert 'data-act="testBox"' in html
    assert "ACTIONS.testBox" in html
    assert "onclick=" not in html, "values reach a handler through data- attributes"


def test_the_route_is_a_post_because_it_costs_a_round_trip() -> None:
    """A GET invites a browser, a proxy or a preloader to repeat it unasked, and this one
    talks to a third party every time."""
    source = (Path(__file__).resolve().parents[2] / "admin" / "app.py").read_text(
        encoding="utf-8"
    )
    assert '@app.post("/api/admin/connection/{service}")' in source


def _console() -> Any:
    """The smallest console that can answer. Built rather than fixtured because the only
    method under test here refuses before touching anything."""
    from unittest.mock import Mock

    from admin.console import AdminConsole

    preflight = Mock()
    preflight.secrets = Credentials()
    return AdminConsole(Mock(), Mock(), preflight, constraints=Mock())

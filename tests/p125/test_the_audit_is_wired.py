"""P125, second half: the audit is reachable by a run and by a person.

An engine nothing calls is this build's most repeated defect, and the one P82's scan was
written to catch. So the audit has three ways in, and each is tested here:

1. **every workbook a run releases**, recorded as `release.audited` - and *recorded*, never
   refused. QC decides what is released; this says what to look at in what was.
2. **the console's deliverables panel**, which re-derives the audit from the released bytes
   through the same digest check the download goes through.
3. **the command line**, which is what a person standing in front of last year's model has.

The one that needs saying out loud is (1): a release must not be able to fail *because* of
this. A formula in the firm's own pinned template being wrong is not this build's call to
make, and a gate that stopped every delivery over a convention finding would be turned off
within a week - after which none of the other two would be trusted either.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from deliver.audit import AUDITED_SUFFIXES
from deliver.qc import DeliverableQC
from deliver.release import ReleaseGate
from ops.console.app import PAGE as ACTIVITY
from ops.console.app import Console, create_app
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, Clock, clean_run
from tests.p23.conftest import delivery as delivery  # noqa: PLC0414 - the fixture, reused
from tests.workbooks import a_model, a_tidy_model, with_cached_values

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "run_p125"
PLAN_HASH = "sha256:" + "a1" * 32


@pytest.fixture
def gate(store: SqlRunStore, bus: EventBus, delivery: Any) -> Iterator[ReleaseGate]:
    """A release gate over a real store, bus and delivery folder, and a started run."""
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash=PLAN_HASH,
        versions={
            "model_pin": "claude-opus-5 @ effort=high",
            "skills": ["model-load@0.1.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "1.0.0",
        },
        tieout_tolerance=1.0,
    )
    store.transition(RUN_ID, RunState.RUNNING)
    yield ReleaseGate(store, bus, delivery, DeliverableQC(bus))


def _events(store: SqlRunStore, kind: str) -> list[Any]:
    return [e for e in store.events(RUN_ID) if e.type == kind]


# ------------------------------------------------- 1. every workbook a run releases


def test_a_released_workbook_is_audited_and_the_findings_are_in_the_record(
    gate: ReleaseGate, store: SqlRunStore
) -> None:
    out = gate.release(RUN_ID, ENGAGEMENT, "input-help.xlsx", a_model())
    assert not out.already_released

    (audited,) = _events(store, "release.audited")
    payload = audited.payload
    assert payload["artifact"] == "input-help.xlsx"
    assert payload["counts"]["wrong"] >= 2
    checks = {f["check"] for f in payload["findings"]}
    assert "total_misses_rows" in checks
    assert "total_counts_a_total" in checks
    assert audited.level == "warn", "a workbook that disagrees with itself is not info"


def test_the_audit_does_not_stop_the_release(
    gate: ReleaseGate, store: SqlRunStore, delivery: Any
) -> None:
    """The invariant this wire has to keep. The file is delivered; the findings are a
    record. Anything else and the first wrong formula in the firm's own template would
    stop every engagement.

    The bytes are built once and compared against themselves. Two calls to `a_model()`
    are not byte-identical - openpyxl stamps `docProps/core.xml` with the time it wrote
    the file - so a test comparing one call with another passes or fails depending on
    which side of a second it ran, which is how a suite acquires a flake."""
    data = a_model()
    out = gate.release(RUN_ID, ENGAGEMENT, "input-help.xlsx", data)
    delivered = Path(delivery.root) / out.path
    assert delivered.is_file()
    assert delivered.read_bytes() == data
    assert _events(store, "release.blocked") == []
    assert store.artifacts(RUN_ID)


def test_a_clean_workbook_is_audited_too_and_says_so(
    gate: ReleaseGate, store: SqlRunStore
) -> None:
    """A guard that only speaks when it fires is, on a quiet day, indistinguishable from
    a guard that never ran - the event schema's own words, and the reason a clean audit
    is emitted rather than skipped."""
    gate.release(RUN_ID, ENGAGEMENT, "clean.xlsx", a_tidy_model())
    (audited,) = _events(store, "release.audited")
    assert audited.level == "info"
    assert audited.payload["counts"] == {"wrong": 0, "suspect": 0, "convention": 0}
    assert audited.payload["findings"] == []
    assert audited.payload["did_not_run"], "the footing check could not run; it says so"


def test_what_the_audit_could_not_evaluate_travels_with_it(
    gate: ReleaseGate, store: SqlRunStore
) -> None:
    """A partly recalculated file. The number of totals the footing check could not run
    on is in the record, so nobody reads the silence as a pass."""
    data = with_cached_values(a_tidy_model(), {"IS": {"C9": 188.0}})
    gate.release(RUN_ID, ENGAGEMENT, "half-saved.xlsx", data)
    (audited,) = _events(store, "release.audited")
    assert any("could not run on 2" in note for note in audited.payload["did_not_run"])


def test_only_a_workbook_is_audited(gate: ReleaseGate, store: SqlRunStore) -> None:
    """There are no formulas in a manifest, and an audit event about one would be noise
    in the only record a run leaves.

    Released under a name QC accepts but the audit does not recognise, because QC runs
    first and refuses anything that is not a workbook at all - so the *bytes* have to be
    a workbook for this to reach the line under test. What is being asserted is that the
    decision is made on the name, which is what the delivery path has to go on."""
    gate.release(RUN_ID, ENGAGEMENT, "carried-across.csv", a_model())
    assert _events(store, "release.audited") == []
    assert ".csv" not in AUDITED_SUFFIXES and ".json" not in AUDITED_SUFFIXES
    assert store.artifacts(RUN_ID), "and it was still delivered"


def test_an_audit_that_raises_is_recorded_as_not_having_run(
    gate: ReleaseGate, store: SqlRunStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absence is never a pass. If the audit itself breaks, the release proceeds and the
    record says the audit did not happen - rather than a release with no audit event,
    which reads identically to a clean one."""
    import deliver.release as release_module

    def explode(_data: bytes, **_kw: Any) -> Any:
        raise RuntimeError("openpyxl fell over")

    monkeypatch.setattr(release_module, "audit_workbook", explode)
    out = gate.release(RUN_ID, ENGAGEMENT, "input-help.xlsx", a_tidy_model())
    assert out.path, "the release still happened"
    (skipped,) = _events(store, "release.audit_skipped")
    assert "openpyxl fell over" in skipped.payload["reason"]
    assert skipped.level == "warn"


def test_a_replayed_release_is_not_audited_twice(
    gate: ReleaseGate, store: SqlRunStore
) -> None:
    """The ledger's whole purpose: a delivery that succeeded and whose acknowledgement
    was lost is retried, and the second attempt is a no-op. An audit event per attempt
    would make the record say the file was checked twice and leave a reviewer wondering
    which answer was about which file."""
    data = a_model()  # the same bytes twice, or the ledger sees two different artifacts
    gate.release(RUN_ID, ENGAGEMENT, "input-help.xlsx", data)
    gate.release(RUN_ID, ENGAGEMENT, "input-help.xlsx", data)
    assert len(_events(store, "release.replayed")) == 1
    assert len(_events(store, "release.audited")) == 1


# --------------------------------------------------------- 2. the console's route


@pytest.fixture
def delivered(store: SqlRunStore, bus: EventBus, delivery: Any) -> TestClient:
    """A workbook in the delivery folder, recorded as this run's artifact - the state the
    console finds after a release, built the way `tests/p43` builds it."""
    clean_run(store, bus)
    data = a_model()
    placed = Path(delivery.root) / ENGAGEMENT / "run_clean" / "input-help.xlsx"
    placed.parent.mkdir(parents=True, exist_ok=True)
    placed.write_bytes(data)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    store.record_artifact(
        "run_clean", "input-help.xlsx", digest, path=f"{ENGAGEMENT}/run_clean/input-help.xlsx"
    )
    store.record_artifact("run_clean", "run_manifest.json", digest, path="manifest.json")
    return TestClient(create_app(Console(store, bus, clock=Clock())))


def test_the_console_audits_a_delivered_workbook(delivered: TestClient) -> None:
    answer = delivered.get("/api/runs/run_clean/artifacts/input-help.xlsx/audit")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["formulas"] > 0
    assert {f["check"] for f in body["findings"]} >= {"total_misses_rows"}
    assert body["sheets"] == ["IS"]


def test_the_console_refuses_to_audit_something_with_no_formulas_in_it(
    delivered: TestClient,
) -> None:
    refused = delivered.get("/api/runs/run_clean/artifacts/run_manifest.json/audit")
    assert refused.status_code == 409
    assert "no formulas" in refused.text


def test_a_workbook_changed_since_release_is_not_audited_as_the_deliverable(
    delivered: TestClient, delivery: Any
) -> None:
    """The digest check, through the audit route. An audit of whatever is at that path
    now would be an audit of a file nobody released, reported as though it were one."""
    placed = Path(delivery.root) / ENGAGEMENT / "run_clean" / "input-help.xlsx"
    placed.write_bytes(a_tidy_model())
    answer = delivered.get("/api/runs/run_clean/artifacts/input-help.xlsx/audit")
    assert answer.status_code == 409 and "changed since it was released" in answer.text


def test_the_convention_findings_are_asked_for_rather_than_default(
    delivered: TestClient,
) -> None:
    assert delivered.get(
        "/api/runs/run_clean/artifacts/input-help.xlsx/audit"
    ).json()["findings"] == delivered.get(
        "/api/runs/run_clean/artifacts/input-help.xlsx/audit?convention=false"
    ).json()["findings"]


def test_the_download_and_the_audit_read_the_file_the_same_way() -> None:
    """Both routes serve bytes that were released, and both check the digest the release
    recorded. Two copies of that check is two chances for one of them to stop checking,
    and the one that stopped would be the one serving a file nobody released - so there
    is one helper and this asserts both routes call it."""
    tree = ast.parse((ROOT / "ops" / "console" / "app.py").read_text(encoding="utf-8"))
    routes = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in ("download", "audit_artifact")
    }
    assert set(routes) == {"download", "audit_artifact"}
    for name, node in routes.items():
        calls = {
            n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "_released" in calls, f"{name} reads a delivered file without the digest check"


def test_the_run_detail_offers_the_check_rather_than_running_it_on_load() -> None:
    """Reading every formula in a workbook is work, and the answer changes the first time
    somebody opens the file in Excel and saves it. A button is the honest shape."""
    assert "async function auditFile(" in ACTIVITY
    assert "ACTIONS.auditFile" in ACTIVITY
    assert "Check formulas" in ACTIVITY
    assert "data-act=" not in ACTIVITY.split("Check formulas")[0][-400:], (
        "the button must carry its values through data(), not through interpolated markup"
    )


# ------------------------------------------------------------- 3. the command line


def test_the_command_line_says_what_is_wrong_and_exits_nonzero(tmp_path: Path) -> None:
    from tools.formula_audit import main

    workbook = tmp_path / "model.xlsx"
    workbook.write_bytes(a_model())
    assert main([str(workbook)]) == 1, "a wrong formula is a non-zero exit"
    assert main([str(tmp_path / "nothing.xlsx")]) == 2, "a missing file is a different exit"

    clean = tmp_path / "clean.xlsx"
    clean.write_bytes(a_tidy_model())
    assert main([str(clean)]) == 0


def test_the_command_line_can_hand_its_answer_to_something_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--json` so a slash command, a hook or a person's own script can read it."""
    from tools.formula_audit import main

    workbook = tmp_path / "model.xlsx"
    workbook.write_bytes(a_model())
    main([str(workbook), "--json"])
    body = json.loads(capsys.readouterr().out)
    assert body["findings"]
    assert body["sheets"] == ["IS"]

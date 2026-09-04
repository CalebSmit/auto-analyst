"""Deliverable QC, the single release gate, the idempotency ledger, the narrative, and
the manifest that lists every step."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from deliver import DeliverableQC, ReleaseRefused, WorkpaperNarrative
from deliver.workpaper import words
from graph.compile import CompiledGraph
from ops.manifest import MANIFEST_CONTRACT, assemble, close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from tests.p21.conftest import (
    ENGAGEMENT,
    TEMPLATE_KEY,
    TEMPLATE_VERSION,
    build,
    events_of,
    workbook_with,
)

# ------------------------------------------------------------- QC


def test_a_produced_workbook_opens_clean(world: dict[str, Any]) -> None:
    """The exit criterion: no #REF!, no broken link, no residual token, stamped, and
    every written range holding the value the mapping gave it."""
    built = build(world)
    result = world["qc"].check(built.data, template_version=TEMPLATE_VERSION, expected=built.writes)
    assert result.passed, result.reasons
    assert result.checked > 43


@pytest.mark.parametrize(
    ("cells", "expects"),
    [
        ({"DCF!C40": "#REF!"}, "#REF!"),
        ({"Inputs!B3": "='//old-share/models/[FY24.xlsx]Sheet1'!A1"}, "external workbook"),
        ({"Inputs!B7": "Officer salary [[PERSON_1]]"}, "residual mask token"),
        ({"Inputs!C1": "=Nonexistent_Name*2"}, "not a defined name"),
        ({"Inputs!C2": "=Missing!A1"}, "does not exist"),
    ],
)
def test_qc_fails_closed_on_each_kind_of_broken_file(cells: dict[str, Any], expects: str) -> None:
    data = workbook_with({"Template_Version": "Inputs!$B$2"}, {"Inputs!B2": "9.4", **cells})
    result = DeliverableQC().check(data, template_version="9.4")
    assert not result.passed and result.code == "DELIVER.QC_FAILED"
    assert any(expects in r for r in result.reasons), result.reasons


def test_qc_checks_the_stamp_and_the_written_values(world: dict[str, Any]) -> None:
    built = build(world)
    wrong_version = world["qc"].check(built.data, template_version="9.9")
    assert not wrong_version.passed and "stamped '9.4'" in wrong_version.reasons[0]
    altered = dict(built.writes)
    altered["Revenue_FY1"] = 1.0
    drifted = world["qc"].check(built.data, template_version=TEMPLATE_VERSION, expected=altered)
    assert not drifted.passed and "Revenue_FY1 holds" in drifted.reasons[0]


def test_bytes_that_are_not_a_workbook_do_not_open() -> None:
    result = DeliverableQC().check(b"not a workbook")
    assert not result.passed and "does not open" in result.reasons[0]


# ------------------------------------------------------------- release


def test_the_release_gate_delivers_through_the_port_and_records_the_ledger(
    world: dict[str, Any], store: SqlRunStore
) -> None:
    built = build(world)
    released = world["release"].release(
        world["run_id"],
        ENGAGEMENT,
        built.name,
        built.data,
        template_version=TEMPLATE_VERSION,
        expected=built.writes,
    )
    assert not released.already_released and released.version == 1
    on_disk = world["outbox"] / released.path
    assert on_disk.is_file() and on_disk.read_bytes() == built.data
    (row,) = store.releases(world["run_id"])
    assert row.content_hash == released.content_hash and row.path == released.path
    (written,) = events_of(store, world["run_id"], "release.written")
    assert written.event_id == row.event_id, "the ledger row names the release event"
    assert written.payload["template_version"] == TEMPLATE_VERSION
    assert [a.name for a in store.artifacts(world["run_id"]) if a.name == built.name]


def test_a_replayed_release_does_not_deliver_a_second_time(
    world: dict[str, Any], store: SqlRunStore
) -> None:
    """The exit criterion. A delivery succeeds, the acknowledgement is lost, the step is
    retried: the ledger answers with the original location and the port is not asked."""
    built = build(world)
    first = world["release"].release(
        world["run_id"], ENGAGEMENT, built.name, built.data, template_version=TEMPLATE_VERSION
    )
    again = world["release"].release(
        world["run_id"], ENGAGEMENT, built.name, built.data, template_version=TEMPLATE_VERSION
    )
    assert again.already_released and again.path == first.path
    assert again.content_hash == first.content_hash
    files = sorted(p.name for p in (world["outbox"] / ENGAGEMENT / world["run_id"]).iterdir())
    assert files == [built.name], "one file, not two"
    assert world["delivery"].version(first.path) == 1
    assert len(store.releases(world["run_id"])) == 1
    assert len(events_of(store, world["run_id"], "release.written")) == 1
    assert len(events_of(store, world["run_id"], "release.replayed")) == 1


def test_a_file_that_fails_qc_is_not_released_and_the_notice_says_so(
    world: dict[str, Any], store: SqlRunStore
) -> None:
    broken = workbook_with(
        {"Template_Version": "Inputs!$B$2"}, {"Inputs!B2": TEMPLATE_VERSION, "DCF!C40": "#REF!"}
    )
    with pytest.raises(ReleaseRefused) as refused:
        world["release"].release(
            world["run_id"], ENGAGEMENT, "broken.xlsx", broken, template_version=TEMPLATE_VERSION
        )
    assert refused.value.diagnostic.code == "DELIVER.QC_FAILED"
    assert refused.value.notice.kind == "blocked_release"
    assert "was not released" in refused.value.notice.text
    assert not (world["outbox"] / ENGAGEMENT / world["run_id"]).exists()
    assert store.releases(world["run_id"]) == ()
    assert events_of(store, world["run_id"], "release.blocked")


def test_the_ledger_row_and_the_release_event_are_one_transaction(
    world: dict[str, Any], store: SqlRunStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the ledger insert fails, the release event is not left behind claiming a
    release that the ledger does not know about."""
    from ops.models import ReleaseLedgerRow

    built = build(world)
    original = ReleaseLedgerRow.__init__

    def boom(self: Any, **kw: Any) -> None:
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(ReleaseLedgerRow, "__init__", boom)
    with pytest.raises(RuntimeError):
        world["release"].release(
            world["run_id"], ENGAGEMENT, built.name, built.data, template_version=TEMPLATE_VERSION
        )
    monkeypatch.setattr(ReleaseLedgerRow, "__init__", original)
    assert events_of(store, world["run_id"], "release.written") == []
    assert store.releases(world["run_id"]) == ()


# ------------------------------------------------------------- the narrative


def test_the_narrative_renders_locked_figures_and_originates_none(
    world: dict[str, Any], contracts: ContractRegistry
) -> None:
    from tests.p20.conftest import load_case

    built = build(world)
    schedule = [
        {
            "candidate_id": "ADD-settlement",
            "category": "non_recurring",
            "amount": {
                "value": 85000.0,
                "scale": 1,
                "currency": "USD",
                "period": {"end": "2024-12-31"},
            },
            "rationale": "a settlement line present in one period only",
            "review_required": True,
            "recurs_in_all_periods": False,
        }
    ]
    locked = built.locked_text + "\n85000"
    narrative = WorkpaperNarrative().render(
        engagement_id=ENGAGEMENT,
        run_id=world["run_id"],
        template_key=TEMPLATE_KEY,
        periods=("FY2023", "FY2024", "FY2025"),
        sources=load_case()["case"]["files"],
        schedule=schedule,
        mapping=built and {"bindings": [1] * 43, "unmapped_template_inputs": []},
        open_items=[],
        locked_text=locked,
    )
    assert contracts.check("workpaper@1.0.0", narrative.body) == ()
    assert narrative.lock.passed, narrative.lock.reasons
    assert (
        "three source file(s)" in narrative.text
        and "forty-three template input(s)" in narrative.text
    )
    assert "85,000 USD" in narrative.text

    strayed = WorkpaperNarrative.check_locked(narrative.text + " and 999 more", locked)
    assert not strayed.passed and strayed.code == "GUARD.NUMERIC_DRIFT"


def test_the_narrative_contract_has_no_numeric_field(contracts: ContractRegistry) -> None:
    from tests.p02.conftest import walk_schemas

    for node in walk_schemas(contracts.get("workpaper@1.0.0")):
        assert node.get("type") not in ("number", "integer"), node
    assert (
        words(43) == "forty-three"
        and words(0) == "zero"
        and words(118) == "one hundred and eighteen"
    )


# ------------------------------------------------------------- the manifest


def test_the_manifest_lists_every_plan_step_with_never_started_ones_as_not_reached(
    world: dict[str, Any], store: SqlRunStore, plan: CompiledGraph, contracts: ContractRegistry
) -> None:
    """The P14 finding, closed: a step that never ran is on the record as not_reached,
    with no key invented for it."""
    manifest = assemble(store, world["run_id"], plan=plan)
    statuses = {s["step_id"]: s["status"] for s in manifest["steps"]}
    assert set(statuses) == set(plan.order)
    assert statuses["release"] == "not_reached"
    never = [s for s in manifest["steps"] if s["status"] == "not_reached"]
    assert never and all(s["step_key"] is None and s["attempts"] == 0 for s in never)
    # A run still going has no verdict yet; the shape is validated as if it had ended.
    contracts.validate(
        MANIFEST_CONTRACT,
        {
            **manifest,
            "outcome": "halted",
            "ended_at": manifest["started_at"],
            "scorecard": {**manifest["scorecard"], "verdict": "halted"},
        },
    )


def test_close_out_writes_the_manifest_beside_the_deliverable(
    world: dict[str, Any], store: SqlRunStore, plan: CompiledGraph, bus: Any
) -> None:
    built = build(world)
    released = world["release"].release(
        world["run_id"], ENGAGEMENT, built.name, built.data, template_version=TEMPLATE_VERSION
    )
    # Not `clean`: this run never normalized, tagged or tied anything out, and since
    # P23 a criterion the record cannot measure keeps the verdict off `pass`.
    closed = close_out(
        store,
        world["run_id"],
        RunState.DELIVERED,
        Outcome.RELEASED_WITH_REVIEW,
        world["delivery"],
        bus=bus,
        plan=plan,
    )
    folder = world["outbox"] / ENGAGEMENT / world["run_id"]
    assert (folder / "run_manifest.json").is_file() and (folder / built.name).is_file()
    body = json.loads((folder / "run_manifest.json").read_text(encoding="utf-8"))
    assert body["scorecard"]["verdict"] == "pass_with_exceptions"
    assert "deliverable_qc" not in body["scorecard"]["failed"]
    assert built.name in {a["name"] for a in body["artifacts"]}
    assert "run_manifest.json" in {a.name for a in store.artifacts(world["run_id"])}, (
        "the manifest is recorded after it is written; it cannot list itself"
    )
    assert any(s["status"] == "not_reached" for s in body["steps"])
    assert closed.run.state is RunState.DELIVERED
    assert Path(released.path).name == built.name
    wb = load_workbook(BytesIO((folder / built.name).read_bytes()))
    assert wb["Inputs"]["B2"].value == TEMPLATE_VERSION

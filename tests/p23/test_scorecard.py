"""Every run gets a scorecard with a computed verdict - the phase's first criterion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ops.events import EventBus
from ops.manifest import MANIFEST_CONTRACT, assemble, close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore
from ops.scorecard import (
    CURRENT_CRITERIA,
    OutcomeContradicted,
    RunScorecard,
    Verdict,
    criteria_versions,
    load_criteria,
)
from registries.contracts import ContractRegistry
from registries.errors import RegistryError
from tests.p23.conftest import ROOT, clean_run, halted_run, reviewed_run

CRITERIA = (
    "document_coverage",
    "period_coverage",
    "provenance",
    "tieout",
    "conflicts",
    "residual_masking",
    "numeric_integrity",
    "budget",
    "review_outstanding",
    "deliverable_qc",
)


def test_the_criteria_are_the_blueprints_ten_and_versioned() -> None:
    criteria = load_criteria()
    assert criteria.key == CURRENT_CRITERIA
    assert tuple(c.id for c in criteria.criteria) == CRITERIA
    assert CURRENT_CRITERIA in criteria_versions()
    assert set(criteria.verdicts) == {str(v) for v in Verdict}
    # The blueprint's bar, verbatim, so the two cannot drift apart unnoticed.
    html = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    for c in criteria.criteria:
        assert c.bar in html, f"{c.id}: the bar is not the blueprint's"


def test_a_clean_run_passes_every_criterion_and_the_manifest_says_so(
    store: SqlRunStore, bus: EventBus, delivery: Any, contracts: ContractRegistry
) -> None:
    clean_run(store, bus)
    result = close_out(store, "run_clean", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus)

    card = result.manifest["scorecard"]
    assert card["verdict"] == "pass" and card["failed"] == []
    assert card["criteria_version"] == CURRENT_CRITERIA
    assert [c["id"] for c in card["criteria"]] == list(CRITERIA)
    assert all(c["status"] == "pass" for c in card["criteria"])
    contracts.validate(MANIFEST_CONTRACT, result.manifest)
    scored = [e for e in store.events("run_clean") if e.type == "run.scored"]
    assert len(scored) == 1 and scored[0].node_id == "run_scorecard"
    assert scored[0].payload["verdict"] == "pass"
    written = next(e for e in store.events("run_clean") if e.type == "run.manifest.written")
    assert written.payload["verdict"] == "pass"
    assert written.payload["criteria_version"] == CURRENT_CRITERIA


def test_a_reviewed_run_passes_with_its_exceptions_named(
    store: SqlRunStore, bus: EventBus, delivery: Any
) -> None:
    reviewed_run(store, bus)
    result = close_out(
        store, "run_reviewed", RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW, delivery, bus=bus
    )
    card = result.manifest["scorecard"]
    assert card["verdict"] == "pass_with_exceptions" and card["failed"] == []
    by_id = {c["id"]: c for c in card["criteria"]}
    assert by_id["period_coverage"]["exceptions"] == [
        "gap reported: FY2022 - not provided by the client"
    ]
    assert by_id["review_outstanding"]["exceptions"] == ["li_10: corrected by Dana Whitfield"]
    assert by_id["review_outstanding"]["measured"] == "0 open, 2 decided"


def test_a_halted_run_names_the_criterion_that_failed_and_the_ones_never_reached(
    store: SqlRunStore, bus: EventBus, delivery: Any
) -> None:
    halted_run(store, bus)
    result = close_out(store, "run_halted", RunState.HALTED, Outcome.HALTED, delivery, bus=bus)
    card = result.manifest["scorecard"]
    assert card["verdict"] == "halted"
    assert card["failed"] == ["tieout", "review_outstanding"]
    by_id = {c["id"]: c for c in card["criteria"]}
    assert by_id["tieout"]["measured"] == "19 / 20 totals"
    assert by_id["deliverable_qc"] == {
        "id": "deliverable_qc",
        "label": "Deliverable QC",
        "bar": "Opens, resolves, stamped, no residual tokens",
        "status": "not_measured",
        "measured": "not reached",
        "exceptions": [],
    }
    assert by_id["numeric_integrity"]["status"] == "not_measured"
    assert by_id["budget"]["status"] == "pass"


def test_the_verdict_is_computed_not_claimed(
    store: SqlRunStore, bus: EventBus, delivery: Any
) -> None:
    """Fail closed: a claim the record does not support is refused before the run is
    ended, and nothing is written."""
    reviewed_run(store, bus)
    with pytest.raises(OutcomeContradicted) as refused:
        close_out(store, "run_reviewed", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus)
    d = refused.value.diagnostic
    assert d.code == "PROCESS.OUTCOME_CONTRADICTED" and d.owner == "system"
    assert d.expected == "pass" and d.found == "pass_with_exceptions"
    assert store.run("run_reviewed").state is RunState.RUNNING
    assert not any(e.type == "run.scored" for e in store.events("run_reviewed"))

    halted_run(store, bus)
    with pytest.raises(OutcomeContradicted) as refused:
        close_out(store, "run_halted", RunState.HALTED, Outcome.BLOCKED, delivery, bus=bus)
    assert refused.value.diagnostic.found == "halted", "a guard refused it; it did not wait"


def test_silence_is_never_a_pass(store: SqlRunStore, bus: EventBus, delivery: Any) -> None:
    """A run that never ran deliverable QC did not pass deliverable QC. The criterion
    is reported as not measured, and the verdict stays off `pass`."""
    s = clean_run(store, bus, run_id="run_quiet")
    # The same run again, with the QC guard silent.
    events = store.events("run_quiet")
    assert any(e.type == "guard.deliverable_qc.pass" for e in events)
    s2 = clean_run.__wrapped__ if hasattr(clean_run, "__wrapped__") else None
    assert s2 is None
    card = RunScorecard(store, bus).score("run_quiet", ending=(RunState.DELIVERED, Outcome.CLEAN))
    assert card.verdict is Verdict.PASS
    # Drop the QC verdict from a fresh run: score it without one.
    from tests.p23.conftest import Script

    quiet = Script(store, bus, "run_no_qc", s.engagement)
    quiet.start()
    quiet.intake()
    quiet.skill(
        "timing", "timing-normalization@0.1.0", summary={"periods": ["FY2025"], "period_gaps": []}
    )
    quiet.guard("provenance_gate", "provenance", True, 10, step_id="timing")
    quiet.guard("tieout_gate", "tieout", True, 2, step_id="timing")
    quiet.guard("reconcile", "reconcile", True, 10, step_id="timing")
    quiet.guard("numeric_lock", "numeric_lock", True, 2, step_id="timing")
    card = RunScorecard(store, bus).score("run_no_qc", ending=(RunState.DELIVERED, Outcome.CLEAN))
    assert card.verdict is Verdict.PASS_WITH_EXCEPTIONS
    assert card.not_measured == ("deliverable_qc",) and card.failed == ()
    with pytest.raises(OutcomeContradicted):
        RunScorecard(store, bus).check_claim("run_no_qc", RunState.DELIVERED, Outcome.CLEAN)


def test_a_run_still_going_has_criteria_so_far_and_no_verdict(
    store: SqlRunStore, bus: EventBus
) -> None:
    halted_run(store, bus)
    card = RunScorecard(store, bus).score("run_halted")
    assert card.in_progress and card.verdict is None
    assert "IN PROGRESS" in card.report()
    assert card.failed == ("tieout", "review_outstanding")
    manifest = assemble(store, "run_halted", bus=bus)
    assert manifest["scorecard"]["verdict"] is None, "assemble reads; it does not end the run"


def test_what_counted_as_working_is_recoverable_from_the_manifest_alone(
    store: SqlRunStore, bus: EventBus, delivery: Any
) -> None:
    """Six months later: the manifest names the criteria version, the file is still on
    disk under that name, and the bar can be read back."""
    clean_run(store, bus)
    manifest = close_out(
        store, "run_clean", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus
    ).manifest
    version = manifest["scorecard"]["criteria_version"]
    criteria = load_criteria(version)
    for row in manifest["scorecard"]["criteria"]:
        assert criteria.get(row["id"]).bar == row["bar"]


def test_an_unknown_or_unmeasurable_criteria_version_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RegistryError) as refused:
        load_criteria("run_criteria@9.9.9")
    assert refused.value.diagnostic.code == "SCOPE.UNKNOWN_CRITERIA"
    with pytest.raises(RegistryError):
        load_criteria("latest")

    import ops.scorecard as module

    (tmp_path / "run_criteria@2.0.0.yaml").write_text(
        "version: '2.0.0'\ncriteria:\n  - id: vibes\n    label: Vibes\n    bar: Feels right\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CRITERIA_DIR", tmp_path)
    with pytest.raises(RegistryError) as refused:
        load_criteria("run_criteria@2.0.0")
    assert "vibes" in refused.value.diagnostic.detail


def test_close_out_still_has_no_branch_on_how_the_run_ended() -> None:
    """The scorecard checks the claim inside its own method; close_out itself keeps the
    P04 property - no conditional mentioning state or outcome - so the manifest is
    still written for every ending that the record supports."""
    import ast

    tree = ast.parse((ROOT / "ops" / "manifest.py").read_text(encoding="utf-8"))
    close = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "close_out"
    )
    tests = [ast.unparse(n.test) for n in ast.walk(close) if isinstance(n, ast.If | ast.IfExp)]
    assert not [t for t in tests if "outcome" in t or "state" in t]

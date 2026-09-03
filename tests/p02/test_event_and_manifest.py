"""event and run_manifest - the two contracts the whole ops view is derived from."""

from __future__ import annotations

from typing import Any

import pytest

from registries.contracts import ContractRegistry
from tests.p02.conftest import SHA

EVENT = "event@1.0.0"
MANIFEST = "run_manifest@1.0.0"


@pytest.fixture
def event() -> dict[str, Any]:
    return {
        "event_id": "evt_00041",
        "ts": "2026-04-02T09:14:03Z",
        "run_id": "run_8b12",
        "engagement_id": "HEND-2026-04",
        "node_id": "provenance_gate",
        "step_id": "step_04",
        "type": "guard.provenance.pass",
        "level": "guard",
        "message": "318 of 318 figures carry source_id + locator + version",
        "payload": {"checked": 318, "failed": 0},
    }


def test_an_event_validates(contracts: ContractRegistry, event: dict[str, Any]) -> None:
    assert contracts.check(EVENT, event) == ()


def test_an_event_without_a_node_id_is_rejected(
    contracts: ContractRegistry, event: dict[str, Any]
) -> None:
    """The run trace is computed from node_id and never stored. It cannot be added
    retrospectively to runs already recorded, which is why it is required rather than
    encouraged."""
    without = {k: v for k, v in event.items() if k != "node_id"}
    assert contracts.check(EVENT, without)


def test_an_event_is_always_scoped_to_an_engagement(
    contracts: ContractRegistry, event: dict[str, Any]
) -> None:
    without = {k: v for k, v in event.items() if k != "engagement_id"}
    assert contracts.check(EVENT, without)


def test_a_guard_pass_is_an_ordinary_event(
    contracts: ContractRegistry, event: dict[str, Any]
) -> None:
    """A guard that only speaks when it fires is, on a quiet day, indistinguishable from
    a guard that never ran. Nothing in the schema privileges failures."""
    assert contracts.check(EVENT, event) == ()
    failed = {
        **event,
        "type": "guard.tieout.fail",
        "level": "error",
        "diagnostic_code": "GUARD.TIEOUT_MISMATCH",
    }
    assert contracts.check(EVENT, failed) == ()


def test_event_types_are_dotted_and_typed(
    contracts: ContractRegistry, event: dict[str, Any]
) -> None:
    for bad in ("Guard.Provenance.Pass", "guard provenance pass", "provenance", ""):
        assert contracts.check(EVENT, {**event, "type": bad}), f"{bad!r} should not validate"


def test_a_diagnostic_code_comes_from_a_declared_family(
    contracts: ContractRegistry, event: dict[str, Any]
) -> None:
    for good in ("GUARD.TIEOUT_MISMATCH", "POLICY.TOOL_NOT_DECLARED", "SKILL.FABRICATED_SOURCE"):
        assert contracts.check(EVENT, {**event, "diagnostic_code": good}) == ()
    for bad in ("OOPS.SOMETHING", "guard.tieout_mismatch", "TIEOUT_MISMATCH"):
        assert contracts.check(EVENT, {**event, "diagnostic_code": bad})


def test_the_payload_is_the_one_open_object_and_says_so(contracts: ContractRegistry) -> None:
    payload = contracts.get(EVENT)["properties"]["payload"]
    assert payload["additionalProperties"] is True
    assert "x-open-by-design" in payload


# ------------------------------------------------------------------ manifest


@pytest.fixture
def manifest() -> dict[str, Any]:
    return {
        "schema_version": "run_manifest@1.0.0",
        "run_id": "run_8b12",
        "engagement_id": "HEND-2026-04",
        "started_at": "2026-04-02T09:00:00Z",
        "ended_at": "2026-04-02T09:41:00Z",
        "outcome": "halted",
        "plan_hash": "sha256:" + "7c" * 32,
        "versions": {
            "model_pin": "claude-sonnet-5 @ effort=high",
            "skills": ["ebitda-normalization@0.1.0", "qc-tieout@0.1.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "2026.1",
            "template_version": None,
            "prompt_version": None,
        },
        "tieout_tolerance": 0.005,
        "sources": [
            {
                "source_id": SHA,
                "filename": "TB_FY23.xlsx",
                "document_type": "trial_balance",
                "source_version": 1,
                "received_at": "2026-04-01T18:02:00Z",
                "bytes": 91422,
            }
        ],
        "steps": [
            {
                "step_id": "step_04",
                "kind": "skill",
                "skill": "ebitda-normalization@0.1.0",
                "status": "completed",
                "step_key": "sha256:" + "1a" * 32,
                "attempts": 1,
                "loop": None,
            }
        ],
        "guard_events": [
            {
                "guard": "provenance_gate",
                "result": "pass",
                "checked": 318,
                "failed": 0,
                "diagnostic_code": None,
                "at": "2026-04-02T09:14:03Z",
            }
        ],
        "human_decisions": [],
        "coverage_gaps": [
            {"what": "FY2021 income statement", "why": "Not supplied by the client."}
        ],
        "artifacts": [],
        "cost": {
            "total_usd": 3.42,
            "model_calls": 11,
            "input_tokens": 84000,
            "output_tokens": 9100,
        },
    }


def test_a_manifest_validates(contracts: ContractRegistry, manifest: dict[str, Any]) -> None:
    assert contracts.check(MANIFEST, manifest) == ()


def test_a_halted_run_still_writes_a_manifest(
    contracts: ContractRegistry, manifest: dict[str, Any]
) -> None:
    """It is written unconditionally, which is the case it is most needed for. Nothing in
    the schema requires an artifact or a released deliverable."""
    assert manifest["outcome"] == "halted"
    assert manifest["artifacts"] == []
    assert contracts.check(MANIFEST, manifest) == ()


def test_the_outcome_is_not_a_boolean(contracts: ContractRegistry) -> None:
    """Conflating 'halted before producing anything' with 'delivered but three figures
    needed a person' hides exactly what a practice lead needs to see."""
    outcomes = contracts.get(MANIFEST)["properties"]["outcome"]["enum"]
    assert set(outcomes) == {"clean", "released_with_review", "halted", "blocked"}


@pytest.mark.parametrize("field", ["model_pin", "skills", "contracts", "constraints", "taxonomy"])
def test_every_version_a_run_used_is_recorded(
    contracts: ContractRegistry, manifest: dict[str, Any], field: str
) -> None:
    versions = {k: v for k, v in manifest["versions"].items() if k != field}
    assert contracts.check(MANIFEST, {**manifest, "versions": versions})


def test_guard_passes_are_in_the_manifest_not_only_failures(
    contracts: ContractRegistry, manifest: dict[str, Any]
) -> None:
    assert manifest["guard_events"][0]["result"] == "pass"
    assert contracts.check(MANIFEST, manifest) == ()


def test_every_step_carries_its_idempotency_key(
    contracts: ContractRegistry, manifest: dict[str, Any]
) -> None:
    """A retry, a resume and a manual re-run are the same operation because of this."""
    steps = [{k: v for k, v in manifest["steps"][0].items() if k != "step_key"}]
    assert contracts.check(MANIFEST, {**manifest, "steps": steps})


def test_a_coverage_gap_has_to_say_why(
    contracts: ContractRegistry, manifest: dict[str, Any]
) -> None:
    gaps = [{"what": "FY2021 income statement"}]
    assert contracts.check(MANIFEST, {**manifest, "coverage_gaps": gaps})

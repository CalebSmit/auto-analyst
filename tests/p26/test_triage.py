"""Triage: it can escalate, and there is no shape in its schema for a number."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from graph.compile import PlanContext
from graph.resolve import ResolvedScope
from guards import GuardFailed
from ops.run_store import SqlRunStore
from orchestrate import Triage
from registries.contracts import ContractRegistry
from tests.p26.conftest import (
    ENGAGEMENT,
    FALLBACK,
    ScriptedPort,
    assessment,
    events_of,
    nothing_fits,
)
from tests.p26.conftest import JobManifest as Manifest

WHY = "the orchestrator answered match: none"


def assess(world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, body: Any) -> Any:
    port = ScriptedPort(body)
    return world["triage_for"](port).assess(
        manifest=manifest, scope=scope, run_id=world["run_id"], why=WHY, owner="Dana Whitfield"
    ), port


def test_triage_has_no_field_a_number_could_be_recorded_in(
    contracts: ContractRegistry, world: dict[str, Any], scope: ResolvedScope, manifest: Manifest
) -> None:
    """The exit criterion. Not a rule triage is asked to follow: no property in the
    schema is numeric, every object is closed, and a body carrying a figure is refused
    before it reaches the record."""
    schema = contracts.get("triage@1.0.0")
    for subschema in _walk(schema):
        assert subschema.get("type") not in ("number", "integer"), subschema
        if subschema.get("type") == "object":
            assert subschema.get("additionalProperties") is False
    assert not {k for sub in _walk(schema) for k in (sub.get("properties") or {})} & {
        "value", "amount", "figure", "total", "confidence", "adjustment", "ebitda"
    }

    for smuggled in ({"estimated_ebitda": 4200000}, {"adjustment": 125000}, {"confidence": 0.4}):
        with pytest.raises(GuardFailed) as refused:
            assess(world, scope, manifest, assessment(**smuggled))
        assert refused.value.result.code == "SKILL.SCHEMA_INVALID"


def test_triage_escalates_to_a_person_and_starts_nothing(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, store: SqlRunStore
) -> None:
    result, port = assess(world, scope, manifest, assessment())
    run_id = world["run_id"]

    (item,) = store.open_review_items(ENGAGEMENT)
    assert item.item_id == result.item_id and item.kind == "clarification"
    assert item.owner == "Dana Whitfield"
    assert "unusual_structure" in item.subject
    assert item.detail["assessment"].startswith("A two-tier holding structure")
    assert item.detail["why"] == WHY
    assert item.detail["suggested_skill"] is None

    (escalated,) = events_of(store, run_id, "triage.escalated")
    assert escalated.node_id == "triage" and escalated.level == "warn"
    assert escalated.payload["item_id"] == result.item_id

    assert store.steps(run_id) == (), "nothing ran"
    assert events_of(store, run_id, "skill.dispatched") == []
    assert port.last.pin.model == "claude-opus-5", "high tier: a mistake here costs most"
    assert len(port.last.messages) == 1


def test_a_suggested_skill_outside_the_index_is_dropped_not_acted_on(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, store: SqlRunStore
) -> None:
    """A suggestion nobody can act on is worse than none: it is recorded as dropped, the
    escalation stands, and the review item does not carry it."""
    result, _ = assess(
        world, scope, manifest,
        assessment(suggested_skill="unit-award-valuation", category="no_matching_skill"),
    )
    assert result.suggested_skill is None
    assert result.dropped_suggestion == "unit-award-valuation"

    (dropped,) = events_of(store, world["run_id"], "triage.suggestion_dropped")
    assert dropped.diagnostic_code == "SCOPE.AMBIGUOUS_SKILL"
    assert "did not resolve into valuation/esop/repeat" in dropped.message

    (item,) = store.open_review_items(ENGAGEMENT)
    assert item.detail["suggested_skill"] is None
    assert item.detail["dropped_suggestion"] == "unit-award-valuation"


def test_a_suggested_skill_in_the_index_is_recorded_for_a_person_never_dispatched(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, store: SqlRunStore
) -> None:
    result, _ = assess(
        world, scope, manifest,
        assessment(suggested_skill="repurchase-obligation", category="unclear_scope",
                   escalation_reason=None),
    )
    assert result.suggested_skill == "repurchase-obligation"
    (item,) = store.open_review_items(ENGAGEMENT)
    assert "triage suggests repurchase-obligation" in item.subject
    assert "a person confirms" in item.subject
    assert store.steps(world["run_id"]) == ()
    assert events_of(world["store"], world["run_id"], "skill.dispatched") == []


def test_triage_cannot_reach_a_dispatcher_or_a_plan(world: dict[str, Any]) -> None:
    """It classifies and escalates. There is no method here that runs a skill, and no
    import that could reach one."""
    import orchestrate.triage as module

    imports = [
        line
        for line in inspect.getsource(module).splitlines()
        if line.startswith(("import ", "from "))
    ]
    for forbidden in ("harness.dispatch", "graph.execute", "graph.compile", "orchestrate.plan"):
        assert not [line for line in imports if forbidden in line], forbidden
    assert {n for n in dir(Triage) if not n.startswith("_")} == {"assess", "pin"}


def test_nothing_fits_goes_to_triage_and_the_run_still_has_a_plan(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, context: PlanContext,
    store: SqlRunStore,
) -> None:
    """The whole low-confidence path: the orchestrator says nothing fits, triage tells a
    person why, and the run proceeds on the named recipe rather than stopping."""
    orchestrator = world["orchestrator_for"](ScriptedPort(nothing_fits()))
    proposed = orchestrator.propose(manifest=manifest, scope=scope, run_id=world["run_id"])
    assert not proposed.routed

    result, _ = assess(world, scope, manifest, assessment())
    planned = world["planner"].from_recipe(FALLBACK, context, world["run_id"])

    assert planned.plan.recipe == FALLBACK and planned.refusal is None
    assert store.open_review_items(ENGAGEMENT)[0].item_id == result.item_id
    types = [e.type for e in store.events(world["run_id"])]
    assert types.index("plan.proposed") < types.index("triage.escalated")
    assert types.index("triage.escalated") < types.index("plan.compiled")


def _walk(schema: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(schema, dict):
        found.append(schema)
        for value in schema.values():
            found += _walk(value)
    elif isinstance(schema, list):
        for value in schema:
            found += _walk(value)
    return found

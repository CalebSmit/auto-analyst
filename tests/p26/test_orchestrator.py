"""The Orchestrator: the index and nothing more, a plan and never a value, and the same
inputs producing the same plan twice."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from graph.compile import PlanContext
from graph.resolve import ResolvedScope
from guards import GuardFailed
from ops.run_store import SqlRunStore
from orchestrate import Orchestrator
from registries.contracts import ContractRegistry
from registries.skills import SkillTree
from tests.p26.conftest import (
    ENGAGEMENT,
    FALLBACK,
    RUN_INPUTS,
    ScriptedPort,
    events_of,
    job_manifest,
    names_the_recipe,
    nothing_fits,
    proposal,
)
from tests.p26.conftest import JobManifest as Manifest


def propose(world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, body: Any) -> Any:
    port = ScriptedPort(body)
    orchestrator = world["orchestrator_for"](port)
    return orchestrator.propose(
        manifest=manifest, scope=scope, run_id=world["run_id"]
    ), port


def test_the_orchestrators_context_is_the_skill_index_and_never_a_skill_body(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, tree: SkillTree
) -> None:
    """The exit criterion, three ways: what was sent, what is in the module, and what the
    module could reach even if somebody wanted it to."""
    _, port = propose(world, scope, manifest, proposal())
    sent = port.sent()

    index = scope.index()
    assert len(index) >= 5
    for entry in index:
        assert f"{entry.name}: {entry.description}" in sent, entry.name

    bodies = {resolved.name: tree.body(resolved.skill) for resolved in scope.skills}
    for name, body in bodies.items():
        substantial = [line.strip() for line in body.splitlines() if len(line.strip()) > 60]
        assert substantial, name
        for line in substantial:
            assert line not in sent, f"{name}'s body reached the orchestrator: {line[:60]}"
    # The whole skill footprint, against what carrying the bodies would have cost. This
    # is the progressive-disclosure claim in one line, and it is what lets the library
    # grow into the hundreds while what the orchestrator reads stays about a dozen lines.
    assert len(index.as_prompt()) < len("".join(bodies.values())) / 2

    import orchestrate.orchestrator as module

    source = inspect.getsource(module)
    imports = [ln for ln in source.splitlines() if ln.startswith(("import ", "from "))]
    assert not [ln for ln in imports if "SkillTree" in ln or "registries.skills" in ln]
    code = [ln for ln in source.splitlines() if not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if ".body(" in ln or ".reference(" in ln]
    assert any("index.as_prompt()" in ln for ln in code)
    assert not [n for n in dir(Orchestrator) if "body" in n or "reference" in n]


def test_a_proposal_is_reproducible_the_same_inputs_give_the_same_plan_hash(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, context: PlanContext
) -> None:
    """Same manifest, same index: the same call, and the same compiled plan. A changed
    manifest is a different call - a cache miss rather than a stale answer reused."""
    first, port_a = propose(world, scope, manifest, proposal())
    second, port_b = propose(world, scope, job_manifest(), proposal())
    assert first.request_hash == second.request_hash
    assert first.manifest_hash == second.manifest_hash
    assert first.proposal_ref == second.proposal_ref
    assert port_a.sent() == port_b.sent()

    planner = world["planner"]
    plan_a = planner.from_proposal(
        first.body, context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    plan_b = planner.from_proposal(
        second.body, context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    assert plan_a.plan_hash == plan_b.plan_hash
    assert plan_a.from_proposal and plan_a.plan.recipe == "proposed"
    assert plan_a.document == plan_b.document

    other, _ = propose(
        world, scope, job_manifest(note="the client also sent the FY24 census"), proposal()
    )
    assert other.request_hash != first.request_hash, "a different manifest is a different call"
    assert other.manifest_hash != first.manifest_hash


def test_the_proposal_has_no_field_a_figure_or_a_ceiling_could_travel_in(
    contracts: ContractRegistry, world: dict[str, Any], scope: ResolvedScope, manifest: Manifest
) -> None:
    """Not a rule the orchestrator is asked to follow - a shape it has no room for."""
    schema = contracts.get("run_plan_proposal@1.0.0")
    for subschema in _walk(schema):
        assert subschema.get("type") not in ("number", "integer"), subschema
        for value in subschema.get("enum") or ():
            assert not isinstance(value, int | float), subschema
    properties = {key for sub in _walk(schema) for key in (sub.get("properties") or {})}
    assert not properties & {"confidence", "score", "value", "amount", "figure", "total"}

    with pytest.raises(GuardFailed) as refused:
        propose(world, scope, manifest, proposal(confidence=0.94))
    assert refused.value.result.code == "SKILL.SCHEMA_INVALID"
    for asked in ("max_iterations", "timeout_s", "model", "retries"):
        with pytest.raises(GuardFailed):
            propose(world, scope, manifest, proposal(**{asked: 4}))


def test_the_orchestrator_proposes_and_starts_nothing(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, store: SqlRunStore
) -> None:
    """A proposal is a plan written down, not work begun: no step ran, no skill was
    dispatched, and dispatch is directed - nothing returns here to ask again."""
    result, port = propose(world, scope, manifest, proposal())
    assert result.routed and result.match == "composed"
    assert store.steps(world["run_id"]) == ()
    assert events_of(store, world["run_id"], "skill.dispatched") == []
    assert len(port.requests) == 1, "one model call"
    assert len(port.last.messages) == 1, "one turn"

    requested = events_of(store, world["run_id"], "plan.requested")[0]
    proposed = events_of(store, world["run_id"], "plan.proposed")[0]
    assert requested.payload["index"] == list(scope.index().names())
    assert proposed.payload["skills"] == [
        "timing-normalization", "line-item-tagging", "ebitda-normalization", "qc-tieout"
    ]
    assert proposed.payload["request_hash"] == result.request_hash
    assert proposed.node_id == "orchestrator" and proposed.step_id == "plan"


def test_the_call_goes_through_the_one_door_like_any_other(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, store: SqlRunStore
) -> None:
    """Mid tier, scanned, metered, pinned. Routing over a closed set with good signal is
    not deep reasoning, and the planning call is not free."""
    result, port = propose(world, scope, manifest, proposal())
    assert port.last.pin.model == "claude-sonnet-5"
    assert world["triage_for"](port).pin().model == "claude-opus-5", "triage is high tier"

    run_id = world["run_id"]
    assert [e.type for e in store.events(run_id) if e.type.startswith("model.")] == [
        "model.called",
        "model.answered",
    ]
    assert world["meter"].spend(run_id).model_calls == 1
    assert world["meter"].spend(run_id).usd > 0
    assert [e.type for e in store.events(run_id) if e.level == "guard"], "the payload was scanned"
    assert result.request_hash.startswith("sha256:")

    wrapped = port.last.messages[0].content
    assert "job manifest" in wrapped.lower()
    assert "BEGIN" in wrapped or "<<<" in wrapped, "the manifest arrived as data, not instruction"


def test_a_proposal_naming_a_recipe_gets_the_recipe_on_disk(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest, context: PlanContext
) -> None:
    """'This is the monthly refresh' is a routing answer, not a licence to restate what
    the monthly refresh contains."""
    from graph.compile import compile_recipe
    from graph.recipes import load_recipe

    result, _ = propose(world, scope, manifest, names_the_recipe())
    planned = world["planner"].from_proposal(
        result.body, context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    assert planned.source == "proposal" and planned.refusal is None
    assert planned.plan.recipe == FALLBACK
    assert planned.plan_hash == compile_recipe(load_recipe(FALLBACK), context).plan_hash
    assert planned.document["rationale"], "why it thought so is on the record"


def test_nothing_fits_is_an_answer_the_orchestrator_can_give(
    world: dict[str, Any], scope: ResolvedScope, manifest: Manifest
) -> None:
    """Categorical, not a confidence below a threshold nobody agreed."""
    result, _ = propose(world, scope, manifest, nothing_fits())
    assert not result.routed and result.match == "none"
    assert "management incentive unit" in result.escalation_reason
    assert result.body["steps"] == [], "it proposed no plan rather than a plan it disbelieves"


def test_the_manifest_shows_documents_and_never_their_contents(manifest: Manifest) -> None:
    rendered = manifest.as_prompt()
    assert "TB_FY25.xlsx [trial_balance]" in rendered
    assert "periods: FY2025, FY2024" in rendered
    assert FALLBACK in rendered and "industry: manufacturing" in rendered
    assert ENGAGEMENT in rendered
    assert not [c for c in rendered if c == "$"], "no money reaches the orchestrator"
    assert manifest.content_hash() == job_manifest().content_hash()


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

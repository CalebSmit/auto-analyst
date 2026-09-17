"""P39: the Provenance and Tie-Out Checks run on every skill output in a live run.

The finding: the blueprint has both as step guards, and until P39 the dispatcher ran only
the schema check - the other two ran in evals and tests. A figure could reach review citing
a real row with the wrong number, or a derived total that did not re-derive. These tests
build the dispatcher the way the composition root now does and tamper with an output.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from graph.compile import Step
from graph.resolve import ResolvedScope
from guards import GuardFailed
from guards.untrusted import UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.context import ContextBuilder
from harness.dispatch import SkillDispatcher
from harness.door import ModelDoor
from harness.procedures.timing_normalization import TimingInputs, TimingNormalization
from ops.cost import CostMeter
from ops.run_store import SqlRunStore
from ops.source_parse import SourceParseStore
from privacy.mask import Masker
from privacy.payload_scan import PayloadScan
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import CITED_VALUE_ABSENT, TIEOUT_MISMATCH
from registries.skills import SkillTree
from tests.p18.conftest import CLIENT, ENGAGEMENT, PIN, ProposalPort, load_case, write_blocks
from tools.recompute import recompute


class Tampered(TimingNormalization):
    """The honest procedure, then one figure changed on the way out."""

    def __init__(self, change: Any) -> None:
        self.change = change

    def apply(self, proposal: Any, tools: Any, inputs: Any, pin: str) -> dict[str, Any]:
        output = copy.deepcopy(super().apply(proposal, tools, inputs, pin))
        figure = output["normalized_historicals"]["line_items"][0]["values"][0]
        self.change(figure)
        return output


@pytest.fixture
def guarded(
    world: dict[str, Any],
    tree: SkillTree,
    contracts: ContractRegistry,
    constraints: ConstraintRegistry,
    store: SqlRunStore,
    parse_store: SourceParseStore,
) -> Any:
    bus, blobs = world["bus"], world["blobs"]
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)

    def run(procedure: TimingNormalization, step: Step, scope: ResolvedScope) -> Any:
        inputs, proposal, _ = load_case("annual_drift")
        assert proposal is not None
        write_blocks(parse_store, world["run_id"], inputs)
        versions = {f.source_id: f.source_version for f in inputs.files}
        dispatcher = SkillDispatcher(
            tree=tree,
            context=ContextBuilder(tree, blobs, bus, store=store),
            door=ModelDoor(ProposalPort(proposal), PayloadScan(bus), governor, meter, bus),
            runtime=world["runtime"],
            contracts=contracts,
            boundary=UntrustedBoundary(bus),
            masker=Masker(world["vault"]),
            bus=bus,
            blobs=blobs,
            parse_store=parse_store,
            sources_for=lambda _run: versions,
            recompute=recompute,
            tolerance_for=lambda _run: 0.0,
        )
        return dispatcher.run(
            step=step,
            run_id=world["run_id"],
            engagement_id=ENGAGEMENT,
            client_id=CLIENT,
            scope=scope,
            engagement_profile=world["engagement_profile"],
            inputs=TimingInputs(inputs.files),
            identifiers=(),
            run_scope=world["run_scope"],
            procedure=procedure,
            pin=PIN,
        )

    return run


def guard_events(store: SqlRunStore, run_id: str, kind: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == kind]


def test_an_honest_output_passes_both_and_both_looked(
    guarded: Any, timing_step: Step, scope: ResolvedScope, store: SqlRunStore, world: dict
) -> None:
    guarded(TimingNormalization(), timing_step, scope)
    for kind in ("guard.provenance.pass", "guard.tieout.pass"):
        (event,) = guard_events(store, world["run_id"], kind)
        assert event.payload["checked"] == 57, f"{kind} passed over nothing"


def test_a_derived_total_nudged_by_one_is_stopped_by_the_tie_out(
    guarded: Any, timing_step: Step, scope: ResolvedScope
) -> None:
    def nudge(figure: dict) -> None:
        figure["value"] = figure["value"] + 1.0

    with pytest.raises(GuardFailed) as failed:
        guarded(Tampered(nudge), timing_step, scope)
    assert failed.value.result.code == TIEOUT_MISMATCH


def test_a_figure_passed_off_as_read_from_the_page_must_be_on_the_page(
    guarded: Any, timing_step: Step, scope: ResolvedScope
) -> None:
    """Drop the derivation, keep a real locator, change the number: the location check alone
    would pass it, and nothing re-derives a figure with no derivation."""

    def disguise(figure: dict) -> None:
        figure["derivation"] = None
        figure["value"] = figure["value"] + 12345.0

    with pytest.raises(GuardFailed) as failed:
        guarded(Tampered(disguise), timing_step, scope)
    assert failed.value.result.code == CITED_VALUE_ABSENT

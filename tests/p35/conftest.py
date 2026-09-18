"""Fixtures for P35: C08's self-service world, and a driver over it.

C08 sets an engagement up through the admin surface, drops files in a watched folder and
sweeps until a run is released - and then ends the run by hand, with a comment saying "this
test is one", because in P08 there was nothing else to end it with. That comment is the
finding this phase closes, so its world is the right thing to hand the driver.

The model port is replayed from a fixture. That is the one stand-in here, and it is what
the fake LLM adapter exists for: everything between the watched folder and the ending is
the real store, the real intake, the real executor, the real dispatcher and the real pool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from guards.untrusted import UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.context import ContextBuilder
from harness.dispatch import SkillDispatcher
from harness.door import ModelDoor
from harness.policy import PolicyGate
from harness.runtime import GuardedRuntime
from ops.blobs import LocalContentStore
from ops.cost import CostMeter
from ops.source_parse import SourceParseStore
from precedent.store import PrecedentStore
from privacy.mask import Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import open_vault
from registries.constraints import ConstraintRegistry
from registries.skills import SkillTree
from tests.checkpoints.c07 import test_c7_deliverable as c7
from tests.checkpoints.c08 import test_c8_self_service as c8
from tests.p16.conftest import LAUNCH, Clock, drop
from tests.p24.conftest import WHO, config_document, profile_for
from tools.coa import chart_of_accounts_lookup
from tools.normalize import timing_normalizer
from tools.precedent import precedent_lookup_tool
from tools.recompute import recompute
from tools.template_schema import template_schema_lookup
from workers.driver import RunDriver, RunWiring

world = c8.world
Replayed = c7.Replayed

HEND = c8.HEND
FOLDER = c8.FOLDER


@pytest.fixture
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture
def wiring(
    world: dict[str, Any],
    tmp_path: Path,
    constraints: ConstraintRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Everything the driver needs, built the way tools/serve.py builds it.

    C08's world sets a placeholder vault key, because nothing in C08 opens the vault. A
    run does - masking is the first thing that happens to a payload - so this sets a real
    one. It is generated per test and never leaves the process.
    """
    from cryptography.fernet import Fernet

    import ports

    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    ports.reset()

    store, bus = world["store"], world["bus"]
    blobs = LocalContentStore(tmp_path / "blobs")
    vault = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    meter = CostMeter(store)
    governor = BudgetGovernor(
        constraints,
        meter,
        bus,
        store,
        budget_for=lambda e: getattr(world["roster"].get(e), "budget_usd", None),
    )
    tree = SkillTree.load()
    precedents = PrecedentStore(store)
    runtime = GuardedRuntime(
        PolicyGate(constraints, bus),
        constraints,
        bus,
        {
            "timing_normalizer": timing_normalizer,
            "recompute": recompute,
            "chart_of_accounts_lookup": chart_of_accounts_lookup,
            "precedent_lookup": precedent_lookup_tool(precedents),
            "template_schema_lookup": template_schema_lookup,
        },
    )
    boundary = UntrustedBoundary(bus)

    def make(port: Any) -> Any:
        def dispatcher_for(_run_id: str) -> SkillDispatcher:
            return SkillDispatcher(
                tree=tree,
                # `precedents=` on purpose. This is the nearest thing to the served wiring
                # in the suite, and it reproduced production's omission rather than
                # catching it: both built a ContextBuilder without it while holding the
                # store, so a run that should have been shown an earlier decision was shown
                # nothing, in the test as well as in the server.
                context=ContextBuilder(tree, blobs, bus, store=store, precedents=precedents),
                door=ModelDoor(port, PayloadScan(bus), governor, meter, bus),
                runtime=runtime,
                contracts=world["contracts"],
                boundary=boundary,
                masker=Masker(vault),
                bus=bus,
                blobs=blobs,
            )

        return RunWiring(
            store=store,
            bus=bus,
            blobs=blobs,
            contracts=world["contracts"],
            constraints=constraints,
            config=world["config"],
            roster=world["roster"],
            intake_store=world["intake_store"],
            parse_store=SourceParseStore(store),
            dispatcher_for=dispatcher_for,
            templates=world["templates"],
            precedents=precedents,
            delivery=ports.get_delivery(),
            storage=ports.get_storage(),
            boundary=boundary,
        )

    return make


@pytest.fixture
def driver_for(wiring: Any) -> Any:
    def build(port: Any) -> RunDriver:
        return RunDriver(wiring(port))

    return build


__all__ = [
    "FOLDER",
    "HEND",
    "LAUNCH",
    "WHO",
    "Clock",
    "Replayed",
    "config_document",
    "drop",
    "profile_for",
]

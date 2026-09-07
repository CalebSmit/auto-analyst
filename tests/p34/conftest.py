"""Fixtures for P34: the world C07 assembles, plus a runner over it.

C07 already builds everything a real skill step needs - store, bus, blobs, vault, meter,
governor, guarded runtime, dispatcher, plan, scope, parse store. It builds it by hand,
which is exactly the finding this phase closes, so it is the right thing to hand the
runner: if the seam works against that, it works against the real components rather than
against a fixture shaped to fit it.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness.inputs import RunFacts
from harness.procedures.timing_normalization import SourceFile
from harness.runner import RunContext, SkillStepRunner
from ops.source_parse import Row
from review import CheckpointPolicy
from tests.checkpoints.c07 import test_c7_deliverable as c7
from tests.p15.conftest import profile
from tests.p20.conftest import load_case
from tests.p21.conftest import SLOTS

world = c7.world

ENGAGEMENT = c7.ENGAGEMENT
CLIENT = c7.CLIENT
RUN_ID = c7.RUN_ID
TAXONOMY = c7.TAXONOMY


@pytest.fixture
def case() -> dict[str, Any]:
    return load_case()


@pytest.fixture
def sources(world: dict[str, Any], case: dict[str, Any]) -> tuple[SourceFile, ...]:
    """The readers' rows, into the parse store, and the typed files beside them."""
    files = []
    for f in case["case"]["files"]:
        for locator, rows in f["blocks"].items():
            world["parse_store"].write(
                RUN_ID, f["source_id"], locator, [Row(**r) for r in rows]
            )
        files.append(
            SourceFile(
                source_id=f["source_id"],
                filename=f["filename"],
                document_type=f["document_type"],
                blocks=f["blocks"],
                scale=f["scale"],
                currency=f["currency"],
                period_type=f["period_type"],
                period_ends=tuple(f["period_ends"]),
                ambiguous=tuple(f["ambiguous"]),
                source_version=f.get("source_version", 1),
                block_periods=f.get("block_periods", {}),
            )
        )
    return tuple(files)


@pytest.fixture
def facts(world: dict[str, Any], sources: tuple[SourceFile, ...]) -> RunFacts:
    template = world["registry"].resolve(world["scope"].template)
    return RunFacts(
        profile=profile(),
        policy=CheckpointPolicy.from_profile(profile(), world["constraints"]),
        taxonomy_version=TAXONOMY,
        sources=sources,
        blocks={f.source_id: f.blocks for f in sources},
        template=template,
        periods=("FY1", "FY2", "FY3"),
        period_slots=SLOTS,
    )


@pytest.fixture
def context(world: dict[str, Any], facts: RunFacts) -> RunContext:
    from harness.door import ModelPin

    return RunContext(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        scope=world["scope"],
        engagement_profile=world["engagement_profile"],
        identifiers=(),
        run_scope=world["run_scope"],
        pin=ModelPin.for_tier("mid"),
        facts=facts,
    )


@pytest.fixture
def runner_for(world: dict[str, Any], context: RunContext) -> Any:
    """A runner over a model port the test controls. The port is the only thing a test
    supplies: everything else is what a run would have."""

    def build(port: Any) -> SkillStepRunner:
        return SkillStepRunner(world["dispatcher"](port), world["blobs"], context)

    return build

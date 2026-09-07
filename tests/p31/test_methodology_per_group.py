"""P31: each practice group's methodology reaches its own runs and nobody else's.

`foundations/` used to be flat - three files, every call, unconditionally. It is now the
same five-layer tree as `skills/`, walked the same way, which means one mechanism decides
what a practice group is rather than two that can drift apart.

The four claims:

1. A valuation run carries the firm's methodology and valuation's, and not consulting's.
2. A group that has written nothing of its own still carries the firm's.
3. Methodology past its size ceiling is refused at setup, not discovered in a bill.
4. A change to what every prompt carries moves the surface snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from admin.preflight import CHECKS, Preflight
from graph.resolve import ScopeResolver
from harness.context import ContextBuilder
from registries.constraints import ConstraintRegistry
from registries.errors import RegistryError
from registries.methodology import MethodologyRegister
from tools.surfaces import SNAPSHOT, foundations_surface

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------- the layer walk


def test_the_walk_is_the_same_one_that_decides_which_skills_a_run_has() -> None:
    """One mechanism, not two. If methodology used a walk of its own, the two could
    disagree about what a practice group is, and the disagreement would be invisible."""
    resolved = ScopeResolver().resolve("valuation/esop/repeat")
    assert resolved.layers == (
        "_firm",
        "valuation/_group",
        "valuation/_repeat",
        "valuation/esop/_segment",
        "valuation/esop/repeat",
    )
    assert resolved.layers[0] == "_firm", "the firm layer is the floor of every walk"


def test_a_run_carries_its_own_groups_methodology_and_no_other_groups(
    cleared: MethodologyRegister, builder: ContextBuilder, request_for: Any
) -> None:
    """The first exit criterion.

    Consulting's methodology is on disk and cleared - so nothing about this is an accident
    of it being missing or unreadable. It simply is not on this run's walk.
    """
    assembled = builder.build(request_for("ebitda"))
    carried = [s.name for s in assembled.section("foundations")]

    assert carried == ["_firm/how-we-work.md", "valuation/_group/how-we-work.md"]
    assert not [name for name in carried if name.startswith("consulting/")]

    body = builder.blobs.get(assembled.ref)
    assert b"We reconcile to the trial balance first" in body
    assert b"We scope the question before the model" not in body, "another group's work"
    assert b"Every engagement gets a scope memo" in body, "the firm layer, unconditionally"


def test_the_firm_layer_comes_first_and_the_order_is_the_walk(
    cleared: MethodologyRegister, builder: ContextBuilder, request_for: Any
) -> None:
    """Order is part of the context hash, so it is the resolver's order rather than a
    glob's. Two contexts differing only in section order would be two keys for one
    question, and neither would be wrong."""
    sections = builder.build(request_for("ebitda")).section("foundations")
    assert [s.name.rsplit("/", 1)[0] for s in sections] == ["_firm", "valuation/_group"]


def test_a_group_with_no_methodology_of_its_own_still_carries_the_firms(
    register: MethodologyRegister, foundations: Path
) -> None:
    """The second exit criterion, and the one that decides whether a new practice group
    works on the day it is declared or has to be onboarded first.

    Corporate Finance is in the scope registry and has no folder. A missing layer
    contributes nothing rather than failing.
    """
    layers = ScopeResolver().resolve("corporate-finance/tbd/repeat").layers
    assert not (foundations / "corporate-finance").exists()

    carried = [register.name_of(p) for p in register.for_layers(layers)]
    assert carried == ["_firm/how-we-work.md"]


def test_an_empty_layer_folder_is_not_an_error(
    register: MethodologyRegister, foundations: Path
) -> None:
    """A group that made the folder and has not written anything yet. Same answer: it
    carries the firm's, and nobody has to remember to delete an empty directory."""
    (foundations / "corporate-finance" / "_group").mkdir(parents=True)
    layers = ScopeResolver().resolve("corporate-finance/tbd/repeat").layers
    assert [register.name_of(p) for p in register.for_layers(layers)] == ["_firm/how-we-work.md"]


def test_two_groups_may_use_the_same_filename(
    cleared: MethodologyRegister, foundations: Path
) -> None:
    """`how-we-work.md` exists three times here and they are three documents. That is why
    a file is identified by its layer, and why clearing one does not clear the others."""
    names = [cleared.name_of(p) for p in cleared.files()]
    assert names == [
        "_firm/how-we-work.md",
        "consulting/_group/how-we-work.md",
        "valuation/_group/how-we-work.md",
    ]
    assert len({row.digest for row in cleared.cleared()}) == 3


def test_a_groups_methodology_must_be_cleared_like_anybody_elses(
    cleared: MethodologyRegister, builder: ContextBuilder, request_for: Any, foundations: Path
) -> None:
    """A practice group layer is not a way around the clearance. It reaches every prompt
    of every run in that group, which is a narrower blast radius than the firm layer and
    the same kind of problem."""
    (foundations / "valuation" / "_group" / "how-we-work.md").write_text(
        "# Valuation\n\nOn HEND-2026-04 we treated the draw as an add-back.\n", encoding="utf-8"
    )
    with pytest.raises(RegistryError) as refused:
        builder.build(request_for("ebitda"))
    assert refused.value.diagnostic.locator == "valuation/_group/how-we-work.md"
    assert refused.value.diagnostic.code == "CONFIG.METHODOLOGY_UNCLEARED"


# ------------------------------------------------------------- the size ceiling


def test_a_layer_past_its_ceiling_is_refused_at_setup(
    cleared: MethodologyRegister, preflight: Preflight, henderson: Any, foundations: Path
) -> None:
    """The third exit criterion. This is content on every model call of every run that
    walks through the layer, so it is a standing cost rather than a one-off - and the
    place to find it is setup, not a bill three weeks later with nothing to attribute."""
    ceiling = ConstraintRegistry.load().methodology_ceiling()
    assert preflight.run().checks[-1].status == "pass"

    fat = foundations / "valuation" / "_group" / "at-length.md"
    fat.write_text("x" * (ceiling + 1), encoding="utf-8")

    check = next(c for c in preflight.run().checks if c.id == "methodology_size")
    assert check.status == "fail"
    assert [f.diagnostic.locator for f in check.failures] == ["valuation/_group"]

    diagnostic = check.failures[0].diagnostic
    assert diagnostic.code == "CONFIG.METHODOLOGY_TOO_LARGE"
    assert diagnostic.owner == "config"
    assert "every model call" in diagnostic.detail
    assert diagnostic.what_now and "constraints.yaml" in diagnostic.what_now
    assert check.failures[0].blocks_everything, "one layer over is not one engagement's problem"


def test_the_ceiling_is_a_constraint_not_a_number_in_the_code() -> None:
    """Raised deliberately in constraints.yaml, like every other ceiling here, rather than
    in whatever wanted the extra room."""
    registry = ConstraintRegistry.load()
    assert registry.methodology_ceiling() == 65536
    raw = (ROOT / "constraints" / "constraints.yaml").read_text(encoding="utf-8")
    assert "per_methodology_layer" in raw
    assert "every prompt of every run" in raw, "the yaml says why the number is a number"


def test_the_ceiling_is_per_layer_not_per_tree(
    register: MethodologyRegister, foundations: Path
) -> None:
    """Per layer, because that is the unit a run actually carries. A firm with ten
    practice groups does not have ten groups' worth of methodology on any one call."""
    for layer in ("_firm", "valuation/_group", "consulting/_group"):
        assert register.bytes_at(layer) == len(
            (foundations / layer / "how-we-work.md").read_bytes()
        )
    assert register.bytes_at("corporate-finance/_group") == 0, "a layer with no folder"


# ------------------------------------------------------------- the snapshot


def test_what_every_prompt_carries_is_in_the_surface_snapshot(
    register: MethodologyRegister, foundations: Path
) -> None:
    """The fourth exit criterion. Nothing else in the snapshot moves when somebody adds a
    paragraph to a document that every prompt carries, which is exactly the kind of change
    the snapshot exists to make visible."""
    before = foundations_surface(register)
    assert sorted(before) == ["_firm", "consulting/_group", "valuation/_group"]
    assert before["_firm"]["files"] == ["how-we-work.md"]
    assert before["_firm"]["digest"].startswith("sha256:")
    assert before["_firm"]["bytes"] > 0

    # An edit moves exactly one layer.
    path = foundations / "valuation" / "_group" / "how-we-work.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nAnd then the adjustments.\n")
    after = foundations_surface(register)
    assert after["valuation/_group"]["digest"] != before["valuation/_group"]["digest"]
    assert after["_firm"] == before["_firm"], "one layer changing is not two"


def test_the_digest_notices_an_addition_a_deletion_and_a_rename(
    register: MethodologyRegister, foundations: Path
) -> None:
    """A digest over the content alone would miss a rename, and one over the names alone
    would miss an edit. This covers both, because either changes what a prompt carries."""
    layer = foundations / "consulting" / "_group"
    original = foundations_surface(register)["consulting/_group"]

    (layer / "second.md").write_text("# More\n", encoding="utf-8")
    added = foundations_surface(register)["consulting/_group"]
    assert added["files"] == ["how-we-work.md", "second.md"]
    assert added["digest"] != original["digest"]

    (layer / "second.md").rename(layer / "third.md")
    renamed = foundations_surface(register)["consulting/_group"]
    assert renamed["digest"] != added["digest"], "a rename changes the framing in context"

    (layer / "third.md").unlink()
    assert foundations_surface(register)["consulting/_group"] == original


def test_the_committed_snapshot_carries_the_repos_own_foundations() -> None:
    """Not just the collector - the recorded snapshot, so a change to the firm's real
    methodology fails a test naming it rather than passing quietly."""
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert "foundations" in recorded, "the group is in the snapshot"
    assert recorded["foundations"] == foundations_surface(), "the snapshot is current"
    assert recorded["foundations"]["_firm"]["files"] == [
        "qc-conventions.md",
        "tagging-policy.md",
        "valuation-standards.md",
    ]


# ------------------------------------------------------------- the repo itself


def test_the_firms_files_moved_into_the_firm_layer() -> None:
    """They are the firm's methodology, so they sit at the firm layer. No content changed
    with the move - what changed is that there is now somewhere else for a group to put
    its own."""
    register = MethodologyRegister()
    assert [register.name_of(p) for p in register.files()] == [
        "_firm/qc-conventions.md",
        "_firm/tagging-policy.md",
        "_firm/valuation-standards.md",
    ]
    stray = [p.name for p in (ROOT / "foundations").glob("*.md") if p.name != "README.md"]
    assert not stray, f"methodology left outside a layer: {stray}"
    assert (ROOT / "foundations" / "README.md").is_file(), "the README explains the layout"


def test_the_readme_explains_the_layers_and_the_clearance() -> None:
    """The folder is edited by people who will not read this test suite."""
    readme = (ROOT / "foundations" / "README.md").read_text(encoding="utf-8")
    for said in (
        "foundations/_firm/",
        "foundations/valuation/_group/",
        "group that has written nothing of its own still carries the firm",
        "cleared.yaml` is not committed",
        "size ceiling",
    ):
        assert said in readme, said


def test_the_blueprint_describes_the_layered_tree() -> None:
    """Code and blueprint disagreeing is a finding, so the design of record says what the
    Context Builder actually does."""
    blueprint = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    assert "Walked through the same five layers that decide which skills a run has" in blueprint
    assert "never consulting" in blueprint
    assert "size ceiling per layer" in blueprint
    assert "METHODOLOGY_TOO_LARGE" in blueprint
    assert len(CHECKS) == 13
    assert "Thirteen checks over a proposed or live configuration" in blueprint

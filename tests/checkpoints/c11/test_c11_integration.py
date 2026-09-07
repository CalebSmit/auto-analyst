"""Checkpoint C11 - a group's methodology, and nobody else's.

Proves: an engagement is set up by choosing its practice group, and carries that group's
cleared methodology and no other group's.

Three phases meet here and none of them is enough alone. P29 made the practice group
something a person picks from a list rather than a path they type correctly. P30 made
methodology something a person clears before it reaches a prompt. P31 made it walk the
same five layers the skills already walk. The question this checkpoint asks is whether
the three agree - whether the group somebody picked in the dashboard is the group whose
methodology the run actually carries, and whether the clearance somebody gave is the one
the run actually checks.

The path, in the order a person walks it: choose a group, register the engagement, watch
setup refuse because nobody has read the methodology yet, clear it by name, watch setup
pass, and see the assembled context carry that group's work and not the other's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin.console import AdminConsole
from harness.context import ContextBuilder
from registries.errors import RegistryError
from registries.methodology import MethodologyRegister


def test_a_practice_group_is_chosen_from_the_registry_not_typed(console: AdminConsole) -> None:
    """P29's half. The dashboard offers the groups; nothing asks anybody to spell
    `valuation/esop/repeat` correctly, and a group with nothing behind it says so."""
    choices = console.scope_choices()
    practices = {p["id"]: p for p in choices["practices"]}

    assert set(practices) == {"valuation", "consulting", "corporate-finance"}
    assert practices["valuation"]["defined"] and not practices["consulting"]["defined"]

    chosen = next(p for p in choices["paths"] if p["scope_path"] == "valuation/esop/repeat")
    assert chosen["defined"] and not chosen["firm_layer_only"]


def test_setup_refuses_until_somebody_has_read_the_methodology(
    console: AdminConsole, henderson: Any, foundations: Path
) -> None:
    """P30's half, at the point it actually bites: an engagement is registered and cannot
    be activated, because the firm's own methodology has not been read by anyone."""
    report = console.check("HEND-2026-04")
    uncleared = next(c for c in report.checks if c.id == "methodology_cleared")

    assert uncleared.status == "fail"
    assert not report.passed
    assert report.blocking("HEND-2026-04"), "an uncleared file blocks activation"

    listed = console.methodology()
    assert sorted(listed["layers"]) == ["_firm", "consulting/_group", "valuation/_group"]
    assert {f["state"] for f in listed["files"]} == {"uncleared"}


def test_the_whole_path_from_choosing_a_group_to_the_context_it_produces(
    console: AdminConsole,
    henderson: Any,
    builder: ContextBuilder,
    request_for: Any,
    register: MethodologyRegister,
    foundations: Path,
) -> None:
    """The checkpoint itself.

    Henderson is a valuation engagement. After a person clears the methodology, the run
    carries the firm's and valuation's - and consulting's is on disk, cleared, and absent,
    which is the part that matters. Isolation by walk, not by accident.
    """
    for found in console.methodology()["files"]:
        console.clear_methodology(found["name"], who="C. Smit")

    report = console.check("HEND-2026-04")
    assert report.passed, report.report()
    assert not report.blocking("HEND-2026-04")

    activated = console.activate("HEND-2026-04", who="C. Smit", reason="setup complete")
    assert activated.state.value == "active"

    assembled = builder.build(request_for("ebitda"))
    carried = [s.name for s in assembled.section("foundations")]
    assert carried == ["_firm/how-we-work.md", "valuation/_group/how-we-work.md"]

    body = builder.blobs.get(assembled.ref)
    assert b"We reconcile to the trial balance first" in body, "the group whose work this is"
    assert b"We scope the question before the model" not in body, "another group's"
    assert register.is_cleared(
        next(row.digest for row in register.cleared() if row.name.startswith("consulting/"))
    ), "consulting is cleared and still absent - it is not on this run's walk"


def test_who_cleared_it_is_on_the_record_and_travels_with_the_context(
    console: AdminConsole,
    henderson: Any,
    builder: ContextBuilder,
    request_for: Any,
    register: MethodologyRegister,
) -> None:
    """A clearance names a person, and the digest they cleared is the digest the context
    manifest carries. The two records are the same fact, which is what makes "what was
    this run shown, and who approved it" one question rather than two."""
    for found in console.methodology()["files"]:
        console.clear_methodology(found["name"], who="R. Partner")

    sections = builder.build(request_for("ebitda")).section("foundations")
    for section in sections:
        entry = register.entry(section.content_hash)
        assert entry is not None, section.name
        assert entry.name == section.name
        assert entry.cleared_by == "R. Partner"
        assert entry.cleared_at.endswith("Z")


def test_changing_a_groups_methodology_changes_what_the_run_is(
    console: AdminConsole,
    henderson: Any,
    builder: ContextBuilder,
    request_for: Any,
    foundations: Path,
) -> None:
    """Methodology is part of the context hash, so it is part of the run's identity.

    That is the property that makes a resumed run safe: change what the firm says about
    how to do the work, and the step's key changes, so no cached result from the old
    methodology can come back as though it were current.
    """
    for found in console.methodology()["files"]:
        console.clear_methodology(found["name"], who="C. Smit")
    before = builder.build(request_for("ebitda"))

    path = foundations / "valuation" / "_group" / "how-we-work.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nAnd we tie out before we normalise.\n",
        encoding="utf-8",
    )

    # Until somebody reads the change, the run stops rather than carrying it.
    with pytest.raises(RegistryError) as refused:
        builder.build(request_for("ebitda"))
    assert refused.value.diagnostic.locator == "valuation/_group/how-we-work.md"
    assert "cleared once, but not this version" in refused.value.diagnostic.detail

    edited = next(
        f for f in console.methodology()["files"] if f["name"].startswith("valuation/")
    )
    assert edited["state"] == "edited"
    console.clear_methodology(edited["name"], who="C. Smit")

    after = builder.build(request_for("ebitda"))
    assert after.context_ref != before.context_ref, "a different context is a different key"
    assert [s.name for s in after.section("foundations")] == [
        s.name for s in before.section("foundations")
    ], "the same documents, one of them changed"


def test_a_group_that_has_written_nothing_is_set_up_the_same_way(
    console: AdminConsole, register: MethodologyRegister, foundations: Path
) -> None:
    """Corporate Finance is declared, has no methodology folder, and is not a special
    case anywhere: it resolves, it carries the firm's methodology, and it is offered in
    the dashboard as an undefined group rather than hidden."""
    from graph.resolve import ScopeResolver

    offered = {p["scope_path"] for p in console.scope_choices()["paths"]}
    assert "corporate-finance/tbd/repeat" in offered

    layers = ScopeResolver().resolve("corporate-finance/tbd/repeat").layers
    assert [register.name_of(p) for p in register.for_layers(layers)] == ["_firm/how-we-work.md"]
    assert not (foundations / "corporate-finance").exists()

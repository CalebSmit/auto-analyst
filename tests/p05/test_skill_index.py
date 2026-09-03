"""The Skill Index carries a name and a description, and never a skill body.

This is progressive disclosure in one object, and the exit criterion is worth a test
because the failure is invisible: an index that quietly grew a `body` field would work
perfectly and cost more on every run, for as long as nobody profiled it.

So the test is not "the index looks right". It is: take every word that only exists in
a body or a reference file, and prove none of them can be reached through the index.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from graph.resolve import ScopeResolver
from registries.skills import IndexEntry, SkillIndex, SkillTree

ROOT = Path(__file__).resolve().parents[2]


def test_the_index_holds_one_entry_per_resolved_skill(resolver: ScopeResolver) -> None:
    resolved = resolver.resolve("valuation/esop/repeat")
    index = resolved.index()
    assert len(index) == len(resolved)
    assert index.names() == resolved.names


def test_an_entry_has_four_fields_and_none_of_them_is_content() -> None:
    """`layer` and `tier` are routing facts - which layer answered, how expensive the
    call is. Neither is a procedure, a reference or an example."""
    assert {f.name for f in dataclasses.fields(IndexEntry)} == {
        "name",
        "description",
        "layer",
        "tier",
    }


def test_no_index_entry_carries_a_line_from_any_skill_body(tree: SkillTree) -> None:
    """The load-bearing version of the criterion.

    Every SKILL.md body is split into its distinctive lines, and each is checked against
    the whole rendered index. A body sentence reaching Tier 1 by any route - a new
    field, a longer description, a helpful `__str__` - fails here.
    """
    index = SkillIndex.of(tree.all())
    rendered = index.as_prompt()
    for skill in tree.all():
        body = (ROOT / skill.path).read_text(encoding="utf-8").split("---", 2)[2]
        for line in body.splitlines():
            stripped = line.strip().lstrip("#> ").strip()
            if len(stripped) < 40 or stripped in skill.description:
                continue
            assert stripped not in rendered, f"{skill.name}: body line reached the index"


def test_no_index_entry_carries_a_line_from_any_reference_file(tree: SkillTree) -> None:
    """References load on demand once a skill is selected. Not before, and not here."""
    index = SkillIndex.of(tree.all())
    rendered = index.as_prompt()
    checked = 0
    for reference in sorted((ROOT / "skills").rglob("references/*.md")):
        for line in reference.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lstrip("#> ").strip()
            if len(stripped) < 40:
                continue
            checked += 1
            assert stripped not in rendered, f"{reference.name}: reference text reached the index"
    assert checked, "no reference content was checked, so this proved nothing"


def test_the_index_names_no_reference_or_script_file(tree: SkillTree) -> None:
    """Not even the file names. Knowing a reference exists is enough to make an
    orchestrator ask for it, and asking for it is what Tier 2 is."""
    rendered = SkillIndex.of(tree.all()).as_prompt()
    for skill in tree.all():
        for filename in (*skill.references, *skill.scripts):
            assert filename not in rendered


def test_the_index_is_small(resolver: ScopeResolver) -> None:
    """About forty tokens a skill is the blueprint's number, and the whole argument for
    the Scope Resolver sitting above this. A rough character budget catches the day a
    description becomes a paragraph."""
    rendered = resolver.resolve("valuation/esop/repeat").index().as_prompt()
    per_skill = len(rendered) / len(resolver.resolve("valuation/esop/repeat"))
    assert per_skill < 320, f"{per_skill:.0f} characters per skill is not a one-liner"


def test_every_description_is_the_blueprints(
    tree: SkillTree, blueprint_skill_descriptions: dict[str, str]
) -> None:
    """The description is the only thing the orchestrator reads, so it is the one field
    where drifting from the blueprint changes what the system does rather than only what
    a document says.

    Whether a description reads as *when to use* rather than *what it is* is an
    editorial judgement the CONFORM table gives to the practice owner, so it is not
    asserted here. Agreement with the blueprint is.
    """
    assert {s.name: s.description for s in tree.all()} == blueprint_skill_descriptions


def test_every_description_is_one_line_and_index_sized(tree: SkillTree) -> None:
    """About forty tokens. A description that grew into a paragraph would take the
    procedure's place in the orchestrator's context without anyone deciding to put it
    there."""
    for skill in tree.all():
        assert "\n" not in skill.description
        assert 40 < len(skill.description) < 320, f"{skill.name}: {len(skill.description)} chars"


def test_an_index_over_a_narrower_scope_is_narrower(resolver: ScopeResolver) -> None:
    """The point of Tier 0. A Corporate Finance run is not declining to use the ESOP
    skills - it never had them."""
    esop = set(resolver.resolve("valuation/esop/repeat").index().names())
    corpfin = set(resolver.resolve("corporate-finance/tbd/repeat").index().names())
    assert corpfin < esop
    assert "dol-adequate-consideration" in esop
    assert "dol-adequate-consideration" not in corpfin

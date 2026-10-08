"""Checkpoint C14 - making it his.

Proves: the division the build is pointed at is the one a person is offered first, can scope
real work into, and is described by the interview in the same terms the resolver uses - and
what the interview learns cannot reach a skill, methodology file or fixture.

P37 is one phase, but it leans on three older ones. The focus is read by P05's registry and
offered by P29's admin surface; the interview's gap report asks P05's resolver and P34's
procedure table rather than keeping its own list. A report that disagreed with the resolver
would send the interview asking about gaps that do not exist, which is the failure this
checkpoint exists to catch.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from admin import AdminConsole
from admin.app import create_admin_app
from graph.resolve import ScopeResolver
from harness.procedures import PROCEDURES
from registries.scopes import ScopePath, ScopeRegistry
from tests.conftest import needs_a_checkout
from tests.p24.conftest import WHO, entry, profile_for
from tools import interview

ROOT = Path(__file__).resolve().parents[3]
FOCUS_ENGAGEMENT = "FOCUS-2026-01"


def test_the_focus_is_offered_first_and_real_work_can_be_scoped_into_it(
    console: AdminConsole,
) -> None:
    served = TestClient(create_admin_app(console)).get("/api/admin/scopes").json()
    first = served["paths"][0]["scope_path"]
    assert served["focus"] == "valuation/non-esop"
    assert first.startswith("valuation/non-esop/")

    registered = console.register_engagement(
        entry(FOCUS_ENGAGEMENT, client="Focus Test Co", scope_path=first),
        profile=profile_for(FOCUS_ENGAGEMENT, first),
        who=WHO,
        reason="C14: an engagement in the focus division",
    )
    assert registered.scope_path == first
    report = console.check(FOCUS_ENGAGEMENT)
    scope_check = next(c for c in report.checks if c.id == "scope_defined")
    assert scope_check.status == "pass", "the focus division is defined, so nothing to warn"


def test_the_interview_describes_the_focus_in_the_resolvers_terms() -> None:
    registry = ScopeRegistry.load()
    assert registry.focus is not None
    practice, segment = registry.focus
    gaps = interview.code_gaps()
    assert gaps[0] == f"focus: {practice}/{segment}"

    resolver = ScopeResolver()
    for disposition in registry.dispositions:
        resolved = resolver.resolve(ScopePath(practice, segment, disposition.id))
        line = next(g for g in gaps if g.startswith(f"{resolved.scope}:"))
        assert f"{len(resolved)} skills" in line
        assert resolved.template is not None and resolved.template.file in line
        missing = sorted(r.name for r in resolved.skills if r.name not in PROCEDURES)
        if missing:
            assert any(g.strip().endswith(", ".join(missing)) for g in gaps)
    assert not any(g.startswith("could not") for g in gaps)


def test_what_the_interview_learns_stays_inside_knowledge() -> None:
    needs_a_checkout("what the interview keeps")
    token = f"C14Probe{uuid.uuid4().hex[:8]}"
    inside = ROOT / "knowledge" / f"_{token}.md"
    outside = ROOT / f"_{token}.md"
    inside.parent.mkdir(exist_ok=True)
    try:
        inside.write_text(f"client {token} walked end to end\n", encoding="utf-8")
        outside.write_text(f"a skill that names {token}\n", encoding="utf-8")
        committable = interview.committable_files()
        assert inside not in committable
        hits = interview.scan(committable, [token])
        assert [path for path, _, _ in hits] == [outside]
    finally:
        inside.unlink(missing_ok=True)
        outside.unlink(missing_ok=True)

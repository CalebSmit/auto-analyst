"""The Diagnostics Registry: every code has a family, an owner and a what_now.

Every failure carries a stable code, an owner and what to do next. A message nobody can
act on is a defect - and this is the check that finds one before a run does.
"""

from __future__ import annotations

import pytest

from registries import errors
from registries.diagnostics import FAMILIES, OWNERS, DiagnosticsRegistry
from registries.errors import RegistryError


@pytest.fixture(scope="module")
def registry() -> DiagnosticsRegistry:
    return DiagnosticsRegistry.load()


def test_every_declared_code_has_a_what_now(registry: DiagnosticsRegistry) -> None:
    """What CI asserts. Every constant in errors.py is registered and says what to do."""
    assert registry.self_check() == []
    for code in registry.codes():
        assert len(registry.get(code).what_now.split()) >= 12


def test_every_code_belongs_to_a_family_the_blueprint_names(registry: DiagnosticsRegistry) -> None:
    for code in registry.codes():
        assert registry.get(code).family in FAMILIES


def test_every_code_has_an_owner_somebody_is(registry: DiagnosticsRegistry) -> None:
    for code in registry.codes():
        assert registry.get(code).owner in OWNERS


def test_the_policy_family_is_complete(registry: DiagnosticsRegistry) -> None:
    """The three the blueprint's table names, plus the two the runtime and the resolver
    needed. Owner policy throughout: the fix is a decision, not a retry."""
    names = {c.name for c in registry.by_family("POLICY")}
    assert {"TOOL_NOT_DECLARED", "ARG_OUT_OF_SCOPE", "BUDGET_EXCEEDED"} <= names
    assert all(c.owner == "policy" for c in registry.by_family("POLICY"))


def test_the_registry_is_the_only_declaration_site(registry: DiagnosticsRegistry) -> None:
    """Built from errors.py rather than from a second list, so there is exactly one place
    a code is declared and the two cannot drift."""
    declared = {
        v for k, v in vars(errors).items()
        if k.isupper() and isinstance(v, str) and v.split(".", 1)[0] in FAMILIES
    }
    assert declared == set(registry.codes())


def test_an_unregistered_code_is_a_diagnostic_not_a_key_error(
    registry: DiagnosticsRegistry,
) -> None:
    with pytest.raises(RegistryError) as raised:
        registry.get("GUARD.SOMETHING_NOBODY_WROTE")
    assert raised.value.diagnostic.code == "PROCESS.DIAGNOSTICS_INVALID"


def test_a_broken_registry_reports_every_problem() -> None:
    """All of them, because "three codes are broken" and "a code is broken" are different
    reports and only one is useful."""
    from registries.diagnostics import Code

    broken = DiagnosticsRegistry({
        "NOPE.THING": Code("NOPE.THING", "policy", "a " * 20),
        "POLICY.thing": Code("POLICY.thing", "policy", "a " * 20),
        "POLICY.SHORT": Code("POLICY.SHORT", "policy", "too short"),
        "POLICY.WHO": Code("POLICY.WHO", "nobody", "a " * 20),
    })
    problems = broken.self_check()
    assert len([p for p in problems if p.startswith("NOPE.THING")]) == 1
    assert len([p for p in problems if p.startswith("POLICY.thing")]) == 1
    assert len([p for p in problems if p.startswith("POLICY.SHORT")]) == 1
    assert len([p for p in problems if p.startswith("POLICY.WHO")]) == 1


def test_the_registry_is_versioned(registry: DiagnosticsRegistry) -> None:
    """A run records which diagnostics it was judged under, so a code that later changes
    meaning does not rewrite the history of runs that carried it."""
    assert registry.version == "1.0.0"
    assert len(registry) >= 30

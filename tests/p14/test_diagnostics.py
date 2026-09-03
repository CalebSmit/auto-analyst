"""The diagnostic namespace: every code has an owner and a what_now, and the blueprint's
table and the registry agree in both directions."""

from __future__ import annotations

import re

import pytest

from guards import GuardFailed, GuardResult
from registries import errors
from registries.diagnostics import FAMILIES, OWNERS, DiagnosticsRegistry
from registries.errors import Diagnostic, diagnose
from tests.p14.conftest import ROOT


@pytest.fixture(scope="module")
def registry() -> DiagnosticsRegistry:
    return DiagnosticsRegistry.load()


def blueprint_table() -> dict[str, set[str]]:
    """The ERRCODES rows in docs/architecture.html, family -> names."""
    html = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    start = html.index("const ERRCODES")
    block = html[start : html.index("];", start)]
    rows: dict[str, set[str]] = {}
    for family, names in re.findall(r"\['([A-Z]+)\.\*','([^']*)'", block):
        rows[family] = {n.strip() for n in re.split(r"\\u00b7|\u00b7", names) if n.strip()}
    return rows


def test_every_error_code_has_an_owner_and_a_what_now(registry: DiagnosticsRegistry) -> None:
    """The exit criterion."""
    assert registry.self_check() == []
    assert len(registry) >= 53
    for code in registry.codes():
        entry = registry.get(code)
        assert entry.owner in OWNERS, code
        assert len(entry.what_now.split()) >= 12, f"{code}: what_now is not actionable"
        assert entry.family in FAMILIES


def test_every_registry_code_is_in_the_blueprints_table() -> None:
    """The P13 finding, as a test. Ten codes had grown in the registry over nine phases
    without reaching the table; this is the assertion that stops it happening again."""
    table = blueprint_table()
    declared = {
        value
        for name, value in vars(errors).items()
        if name.isupper()
        and isinstance(value, str)
        and "." in value
        and value.split(".")[0] in FAMILIES
    }
    missing = sorted(
        c for c in declared if c.split(".")[1] not in table.get(c.split(".")[0], set())
    )
    assert missing == [], f"in registries/errors.py but not in the blueprint's ERRCODES: {missing}"


def test_every_table_code_is_in_the_registry(registry: DiagnosticsRegistry) -> None:
    table = blueprint_table()
    listed = {f"{family}.{name}" for family, names in table.items() for name in names}
    missing = sorted(listed - set(registry.codes()))
    assert missing == [], f"in the blueprint's ERRCODES but not in registries/errors.py: {missing}"
    assert set(table) == set(FAMILIES)


def test_the_diagnostic_shape_is_the_blueprints() -> None:
    """code, owner, expected, found, delta, where, step, skill, retryable, what_now."""
    d = diagnose(
        errors.TIEOUT_MISMATCH,
        "officer comp",
        locator="TB_FY25!B48",
        expected=331000.0,
        found=332324.0,
        delta=1324.0,
        step_id="ebitda",
        skill="ebitda-normalization@0.1.0",
    )
    wire = d.as_dict()
    assert set(wire) == {
        "code",
        "owner",
        "what_now",
        "detail",
        "where",
        "expected",
        "found",
        "delta",
        "step_id",
        "skill",
        "retryable",
    }
    assert wire["expected"] == "331000.0" and wire["found"] == "332324.0"
    assert wire["owner"] == "client-data" and wire["retryable"] is False
    assert "expected 331000.0, found 332324.0 (delta 1324.0)" in str(d)


def test_no_guard_or_loop_code_is_retryable(registry: DiagnosticsRegistry) -> None:
    """A retry with unchanged input fails identically. The shape makes that the default
    and nothing in guards/ or harness/loops.py overrides it."""
    for family in ("GUARD", "LOOP"):
        for entry in registry.by_family(family):
            assert diagnose(entry.code).retryable is False
    for path in ("guards", "harness/loops.py"):
        for file in (ROOT / path).rglob("*.py") if (ROOT / path).is_dir() else [ROOT / path]:
            assert "retryable=True" not in file.read_text(encoding="utf-8"), file


def test_a_guard_failure_carries_both_values_and_the_delta() -> None:
    result = GuardResult(
        guard="tieout",
        passed=False,
        checked=1,
        failed=1,
        code=errors.TIEOUT_MISMATCH,
        reasons=("officer comp",),
        detail={"mismatches": [{"stated": 332324.0, "recomputed": 331000.0, "delta": 1324.0}]},
    )
    failure = GuardFailed(result, locator="ebitda")
    assert failure.diagnostic.expected == "331000.0"
    assert failure.diagnostic.found == "332324.0"
    assert failure.diagnostic.delta == "1324.0"


def test_the_families_are_the_blueprints_nine() -> None:
    assert FAMILIES == (
        "INTAKE",
        "SCOPE",
        "PRIVACY",
        "POLICY",
        "SKILL",
        "GUARD",
        "DELIVER",
        "LOOP",
        "PROCESS",
    )


def test_a_diagnostic_is_frozen() -> None:
    d = diagnose(errors.LOOP_EXHAUSTED, "x")
    with pytest.raises(AttributeError):
        d.owner = "system"  # type: ignore[misc]
    assert isinstance(d, Diagnostic)

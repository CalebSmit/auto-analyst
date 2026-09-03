"""The Recompute Engine: pure arithmetic over rows, knowing nothing about who claimed what."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.recompute import OPERATIONS, recompute

ROOT = Path(__file__).resolve().parents[2]


def test_every_derivation_op_in_the_contract_is_implemented() -> None:
    import json

    schema = json.loads((ROOT / "contracts" / "figure.schema.json").read_text(encoding="utf-8"))
    ops = set(schema["$defs"]["derivation"]["properties"]["op"]["enum"])
    assert ops == set(OPERATIONS)


def test_a_sum_over_rows(tmp_path: Path) -> None:
    r = recompute("sum", [[240000.0, 60000.0, 18400.0, 12600.0]], 331000.0, tolerance=1.0)
    assert r.recomputed == 331000.0 and r.matches and r.delta == 0.0 and r.rows_used == 4


def test_a_difference_is_first_minus_the_rest() -> None:
    assert recompute("difference", [[1000.0], [250.0], [50.0]], 700.0).matches


def test_a_quotient_over_zero_is_an_error_not_a_number() -> None:
    with pytest.raises(ZeroDivisionError):
        recompute("quotient", [[100.0], [0.0]], 1.0)


def test_annualize_is_twelve_over_the_months_read() -> None:
    assert recompute("annualize", [[100.0, 100.0, 100.0]], 1200.0).matches


def test_tolerance_is_inclusive() -> None:
    assert recompute("sum", [[10.0]], 11.0, tolerance=1.0).matches
    assert not recompute("sum", [[10.0]], 11.01, tolerance=1.0).matches


def test_the_engine_knows_nothing_about_models() -> None:
    """Only the claim, the citation and the rows."""
    tree = ast.parse((ROOT / "tools" / "recompute.py").read_text(encoding="utf-8"))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
    }
    assert not any(i.startswith(("ports", "harness", "anthropic", "registries")) for i in imported)


def test_the_guard_does_not_import_the_engine() -> None:
    """Binding a tool implementation is the runtime's job. The tie-out guard takes the
    engine as a parameter and imports no module under tools/."""
    tree = ast.parse((ROOT / "guards" / "tieout.py").read_text(encoding="utf-8"))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
    }
    assert not any(i == "tools" or i.startswith("tools.") for i in imported)


def test_an_unknown_op_is_refused() -> None:
    with pytest.raises(ValueError, match="derivation op"):
        recompute("guess", [[1.0]], 1.0)

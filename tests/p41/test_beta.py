"""P41: beta - the comps' median unlevered beta, relevered to the subject company.

The analyst's method (knowledge, 2026-09-17-2), with the two things not yet confirmed - the
formula and the capital structure - left as the caller's explicit choices.
"""

from __future__ import annotations

import pytest

from tools.beta import FORMULAS, Comparable, median_unlevered, relever, unlever

TOL = 1e-5


def test_hamada_unlevers_and_relevers_with_the_tax_shield() -> None:
    # 1.2 levered at D/E 0.5 and 25% tax: 1.2 / (1 + 0.75 * 0.5) = 0.872727
    assert unlever(1.2, 0.5, 0.25, formula="hamada") == pytest.approx(1.2 / 1.375, abs=TOL)
    assert relever(0.8, 0.5, 0.25, formula="hamada") == pytest.approx(0.8 * 1.375, abs=TOL)


def test_harris_pringle_has_no_tax_term() -> None:
    assert relever(0.8, 0.5, 0.25, formula="harris_pringle") == pytest.approx(1.2, abs=TOL)


def test_unlevering_then_relevering_at_the_same_structure_returns_the_beta() -> None:
    for formula in FORMULAS:
        back = relever(unlever(1.1, 0.4, 0.21, formula=formula), 0.4, 0.21, formula=formula)
        assert back == pytest.approx(1.1, abs=TOL)


@pytest.mark.parametrize("formula", ["", "damodaran", None])
def test_there_is_no_default_formula(formula: object) -> None:
    with pytest.raises(ValueError, match="not a relevering formula"):
        relever(1.0, 0.5, 0.25, formula=formula)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not a relevering formula"):
        median_unlevered([Comparable("A", unlevered_beta=1.0)], formula=formula)  # type: ignore[arg-type]


@pytest.mark.parametrize(("de", "tax"), [(-0.1, 0.25), (0.5, 1.0), (0.5, -0.2)])
def test_impossible_structures_are_refused(de: float, tax: float) -> None:
    with pytest.raises(ValueError):
        relever(1.0, de, tax, formula="hamada")


def test_the_median_names_every_company_used_and_left_out() -> None:
    comps = [
        Comparable("Alpha", unlevered_beta=0.9),
        Comparable("Bravo", levered_beta=1.375, debt_to_equity=0.5, tax_rate=0.25),  # -> 1.0
        Comparable("Charlie", unlevered_beta=1.3),
        Comparable("Delta"),
        Comparable("Echo", levered_beta=1.1),
    ]
    result = median_unlevered(comps, formula="hamada")
    assert [name for name, _ in result.used] == ["Alpha", "Bravo", "Charlie"]
    assert result.value == pytest.approx(1.0, abs=TOL)
    assert dict(result.left_out) == {
        "Delta": "no beta in the export",
        "Echo": "a levered beta with no debt to equity or tax rate to unlever it at",
    }
    assert result.formula == "hamada"


def test_an_even_set_averages_the_middle_two() -> None:
    comps = [
        Comparable(n, unlevered_beta=b) for n, b in [("A", 0.6), ("B", 1.4), ("C", 0.8), ("D", 1.0)]
    ]
    assert median_unlevered(comps, formula="hamada").value == pytest.approx(0.9, abs=TOL)


def test_an_inconvenient_beta_is_not_dropped() -> None:
    """Dropping a comp is the analyst's call on the set; the median uses every beta given."""
    comps = [Comparable(n, unlevered_beta=b) for n, b in [("A", 0.9), ("B", 1.0), ("C", 4.5)]]
    result = median_unlevered(comps, formula="hamada")
    assert len(result.used) == 3 and result.value == pytest.approx(1.0, abs=TOL)


def test_no_usable_beta_is_no_median() -> None:
    result = median_unlevered([Comparable("A")], formula="hamada")
    assert result.value is None and result.left_out

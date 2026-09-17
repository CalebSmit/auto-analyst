"""P39: a citation is verified by finding the cited number where it says it is.

From the LlamaIndex due-diligence agent (docs/research/ai-in-valuation.md): an answer's
citation is only trusted once the cited text is found on the cited page, through a few
forgiving matches for how numbers are printed, and one that is not found is shown rather
than hidden. Here the provenance guard already required the location to exist; it now
requires the number to be there too, for every figure read off the page.
"""

from __future__ import annotations

from typing import Any

import pytest

from guards.provenance import ProvenanceGate, cited_value_found, printed_number
from ops.run_store import SqlRunStore
from ops.source_parse import Row, SourceParseStore
from registries.contracts import ContractRegistry
from registries.errors import CITED_VALUE_ABSENT, UNKNOWN_SOURCE
from tests.p13.conftest import ROWS_LOCATOR, SOURCE, TOTAL_LOCATOR, TRUE_TOTAL, figure

# --------------------------------------------------------------- printed numbers


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("240,000.00", 240000.0),
        ("$240,000", 240000.0),
        ("USD 1,250", 1250.0),
        ("(18,400.00)", -18400.0),
        ("18,400-", -18400.0),
        ("−1,250", -1250.0),
        ("-1,250", -1250.0),
        ("0", 0.0),
        ("12.5", 12.5),
    ],
)
def test_a_number_as_statements_print_it(raw: str, value: float) -> None:
    assert printed_number(raw) == value


@pytest.mark.parametrize("raw", ["1.2M", "52 billion", "12%", "2025-12-31", "n/a", "", "1,23,4"])
def test_anything_else_is_not_guessed(raw: str) -> None:
    """A suffix changes the scale, and scale is the envelope's to state."""
    assert printed_number(raw) is None


# ------------------------------------------------------------------ the match


def test_found_by_value_or_by_what_is_printed() -> None:
    assert cited_value_found(240000.0, [Row("Salary", 240000.0, "240,000.00")])[0]
    assert cited_value_found(-18400.0, [Row("Allowance", None, "(18,400.00)")])[0]
    assert cited_value_found(240000.004, [Row("Salary", 240000.0, "")])[0], "within half a cent"


def test_not_found_says_what_the_rows_do_say() -> None:
    found, why = cited_value_found(204000.0, [Row("Officer salary", 240000.0, "240,000.00")])
    assert not found
    assert "does not show 204,000.00" in why and "Officer salary 240,000.00" in why


def test_the_opposite_sign_is_not_a_match_but_is_named() -> None:
    """Never the absolute value: an expense cited as a gain is the error itself."""
    found, why = cited_value_found(-12600.0, [Row("Health premium", 12600.0, "12,600.00")])
    assert not found and "opposite sign" in why


def test_a_long_block_is_summarised_not_dumped() -> None:
    rows = [Row(f"line {n}", float(n), str(n)) for n in range(1, 8)]
    found, why = cited_value_found(999.0, rows)
    assert not found and "and 4 more" in why


# ------------------------------------------------------------------ the guard


@pytest.fixture
def gate(
    store: SqlRunStore, contracts: ContractRegistry, parsed: SourceParseStore
) -> ProvenanceGate:
    return ProvenanceGate(contracts, parsed)


def check(gate: ProvenanceGate, started: str, *figures: dict[str, Any]) -> Any:
    return gate.check({"figures": list(figures)}, started, {SOURCE: 1})


def test_a_real_location_with_the_wrong_number_fails(gate: ProvenanceGate, started: str) -> None:
    result = check(gate, started, figure(204000.0, locator=ROWS_LOCATOR))
    assert not result.passed and result.code == CITED_VALUE_ABSENT
    assert "204,000.00" in result.reasons[0] and "240,000.00" in result.reasons[0]


def test_the_right_number_at_the_right_location_passes(gate: ProvenanceGate, started: str) -> None:
    assert check(gate, started, figure(TRUE_TOTAL, locator=TOTAL_LOCATOR)).passed
    assert check(gate, started, figure(60000.0, locator=ROWS_LOCATOR)).passed


def test_a_derived_figure_is_left_to_the_tie_out(gate: ProvenanceGate, started: str) -> None:
    """A sum is not on any one row; the Tie-Out Check re-derives it."""
    derived = figure(331000.0, locator=ROWS_LOCATOR, derivation={"op": "sum", "of": [ROWS_LOCATOR]})
    assert check(gate, started, derived).passed


def test_a_missing_location_is_still_the_worse_finding(gate: ProvenanceGate, started: str) -> None:
    result = check(
        gate,
        started,
        figure(204000.0, locator=ROWS_LOCATOR),
        figure(1.0, locator="TB_FY25!Z99"),
    )
    assert result.code == UNKNOWN_SOURCE and result.failed == 2

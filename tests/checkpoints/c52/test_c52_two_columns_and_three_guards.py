"""C52 - Two columns, and three guards that did not move.

P85 changed what the Source Parse Store holds and the grammar of the locators that address
it. Three guards resolve against exactly that: Provenance asks whether a cited locator
exists and whether the value is really there, Tie-Out asks for the rows behind a stated
total, and the Numeric Lock compares a released figure against the value first read.

The whole design was chosen so those three would not have to change - the column went into
the locator rather than more values into the row. That is a claim, and P85's own tests
cannot test it: they read documents. This resolves real figures against a real store
through the real guards.

`test_a_total_is_footed_against_its_own_column` is the one worth having. Footing got
*more* exact, not less: before, a comparative table wrote one block of whichever column
the reader happened to take, so a total could only ever be re-added against that one. Now
each column is its own block, and a 2025 total that re-adds against 2024's rows is a
mismatch the guard can see - which it could not before, because those rows were never
stored.
"""

from __future__ import annotations

from typing import Any

import pytest

from guards import GuardFailed
from intake.readers.documents import read_document
from ops.source_parse import LateResult, Row, SourceParseStore, parse_locator
from tests.p13.conftest import ENGAGEMENT, SOURCE, figure

STATEMENT = (
    "CONSOLIDATED STATEMENTS OF OPERATIONS",
    "(in thousands of US dollars)",
    "                          2025          2024",
    "Officer salary           240,000       232,000",
    "Officer bonus             60,000        55,000",
    "Auto allowance            18,400        18,400",
    "Health premium            12,600        11,900",
    "Total officer comp       331,000       317,300",
)


@pytest.fixture
def written(store: Any, started: str) -> SourceParseStore:
    """A real comparative document, read and written to the real store."""
    parsed = read_document("\n".join(STATEMENT).encode("utf-8"), "is.txt")
    parse_store = SourceParseStore(store)
    for locator, rows in parsed.blocks().items():
        parse_store.write(started, SOURCE, locator, rows)
    return parse_store


# ------------------------------------------------- the store holds what was read


def test_each_column_is_its_own_block(written: SourceParseStore, started: str) -> None:
    locators = set(written.locators(started, SOURCE))
    assert "p1/t1/c1" in locators and "p1/t1/c2" in locators


def test_the_two_columns_hold_different_figures(written: SourceParseStore, started: str) -> None:
    """The defect this closed, at the far end of the pipe: before, one of these two sets
    of numbers simply did not exist anywhere."""
    first = {r.label: r.value for r in written.rows(started, SOURCE, "p1/t1/c1")}
    second = {r.label: r.value for r in written.rows(started, SOURCE, "p1/t1/c2")}
    assert first["Officer salary"] == 240000.0
    assert second["Officer salary"] == 232000.0
    assert first.keys() == second.keys(), "one row, two columns, one set of labels"


def test_every_locator_the_reader_writes_is_one_the_resolver_can_read(
    written: SourceParseStore, started: str
) -> None:
    """The store refuses a locator the grammar cannot parse, so this is really a check that
    the reader and the grammar were changed together."""
    for locator in written.locators(started, SOURCE):
        parse_locator(locator)


# ------------------------------------------------- provenance resolves them unchanged


def test_provenance_accepts_a_figure_citing_a_column(
    provenance_gate: Any, written: SourceParseStore, started: str, sources: dict[str, int]
) -> None:
    """A citation into the second column, resolved by a guard that was not told columns
    exist."""
    result = provenance_gate.run(
        {"figures": [figure(232000.0, locator="p1/t1/c2/r1")]}, started, ENGAGEMENT, sources
    )
    assert result.passed, result.failures


def test_provenance_refuses_a_figure_that_cites_the_wrong_column(
    provenance_gate: Any, written: SourceParseStore, started: str, sources: dict[str, int]
) -> None:
    """The failure the columns make newly catchable. 240,000 is a real figure in this
    document and it is not in the 2024 column, and before P85 the 2024 column was not in
    the store at all - so a figure citing it could not be checked against anything."""
    with pytest.raises(GuardFailed) as refused:
        provenance_gate.run(
            {"figures": [figure(240000.0, locator="p1/t1/c2/r1")]}, started, ENGAGEMENT, sources
        )
    assert refused.value.diagnostic.code.startswith("SKILL.")


def test_provenance_still_refuses_a_locator_that_is_not_there(
    provenance_gate: Any, written: SourceParseStore, started: str, sources: dict[str, int]
) -> None:
    """There is no ninth column. The code matters and not only the refusal: a missing
    locator and a value that is not in the rows are different failures with different
    repairs, and asserting only that something was raised could not tell them apart -
    which it could not, until this named the code."""
    with pytest.raises(GuardFailed) as refused:
        provenance_gate.run(
            {"figures": [figure(240000.0, locator="p1/t1/c9/r1")]}, started, ENGAGEMENT, sources
        )
    assert refused.value.diagnostic.code == "SKILL.UNKNOWN_SOURCE"


# ------------------------------------------------- and tie-out foots one column


def summing(total: float, of: str) -> dict[str, Any]:
    """A figure the skill says it derived by adding up one block."""
    return {
        "figures": [
            figure(total, locator="p1/t1/c1/r5", derivation={"op": "sum", "of": [of]})
        ]
    }


def test_a_total_is_footed_against_its_own_column(
    tieout_gate: Any, written: SourceParseStore, started: str
) -> None:
    """Through the real gate. The 2025 column sums to 331,000 including its own stated
    total, so the guard is given the block and asked to re-add it - which is exactly what
    it did before columns existed, against a block that is now one year rather than a
    mixture."""
    rows = written.rows(started, SOURCE, "p1/t1/c1")
    assert tieout_gate.run(summing(sum(r.value for r in rows), "p1/t1/c1"),
                           started, ENGAGEMENT).passed


def test_a_total_that_foots_against_the_other_year_is_a_mismatch(
    tieout_gate: Any, written: SourceParseStore, started: str
) -> None:
    """The check that could not exist before. A 2025 total re-added against 2024's rows is
    wrong - and before P85 only one of those two sets of rows was ever stored, so nothing
    could tell them apart. This is footing getting *more* exact, not less."""
    first = sum(r.value for r in written.rows(started, SOURCE, "p1/t1/c1"))
    second = sum(r.value for r in written.rows(started, SOURCE, "p1/t1/c2"))
    assert first != second, "the two years must differ or this proves nothing"

    with pytest.raises(GuardFailed) as refused:
        tieout_gate.run(summing(first, "p1/t1/c2"), started, ENGAGEMENT)
    assert refused.value.diagnostic.code == "GUARD.TIEOUT_MISMATCH"


def test_the_stated_totals_are_each_in_their_own_column(
    written: SourceParseStore, started: str
) -> None:
    first = {r.label: r.value for r in written.rows(started, SOURCE, "p1/t1/c1")}
    second = {r.label: r.value for r in written.rows(started, SOURCE, "p1/t1/c2")}
    assert first["Total officer comp"] == 331000.0
    assert second["Total officer comp"] == 317300.0


# ------------------------------------------------- and a single column is unchanged


def test_a_single_column_document_writes_exactly_what_it_used_to(
    store: Any, started: str
) -> None:
    """The compatibility the design turns on. A locator is what a figure cites, and a
    citation outlives the code that made it - so a document with one column of figures has
    to write the locators it wrote before this phase, character for character."""
    parsed = read_document(
        b"Officer salary   240,000\nOfficer bonus     60,000\nAuto allowance    18,400\n",
        "notes.txt",
    )
    written_here = set(parsed.blocks())
    assert "p1/t1" in written_here
    assert not any("/c" in locator for locator in written_here)


def test_the_guards_were_not_taught_what_a_column_is() -> None:
    """The claim the whole design rests on, stated where it can fail. If a guard ever has
    to know, the column belongs in the row after all and this checkpoint was wrong."""
    import inspect

    from guards import provenance, tieout
    from guards.numeric_lock import NumericLock

    for module in (provenance, tieout, NumericLock):
        source = inspect.getsource(module)
        assert "column" not in source.lower(), f"{module} now knows about columns"


def test_a_row_is_still_one_value(written: SourceParseStore, started: str) -> None:
    """`Row` keeping its shape is why the guards did not move. A row that grew a list of
    values would have made every one of them ask which value it meant."""
    row = written.rows(started, SOURCE, "p1/t1/c1")[0]
    assert isinstance(row.value, float)
    assert not hasattr(row, "values")


# ------------------------------------------------- and the store's own rules hold


def test_a_column_is_written_once_like_any_other_block(
    written: SourceParseStore, started: str
) -> None:
    """Immutability is per locator, and the columns are locators - so the rule that a block
    cannot be rewritten covers them without being told about them."""
    with pytest.raises(LateResult):
        written.write(started, SOURCE, "p1/t1/c1", [Row("Something else", 1.0, "1.00")])

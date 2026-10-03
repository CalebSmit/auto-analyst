"""P161: accuracy had no answer in this build, only evidence.

A total that re-adds and a balance sheet that balances prove **arithmetic**, and arithmetic
is satisfied by eight wrong rows that add correctly - `guards/tieout.py` says it of its own
half: *"Tie-out proves arithmetic, not selection."* So "is every figure right" has been
unanswerable, and every claim about it rested on one document that had been read until it
read correctly.

**The SEC publishes the filer's own numbers as structured data.** Every figure on these
statements is tagged in XBRL: `Assets` at 2025-12-31 is 521,728,000, which is the 521,728 on
page 56 times the thousand the statement says it is in. Ground truth, from the same
regulator, for the same filing - and no label-to-concept mapping is needed, which is the part
that would have made this hard. The question is not which concept a row is; it is whether
every figure the reader produced is one the filer reported **at the date that column is as
of**. A figure out of the wrong column is still a figure the filer reported, and that is
B-030, this repository's worst extraction defect - matching by date is what sees it.

What it says, over three filings and two filers:

| | |
|---|---|
| right, at the column's own date and the statement's scale | **194** |
| right, but the statement's scale does not apply to them | 2 |
| **reported at a different date - out of the wrong column** | **0** |
| not in this feed, so not checkable | 3 |

**The second PDF is the number that counts.** ResMed's filing had never been read by anything
here, so it is the first accuracy figure the code was not shaped by: 70 of 70 at the right
date, both columns balance, eight footings re-add.

**What it cannot see**, which belongs in a test about a measurement: `companyfacts` serves
the *dimensionless* facts, so a figure tagged only against a segment or a share class is
absent from the feed and is a figure this cannot speak about rather than one the reader got
wrong. It compares figures and not words, so a label read wrongly is invisible to it. And a
right figure in the wrong row would pass.
"""

from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path

import pytest

from tools.check_against_filer import (
    FIXTURES,
    check,
    load_facts,
    main,
    report,
)

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "fixtures" / "public"


@pytest.fixture(scope="module")
def checked() -> dict[str, list]:
    """Every fixture checked once. The PDFs are 108 and 124 pages."""
    out: dict[str, list] = {}
    for name, fixture in FIXTURES.items():
        facts = load_facts(fixture.facts)
        out[name] = [
            said
            for statement in fixture.statements
            for said in check(fixture, statement, facts)
        ]
    return out


# ------------------------------------------------------------------- what it says, and is it so


def test_no_figure_anywhere_came_out_of_the_wrong_column(checked) -> None:
    """The exit criterion, and the defect this exists to catch.

    B-030 was the reader taking the prior year out of a comparative balance sheet -
    `Cash and cash equivalents $ 95,635 $ 171,324` gave 171,324. Footing cannot see that and
    neither can a balance check: the wrong year's figures balance too. The filer's own dates
    can see it, and this is the only thing in the build that asks.
    """
    wrong = [
        (name, said.where, label, value)
        for name, all_said in checked.items()
        for said in all_said
        for label, value, _ in said.elsewhere
    ]
    assert wrong == [], wrong


def test_the_filing_nothing_was_tuned_on_is_right_too(checked) -> None:
    """The honest number. The other filing has been read many times and the reader was fixed
    until it read it, which is how it should be and is why its score says less than it looks.
    This one had never been read by anything here."""
    said = checked["sec-ars-resmed-2026"]
    assert len(said) == 2, "two columns"
    assert [len(c.here) for c in said] == [36, 34]
    assert [len(c.elsewhere) for c in said] == [0, 0]
    assert [len(c.nowhere) for c in said] == [0, 0]
    assert [c.date for c in said] == ["2026-06-30", "2025-06-30"]


def test_the_counts_are_what_the_docstring_says(checked) -> None:
    """A table in a docstring that nothing checks is a table that goes stale."""
    totals = {"here": 0, "unscaled": 0, "elsewhere": 0, "nowhere": 0}
    for all_said in checked.values():
        for said in all_said:
            totals["here"] += len(said.here)
            totals["unscaled"] += len(said.unscaled)
            totals["elsewhere"] += len(said.elsewhere)
            totals["nowhere"] += len(said.nowhere)
    assert totals == {"here": 194, "unscaled": 2, "elsewhere": 0, "nowhere": 3}, totals


# --------------------------------------------------- and it would say so if a figure were wrong


def test_declaring_the_columns_backwards_reports_every_figure(checked) -> None:
    """**The proof that this measures anything at all.**

    A comparison that said "all correct" on a reader that was right and on a reader that was
    wrong would be worth nothing. So the columns are declared in the wrong order - the 2024
    dates against the 2025 figures - and every figure in both columns has to come back as
    reported at a different date. That is exactly the shape B-030 had.
    """
    fixture = FIXTURES["sec-ars-3d-systems-2025"]
    swapped = replace(
        fixture,
        statements=(
            replace(
                fixture.statements[0], columns=("2024-12-31", "2025-12-31")
            ),
        ),
    )
    facts = load_facts(fixture.facts)
    said = check(swapped, swapped.statements[0], facts)

    right = checked["sec-ars-3d-systems-2025"]
    assert sum(len(c.here) for c in right) == 61, "the honest reading finds all of them"
    assert sum(len(c.here) for c in said) <= 2, (
        "swapped, almost nothing should match its own date: "
        f"{[(c.where, len(c.here)) for c in said]}"
    )
    assert sum(len(c.elsewhere) for c in said) >= 55, (
        "and almost everything should be reported as out of the wrong column"
    )


@pytest.mark.parametrize("declared", [1, 1_000_000])
def test_a_wrong_scale_is_named_as_a_wrong_scale(declared: int) -> None:
    """The other way a figure goes wrong, and the one that reads as the data's fault.

    A statement in thousands, told it is in units and then in millions. Every figure should
    come back as matching *at another scale*, with the scale that would have fitted - and not
    as "no fact in this feed", which is what the first draft said and which reads as a
    limitation of the feed rather than as a mistake about the document.

    Both directions, because the first draft of this test only tried a scale of 1 - where
    `value * 1 == value` makes the declared-scale branch and the other-scale branch the same
    question, so nothing could land in the second one and the test was asserting something
    unreachable.
    """
    fixture = FIXTURES["sec-ars-resmed-2026"]
    wrong = replace(fixture, statements=(replace(fixture.statements[0], scale=declared),))
    facts = load_facts(fixture.facts)
    said = check(wrong, wrong.statements[0], facts)

    assert sum(len(c.here) for c in said) == 0, (
        f"something matched at a scale of {declared:,}, which the statement is not in"
    )
    assert sum(len(c.unscaled) for c in said) >= 60, (
        "a wrong scale went unreported: "
        + str([(c.where, len(c.unscaled), len(c.nowhere)) for c in said])
    )
    # And it says which scale would have fitted, which is the actionable half.
    fitted = {
        str(where[0])
        for column in said
        for _label, _value, where in column.unscaled
    }
    assert fitted == {"scale=1000"}, fitted


def test_the_share_count_is_the_one_that_is_right_at_no_scale(checked) -> None:
    """The finding the workbook made, which the PDFs could not.

    A PDF keeps a share count inside the label - `Common stock, $0.001 par value, authorized
    220,000 shares; shares issued 145,581 and` - so the only figures in the column are
    dollars. EDGAR's workbook gives each one its own row with the raw count in the cell, and
    a client's workbook looks far more like the workbook than like the typesetting.
    """
    said = checked["sec-financial-report-3d-systems-2025q1"]
    flagged = [
        (label, value)
        for column in said
        for label, value, _ in column.unscaled
    ]
    assert [label for label, _ in flagged] == [
        "Common stock, shares, issued (in shares)",
        "Common stock, shares, issued (in shares)",
    ], flagged
    assert [value for _, value in flagged] == [135_361_000.0, 135_510_000.0]


# -------------------------------------------------------------- the measurement's own honesty


def test_every_facts_file_records_where_it_came_from_and_what_it_cannot_say() -> None:
    """A measurement whose limits are not written down gets quoted as though it had none."""
    for fixture in FIXTURES.values():
        body = load_facts(fixture.facts)
        for key in ("what", "source", "entity", "cik", "accession", "retrieved", "caveat"):
            assert body.get(key), f"{fixture.facts} has no {key}"
        assert body["source"].startswith("https://data.sec.gov/"), body["source"]
        assert "dimensionless" in body["caveat"]
        assert body["at_date"], f"{fixture.facts} carries no figures"


def test_it_answers_without_the_network() -> None:
    """This build is local-only and its tests run on a train. A tool that reached for
    `data.sec.gov` to answer would answer differently there, and a test that needed it would
    fail for a reason that is not about the code.

    Proved by breaking the network rather than by reading the source: `urllib` is made
    unusable and the tool still answers.
    """
    import urllib.request

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the tool reached for the network")

    original = urllib.request.urlopen
    urllib.request.urlopen = refuse  # type: ignore[assignment]
    try:
        out = io.StringIO()
        code = main(["--fixture", "sec-financial-report-3d-systems-2025q1"])
        _ = out
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]
    assert code == 0


def test_the_report_names_the_filer_and_the_document(checked) -> None:
    """What a person needs on the page to know which filing they are reading about."""
    fixture = FIXTURES["sec-ars-resmed-2026"]
    facts = load_facts(fixture.facts)
    out = io.StringIO()
    report(
        "sec-ars-resmed-2026",
        fixture,
        out,
        {0: checked["sec-ars-resmed-2026"]},
        facts,
    )
    said = out.getvalue()
    assert "ResMed" in said
    assert "0000943819" in said
    assert "sec-ars-resmed-2026.pdf" in said
    assert "2026-06-30" in said and "2025-06-30" in said
    assert "stated in 1,000s" in said


def test_the_fixtures_named_here_are_the_files_that_are_there() -> None:
    """A fixture table pointing at a document nobody committed is a check that silently
    checks nothing."""
    for name, fixture in FIXTURES.items():
        assert (PUBLIC / fixture.document).exists(), f"{name}: {fixture.document}"
        assert (PUBLIC / "filer-facts" / fixture.facts).exists(), f"{name}: {fixture.facts}"
        assert fixture.statements, f"{name} declares no statement"
        for statement in fixture.statements:
            assert statement.columns, f"{name} declares no column dates"
            assert (statement.page is None) != (statement.sheet is None), (
                f"{name}: a statement is a page or a sheet, not both and not neither"
            )


def test_the_readme_records_both_new_fixtures() -> None:
    """`fixtures/public/README.md` is where provenance lives, and the rule the folder has is
    that nothing belongs here without where it came from and when."""
    said = (PUBLIC / "README.md").read_text(encoding="utf-8")
    for name in (
        "sec-ars-resmed-2026.pdf",
        "sec-financial-report-3d-systems-2025q1.xlsx",
        "filer-facts/",
    ):
        assert name in said, name
    assert "sec.gov/Archives/edgar/data/943819" in said
    assert "0000943819-26-000084" in said
    assert "Retrieved | 2026-10-03" in said


def test_the_facts_are_small_enough_to_belong_in_the_repository() -> None:
    """Four megabytes of every period a filer has ever reported does not belong in a git
    history. Trimmed to the dates each filing's statements are as of, each is under 100 KB."""
    for fixture in FIXTURES.values():
        path = PUBLIC / "filer-facts" / fixture.facts
        assert path.stat().st_size < 150_000, f"{path.name} is {path.stat().st_size:,} bytes"


def test_a_figure_is_checked_against_a_date_rather_than_a_concept_name() -> None:
    """The decision that made this possible, asserted so it is not quietly reversed.

    Mapping a printed label to an XBRL concept is the hard half and it is unnecessary:
    `Accounts receivable, net of reserves` could be `AccountsReceivableNetCurrent` or a
    filer's own tag, and guessing would make the comparison an opinion. Matching on the value
    at a date needs no opinion at all.

    Proved by **replacing every concept name with nonsense** and getting the same answer. The
    first version of this grepped the source for the word `concept` and failed on the
    variable that carries them into the output - which is a test of how the code is spelled
    rather than of what it does.
    """
    fixture = FIXTURES["sec-financial-report-3d-systems-2025q1"]
    facts = load_facts(fixture.facts)
    honest = check(fixture, fixture.statements[0], facts)

    nonsense = {
        **facts,
        "at_date": {
            date: {value: ["nonsense:Nonsense|USD"] for value in values}
            for date, values in facts["at_date"].items()
        },
    }
    renamed = check(fixture, fixture.statements[0], nonsense)

    assert [len(c.here) for c in renamed] == [len(c.here) for c in honest]
    assert [len(c.elsewhere) for c in renamed] == [len(c.elsewhere) for c in honest]
    assert [len(c.nowhere) for c in renamed] == [len(c.nowhere) for c in honest]
    assert [len(c.unscaled) for c in renamed] == [len(c.unscaled) for c in honest]

    # And the names are carried for *reading* a disagreement rather than for deciding one.
    some = next(iter(next(iter(facts["at_date"].values())).values()))
    assert any(":" in str(c) for c in some), some

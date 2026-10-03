"""C85 - what reaches a model, and what counts as evidence.

* **P153.** The reader decoded anything it did not recognise as UTF-8 and called the result a
  document. An RTF arrived as one line of `{\\rtf1\\ansi...}` and a `.doc` as a dump of the
  bytes 0 to 255 - both written to the parse store as rows a figure could cite, and both
  appended to the text a model is sent.
* **P154.** The footing check knew a total of lines and a total of subtotals, and a real
  balance sheet's grand total is a mix of the two. `Total assets`, `Total liabilities` and
  the line that totals the other side were all uncovered, so every row above them was too.

Both feed the same two consumers, and neither phase is placed to ask about either.

**The Untrusted Content Boundary** is given whatever the readers produce. A reader that
refuses a format is only worth having if nothing from that format gets past it by another
route, so the question is asked of the text itself: is there anything in what a model would
be sent that no reader claims to have read?

**`review/router.py`** routes a figure to a person unless a total that re-adds covers it.
P154 widened what re-adds, and widening the evidence is the one change that can quietly stop
a figure being shown. So every footing is re-added here independently - not asked whether it
thinks it covers its rows, but given its rows and made to prove it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.fingerprint import BY_EXTENSION, DOCUMENT, READ, SPREADSHEET, kind_of, mime_of
from intake.readers.documents import NotText, read_document
from intake.readers.footing import footings_in, two_sides
from intake.readers.tabular import converts

ROOT = Path(__file__).resolve().parents[3]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


# ------------------------------------------------- every figure's cover, re-added here


def test_every_footing_really_re_adds_to_its_total(filing) -> None:
    """Given its rows, not asked whether it believes itself.

    A footing is the only evidence that lets a figure past a person. A reader that returned
    the right ordinals for the wrong reason, or widened what it accepts, would show up here
    and nowhere else - the phase that widened it tests the totals it wanted to fix.

    What that is worth on this document, measured: the nearest thing to a footing that is
    not one is `Total` on page 31, out by $1.60, and the next is out by $753. So a reader
    whose tolerance went past a couple of dollars would hand this check a total that does
    not add, and one loosened only to a dollar would not - which is the range of slack this
    document can see, and the reason `tests/p154` asks the same question of a statement
    written small enough to be out by nine dollars on purpose.
    """
    wrong = []
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                by_ordinal = {row.ordinal: row for row in column.rows}
                for found in footings_in(column.rows).footings:
                    if not found.covered:
                        continue
                    parts = [by_ordinal[o].value for o in found.ordinals]
                    assert all(v is not None for v in parts), found.label
                    re_added = sum(v for v in parts if v is not None)
                    if abs(re_added - found.value) > 0.005:
                        wrong.append(
                            f"p{page.number}: {found.label} says {found.value:,.2f} "
                            f"and its {len(parts)} rows add to {re_added:,.2f}"
                        )
    assert wrong == [], "a footing that does not foot:\n" + "\n".join(wrong[:8])


def test_a_covered_row_is_covered_by_exactly_one_total(filing) -> None:
    """Cover claimed twice is evidence counted twice. The carried-figure rule exists to stop
    a subtotal repeated as a later total covering its own rows a second time."""
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                seen: dict[int, str] = {}
                for found in footings_in(column.rows).footings:
                    for ordinal in found.ordinals:
                        assert ordinal not in seen, (
                            f"p{page.number}: row {ordinal} is covered by "
                            f"{seen.get(ordinal)!r} and by {found.label!r}"
                        )
                        seen[ordinal] = found.label


def test_a_total_covers_rows_that_come_before_it(filing) -> None:
    """A statement's total sums what is above it. A run reaching past the total would be a
    reader finding a combination rather than reading a layout."""
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                ordinals = {row.ordinal: n for n, row in enumerate(column.rows)}
                for n, found in enumerate(footings_in(column.rows).footings):
                    del n
                    at = next(
                        (ordinals[r.ordinal] for r in column.rows if r.label == found.label),
                        None,
                    )
                    if at is None:
                        continue
                    for ordinal in found.ordinals:
                        assert ordinals[ordinal] < at, (
                            f"p{page.number}: {found.label!r} covers a row below it"
                        )


def test_the_balance_sheet_still_balances_and_only_the_balance_sheet(filing) -> None:
    """One check, on the one statement that states both sides. A check that spoke about
    every page would be noise, and a check that spoke about none would be nothing.

    The scope of what this proves, measured rather than assumed: of a hundred and eight
    pages, **page 56 is the only one that writes any of the three labels**, and it writes
    `Total assets` exactly, `Total liabilities` alone, and the line that totals the other
    side. So this catches taking `Total liabilities` for the other side - the break that
    would report every balance sheet as out by its equity - and cannot see the prefix rule
    or the one-side rule, because no page here holds a `Total assets ...` line or states a
    single side. Those two are held by `tests/p154` on statements written for them, and
    saying so here is the difference between a checkpoint and a checkpoint that reads as
    though it covered more than it does.
    """
    speaks = []
    for page in filing.pages:
        widest = max((len(t.columns) for t in page.tables), default=0)
        for n in range(widest):
            rows = [
                row
                for table in page.tables
                if n < len(table.columns)
                for row in table.columns[n].rows
            ]
            sides = two_sides(rows)
            if sides.stated:
                speaks.append((page.number, sides.balances))
    assert speaks == [(56, True), (56, True)], speaks


# ------------------------------------------- and nothing reaches a model unread


def test_nothing_a_model_is_sent_is_markup_or_a_decoding_artefact(filing) -> None:
    """Asked of every reader, because the boundary is given all of them.

    The filing alone cannot answer it. Breaking the RTF reader so that it left its control
    words in place kept this test green, because a PDF's text could never hold one - the
    assertion could not fail, which is this repository's own named defect. The reader that
    has markup to leave behind is the one that has to be asked, and the refusal is what
    keeps a binary file's bytes out, so all three are put to the question.
    """
    backslash = chr(92)
    artefact = chr(0xFFFD)

    # Built rather than written for two reasons. A control word is terminated by the first
    # non-alphanumeric character, so a literal makes one unknown word out of a control word
    # and the sentence after it; and an editor that resolves an escape on the way to disk
    # writes the character into the file, after which the test reads as though somebody had
    # typed it. Built here rather than imported from P153, because a checkpoint that borrows
    # a phase's fixture borrows the assumption it was written under.
    letter = (
        "{" + backslash + "rtf1" + backslash + "ansi" + backslash + "ansicpg1252"
        + backslash + "deff0"
        + "{" + backslash + "fonttbl{" + backslash + "f0" + backslash + "fnil Calibri;}}"
        + "{" + backslash + "*" + backslash + "generator Riched20 10.0;}"
        + backslash + "pard Fee: " + backslash + "'2445,000" + backslash + "par" + chr(10)
        + "}"
    ).encode("cp1252")

    reads = {
        "the filing": filing.as_text(),
        "an rtf": read_document(letter, "Engagement letter.rtf").as_text(),
    }
    for what, text in reads.items():
        assert artefact not in text, f"a decoding artefact reached {what}"
        for markup in ("rtf1", "fonttbl", "ansicpg", "Riched20", "Calibri"):
            assert markup not in text, f"{markup} reached {what}"
    # A surviving backslash in an RTF is a control word the reader did not resolve. Not
    # asked of the filing, whose own prose contains one legitimately.
    assert backslash not in reads["an rtf"], "an unresolved escape reached a model"
    assert "$45,000" in reads["an rtf"], "and the words themselves still have to arrive"

    # And a file that is not text produces no text at all, so there is nothing of it to put
    # in front of a model in the first place.
    with pytest.raises(NotText):
        read_document(bytes.fromhex("d0cf11e0a1b11ae1") + bytes(range(256)), "notes.txt")


def test_every_format_the_table_routes_is_either_read_or_refused() -> None:
    """Being routed and being read are two claims, and a format that is neither is a file
    that reaches a reader with nothing to say about it."""
    for extension, mime in BY_EXTENSION.items():
        kind = kind_of(mime)
        assert kind in ("spreadsheet", "document"), f"{extension} routes to {kind!r}"
        if kind == "spreadsheet":
            # Read by openpyxl directly, or converted to something openpyxl reads.
            assert converts(f"x{extension}") or mime in SPREADSHEET
        else:
            assert mime in DOCUMENT


def test_a_document_format_that_is_not_read_is_refused_rather_than_decoded() -> None:
    """The one in the table that is routed and not read. It has to be refused by the reader,
    not quietly decoded, or routing it is how the garbage gets in."""
    not_read = {mime for mime in DOCUMENT if mime not in READ}
    assert not_read == {"application/msword"}, not_read
    assert mime_of("letter.doc") in not_read

    ole2 = bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 64
    with pytest.raises(NotText):
        read_document(ole2, "letter.doc")


def test_the_readers_agree_about_what_a_figure_is(filing) -> None:
    """A figure that footed has to be the same figure the reader stored, after both phases
    moved what a row is and what a total is."""
    page = next(p for p in filing.pages if p.number == 56)
    rows = {row.label: row.value for table in page.tables for row in table.columns[0].rows}
    report = footings_in(
        [row for table in page.tables for row in table.columns[0].rows]
    )
    for found in report.footings:
        if found.covered:
            assert rows[found.label] == found.value

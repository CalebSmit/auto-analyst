"""P158: a letter standing in for a digit makes a row vanish, and nothing said why.

Measured on page 56 of the filing in `fixtures/public`, read by a real engine: the printed
**5,000** came back as **`5,0o0`** - a zero read as the letter o - **at 0.938 confidence**.
Too high for any score to flag, which is this build's own stated thesis about OCR.

The usual answer to a misread here is arithmetic: a total that stops adding up is what finds
one. That works when the misread produces a *wrong figure*. This one produces no figure at
all, and what happens next is why it needs its own check. Through the reader:

    Inventories l27,496   ->  label '', values []

The whole row goes, label and all. That is the safe direction - nothing wrong is stored - and
it is **silent**: the statement quietly loses a row, the total above it stops footing, and the
only thing a person is told is that some total is out by an amount nobody can account for.
The amount it is out by *is* the row that went missing.

**Report, never repair.** Substituting the digit would be this code guessing at a client's
figure and producing a plausible number, with a real locator, that the document does not
print. `reads_as` is offered because it is the first thing a person wants - and it is a
string, never a float, so nothing downstream can total it.

**Calibrated against text nobody misread**, which is the rule here. Over all 108 pages of the
filing's text layer - 58,606 tokens - it reports nothing, and two things were taken out to
get there, both on the measurement:

* the **two-digit floor**: without it the rule reported `1B` and `9B` on four pages, which
  are billions written the way people write them;
* **`D` for zero**: a real confusion on a bad photocopy, and it reported `21D` twice -
  *"contribution under Section 10(b) and 21D of the Securities Exchange Act"*. Two findings
  that are not findings out of three is the ratio this repo takes a check out over, and the
  company in this filing is called 3D Systems.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intake.readers.documents import Line, read_document
from intake.readers.misread import CONFUSIONS, Misread, misreads_in, nearly_a_figure

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"
CAPTURE = ROOT / "fixtures" / "public" / "ocr-sec-ars-3d-systems-p56.json"


def rows_of(lines: list[str]) -> list[tuple[str, float]]:
    """What the reader makes of these lines, as a page of a PDF.

    Through `read_document` rather than against a helper, because what matters is the path a
    client's file actually takes.
    """
    from tests.p17.conftest import build_pdf

    doc = read_document(build_pdf([(line, 10.0) for line in lines]), "TB_FY25.pdf")
    return [
        (row.label, row.value)
        for page in doc.pages
        for table in page.tables
        for column in table.columns
        for row in column.rows
        if row.value is not None
    ]


@pytest.fixture(scope="module")
def captured() -> dict:
    return json.loads(CAPTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


# ------------------------------------------------------------------ the misread that happened


def test_the_misread_the_engine_really_made_is_named(captured) -> None:
    """The exit criterion, on the engine's own output rather than on a token I typed."""
    found = misreads_in(
        [Line(text=f["text"], ocr=True) for f in captured["fragments"]]
    )
    assert len(found) == 1, [m.token for m in found]
    only = found[0]
    assert only.token == "5,0o0"
    assert only.reads_as == "5,000"
    assert only.ocr is True
    assert "Preferred stock" in only.line, "the label beside it says which row was lost"
    assert "5,0o0" in only.as_line() and "5,000" in only.as_line()


def test_the_figure_the_page_actually_prints_is_not_named(filing) -> None:
    """The same row, from the text layer, where `5,000` is what it says. A check that fired
    on the correct reading would be worse than no check."""
    page = next(p for p in filing.pages if p.number == 56)
    printed = [line.text for line in page.lines if "Preferred stock" in line.text]
    assert printed and "5,000" in printed[0], "the page prints it correctly"
    assert misreads_in([Line(text=printed[0])]) == ()


def test_the_whole_filings_text_layer_reports_nothing(filing) -> None:
    """Calibration, as an assertion. 58,606 tokens of real prose, tables, legal boilerplate
    and statutory citations, and a finding here means something because of this."""
    lines = [line for page in filing.pages for line in page.lines]
    tokens = sum(len(line.text.split()) for line in lines)
    assert tokens > 50_000, f"only {tokens} tokens; this is not the calibration set"
    found = misreads_in(lines)
    assert found == (), "\n".join(m.as_line() for m in found[:8])


def test_the_two_things_taken_out_would_both_have_fired(filing) -> None:
    """The measurements that settled each rule, kept, because a threshold nobody can check
    is a threshold nobody can trust - and because both of these are in this document.

    A third rule was taken out for the opposite reason. Requiring **exactly one** letter
    changed no answer on either input, which is the state P151 removed a `COLUMN_SHARE`
    threshold in rather than keep as caution, and it was silently skipping `1O,5O0`.
    """
    # The two-digit floor. `1B` is a billion.
    assert nearly_a_figure("1B") is None
    assert nearly_a_figure("9B") is None
    assert any(
        "1B" in line.text or "9B" in line.text
        for page in filing.pages
        for line in page.lines
    ), "the filing really does write a billion this way"

    # D for zero. `21D` is a section of the Securities Exchange Act.
    assert "D" not in CONFUSIONS
    assert nearly_a_figure("21D") is None
    assert any(
        "21D" in line.text for page in filing.pages for line in page.lines
    ), "the filing really does cite that section"

    # And the company's own name, which is on nearly every page of it.
    assert nearly_a_figure("3D") is None

    # The one-letter rule, gone: two misread digits in one figure is a photocopy.
    assert nearly_a_figure("1O,5O0") == "10,500"
    # And what actually keeps a word out is the digit floor, not a count of letters.
    assert nearly_a_figure("lOSS") is None
    assert nearly_a_figure("lOSS12") == "1055" + "12"


# --------------------------------------------------------------- what it does and does not do


@pytest.mark.parametrize(
    ("token", "reads_as"),
    [
        ("5,0o0", "5,000"),
        ("l27,496", "127,496"),
        ("1S,575", "15,575"),
        ("95,6B5", "95,685"),
        ("(1,2O0)", "1,200"),
        ("l46", "146"),
        ("4Z,000", "42,000"),
        ("1O,5O0", "10,500"),
    ],
)
def test_a_figure_with_a_letter_in_it_is_named(token: str, reads_as: str) -> None:
    """The confusions the research names, in figure position.

    `l46` is here because a cell can hold a bare number - the Common stock balance on this
    filing's own balance sheet is 146 - so the check cannot require comma grouping. `1O,5O0`
    is here because a rule requiring exactly one letter was skipping it, and two digits
    misread in one figure is an ordinary photocopy rather than an exotic case.
    """
    assert nearly_a_figure(token) == reads_as


@pytest.mark.parametrize(
    "token",
    [
        "123,576",  # a figure
        "2024",  # a year
        "loss",  # a word
        "lOSS",  # a word in capitals - excluded by the digit floor, not by its letters
        "FY25",  # a period label
        "1B",  # a billion
        "21D",  # a statute
        "3D",  # the company
        "",  # nothing
        "$",  # a currency mark
        "(a)",  # a footnote marker
        "p1/t2/r7",  # a locator
    ],
)
def test_what_is_not_a_near_miss(token: str) -> None:
    assert nearly_a_figure(token) is None, token


def test_nothing_is_substituted_anywhere(captured) -> None:
    """The exit criterion that matters most, and the easiest one to lose later.

    `reads_as` is a **string**. The moment it is a float, something downstream totals it and
    this system has invented a figure with a real locator that the document does not print -
    which is precisely the failure every other guard here is arranged against.
    """
    found = misreads_in([Line(text=f["text"], ocr=True) for f in captured["fragments"]])
    only = found[0]
    assert isinstance(only.reads_as, str)
    assert not isinstance(only.reads_as, (int, float))
    with pytest.raises((TypeError, ValueError)):
        sum(m.reads_as for m in found)  # type: ignore[misc]

    # And the token itself is carried exactly as it was read.
    assert only.token == "5,0o0"
    assert "o" in only.token, "unchanged, letter and all"


def test_the_line_a_misread_sits_on_is_carried_whole(captured) -> None:
    """Because the label is the point. `5,0o0` on its own tells a person nothing; `Preferred
    stock, 5,0o0 shares authorized` tells them which row to read off the page."""
    found = misreads_in([Line(text=f["text"], ocr=True) for f in captured["fragments"]])
    assert found[0].line.startswith("Preferred stock")


def test_whether_an_engine_read_it_changes_what_is_said() -> None:
    """Two different facts about a file, and two different things to do. On a scan the figure
    is on the page and can be read off it. In a text layer the document itself contains this,
    which re-reading does not fix."""
    scanned = misreads_in([Line(text="Inventories l27,496", ocr=True)])[0]
    printed = misreads_in([Line(text="Inventories l27,496", ocr=False)])[0]
    assert scanned.ocr and not printed.ocr
    assert "read off a scan" in scanned.as_line()
    assert "printed in the file" in printed.as_line()
    assert scanned.as_line() != printed.as_line()


def test_the_row_this_is_about_really_does_vanish() -> None:
    """The reason the check exists, asserted through the reader rather than described.

    If the reader simply dropped the *figure* and kept the label, the row would still be
    there and uncovered, and the acceptance rule would show it to a person of its own accord.
    It drops the whole line - and the line above it too, because a line carrying no figure
    breaks the run of lines that do. One letter, two rows.

    Asserted end to end on purpose. This test first called `_split_figures`, which does
    exactly this and which **nothing has called since P151** - the live reader has the same
    logic inline in `_tables_from_lines`. So the test was describing a function that was not
    on the path, and was the only thing keeping it in the tree; the function is gone and the
    question is put to `read_document`.
    """
    clean = rows_of(
        [
            "Cash 95,635",
            "Inventories 127,496",
            "Prepaid 123,576",
            "Total current assets 346,707",
        ]
    )
    assert clean == [
        ("Cash", 95_635.0),
        ("Inventories", 127_496.0),
        ("Prepaid", 123_576.0),
        ("Total current assets", 346_707.0),
    ], clean

    misread = rows_of(
        [
            "Cash 95,635",
            "Inventories l27,496",
            "Prepaid 123,576",
            "Total current assets 346,707",
        ]
    )
    assert misread == [
        ("Prepaid", 123_576.0),
        ("Total current assets", 346_707.0),
    ], misread
    assert not any(value == 127_496.0 for _, value in misread), "nothing was invented"


def test_a_misread_is_a_frozen_record() -> None:
    """Nothing downstream edits one into a figure."""
    one = Misread(token="5,0o0", reads_as="5,000", line="Preferred stock, 5,0o0", ocr=True)
    with pytest.raises(Exception):  # noqa: B017, PT011 - dataclasses raise FrozenInstanceError
        one.reads_as = "5000"  # type: ignore[misc]

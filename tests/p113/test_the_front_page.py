"""P113 - the front page, and what it now has to say.

It is the first sheet because it is the first thing that opens, and it is the only thing
standing between this file and being used as the firm's model. It told an analyst two
things that had stopped being true:

*"stored to the cent"* - P108 restates to thousands and keeps every decimal the division
produced. The first workbook off the real client folder holds `37.83500041` in a cell the
page said carried two decimals.

*"A blank Value is a figure version 1 could not find"* - P112 writes `not found` into that
cell instead, precisely because a blank among filled cells reads as a zero.

A page describing a workbook that no longer exists is worse than no page: it is the one
part of the file an analyst reads rather than checks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

from deliver.builder import NOT_FOUND
from tools.synthesize_templates import SHOWN_TO_THE_DOLLAR, WHAT_IT_IS

ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = ROOT / "templates" / "Chartwell_Input_Help_v1.xlsx"


@pytest.fixture(scope="module")
def page() -> str:
    """The front sheet of the built template, as text - what a person actually sees."""
    sheet = load_workbook(WORKBOOK).worksheets[0]
    return "\n".join(
        str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value is not None
    )


# ============================================================ what it says now


def test_the_page_uses_the_writer_s_own_word(page: str) -> None:
    """Not a paraphrase. An analyst matches what they see in a cell against what the page
    told them to expect, and "unavailable" would not match "not found"."""
    assert NOT_FOUND.upper() in page.upper()


def test_the_page_says_why_it_is_not_a_blank(page: str) -> None:
    """The reason is the thing worth writing down: a blank among filled cells reads as a
    zero, and a zero in a valuation is a number."""
    assert "reads" in page and "zero" in page
    assert "rather than being left blank" in page


def test_the_page_no_longer_promises_a_blank(page: str) -> None:
    assert "A blank Value is a figure" not in page


def test_the_page_no_longer_says_two_decimals(page: str) -> None:
    """The analyst's instruction was to keep every decimal and let Excel round for the
    eye. "Stored to the cent" describes a rounding nobody does."""
    assert "stored to the cent" not in page
    assert "not rounded at all" in page


def test_the_page_says_thousands_whatever_arrived(page: str) -> None:
    """*"The client could give us their financials in any form, we always put it in
    thousands no matter what they give us."* The page is where that promise is made to
    whoever opens the file."""
    assert "FIGURES ARE IN THOUSANDS" in page
    assert "whatever the client's own statements were stated in" in page


def test_the_page_still_says_what_this_is_not(page: str) -> None:
    """Unchanged and the reason the sheet exists at all."""
    assert "not the Chartwell model" in page
    assert "Nothing here is a valuation" in page


# ============================================================ tied to the code


def test_the_marker_is_imported_rather_than_retyped() -> None:
    """Two copies of one string drift. The page describes what the writer does, so it
    reads the writer's constant."""
    source = (ROOT / "tools" / "synthesize_templates.py").read_text(encoding="utf-8")
    assert "from deliver.builder import NOT_FOUND" in source
    assert f'"{NOT_FOUND}"' not in "\n".join(WHAT_IT_IS)


def test_changing_the_marker_changes_the_page() -> None:
    """The tie, exercised. If the writer's word changes and the page does not, an analyst
    is told to look for something that is not there."""
    assert NOT_FOUND.upper() in "\n".join(WHAT_IT_IS).upper()


def test_the_display_format_still_rounds_for_the_eye_only() -> None:
    """The other half of the page's claim. `#,##0` draws a whole number over a cell that
    holds every decimal - if that ever became a real rounding, the page would be wrong
    again and in the more dangerous direction."""
    assert SHOWN_TO_THE_DOLLAR == "#,##0"
    sheet = load_workbook(WORKBOOK)["Input"]
    # Every row that holds an input, found by its label rather than by a row number: the
    # header, the two stamps and the spacer are not inputs and are formatted as they come.
    not_inputs = {None, "Input", "Template version", "Run id"}
    formats = {
        sheet.cell(row=r, column=2).number_format
        for r in range(1, sheet.max_row + 1)
        if sheet.cell(row=r, column=1).value not in not_inputs
    }
    assert formats == {SHOWN_TO_THE_DOLLAR}, "an input cell formatted some other way"
    assert len(formats) == 1 and "0.0" not in SHOWN_TO_THE_DOLLAR


# ============================================================ the file on disk


def test_the_built_workbook_is_what_the_code_would_build_now() -> None:
    """A template checked in from an older run of the synthesizer is a template whose face
    nobody has read - the page on disk would go on promising a blank however carefully the
    text above it was edited. Compare the built sheet against the text it is built from."""
    before = load_workbook(WORKBOOK).worksheets[0]
    said = [c.value for row in before.iter_rows() for c in row if c.value is not None]
    assert said[1:] == [line for line in WHAT_IT_IS if line != ""] or said[1:] == [
        line for line in WHAT_IT_IS
    ], "the checked-in workbook was built from a different version of this text"


def test_the_synthesizer_runs(tmp_path: Path) -> None:
    """It is in CLAUDE.md as a command a person runs, and a command that only works from
    one directory is a command people stop running."""
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tools" / "synthesize_templates.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Chartwell_Input_Help_v1.xlsx" in done.stdout

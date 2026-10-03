"""P157: the rehearsal case called `pdf` had never read a PDF.

Measured by printing every `intake.read` event per case: the `pdf` case read three files and
all three were `.xlsx`. Its document was called `Statements.pdf`, and a name carrying no
document-type token is **held** by the binder rather than bound - so it reached no reader at
all, three runs on three workbooks, green every time since the rehearsal was written.

Two things were wrong and each hid the other. The bytes were not a PDF either: pypdf raises
`PdfReadError` on them. Nobody had met that error because nothing ever opened the file.

**Three times now, the same shape.** B-121 was a CSV refused while the case passed, because
a halted run has reached an ending and nothing asked whether the refusal was right. The
`half-sent` case added in P156 read as a pass until its file was renamed to one the
conventions claim. And this. Each time the rehearsal judged a case by whether its run
finished, and each time the file the case was *about* was never looked at - which is
invisible in an ending, because the other files in the folder are fine and the run ends on
them.

So the rehearsal says what it looked at. `MUST_BE_READ` names the file each such case exists
for and makes the case a finding when no `intake.read` event names it, and the finding says
what the run *did* read rather than sending somebody to the events by hand.

**What this file does, and why not the rehearsal.** Running the rehearsal takes minutes and
needs a server; this holds the same claims statically, which is both faster and stricter.
The question "will this filename bind" is answerable from the name and the conventions, and
answering it here means the next case added is checked before it is ever run.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from intake.bind import bind_document_type
from intake.readers.documents import read_document
from tools.simulate_files import (
    CASES,
    EVERY_FILE_IS_READABLE,
    INLINE_CASES,
    MUST_BE_READ,
    ONE_FILE_IS_UNREADABLE,
    ONE_PIXEL_PNG,
    pdf,
)

CONVENTIONS = {
    "trial_balance": ("tb", "tb_", "trial balance", "trial_balance", "trialbalance", "susa"),
    "financial_statements": (
        "income statement",
        "balance sheet",
        "financials",
        "financial statements",
        "profit and loss",
        "p&l",
        "statement of income",
        "statement of operations",
        "statement of financial position",
        "is",
        "bs",
        "fs",
        "guv",
        "bilanz",
    ),
}
"""The tokens a first setup declares, from `admin/console.py`.

Spelled here rather than read out of a live config, because this test is about names and
starting a server to ask about a name would make it a slow test of something else. The
binder itself is imported, so what is being tested is the real rule.
"""


# ------------------------------------------------- the defect, caught from the name alone


@pytest.mark.parametrize("case", sorted(MUST_BE_READ))
def test_the_file_a_case_is_about_is_one_the_conventions_claim(case: str) -> None:
    """The whole defect, and it is answerable without running anything.

    `Statements.pdf` carries no token, so the binder holds it and no reader sees it. The run
    still ends, on the other files in the folder, and that is what three cases in a row were
    judged by.
    """
    filename = MUST_BE_READ[case]
    bound = bind_document_type(filename, CONVENTIONS)
    assert bound is not None, (
        f"{case}: {filename} carries no document-type token, so the binder will hold it and "
        f"no reader will ever see it - which is how this case would pass while testing "
        f"nothing"
    )


@pytest.mark.parametrize("case", sorted(ONE_FILE_IS_UNREADABLE))
def test_the_file_a_refusal_case_is_about_is_also_bound(case: str) -> None:
    """A file that cannot be read has to reach a reader before it can be refused.

    This is the one the `half-sent` case taught: named `Statements.pdf` it ended
    `quarantined` with the fix and `quarantined` without it, because the truncated PDF was
    held and the run ended on the workbooks beside it.
    """
    filename = ONE_FILE_IS_UNREADABLE[case]
    assert bind_document_type(filename, CONVENTIONS) is not None, (
        f"{case}: {filename} would be held rather than refused"
    )


def test_the_name_that_started_this_is_still_unbound() -> None:
    """The measurement itself, kept, because the assertions above only mean something if a
    name really can fail to bind. `Statements` is not a token anybody declared - the
    conventions name the statements individually - and a reader would never see the file."""
    assert bind_document_type("Statements.pdf", CONVENTIONS) is None
    assert bind_document_type("TB_FY25.pdf", CONVENTIONS) == "trial_balance"
    assert bind_document_type("Balance sheet screenshot.png", CONVENTIONS) == (
        "financial_statements"
    )


# ------------------------------------------------------- and the fixtures are what they say


def test_the_rehearsals_pdf_is_a_pdf_that_opens_and_carries_its_rows() -> None:
    """What replaced four plausible-looking lines of PDF-ish bytes.

    The old fixture raised `PdfReadError`, which is worse than an unreadable fixture usually
    is: the case existed to prove a PDF could be read, so a fixture nothing can open made it
    prove the opposite silently. The rows are asserted as well as the opening, because a
    PDF that opens to nothing would be the same defect one step along.
    """
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "TB_FY25.pdf"
        pdf(
            path,
            [
                "Case Co - Trial Balance FY2025",
                "Officer salary      240,000",
                "Officer bonus        60,000",
                "Total officer comp  300,000",
            ],
        )
        doc = read_document(path.read_bytes(), path.name)

    assert doc.kind == "pdf"
    assert len(doc.pages) == 1
    rows = [
        (row.label, row.value)
        for table in doc.pages[0].tables
        for column in table.columns
        for row in column.rows
        if row.value is not None
    ]
    assert rows == [
        ("Officer salary", 240_000.0),
        ("Officer bonus", 60_000.0),
        ("Total officer comp", 300_000.0),
    ], rows


def test_the_rehearsals_png_is_a_png_the_reader_routes_as_an_image() -> None:
    """The screenshot case's fixture, held to the same standard as the PDF's.

    No blocks, because there is no engine here and an empty page is the honest answer - but
    it has to be an *image* that produced the empty page rather than a file refused as
    binary, and those read identically from the outside.
    """
    doc = read_document(ONE_PIXEL_PNG, "Balance sheet screenshot.png")
    assert doc.kind == "image"
    assert [page.scanned for page in doc.pages] == [True]
    assert doc.blocks() == {}


# --------------------------------------------------------------- and the sets agree with each other


def test_every_case_named_in_either_set_exists() -> None:
    """A set keyed by a case name that nobody registered checks nothing, silently.

    `INLINE_CASES` as well as `CASES`, because two of them need the clock - one holds a file
    open while the sweep looks, the other rewrites one after it has settled - so they are
    built in the body of the sweep rather than by a function. Their names were string
    literals in the middle of that function until this test asked for them.
    """
    known = set(CASES) | set(INLINE_CASES)
    for name in {*MUST_BE_READ, *ONE_FILE_IS_UNREADABLE, *EVERY_FILE_IS_READABLE}:
        assert name in known, f"{name} is checked and is not a case"


def test_a_case_is_not_both_read_and_refused() -> None:
    """`half-sent` is about a file that cannot be read, so it halts before any `intake.read`
    is emitted for it - and asking both questions of one case asks one of them wrongly. The
    two sets are the two halves of one question: was this file looked at, and what was said
    about it."""
    both = set(MUST_BE_READ) & set(ONE_FILE_IS_UNREADABLE)
    assert both == set(), f"{both} is in both sets"

    overlap = set(ONE_FILE_IS_UNREADABLE) & set(EVERY_FILE_IS_READABLE)
    assert overlap == set(), f"{overlap} has a broken file and is said to have none"


def test_each_case_writes_the_file_it_is_about() -> None:
    """The last way this could be hollow: a set naming a file the case does not create.

    The builders are run into a temporary folder and the file looked for, because a name in
    a dictionary agreeing with a name in a function is not something either of them checks.
    """
    for case, filename in {**MUST_BE_READ, **ONE_FILE_IS_UNREADABLE}.items():
        if case in INLINE_CASES:
            continue  # built by the sweep itself, with the clock, not by a builder here
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / case
            CASES[case](folder)
            assert (folder / filename).exists(), (
                f"{case} is said to be about {filename} and does not write it; "
                f"it writes {sorted(p.name for p in folder.iterdir())}"
            )

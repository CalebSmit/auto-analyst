"""P152: two of the four spreadsheet types this build accepts could not be opened.

`intake/fingerprint.py` routes `.xlsx`, `.xlsm`, `.xls` and `.csv` to the workbook reader,
and that reader calls openpyxl, which reads the first two. A trial balance sent as a CSV was
refused, and what a person was told was:

    TB.csv cannot be opened as a workbook (BadZipFile: File is not a zip file)

Measured through the real server by `tools/simulate_files.py`, whose CSV case had been
passing since it was written - a refusal on the record counts as an outcome, and nothing
asked whether the refusal was right. It was not: the file is a perfectly good trial balance,
and a CSV is one of the two things a client is most likely to send.

**The conversion is at the door and nothing above it changed.** A CSV becomes a one-sheet
workbook and an `.xls` becomes the sheets it has, so sheet selection, normalisation, the
footing check and the `Sheet!A1:B20` locator a figure cites are all still reading a real
workbook with real cells.

**The care is in the numbers.** A CSV has no types: every cell is text, and `402,000` is
four hundred and two thousand in one convention and four hundred and two in another. Getting
it wrong is undetectable afterwards, because both readings are plausible figures. So the
convention is decided once from the whole file on evidence that can only mean one thing, and
where the file settles nothing, **the cell stays text and is named** - which is the same
answer this build already gives for a scale it cannot infer.
"""

from __future__ import annotations

import io

import pytest

from intake.readers.tabular import as_workbook, converts
from intake.readers.workbook import normalize_workbook, survey_workbook

TRIAL_BALANCE = (
    b"Henderson Manufacturing\n"
    b"Trial balance, 31 December 2025\n"
    b"\n"
    b"Account,Debit,Credit\n"
    b"Cash,402000,\n"
    b"Accounts receivable,318400,\n"
    b"Revenue,,4650000\n"
    b"Total,720400,4650000\n"
)


def blocks(conversion) -> dict[str, dict[str, float | None]]:
    """What the workbook reader gets out of the converted file, by locator.

    Kept per block rather than flattened, because a trial balance has a debit column and a
    credit column and they are two blocks at two ranges - which is the whole point of
    converting to a workbook rather than to a list of rows.
    """
    survey = survey_workbook(conversion.workbook)
    tables = normalize_workbook(conversion.workbook, [s.name for s in survey.sheets])
    return {
        locator: {row.label: row.value for row in rows}
        for table in tables
        for locator, rows in table.blocks.items()
    }


def figures(conversion) -> dict[str, float | None]:
    """The first block's rows - a one-column sheet, which most of these are."""
    found = blocks(conversion)
    assert found, "the reader got no block out of the file at all"
    return next(iter(found.values()))


# ------------------------------------------------------------- a csv is a trial balance


def test_a_trial_balance_sent_as_a_csv_is_read() -> None:
    """The case `tools/simulate_files.py` has carried since it was written, and called a
    pass because the file ended on the record. It ends on the record read, now - and as two
    columns at two ranges, which is what a debit and a credit column are."""
    found = blocks(as_workbook(TRIAL_BALANCE, "TB 2025.csv"))
    assert found == {
        "'TB 2025'!B5:B8": {"Cash": 402_000, "Accounts receivable": 318_400, "Total": 720_400},
        "'TB 2025'!C7:C8": {"Revenue": 4_650_000, "Total": 4_650_000},
    }


def test_the_sheet_is_named_for_the_file_so_a_locator_still_says_something() -> None:
    """A figure cites `TB 2025!B5` for as long as it exists. A sheet called `Sheet` would
    tell a reviewer nothing about which of three files it came from."""
    survey = survey_workbook(as_workbook(TRIAL_BALANCE, "TB 2025.csv").workbook)
    assert [s.name for s in survey.sheets] == ["TB 2025"]


def test_a_title_block_above_the_headers_does_not_decide_the_delimiter() -> None:
    """What an accountant's export looks like: the name of the firm, the name of the report,
    a blank line, and then the columns.

    The firm's name has a comma in it and the file is semicolon-delimited - which is what a
    European Excel writes. Reading the delimiter off the first line calls it a comma, cuts
    every row in the wrong place, and turns a trial balance into one column of nonsense. The
    delimiter is the one that cuts the *whole file* into a consistent width, and here that
    is the semicolon on every line but the title.
    """
    misleading = (
        b"Henderson Manufacturing, Inc.\n"
        b"Trial balance, 31 December 2025\n"
        b"\n"
        b"Konto;Soll;Haben\n"
        b"Kasse;402000;\n"
        b"Forderungen;318400;\n"
        b"Erloese;;4650000\n"
    )
    got = as_workbook(misleading, "SuSa.csv")
    assert got.delimiter == ";", "the title line decided the delimiter"
    assert figures(got)["Kasse"] == 402_000

    assert as_workbook(TRIAL_BALANCE, "TB.csv").delimiter == ","


@pytest.mark.parametrize(
    ("raw", "delimiter"),
    [
        (b"Account;Amount\nCash;402000\nRevenue;4650000\n", ";"),
        (b"Account\tAmount\nCash\t402000\nRevenue\t4650000\n", "\t"),
        (b"Account|Amount\nCash|402000\nRevenue|4650000\n", "|"),
    ],
)
def test_the_delimiter_is_whatever_cuts_the_file_into_columns(raw: bytes, delimiter: str) -> None:
    """A European Excel writes semicolons, because the comma is already the decimal point -
    which is exactly the file this is most careful about."""
    got = as_workbook(raw, "TB.csv")
    assert got.delimiter == delimiter
    assert figures(got)["Cash"] == 402_000


def test_the_encoding_is_the_one_that_read_it_and_is_recorded() -> None:
    """Excel on Windows writes cp1252 and says nothing. Trying cp1252 first would decode a
    UTF-8 file without complaining and turn every accented name into two characters, so the
    order is strictest first and the answer is which one worked."""
    latin = b"Compte;Montant\nCr" + bytes([0xE9]) + b"ances clients;402000\n"
    got = as_workbook(latin, "TB.csv")
    assert got.encoding == "cp1252"
    assert "Créances clients" in figures(got)

    unicode_file = "Account,Amount\nCréances,402000\n".encode()
    assert as_workbook(unicode_file, "TB.csv").encoding == "utf-8"

    excels_own = "Account,Amount\nCash,402000\n".encode("utf-8-sig")
    assert as_workbook(excels_own, "TB.csv").encoding == "utf-8-sig"


# ------------------------------------------------- and the number that could be two numbers


def test_a_file_that_says_which_convention_it_uses_is_read_that_way() -> None:
    """One unambiguous cell settles the file. `1,234.56` can only be grouped-then-decimal,
    and `1.234,56` can only be the other way round."""
    american = b'Account,Amount\nCash,"402,000"\nRevenue,"4,650,000.50"\n'
    got = as_workbook(american, "TB.csv")
    assert got.decimal == "."
    assert figures(got) == {"Cash": 402_000, "Revenue": 4_650_000.50}

    european = b"Konto;Betrag\nKasse;402.000,00\nUmsatz;4.650.000,50\n"
    got = as_workbook(european, "TB.csv")
    assert got.decimal == ","
    assert figures(got) == {"Kasse": 402_000, "Umsatz": 4_650_000.50}


def test_a_cell_that_could_be_two_numbers_stays_text_and_is_named() -> None:
    """The whole reason this module is careful. A file carrying both `402,000` and `1.234`
    is using both characters as a group separator or as a decimal point, and nothing in it
    says which. Four hundred thousand and four hundred and two are both plausible, and a
    figure a thousand times out is not visible to anyone downstream.
    """
    confused = b'Account,Amount\nCash,"402,000"\nOther,"1.234"\n'
    got = as_workbook(confused, "TB.csv")
    assert got.decimal == "", "it picked a convention the file does not state"
    assert set(got.ambiguous) == {"402,000", "1.234"}
    # And the consequence, said plainly: with both cells left as text the sheet has no
    # column of figures, so the reader finds no block. A file it cannot read without
    # guessing yields nothing and says why, rather than yielding a number either way.
    assert blocks(got) == {}


def test_a_negative_in_brackets_and_a_currency_mark_are_still_figures() -> None:
    raw = b'Account,Amount\nLoss,"($96,083)"\nGain,"$12,400"\n'
    assert figures(as_workbook(raw, "TB.csv")) == {"Loss": -96_083, "Gain": 12_400}


def test_an_empty_file_is_refused_rather_than_read_as_an_empty_workbook() -> None:
    """A file with no rows is a file that did not arrive, and saying so is the caller's one
    diagnostic for every spreadsheet that will not open."""
    with pytest.raises(ValueError):
        as_workbook(b"", "TB.csv")
    with pytest.raises(ValueError):
        as_workbook(b"\n\n\n", "TB.csv")


# ----------------------------------------------------------------------- the old excel


def build_xls(rows: list[list[object]], sheet: str = "TB") -> bytes:
    """A real `.xls`, written by the only library that still writes one."""
    import xlwt

    book = xlwt.Workbook()
    ws = book.add_sheet(sheet)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            ws.write(r, c, value)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def test_an_xls_is_read_as_the_workbook_it_is() -> None:
    """openpyxl has never been able to open one, and this build has been routing them to it
    since the routing table was written."""
    raw = build_xls(
        [["Account", "Amount"], ["Cash", 402000], ["Revenue", 4650000], ["Total", 5052000]]
    )
    rows = figures(as_workbook(raw, "TB 2025.xls"))
    assert rows == {"Cash": 402_000, "Revenue": 4_650_000, "Total": 5_052_000}


def test_a_date_in_an_xls_comes_back_a_date_and_not_a_serial_number() -> None:
    """An `.xls` stores a date as a number and a mode kept on the workbook, and the two are
    only a date together. Losing the mode turns 31 December 2025 into 46022, which is a
    plausible figure in a trial balance and is not a date at all - the period detector would
    read it as an amount and the year end would be gone.
    """
    import datetime

    import xlwt

    book = xlwt.Workbook()
    ws = book.add_sheet("TB")
    ws.write(0, 0, "As of")
    ws.write(0, 1, datetime.datetime(2025, 12, 31), xlwt.easyxf(num_format_str="YYYY-MM-DD"))
    out = io.BytesIO()
    book.save(out)

    from openpyxl import load_workbook

    converted = as_workbook(out.getvalue(), "TB.xls")
    cell = load_workbook(io.BytesIO(converted.workbook))["TB"]["B1"].value
    assert isinstance(cell, datetime.datetime), f"the date came back as {cell!r}"
    assert (cell.year, cell.month, cell.day) == (2025, 12, 31)


def test_an_xls_keeps_its_sheet_names() -> None:
    raw = build_xls([["Account", "Amount"], ["Cash", 1]], sheet="Prior year")
    survey = survey_workbook(as_workbook(raw, "TB.xls").workbook)
    assert [s.name for s in survey.sheets] == ["Prior year"]


def test_an_xls_number_was_never_text_so_nothing_is_inferred() -> None:
    """A value in an `.xls` comes back typed. None of the convention work applies, and
    saying so is how a reader knows this path cannot have guessed."""
    raw = build_xls([["Account", "Amount"], ["Cash", 402000.5]])
    got = as_workbook(raw, "TB.xls")
    assert got.decimal == "" and got.delimiter == "" and got.ambiguous == ()
    assert figures(got)["Cash"] == 402_000.5


# --------------------------------------------------------------- and which files convert


def test_only_the_formats_that_need_converting_are_converted() -> None:
    """An `.xlsx` must go to openpyxl untouched - rewriting it would lose the formulas,
    the formatting and the hidden sheets the reader above reports on."""
    assert converts("TB.csv") and converts("TB.CSV")
    assert converts("TB.tsv")
    assert converts("TB 2025.xls")
    assert not converts("TB.xlsx")
    assert not converts("TB.xlsm")
    assert not converts("Statements.pdf")


# ------------------------------------------- and the rehearsal that let this through


def test_the_rehearsal_checks_that_a_good_file_was_read() -> None:
    """Why this went unnoticed for so long.

    `tools/simulate_files.py` judged a case by whether its run reached an end, and a halted
    run has ended. So `TB.csv cannot be opened as a workbook (BadZipFile)` was a pass, every
    time it ran, for as long as the case existed. A rehearsal that accepts any ending accepts
    the wrong one, and the hole is wider than this phase: it would have hidden the same
    defect in any of the cases whose files are all well formed.
    """
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "tools" / "simulate_files.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    named = {
        element.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "EVERY_FILE_IS_READABLE" for t in node.targets)
        for element in getattr(node.value, "elts", [])
        if isinstance(element, ast.Constant)
    }
    assert "csv" in named, "the case this phase was about is not among the readable ones"
    assert len(named) >= 10, f"only {len(named)} cases are held to being readable"
    assert "UNREADABLE_FILE" in source, "nothing looks for a refusal on those cases"

    # And the cases that really are malformed must not be in it, or the check is a check
    # that can never fire.
    for malformed in ("zero-byte", "not-a-workbook", "odd-names", "password"):
        assert malformed not in named, f"{malformed} holds a file that cannot be read"

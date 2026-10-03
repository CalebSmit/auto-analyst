"""Formula audit: the mistakes a spreadsheet makes that a spreadsheet cannot see.

`deliver/qc.py` already asks whether a workbook is *broken* - does it open, does any cell
hold `#REF!`, does every name resolve, is a mask token left in it. Those are the failures
Excel itself admits to. This module asks the other question, the one the analyst named: is
any formula **quietly wrong**. A total that sums nine rows of a ten-row block opens
cleanly, prints a number, shows no error, and is wrong by one line - and it is wrong in
exactly the way nobody catches, because the wrongness is a plausible number.

Nine checks, in three severities, and the severity is the whole design:

* **wrong** - the arithmetic demonstrably disagrees with itself. A numeric row sits
  between the end of a total's range and the total. A total's range contains another
  total. A cached total does not equal the cached values it adds. Each of these is a
  statement about the file, provable from the file, with no judgement in it.
* **suspect** - a pattern break. One cell in a row of eleven does something the other ten
  do not; a hardcoded number sits in a row of formulas; a range starts one row below a
  number. Each needs an eye, and each is a real mistake often enough to be worth the look.
* **convention** - a cross-sheet reference by cell address rather than by name. The
  blueprint's rule - *bind by named range, never by cell address* - applied to a workbook
  this build did not write. On the firm's own model this fires everywhere, which is why it
  is its own severity and off by default rather than mixed into the findings that matter.

**It never edits.** The audit reads bytes and returns findings. Nothing here opens Excel,
recalculates, repairs a range or rewrites a formula - a tool that silently widened a SUM
to cover what it guessed was meant would be the most dangerous thing in this repository.

**Absence is never a pass.** Excel caches the last computed value of every formula; a file
openpyxl wrote and Excel has never opened has no cached values at all. The footing check
therefore cannot run on a freshly generated workbook, and it says so in `skipped` rather
than reporting nothing wrong. `statement_checks.py` makes the same distinction for the
same reason: a checklist that reports silence as success is the commonest way one lies.

    python -m uv run python tools/formula_audit.py <workbook.xlsx>
    python -m uv run python tools/formula_audit.py <workbook.xlsx> --all --json

Pure Python over openpyxl. No Excel, no COM, no recalculation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # this is run as a script, from wherever somebody is standing
    sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

# openpyxl is a project dependency, so this import succeeds everywhere the suite, the gate
# and the server run. It fails on a bare `python tools/formula_audit.py` outside the
# virtualenv - which is the first thing somebody tries - and `needs` is the difference
# between a traceback about somebody else's library and the line to type.
needs("openpyxl", script="tools/formula_audit.py")

from openpyxl import load_workbook  # noqa: E402
from openpyxl.formula import Tokenizer  # noqa: E402
from openpyxl.utils.cell import (  # noqa: E402
    column_index_from_string,
    get_column_letter,
    range_boundaries,
)
from openpyxl.worksheet.worksheet import Worksheet  # noqa: E402

__all__ = [
    "CHECKS",
    "Audit",
    "Finding",
    "Ref",
    "audit",
    "normalise",
    "refs_in",
    "report",
]

WRONG, SUSPECT, CONVENTION = "wrong", "suspect", "convention"

# Every check this module can report, with its severity and what the finding means. One
# table rather than strings at the call sites: the CLI groups by it, the console labels
# from it, and `tests/p125` asserts that every check a finding carries is in here - so a
# check added without a description fails rather than printing an unexplained id.
CHECKS: dict[str, tuple[str, str]] = {
    "total_misses_rows": (
        WRONG,
        "A row holding a number sits between the end of this total's range and the "
        "total itself. Either the range is short or that row does not belong.",
    ),
    "total_counts_a_total": (
        WRONG,
        "This total's range includes a cell that is itself a total, so part of the "
        "block is counted twice.",
    ),
    "total_does_not_foot": (
        WRONG,
        "The value Excel last saved for this total does not equal the sum of the "
        "values it last saved for the cells it adds. The file has been edited since "
        "it was recalculated, or the range is not what the number was computed from.",
    ),
    "total_starts_late": (
        SUSPECT,
        "The cell directly above this total's range holds a number. A range that "
        "starts one row below the block is the commonest off-by-one in a model.",
    ),
    "total_crosses_a_blank_row": (
        SUSPECT,
        "This total's range spans a blank row with numbers on both sides of it, so it "
        "reaches across what looks like a section boundary.",
    ),
    "formula_breaks_the_pattern": (
        SUSPECT,
        "Every other cell in this run does the same thing to its own column; this one "
        "does something different.",
    ),
    "number_where_the_row_calculates": (
        SUSPECT,
        "A typed number sits inside a run of cells that are otherwise all the same "
        "formula. It will not move when the model does.",
    ),
    "run_has_no_agreement": (
        SUSPECT,
        "Three or more calculated cells in a row, and no two of them calculate the "
        "same way. Across the year columns of one line, they normally all agree.",
    ),
    "cell_address_across_sheets": (
        CONVENTION,
        "A reference to another sheet by cell address. Insert a row on that sheet and "
        "this points somewhere else, silently - bind by name instead.",
    ),
}

# Functions that make a cell a total for the purposes of the range checks. SUBTOTAL and
# AGGREGATE are here because a model that uses them uses them *as* totals; a range that
# swallows one double-counts exactly the way a swallowed SUM does.
TOTAL_FUNCTIONS = ("SUM", "SUBTOTAL", "AGGREGATE", "SUMPRODUCT", "SUMIF", "SUMIFS")

# How far apart two cached numbers may be and still be called equal. Floating point and
# Excel's own rounding, not a materiality threshold - materiality belongs to the practice
# (BUILD/OPEN.md section 2) and this check is about arithmetic, not about significance.
FOOTING_TOLERANCE = 0.005

# The shortest run of neighbouring cells that can hold a pattern at all. Three: with two
# cells there is no majority and no exception, only two cells that differ.
#
# The *majority* is deliberately not three. A valuation model's historical block is three
# year columns wide more often than not - FY1, FY2, FY3 - so "two agree and the third does
# not" is precisely the case the analyst described, and a quorum of three would have made
# this check blind to it on the layout it matters most on. The rule is a strict majority:
# the shape reported has fewer members than the shape it is measured against, and that one
# has at least two.
PATTERN_QUORUM = 3
PATTERN_MAJORITY = 2


@dataclass(frozen=True)
class Ref:
    """One reference out of one formula, resolved as far as text can resolve it.

    `sheet` is empty for a reference on the formula's own sheet. `name` is set, and the
    bounds are not, when the operand is a defined name rather than an address - which is
    the case this module treats as correct rather than as unparseable.
    """

    text: str
    sheet: str = ""
    name: str = ""
    min_col: int = 0
    min_row: int = 0
    max_col: int = 0
    max_row: int = 0

    @property
    def is_address(self) -> bool:
        return not self.name and self.min_row > 0

    @property
    def is_single_cell(self) -> bool:
        return self.is_address and self.min_row == self.max_row and self.min_col == self.max_col

    @property
    def is_one_column(self) -> bool:
        return self.is_address and self.min_col == self.max_col

    def rows(self) -> range:
        return range(self.min_row, self.max_row + 1)


@dataclass(frozen=True)
class Finding:
    """One thing worth a person's attention, with what the file says behind it."""

    check: str
    severity: str
    sheet: str
    cell: str
    formula: str
    says: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "sheet": self.sheet,
            "cell": self.cell,
            "formula": self.formula,
            "says": self.says,
            "evidence": self.evidence,
        }

    def __str__(self) -> str:
        return f"{self.sheet}!{self.cell}  {self.check}  {self.says}"


@dataclass(frozen=True)
class Audit:
    """What the audit found, what it looked at, and what it could not look at."""

    findings: tuple[Finding, ...]
    formulas: int
    sheets: tuple[str, ...]
    skipped: tuple[str, ...] = ()

    def of(self, *severities: str) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity in severities)

    @property
    def wrong(self) -> tuple[Finding, ...]:
        return self.of(WRONG)

    @property
    def clean(self) -> bool:
        """No finding at either severity that states something about the file. A
        convention finding does not make a workbook unclean; it makes it somebody
        else's workbook."""
        return not self.of(WRONG, SUSPECT)

    def as_dict(self) -> dict[str, Any]:
        return {
            "formulas": self.formulas,
            "sheets": list(self.sheets),
            "skipped": list(self.skipped),
            "findings": [f.as_dict() for f in self.findings],
        }


# ------------------------------------------------------------------ reading a formula


def refs_in(formula: str) -> tuple[Ref, ...]:
    """Every operand in a formula that is a reference, parsed where it is an address.

    A defined name and a cell address are both `OPERAND/RANGE` to the tokenizer, so the
    discrimination is whether the text parses as bounds. That is the right test anyway:
    what matters downstream is whether a reference can be followed to a row and a column.
    """
    if not formula.startswith("="):
        return ()
    out: list[Ref] = []
    try:
        tokens = Tokenizer(formula).items
    except Exception:  # noqa: BLE001 - an unparseable formula is reported, never raised
        return ()
    for token in tokens:
        if token.type != "OPERAND" or token.subtype != "RANGE":
            continue
        text = str(token.value)
        sheet, _, addr = text.rpartition("!")
        sheet = sheet.strip("'")
        try:
            min_col, min_row, max_col, max_row = range_boundaries(addr.replace("$", ""))
        except Exception:  # noqa: BLE001 - then it is a name, which is the good case
            out.append(Ref(text=text, sheet=sheet, name=addr))
            continue
        if None in (min_col, min_row, max_col, max_row):
            # A whole-column or whole-row reference (`C:C`, `5:5`). Real, and nothing
            # here can say which rows it covers, so it is carried without bounds.
            out.append(Ref(text=text, sheet=sheet, name=addr))
            continue
        out.append(
            Ref(
                text=text,
                sheet=sheet,
                min_col=int(min_col),
                min_row=int(min_row),
                max_col=int(max_col),
                max_row=int(max_row),
            )
        )
    return tuple(out)


def normalise(formula: str, row: int, col: int) -> str:
    """A formula with every relative address rewritten as an offset from its own cell.

    Two cells "do the same thing" when this string matches. `=C5*D5` in C6 and `=D5*E5`
    in D6 normalise identically; `=C5*D5` in C6 and `=C5*D4` in D6 do not. Absolute
    references keep their address, because an absolute reference means the same cell
    from wherever it is read and two cells pointing at one cell are doing the same thing.
    """
    if not formula.startswith("="):
        return formula
    try:
        tokens = Tokenizer(formula).items
    except Exception:  # noqa: BLE001
        return formula
    parts: list[str] = ["="]
    for token in tokens:
        value = str(token.value)
        if token.type == "OPERAND" and token.subtype == "RANGE":
            parts.append(_offset(value, row, col))
        elif token.type == "OPERAND" and token.subtype == "TEXT":
            parts.append(f'"{value}"')
        elif token.type == "FUNC" and token.subtype == "CLOSE":
            parts.append(")")
        elif token.type == "PAREN":
            parts.append("(" if token.subtype == "OPEN" else ")")
        else:
            parts.append(value)
    return "".join(parts)


def _offset(text: str, row: int, col: int) -> str:
    """One reference, as an offset. Names and unparseable text come back unchanged."""
    sheet, sep, addr = text.rpartition("!")
    pieces: list[str] = []
    for piece in addr.split(":"):
        rendered = _offset_one(piece, row, col)
        if rendered is None:
            return text
        pieces.append(rendered)
    return f"{sheet}{sep}" + ":".join(pieces)


def _offset_one(piece: str, row: int, col: int) -> str | None:
    col_abs = piece.startswith("$")
    rest = piece[1:] if col_abs else piece
    letters = ""
    for ch in rest:
        if ch.isalpha():
            letters += ch
        else:
            break
    rest = rest[len(letters) :]
    row_abs = rest.startswith("$")
    digits = rest[1:] if row_abs else rest
    if not letters or not digits.isdigit():
        return None
    ref_col = column_index_from_string(letters)
    ref_row = int(digits)
    c = f"${letters}" if col_abs else f"c{ref_col - col:+d}"
    r = f"${digits}" if row_abs else f"r{ref_row - row:+d}"
    return f"[{c}{r}]"


def _functions(formula: str) -> set[str]:
    try:
        tokens = Tokenizer(formula).items
    except Exception:  # noqa: BLE001
        return set()
    return {
        str(t.value).rstrip("(").upper()
        for t in tokens
        if t.type == "FUNC" and t.subtype == "OPEN"
    }


def _is_total(value: Any) -> bool:
    return isinstance(value, str) and bool(_functions(value) & set(TOTAL_FUNCTIONS))


def _is_bare_sum(formula: str) -> bool:
    """`=SUM(C5:C9)` and nothing else: one function, one range, no arithmetic around it.

    The footing check re-adds the cells a total covers and compares. That comparison is
    only meaningful when the formula *is* the addition - `=SUM(C5:C9)-C10` has the same
    function set and a legitimately different answer, and reporting it as not footing
    would be this module being wrong about a file that is right.
    """
    try:
        tokens = Tokenizer(formula).items
    except Exception:  # noqa: BLE001
        return False
    shape = [(t.type, t.subtype) for t in tokens]
    if shape != [("FUNC", "OPEN"), ("OPERAND", "RANGE"), ("FUNC", "CLOSE")]:
        return False
    return str(tokens[0].value).rstrip("(").upper() == "SUM"


def _is_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("=")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ------------------------------------------------------------------------- the checks


def _total_ranges(formula: str, row: int, col: int) -> Iterator[Ref]:
    """The vertical single-column ranges a total on this cell adds above itself.

    Narrow on purpose. A total over a horizontal range, a multi-column block, another
    sheet or a defined name is not something the row checks below can reason about, and
    reporting on a reference this module cannot follow is how a check becomes noise.
    """
    if not (_functions(formula) & set(TOTAL_FUNCTIONS)):
        return
    for ref in refs_in(formula):
        if ref.sheet or not ref.is_one_column or ref.min_col != col:
            continue
        if ref.min_row == ref.max_row:
            continue
        if ref.max_row >= row:
            continue
        yield ref


def _column_values(ws: Worksheet, col: int, rows: Iterable[int]) -> dict[int, Any]:
    letter = get_column_letter(col)
    return {r: ws[f"{letter}{r}"].value for r in rows}


def _check_ranges(ws: Worksheet, row: int, col: int, formula: str) -> Iterator[Finding]:
    letter = get_column_letter(col)
    cell = f"{letter}{row}"
    for ref in _total_ranges(formula, row, col):
        between = _column_values(ws, col, range(ref.max_row + 1, row))
        orphans = [r for r, v in between.items() if _is_number(v) or _is_formula(v)]
        if orphans:
            yield Finding(
                check="total_misses_rows",
                severity=WRONG,
                sheet=ws.title,
                cell=cell,
                formula=formula,
                says=(
                    f"the range ends at row {ref.max_row} but "
                    f"{_rows_phrase(orphans)} below it, above this total, "
                    f"{'hold' if len(orphans) > 1 else 'holds'} a value"
                ),
                evidence={
                    "range": ref.text,
                    "rows_left_out": orphans,
                    "column": letter,
                },
            )

        inside = _column_values(ws, col, ref.rows())
        swallowed = [r for r, v in inside.items() if _is_total(v)]
        if swallowed:
            yield Finding(
                check="total_counts_a_total",
                severity=WRONG,
                sheet=ws.title,
                cell=cell,
                formula=formula,
                says=(
                    f"the range covers {_rows_phrase(swallowed)}, which "
                    f"{'are totals' if len(swallowed) > 1 else 'is itself a total'}"
                ),
                evidence={
                    "range": ref.text,
                    "totals_inside": swallowed,
                    "column": letter,
                },
            )

        if ref.min_row > 1:
            above = ws[f"{letter}{ref.min_row - 1}"].value
            if _is_number(above):
                yield Finding(
                    check="total_starts_late",
                    severity=SUSPECT,
                    sheet=ws.title,
                    cell=cell,
                    formula=formula,
                    says=(
                        f"the range starts at row {ref.min_row} and row "
                        f"{ref.min_row - 1} directly above it holds a number"
                    ),
                    evidence={
                        "range": ref.text,
                        "row_above": ref.min_row - 1,
                        "value_above": above,
                        "column": letter,
                    },
                )

        blanks = [r for r, v in inside.items() if v is None]
        crossed = [
            r
            for r in blanks
            if any(inside.get(x) is not None for x in inside if x < r)
            and any(inside.get(x) is not None for x in inside if x > r)
        ]
        if crossed:
            yield Finding(
                check="total_crosses_a_blank_row",
                severity=SUSPECT,
                sheet=ws.title,
                cell=cell,
                formula=formula,
                says=(
                    f"the range spans blank {_rows_phrase(crossed)} with values on "
                    f"both sides"
                ),
                evidence={"range": ref.text, "blank_rows": crossed, "column": letter},
            )


def _rows_phrase(rows: Sequence[int]) -> str:
    if len(rows) == 1:
        return f"row {rows[0]}"
    return "rows " + ", ".join(str(r) for r in rows)


def _check_footing(
    ws: Worksheet, cached: Worksheet, row: int, col: int, formula: str
) -> tuple[list[Finding], int, int]:
    """A total against the values Excel last saved for the cells it adds.

    Returns the findings and two counts: how many of this cell's total ranges could be
    evaluated and how many could not. The second count is the point. The check needs the
    whole picture cached - the total's own saved value and every saved value in its range
    - and one `None` inside means it cannot run on that total. A sheet where some totals
    carry saved values and some do not would otherwise report nothing wrong with the ones
    it never looked at, which is the shape of lie `statement_checks.py` calls
    `could_not_evaluate` for the same reason.
    """
    letter = get_column_letter(col)
    cell = f"{letter}{row}"
    if not _is_bare_sum(formula):
        return [], 0, 0

    findings: list[Finding] = []
    evaluated = unevaluated = 0
    for ref in _total_ranges(formula, row, col):
        stated = cached[cell].value
        parts = [cached[f"{letter}{r}"].value for r in ref.rows()]
        if not _is_number(stated) or any(p is not None and not _is_number(p) for p in parts):
            unevaluated += 1
            continue
        evaluated += 1
        recomputed = sum(float(p) for p in parts if _is_number(p))
        delta = float(stated) - recomputed
        if abs(delta) > FOOTING_TOLERANCE:
            findings.append(
                Finding(
                    check="total_does_not_foot",
                    severity=WRONG,
                    sheet=ws.title,
                    cell=cell,
                    formula=formula,
                    says=(
                        f"the saved total is {stated:,.2f} and the cells it adds come to "
                        f"{recomputed:,.2f}, a difference of {delta:,.2f}"
                    ),
                    evidence={
                        "range": ref.text,
                        "stated": float(stated),
                        "recomputed": recomputed,
                        "delta": delta,
                    },
                )
            )
    return findings, evaluated, unevaluated


def _runs(cells: dict[int, Any], quorum: int) -> Iterator[list[int]]:
    """Maximal contiguous stretches of non-empty cells, long enough to hold a pattern."""
    run: list[int] = []
    for k in sorted(cells):
        if cells[k] is None:
            if len(run) >= quorum:
                yield run
            run = []
            continue
        if run and k != run[-1] + 1:
            if len(run) >= quorum:
                yield run
            run = []
        run.append(k)
    if len(run) >= quorum:
        yield run


def _check_pattern(
    ws: Worksheet,
    *,
    along: str,
    fixed: int,
    cells: dict[int, Any],
) -> Iterator[Finding]:
    """One run of cells that should agree, and whichever of them does not.

    `along` is the axis the run lies on: `"row"` means the run moves across columns at a
    fixed row. The minority is reported only against a strict majority, so a run where
    the cells merely differ from each other produces one finding about the run rather
    than one about each cell.
    """

    def at(k: int) -> tuple[int, int]:
        return (fixed, k) if along == "row" else (k, fixed)

    def name(k: int) -> str:
        row, col = at(k)
        return f"{get_column_letter(col)}{row}"

    for run in _runs(cells, PATTERN_QUORUM):
        shapes: dict[str, list[int]] = {}
        constants: list[int] = []
        for k in run:
            value = cells[k]
            row, col = at(k)
            if _is_formula(value):
                shapes.setdefault(normalise(str(value), row, col), []).append(k)
            elif _is_number(value):
                constants.append(k)
        if not shapes:
            continue

        majority = max(shapes, key=lambda s: len(shapes[s]))
        agreed = shapes[majority]

        if len(agreed) < PATTERN_MAJORITY:
            # Nobody agrees with anybody. One finding about the run, and only when every
            # cell in it calculates - a run mixing inputs and formulas is ordinary.
            if len(run) >= PATTERN_QUORUM and not constants and len(shapes) == len(run):
                yield Finding(
                    check="run_has_no_agreement",
                    severity=SUSPECT,
                    sheet=ws.title,
                    cell=name(run[0]),
                    formula=str(cells[run[0]]),
                    says=(
                        f"{len(run)} calculated cells along this {along} "
                        f"({name(run[0])}..{name(run[-1])}) and no two of them "
                        f"calculate the same way"
                    ),
                    evidence={
                        "axis": along,
                        "cells": [name(k) for k in run],
                        "formulas": [str(cells[k]) for k in run],
                    },
                )
            continue

        for shape, members in shapes.items():
            if shape == majority or len(members) >= len(agreed):
                continue
            for k in members:
                yield Finding(
                    check="formula_breaks_the_pattern",
                    severity=SUSPECT,
                    sheet=ws.title,
                    cell=name(k),
                    formula=str(cells[k]),
                    says=(
                        f"{', '.join(name(m) for m in agreed)} along this {along} all "
                        f"calculate the same way and this one does not"
                    ),
                    evidence={
                        "axis": along,
                        "agree": [name(m) for m in agreed],
                        "shape_here": shape,
                        "shape_agreed": majority,
                    },
                )

        if len(constants) < len(agreed):
            for k in constants:
                yield Finding(
                    check="number_where_the_row_calculates",
                    severity=SUSPECT,
                    sheet=ws.title,
                    cell=name(k),
                    formula=str(cells[k]),
                    says=(
                        f"a typed number where {', '.join(name(m) for m in agreed)} "
                        f"along this {along} all calculate"
                    ),
                    evidence={"axis": along, "value": cells[k], "shape_agreed": majority},
                )


def _check_convention(ws: Worksheet, row: int, col: int, formula: str) -> Iterator[Finding]:
    offenders = [r for r in refs_in(formula) if r.sheet and r.is_address]
    if not offenders:
        return
    yield Finding(
        check="cell_address_across_sheets",
        severity=CONVENTION,
        sheet=ws.title,
        cell=f"{get_column_letter(col)}{row}",
        formula=formula,
        says=(
            "reaches another sheet by cell address: "
            + ", ".join(sorted({r.text for r in offenders}))
        ),
        evidence={"references": sorted({r.text for r in offenders})},
    )


# ------------------------------------------------------------------------- the audit


def audit(
    data: bytes,
    *,
    sheets: Sequence[str] | None = None,
    include_convention: bool = False,
) -> Audit:
    """Audit a workbook's formulas. Bytes in, findings out; nothing is written.

    `sheets` limits the audit to the named worksheets, for the case where only the
    output tab is this build's business. `include_convention` admits the cross-sheet
    address findings, which are correct and, on somebody else's model, numerous.
    """
    wb = load_workbook(BytesIO(data), data_only=False)
    cached_wb = load_workbook(BytesIO(data), data_only=True)

    findings: list[Finding] = []
    counted = 0
    skipped: list[str] = []
    looked_at: list[str] = []

    for ws in wb.worksheets:
        if sheets is not None and ws.title not in sheets:
            continue
        looked_at.append(ws.title)
        cached = cached_wb[ws.title]

        by_row: dict[int, dict[int, Any]] = {}
        by_col: dict[int, dict[int, Any]] = {}
        footed = unfooted = 0

        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                r, c = int(cell.row), int(cell.column)
                if _is_formula(value) or _is_number(value):
                    by_row.setdefault(r, {})[c] = value
                    by_col.setdefault(c, {})[r] = value
                if not _is_formula(value):
                    continue
                formula = str(value)
                counted += 1
                findings.extend(_check_ranges(ws, r, c, formula))
                footing, could, could_not = _check_footing(ws, cached, r, c, formula)
                findings.extend(footing)
                footed += could
                unfooted += could_not
                if include_convention:
                    findings.extend(_check_convention(ws, r, c, formula))

        for r, cells in by_row.items():
            findings.extend(_check_pattern(ws, along="row", fixed=r, cells=cells))
        for c, cells in by_col.items():
            findings.extend(_check_pattern(ws, along="column", fixed=c, cells=cells))

        if unfooted:
            skipped.append(
                f"{ws.title}: 'total_does_not_foot' ran on {footed} total(s) and could "
                f"not run on {unfooted}, which carry no value Excel has saved - or cover "
                f"a cell that does not. Excel writes those values when a person saves the "
                f"file; a workbook this build generated has none until somebody opens it."
            )

    if sheets is not None:
        missing = [s for s in sheets if s not in looked_at]
        if missing:
            skipped.append("asked for sheets this workbook does not have: " + ", ".join(missing))

    return Audit(
        findings=tuple(_ordered(findings)),
        formulas=counted,
        sheets=tuple(looked_at),
        skipped=tuple(skipped),
    )


def _ordered(findings: Iterable[Finding]) -> list[Finding]:
    """Worst first, then by where it is, with duplicates dropped.

    A cell can be reached by the row pass and the column pass with the same complaint;
    reporting it twice makes a reviewer check one thing twice.
    """
    rank = {WRONG: 0, SUSPECT: 1, CONVENTION: 2}
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.sheet, f.cell, f.check)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return sorted(
        unique,
        key=lambda f: (rank.get(f.severity, 9), f.sheet, _sort_cell(f.cell), f.check),
    )


def _sort_cell(cell: str) -> tuple[int, int]:
    letters = "".join(ch for ch in cell if ch.isalpha())
    digits = "".join(ch for ch in cell if ch.isdigit())
    try:
        return (int(digits or 0), column_index_from_string(letters or "A"))
    except Exception:  # noqa: BLE001
        return (0, 0)


# ------------------------------------------------------------------------------- CLI


def report(result: Audit, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(result.as_dict(), indent=2, default=str)
    lines: list[str] = []
    lines.append(
        f"  {result.formulas} formula(s) over {len(result.sheets)} sheet(s): "
        + ", ".join(result.sheets)
    )
    if not result.findings:
        lines.append("\n  Nothing found.")
    for severity, heading in (
        (WRONG, "Wrong - the file disagrees with itself"),
        (SUSPECT, "Suspect - worth an eye"),
        (CONVENTION, "Convention - binds by address, not by name"),
    ):
        group = result.of(severity)
        if not group:
            continue
        lines.append(f"\n  {heading}  ({len(group)})")
        for f in group:
            lines.append(f"    {f.sheet}!{f.cell}  {f.says}")
            lines.append(f"        {f.check}: {f.formula}")
    if result.skipped:
        lines.append("\n  Did not run")
        for note in result.skipped:
            lines.append(f"    - {note}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="formula_audit.py",
        description="Find the formulas in a workbook that are quietly wrong.",
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--sheet", action="append", help="limit to this sheet; repeatable")
    parser.add_argument(
        "--all",
        action="store_true",
        help="include the cross-sheet-address convention findings",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if not args.workbook.is_file():
        print(f"  no such workbook: {args.workbook}", file=sys.stderr)
        return 2

    result = audit(
        args.workbook.read_bytes(),
        sheets=args.sheet,
        include_convention=args.all,
    )
    print(report(result, as_json=args.as_json))
    return 1 if result.wrong else 0


if __name__ == "__main__":  # pragma: no cover - the CLI's own line
    raise SystemExit(main())

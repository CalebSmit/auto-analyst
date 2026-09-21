# ruff: noqa: E501 - the patterns read better on one line each
"""The Period & Timing Detector: monthly or annual? Which year end? What currency and units?

Deterministic date and header parsing. Ambiguity is reported, never assumed: every
field this detector cannot settle from a cue it can read is left None and named in
`ambiguous`, and the Timing Normalization skill must handle it. "Thousands vs. units" is
the single most expensive silent error available in this whole pipeline, and it is
almost always recoverable from a header the parser can read - so it is decided here,
once, or declared undecided here, once.

The model call the blueprint allows for the residue lands with the dispatcher; this
module is the deterministic half and the shape the residue fills in.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

__all__ = ["PeriodDetection", "detect_periods", "headings_in"]

_SCALE_CUES: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (
        re.compile(
            r"\bin thousands\b|\$\s?000s?\b|\(\s?000s?\s?\)|\b000s? omitted\b|\bthousands of\b|\$\s?k\b"
            r"|\b(?:amounts?|figures?|stated|expressed|presented)\s+in\s+(?:\$\s?)?000s?\b"
            r"|\b(?:USD|CAD|GBP|EUR|dollars?)\s+(?:in\s+)?thousands\b",
            re.I,
        ),
        1000,
        "thousands",
    ),
    (
        re.compile(r"\bin millions\b|\$\s?mm?\b|\(\s?mm?\s?\)|\bmillions of\b", re.I),
        1_000_000,
        "millions",
    ),
    (
        re.compile(
            r"\bin (?:units|dollars|whole dollars)\b|\bactual dollars\b|\bnot in thousands\b", re.I
        ),
        1,
        "units",
    ),
)
_CURRENCY_CUES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bUSD\b|\bUS\s?\$|\bU\.S\. dollars\b"), "USD"),
    (re.compile(r"\bCAD\b|\bC\$"), "CAD"),
    (re.compile(r"\bEUR\b|€"), "EUR"),
    (re.compile(r"\bGBP\b|£"), "GBP"),
)
_DOLLAR = re.compile(r"\$")
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_MONTH_YEAR = re.compile(rf"\b(?P<m>{_MONTHS})[a-z]*\.?[\s'\-/]*(?P<y>\d{{4}}|\d{{2}})\b", re.I)
# A money-shaped figure: at least four digits, or grouped with commas, optionally in
# parentheses or carrying a currency mark. Deliberately not "any number" - a page number,
# a note reference and a year are all numbers, and none of them is a column of figures.
_TRAILING_FIGURES = re.compile(r"(?<![\w.])\(?-?[$£€]?\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?(?![\w.])")
_FY = re.compile(r"\bFY\s?'?(?P<y>\d{4}|\d{2})\b", re.I)
_QUARTER = re.compile(r"\bQ(?P<q>[1-4])\s?(?:FY)?\s?'?(?P<y>\d{4}|\d{2})\b", re.I)
_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_US = re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4}|\d{2})\b")
_LONG = re.compile(rf"\b(?P<m>{_MONTHS})[a-z]*\.?\s+(?P<d>\d{{1,2}}),?\s+(?P<y>\d{{4}})\b", re.I)
_YEAR_END = re.compile(
    rf"\b(?:year[\s-]?end(?:ed|ing)?|fiscal year[\s-]?end|FYE)\b[^\n]{{0,20}}?\b(?P<m>{_MONTHS})[a-z]*\b",
    re.I,
)
_MONTH_INDEX = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}


@dataclass(frozen=True)
class PeriodDetection:
    period_type: str | None = None
    """monthly, quarterly, annual - or None when the cues disagree or are absent."""
    period_ends: tuple[str, ...] = ()
    fiscal_year_end_month: int | None = None
    currency: str | None = None
    scale: int | None = None
    """1, 1000 or 1000000 - or None. Never a default."""
    ambiguous: tuple[str, ...] = ()
    cues: dict[str, list[str]] = field(default_factory=dict)

    @property
    def settled(self) -> bool:
        return not self.ambiguous


def _spacing(gaps: list[int]) -> str | None:
    """What period a run of end dates ends, from the days between them."""
    if not gaps:
        return None
    if all(350 <= g <= 380 for g in gaps):
        return "annual"
    if all(85 <= g <= 95 for g in gaps):
        return "quarterly"
    if all(28 <= g <= 31 for g in gaps):
        return "monthly"
    return None


_BARE_YEAR = re.compile(r"(?<![\w,./-])(?:19|20)\d{2}(?![\w,./-])")


def headings_in(line: str) -> tuple[str, ...]:
    """The period headings on one line, left to right, as they were written.

    For naming the columns of a comparative statement, which is what says which figure
    belongs to which year. Returned as the text found rather than as a parsed date: a
    header reading `2025` names a year and not a year end, and turning it into
    `2025-12-31` here would be inventing a fiscal calendar this function cannot see. The
    engagement profile knows the year end; this knows what the document said.

    Order matters and a set would lose it, which is why this exists beside the detector
    rather than inside it - the detector wants to know which periods a document covers,
    and this wants to know which one is in the third column.
    """
    found = [
        (m.start(), m.group(0).strip())
        for pattern in (_ISO, _US, _LONG, _MONTH_YEAR, _QUARTER, _FY)
        for m in pattern.finditer(line)
    ]
    if not found:
        # The commonest header a statement has: two or three bare years over the columns.
        found = [(m.start(), m.group(0)) for m in _BARE_YEAR.finditer(line)]
    ordered: list[str] = []
    seen: set[tuple[int, str]] = set()
    # Longest first at any one position: `December 31, 2025` is matched by _LONG and its
    # month by _MONTH_YEAR, both starting at the same character, and the shorter one
    # winning is how a column headed 2025 ends up labelled `December 31`.
    for start, text in sorted(found, key=lambda f: (f[0], -len(f[1]))):
        # Overlapping patterns match the same heading twice - `December 31, 2025` is
        # caught by _LONG and its year by _MONTH_YEAR. The leftmost, longest wins.
        if any(start < s + len(t) and s <= start for s, t in seen):
            continue
        seen.add((start, text))
        ordered.append(text)
    return tuple(ordered)


def detect_periods(text: str, tables: Sequence[Any] = ()) -> PeriodDetection:
    ambiguous: list[str] = []
    cues: dict[str, list[str]] = {}

    # -- scale
    scales: dict[int, str] = {}
    for pattern, factor, name in _SCALE_CUES:
        match = pattern.search(text)
        if match:
            scales[factor] = match.group(0)
            cues.setdefault("scale", []).append(f"{name}: {match.group(0)!r}")
    if len(scales) == 1:
        scale: int | None = next(iter(scales))
    elif scales:
        scale = None
        ambiguous.append("scale: conflicting cues " + ", ".join(sorted(scales.values())))
    else:
        scale = None
        ambiguous.append("scale: no cue in the headers - units or thousands is not stated")

    # -- currency
    currencies = {code for pattern, code in _CURRENCY_CUES if pattern.search(text)}
    if not currencies and _DOLLAR.search(text):
        currencies = {"USD"}
        cues.setdefault("currency", []).append("'$' taken as USD; no code stated")
    if len(currencies) == 1:
        currency: str | None = next(iter(currencies))
    elif currencies:
        currency = None
        ambiguous.append("currency: " + " and ".join(sorted(currencies)) + " both appear")
    else:
        currency = None
        ambiguous.append("currency: no cue")

    # -- periods
    ends: set[date] = set()
    types: set[str] = set()
    for match in _ISO.finditer(text):
        ends.add(date(int(match.group("y")), int(match.group("m")), int(match.group("d"))))
    for match in _US.finditer(text):
        ends.add(date(_year(match.group("y")), int(match.group("m")), int(match.group("d"))))
    for match in _LONG.finditer(text):
        ends.add(
            date(
                int(match.group("y")),
                _MONTH_INDEX[match.group("m")[:3].lower()],
                int(match.group("d")),
            )
        )
    month_year = [
        (_MONTH_INDEX[m.group("m")[:3].lower()], _year(m.group("y")))
        for m in _MONTH_YEAR.finditer(text)
        if not _LONG.match(text, m.start()) and not _is_a_day(m, text)
    ]
    for month, year in month_year:
        ends.add(date(year, month, calendar.monthrange(year, month)[1]))
    if len({(m, y) for m, y in month_year}) >= 3:
        types.add("monthly")
        cues.setdefault("period", []).append(f"{len(set(month_year))} month-year columns")
    quarters = list(_QUARTER.finditer(text))
    if quarters:
        types.add("quarterly")
        cues.setdefault("period", []).append(f"{len(quarters)} quarter column(s)")
    fys = list(_FY.finditer(text))
    if fys:
        types.add("annual")
        cues.setdefault("period", []).append(", ".join(m.group(0) for m in fys[:4]))
    if not types and len(ends) >= 2:
        # Real dates in the header row and no word beside them. The spacing says what
        # kind of period they end: a year apart is annual, a month apart monthly, a
        # quarter apart quarterly. Anything else stays unsettled.
        ordered = sorted(ends)
        gaps = [(b - a).days for a, b in zip(ordered, ordered[1:], strict=False)]
        spacing = _spacing(gaps)
        if spacing:
            types.add(spacing)
            cues.setdefault("period", []).append(
                f"{len(ordered)} dated columns, {spacing} by their spacing"
            )
    if len(types) == 1:
        period_type: str | None = next(iter(types))
    elif types:
        period_type = None
        ambiguous.append("period_type: " + " and ".join(sorted(types)) + " cues both present")
    else:
        period_type = None
        if not ends:
            ambiguous.append("period_type: no period cue")

    # -- fiscal year end
    fye = _YEAR_END.search(text)
    fiscal_year_end = _MONTH_INDEX[fye.group("m")[:3].lower()] if fye else None
    if fiscal_year_end is None and period_type == "annual" and ends:
        months = {d.month for d in ends}
        if len(months) == 1:
            fiscal_year_end = next(iter(months))
            cues.setdefault("fiscal_year_end", []).append("from the annual period end dates")
    if fiscal_year_end is None:
        ambiguous.append("fiscal_year_end: not stated")

    # -- whether the columns can be told apart
    #
    # A comparative statement - which is every audited one, and the usual shape of a PDF
    # arriving from a client - puts this year and last year on the same line. The reader
    # used to match one figure per row anchored to the end of the line, so on the real
    # filing in fixtures/public it stored `Revenue $ 386,902 $ 440,121 $` as a label and
    # -53,219 as the value: the *Change* column, not a year at all. `Loss from operations`
    # came out as +181,317 on a year the company lost 96,083. Silently, and past every
    # guard - provenance passed because the number really was at that locator, and footing
    # passed because the rows were consistently one column so the totals still re-added.
    #
    # Asked of the tables when there are tables. The text form below is a sample - the
    # caller passes page-one headers and one table's first rows - and on that filing the
    # sample is a share-buyback table with one figure a row, so it said nothing while
    # fifty-eight comparative tables were read wrong. A guard on a sample is a guard on
    # whatever happened to be first.
    if tables:
        unnamed = [t for t in tables if len(t.columns) > 1 and not any(t.headings)]
        if unnamed:
            where = ", ".join(t.locator for t in unnamed[:3])
            cues.setdefault("columns", []).append(
                f"{len(tables) - len(unnamed)} of {len(tables)} tables name their columns"
            )
            ambiguous.append(
                f"columns: {len(unnamed)} table(s) carry more than one column of figures "
                f"and no header row names them - {where}"
                + (", and others" if len(unnamed) > 3 else "")
            )
        elif any(len(t.columns) > 1 for t in tables):
            cues.setdefault("columns", []).append("every column is named by a header row")
    else:
        widths = [len(_TRAILING_FIGURES.findall(line)) for line in text.splitlines()]
        tabular = [w for w in widths if w]
        if tabular:
            most = max(set(tabular), key=tabular.count)
            if most > 1 and not any(len(headings_in(line)) == most for line in text.splitlines()):
                cues.setdefault("columns", []).append(f"{most} figures on a typical row")
                ambiguous.append(
                    f"columns: rows carry {most} figures and no line names {most} periods, "
                    "so which column belongs to which period is not stated"
                )

    return PeriodDetection(
        period_type=period_type,
        period_ends=tuple(d.isoformat() for d in sorted(ends)),
        fiscal_year_end_month=fiscal_year_end,
        currency=currency,
        scale=scale,
        ambiguous=tuple(ambiguous),
        cues=cues,
    )


def _is_a_day(m: re.Match[str], text: str) -> bool:
    """Two digits after a written-out month and a space are a day, not a year:
    "December 31" in "for the years ended December 31" is the 31st, and reading it as
    2031 gave every statement a period end six years out. "Dec-25", "Dec'25", "Dec/25"
    and the abbreviated "Dec 25" keep their year."""
    year = m.group("y")
    if len(year) != 2:
        return False
    between = text[m.end("m") : m.start("y")]
    if any(ch in between for ch in "'-/"):
        return False
    written_out = between.rstrip(". ").isalpha() and between.rstrip(". ") != ""
    return written_out and int(year) <= 31


def _year(text: str) -> int:
    n = int(text)
    return n if n >= 100 else 2000 + n

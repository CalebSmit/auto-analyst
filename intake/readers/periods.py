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
from dataclasses import dataclass, field
from datetime import date

__all__ = ["PeriodDetection", "detect_periods"]

_SCALE_CUES: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (
        re.compile(
            r"\bin thousands\b|\$\s?000s?\b|\(\s?000s?\s?\)|\b000s? omitted\b|\bthousands of\b|\$\s?k\b",
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


def detect_periods(text: str) -> PeriodDetection:
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
        if not _LONG.match(text, m.start())
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

    return PeriodDetection(
        period_type=period_type,
        period_ends=tuple(d.isoformat() for d in sorted(ends)),
        fiscal_year_end_month=fiscal_year_end,
        currency=currency,
        scale=scale,
        ambiguous=tuple(ambiguous),
        cues=cues,
    )


def _year(text: str) -> int:
    n = int(text)
    return n if n >= 100 else 2000 + n

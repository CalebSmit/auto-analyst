"""The due diligence request list: what the client was asked for, and what has arrived.

The firm sends a request list at the start of an engagement, and the same workbook is the
tracker. Its seven section groupings are stable across engagements; the items inside them
are written for the engagement and stay similar year to year for a repeat client. Each
section is also a folder in Box and in ShareFile, and the firm writes item references -
`B.6`, `C.7`, `D.5` - as the names of the tabs that carry supporting data.

Two axes, kept apart on purpose:

* **document type** - what kind of file this is (`trial_balance`, `financial_statements`).
  `intake/readers/classify.py` answers that from the file's own content.
* **request section and item** - which of the things we asked for this answers. That is
  what the analyst tracks, and the folder already knows it.

A file has both, and neither substitutes for the other: a PDF of financial statements
filed under `C. Operational Matters` is still financial statements, and is still an answer
to something in section C. Nothing here classifies a document type.

**What is deliberately not here.** The items themselves. The seven sections are the firm's
and are the same every time, so they are written down; the item lists belong to an
engagement, and the ones in hand are a single real example belonging to a client. They are
loaded per engagement (`RequestList.from_rows`) rather than invented here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "SECTIONS",
    "Coverage",
    "ItemRef",
    "RequestItem",
    "RequestList",
    "Status",
    "section_of",
]

SECTIONS: dict[str, str] = {
    "A": "Financial Records",
    "B": "Corporate Documents",
    "C": "Operational Matters",
    "D": "Employment/Labor Matters",
    "E": "Properties & Equipment",
    "F": "Contracts",
    "G": "Legal Matters",
}
"""The stable half of the request list, from a real one (2026-09-18-1).

The groupings do not change between engagements, which is why they can live in the code
while the items cannot. Section A is the one that feeds the model.
"""


class Status(StrEnum):
    """The tracker's own three answers, and no fourth.

    `OUTSTANDING` rather than `missing`: the firm's word, and the honest one - nothing has
    arrived *yet*, which is not the same as a client having refused.
    """

    PROVIDED = "provided"
    OUTSTANDING = "outstanding"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, order=True)
class ItemRef:
    """A reference to one numbered item, as the firm writes it: `B.6`, `E.1`.

    Ordered so a coverage report reads in the order the request list does.
    """

    section: str
    number: int

    def __str__(self) -> str:
        return f"{self.section}.{self.number}"

    @property
    def section_title(self) -> str:
        return SECTIONS[self.section]


_REF = re.compile(r"(?<![A-Za-z0-9])([A-G])[.\s]?(\d{1,2})(?![0-9])")


def parse_ref(text: str) -> ItemRef | None:
    """The first item reference in a piece of text, or None.

    Refuses rather than half-reading: a section letter with no number, or a letter outside
    A-G, is not a reference. The firm writes these as tab names and in notes ("see D.5"),
    so the same parser serves a filename, a folder and a note.
    """
    found = _REF.search(text)
    if not found:
        return None
    section = found.group(1).upper()
    if section not in SECTIONS:  # pragma: no cover - the pattern already bounds it
        return None
    return ItemRef(section, int(found.group(2)))


_SECTION_FOLDER = re.compile(r"^([A-G])[.)\s_-]+(.*)$")


def section_of(path: str) -> str | None:
    """Which request section a file arrived under, from its path - or None.

    Reads the folder names, not the file's content. A path component like `A. Financial
    Records`, `B - Corporate Documents` or `C_Operational` names a section; anything else
    does not. **None is a real answer**, not a default: a file dropped outside the
    lettered folders has no section, and saying so is better than guessing one, in the
    same way an unclaimed folder is reported rather than assigned to an engagement.

    The last matching component wins, so a nested `.../A. Financial Records/B.6/` reads as
    B rather than A - the deeper folder is the more specific statement.
    """
    found: str | None = None
    for part in re.split(r"[\\/]+", path):
        cleaned = part.strip()
        if not cleaned:
            continue
        match = _SECTION_FOLDER.match(cleaned)
        if not match:
            continue
        letter, rest = match.group(1).upper(), match.group(2).strip()
        # `A. Financial Records` names a section. So does a bare `B`. `E.1 & E.2` is an
        # item tab, and its section is still E.
        if letter in SECTIONS and (rest == "" or not rest[0].isdigit() or parse_ref(cleaned)):
            found = letter
    return found


@dataclass(frozen=True)
class RequestItem:
    """One numbered thing asked of the client."""

    ref: ItemRef
    text: str
    essential: bool = False
    """Whether the engagement cannot proceed without it. The analyst's own distinction:
    historical financials are the gate the whole job waits on, and most of the list is not.
    """


@dataclass(frozen=True)
class Arrived:
    """A file that has landed, as far as this module cares about it."""

    path: str
    ref: ItemRef | None = None
    """Set where the firm's own numbering appears in the path; otherwise the file answers
    a section but not a known item."""

    @classmethod
    def at(cls, path: str) -> Arrived:
        return cls(path=path, ref=parse_ref(path))

    @property
    def section(self) -> str | None:
        return section_of(self.path)


@dataclass(frozen=True)
class Coverage:
    item: RequestItem
    status: Status
    evidence: tuple[str, ...] = ()
    """The paths that answered it, so "provided" can be checked rather than believed."""


class RequestList:
    """One engagement's request list, and what has arrived against it."""

    def __init__(
        self, items: Sequence[RequestItem], not_applicable: Iterable[ItemRef] = ()
    ) -> None:
        self.items = tuple(sorted(items, key=lambda i: i.ref))
        self.not_applicable = frozenset(not_applicable)

    @classmethod
    def from_rows(cls, rows: Iterable[tuple[str, str]], **kw: object) -> RequestList:
        """From `(ref, text)` pairs - the shape a row of the firm's tracker exports to."""
        items = []
        for ref, text in rows:
            parsed = parse_ref(ref)
            if parsed is None:
                raise ValueError(f"{ref!r} is not a request item reference like 'B.6'")
            items.append(RequestItem(parsed, text))
        return cls(items, **kw)  # type: ignore[arg-type]

    def coverage(self, arrived: Iterable[Arrived]) -> tuple[Coverage, ...]:
        """Per item, in the order the list is written: provided, outstanding, or not
        applicable.

        A file counts for an item when it carries that item's reference. A file that names
        only a section is evidence for the section and for no particular item - it does not
        silently satisfy the first outstanding thing in that section, because "something
        from section A turned up" is not "item A.3 has been provided".
        """
        landed = list(arrived)
        by_ref: dict[ItemRef, list[str]] = {}
        for file in landed:
            if file.ref is not None:
                by_ref.setdefault(file.ref, []).append(file.path)

        report = []
        for item in self.items:
            if item.ref in self.not_applicable:
                report.append(Coverage(item, Status.NOT_APPLICABLE))
                continue
            paths = tuple(by_ref.get(item.ref, ()))
            status = Status.PROVIDED if paths else Status.OUTSTANDING
            report.append(Coverage(item, status, paths))
        return tuple(report)

    def outstanding(self, arrived: Iterable[Arrived]) -> tuple[Coverage, ...]:
        """What the client still owes - the follow-up list, essential items first."""
        waiting = [c for c in self.coverage(arrived) if c.status is Status.OUTSTANDING]
        return tuple(sorted(waiting, key=lambda c: (not c.item.essential, c.item.ref)))

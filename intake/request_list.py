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
from pathlib import Path

__all__ = [
    "DEFAULT_LISTS",
    "SECTIONS",
    "STARTING_POINT",
    "THE_FIRM_S_OWN",
    "Coverage",
    "ItemRef",
    "RequestItem",
    "RequestList",
    "Status",
    "for_scope",
    "load_list",
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

    answered_by: tuple[str, ...] = ()
    """Document classes from `intake/readers/classify.py` that satisfy this item.

    How a pile of files with ordinary names gets matched to things that were asked for.
    A client sending twenty documents does not file them under `A. Financial Records/A.3/`
    - they arrive as `TB 2025 final.xlsx` - so without this the only evidence available is
    the folder, and the folder is usually `inbox`.

    Empty is not a gap. Most of a request list is prose, minutes and contracts that no
    classifier recognises, and those are matched by reference or by a person."""


@dataclass(frozen=True)
class Arrived:
    """A file that has landed, as far as this module cares about it."""

    path: str
    ref: ItemRef | None = None
    """Set where the firm's own numbering appears in the path; otherwise the file answers
    a section but not a known item."""

    kind: str | None = None
    """What `intake/readers/classify.py` made of the file's content, where anything has
    read it. None means nobody has looked, which is different from `other` - a file
    classified `other` was read and recognised as nothing in particular."""

    @classmethod
    def at(cls, path: str, kind: str | None = None) -> Arrived:
        return cls(path=path, ref=parse_ref(path), kind=kind)

    @property
    def section(self) -> str | None:
        return section_of(self.path)


BY_REFERENCE = "reference"
BY_KIND = "kind"
"""How an item came to be marked provided, and the two are not equally strong.

`reference` is the firm's own numbering in the path - `B.6` - which is somebody saying
this file answers that item. `kind` is the classifier recognising a trial balance and an
item asking for one, which is a good inference and still an inference. A tracker that did
not distinguish them would make a person re-check all of it or none of it.
"""


@dataclass(frozen=True)
class Coverage:
    item: RequestItem
    status: Status
    evidence: tuple[str, ...] = ()
    """The paths that answered it, so "provided" can be checked rather than believed."""

    matched_by: str = ""
    """`reference`, `kind`, or empty when nothing matched. See BY_REFERENCE."""

    @property
    def inferred(self) -> bool:
        """True when a person should look. A kind match is the tool's reading of what a
        document is; a reference match is somebody's statement about it."""
        return self.matched_by == BY_KIND


STARTING_POINT = "starting point"
THE_FIRM_S_OWN = "the firm's own"
"""Where a list came from, and it belongs on every report made against it.

"Nine of twenty provided" against a list somebody guessed and against the firm's own
request list are different sentences. The first is worth acting on and worth correcting;
the second is worth acting on. A report that did not say which invites the first to be
read as the second.
"""

DEFAULT_LISTS = Path(__file__).resolve().parent / "request_lists"


class RequestList:
    """One engagement's request list, and what has arrived against it."""

    def __init__(
        self,
        items: Sequence[RequestItem],
        not_applicable: Iterable[ItemRef] = (),
        *,
        name: str = "",
        origin: str = THE_FIRM_S_OWN,
    ) -> None:
        self.items = tuple(sorted(items, key=lambda i: i.ref))
        self.not_applicable = frozenset(not_applicable)
        self.name = name
        self.origin = origin

    def __repr__(self) -> str:
        return f"RequestList({self.name!r}, {len(self.items)} items, {self.origin})"

    @property
    def is_a_starting_point(self) -> bool:
        return self.origin == STARTING_POINT

    @property
    def essential(self) -> tuple[RequestItem, ...]:
        return tuple(i for i in self.items if i.essential)

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

        A file counts for an item two ways, and the report says which.

        **By reference**, when it carries that item's number: somebody filed it there, and
        that is a statement about the file which this is not the place to argue with.

        **By kind**, when nothing in the path said anything and the classifier recognised
        the document as something the item asks for. This is what makes a pile of files
        with ordinary names trackable at all - a client sends `TB 2025 final.xlsx`, not
        `A. Financial Records/A.3/...`. It is a good inference and it stays marked as one.

        A file that names only a *section* still counts for nothing in particular. "Something
        from section A turned up" is not "item A.3 has been provided", and it never was.
        """
        landed = list(arrived)
        by_ref: dict[ItemRef, list[str]] = {}
        by_kind: dict[str, list[str]] = {}
        for file in landed:
            if file.ref is not None:
                by_ref.setdefault(file.ref, []).append(file.path)
            elif file.kind:
                # Only where the path said nothing. A file that carries `B.6` is claimed
                # by B.6 whatever it turns out to be - somebody filed it there, and this
                # is not the place to argue with them.
                by_kind.setdefault(file.kind, []).append(file.path)

        report = []
        for item in self.items:
            if item.ref in self.not_applicable:
                report.append(Coverage(item, Status.NOT_APPLICABLE))
                continue

            paths = tuple(by_ref.get(item.ref, ()))
            if paths:
                report.append(Coverage(item, Status.PROVIDED, paths, BY_REFERENCE))
                continue

            # One document can answer more than one item, and does: a five-year set of
            # financial statements matches both "the last five fiscal years" and "interim
            # year to date", and only one of those is true. Deliberately not
            # first-come-first-served, which would pick one of them arbitrarily and be
            # wrong half the time with no sign of it. Both are marked, both are flagged
            # as inferred, and a person settles it - which is the whole reason the flag
            # exists.
            inferred = tuple(
                path for kind in item.answered_by for path in by_kind.get(kind, ())
            )
            if inferred:
                report.append(Coverage(item, Status.PROVIDED, inferred, BY_KIND))
                continue

            report.append(Coverage(item, Status.OUTSTANDING))
        return tuple(report)

    def report(self, arrived: Iterable[Arrived]) -> dict[str, object]:
        """The tracker, in one shape: what was asked for, what arrived, and how it was
        decided - with where the list came from attached, not left to be remembered."""
        rows = self.coverage(arrived)
        counted = {s.value: sum(1 for c in rows if c.status is s) for s in Status}
        return {
            "list": self.name,
            "origin": self.origin,
            "is_a_starting_point": self.is_a_starting_point,
            "counts": counted,
            "inferred": sum(1 for c in rows if c.inferred),
            "essential_outstanding": [
                str(c.item.ref)
                for c in rows
                if c.status is Status.OUTSTANDING and c.item.essential
            ],
            "items": [
                {
                    "ref": str(c.item.ref),
                    "section": c.item.ref.section_title,
                    "text": c.item.text,
                    "essential": c.item.essential,
                    "status": c.status.value,
                    "matched_by": c.matched_by,
                    "inferred": c.inferred,
                    "evidence": list(c.evidence),
                }
                for c in rows
            ],
        }

    def outstanding(self, arrived: Iterable[Arrived]) -> tuple[Coverage, ...]:
        """What the client still owes - the follow-up list, essential items first."""
        waiting = [c for c in self.coverage(arrived) if c.status is Status.OUTSTANDING]
        return tuple(sorted(waiting, key=lambda c: (not c.item.essential, c.item.ref)))


def load_list(path: Path | str, *, origin: str = THE_FIRM_S_OWN) -> RequestList:
    """A request list from a YAML file.

    `origin` defaults to the firm's own, because a file somebody registered usually is.
    `for_scope` passes STARTING_POINT for the ones that ship with the code.
    """
    import yaml  # noqa: PLC0415 - not needed to parse a reference

    document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = []
    for row in document.get("items") or ():
        ref = parse_ref(str(row.get("ref", "")))
        if ref is None:
            raise ValueError(f"{row.get('ref')!r} is not a request item reference like 'B.6'")
        items.append(
            RequestItem(
                ref=ref,
                text=str(row.get("text", "")).strip(),
                essential=bool(row.get("essential", False)),
                answered_by=tuple(row.get("answered_by") or ()),
            )
        )
    if not items:
        raise ValueError(f"{path} holds no request items")
    return RequestList(items, name=str(document.get("name") or Path(path).stem), origin=origin)


def for_scope(scope_path: str, where: Path | str = DEFAULT_LISTS) -> RequestList | None:
    """The list an engagement starts from when nobody has written one, or None.

    Matched on the scope path - `valuation/non-esop` - walking up, so a division with no
    list of its own inherits its practice's. None is a real answer: a division nobody has
    written a starting list for gets no list rather than another division's, because a
    request list is what the client is asked for and sending the wrong one is worse than
    sending none.

    `where` takes the directory it reads rather than assuming this one, so the walking-up
    can be shown working on a tree built for the purpose. The alternative - a test that
    writes a file into `intake/request_lists/` and takes it away again - is a test that
    can leave the repo edited, and this project has lost committed records that way.
    """
    root = Path(where)
    parts = [p for p in scope_path.strip("/").split("/") if p]
    while parts:
        candidate = root / (("-".join(parts)) + ".yaml")
        if candidate.is_file():
            return load_list(candidate, origin=STARTING_POINT)
        parts.pop()
    return None

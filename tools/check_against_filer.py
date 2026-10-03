"""Every figure the readers extract, against the figures the filer reported.

**Accuracy has never had an answer in this build, only evidence.** A total that re-adds and a
balance sheet that balances prove *arithmetic*, and arithmetic is satisfied by eight wrong
rows that add correctly - `guards/tieout.py` says so about its own half: *"Tie-out proves
arithmetic, not selection."* So "is every figure right" has been unanswerable, and every
claim about it rested on one document that one person read.

The SEC publishes the filer's own numbers as structured data. Every figure on these
statements is tagged in XBRL, so `Assets` at 2025-12-31 is 521,728,000 - which is the 521,728
on page 56 times the thousand the statement says it is in. That is ground truth, from the
same regulator, for the same filing.

**No label-to-concept mapping is needed**, which is the part that would have made this hard.
The question is not which concept a row is. It is:

* **precision** - is every figure the reader produced a figure the filer reported, *at the
  date that column is as of*? A figure from the wrong column is still a figure the filer
  reported, and taking the prior year out of a comparative balance sheet is B-030, this
  repository's own worst extraction defect. Matching by date is what sees it.
* **recall** - which figures did it not find? Reported as a count rather than a list, because
  the fact set includes every note in the filing and a balance sheet is not supposed to
  account for all of it.

**It is offline.** The facts are committed under `fixtures/public/filer-facts/`, trimmed to
the dates each filing's statements are as of, because this build is local-only and its tests
run on a train. `--fetch` is the one networked path and it is an explicit act.

    python -m uv run python tools/check_against_filer.py              # every fixture
    python -m uv run python tools/check_against_filer.py --fixture sec-ars-resmed-2026
    python -m uv run python tools/check_against_filer.py --fetch 0000943819

**What it cannot see**, said here because a measurement whose limits are not written down
gets quoted as though it had none. `companyfacts` serves the *dimensionless* facts: a figure
tagged only against a segment, a product or a share class is in the filing's own XBRL and not
in this feed, so a figure absent from it is a figure this comparison cannot speak about
rather than one the reader got wrong. It is also blind to a label read wrongly, because it
compares figures and not words - and to a figure that is right and in the wrong row.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "fixtures" / "public"
FACTS = PUBLIC / "filer-facts"

sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

# A person who runs this outside the project environment gets the line to type rather than
# an ImportError from the middle of reading a PDF. `pdfplumber` and `pypdf` read the filings
# and `openpyxl` reads the workbook; none of them is in a bare interpreter.
needs("pdfplumber", "pypdf", "openpyxl", script="tools/check_against_filer.py")

AGENT = "Chartwell Automated Analyst research caleb.smit@icloud.com"


@dataclass(frozen=True)
class Statement:
    """One statement in a filing, and what each of its columns is as of.

    The dates are the one thing this cannot derive. A column headed `2025` names a year and
    not a year end, and which date a fiscal year ends on is a property of the company - the
    same reason `tools/read_template.py` will not fill in a `line:` for you. So they are
    declared here, from the filing's own cover, and a wrong one shows up immediately as
    every figure in that column landing at another date.
    """

    page: int | None = None
    """For a PDF. `None` for a workbook, where `sheet` says which."""
    sheet: str | None = None
    columns: tuple[str, ...] = ()
    """The date each column is as of, left to right, 1-based to match `Column.index`."""
    scale: int = 1_000
    """What the statement says it is in. Stated rather than detected, because this tool is
    checking the reader and a detected scale is one of the things being checked."""
    what: str = ""


@dataclass(frozen=True)
class Fixture:
    document: str
    facts: str
    statements: tuple[Statement, ...] = ()


FIXTURES: dict[str, Fixture] = {
    "sec-ars-3d-systems-2025": Fixture(
        document="sec-ars-3d-systems-2025.pdf",
        facts="sec-ars-3d-systems-2025.json",
        statements=(
            Statement(
                page=56,
                columns=("2025-12-31", "2024-12-31"),
                what="consolidated balance sheet",
            ),
        ),
    ),
    "sec-ars-resmed-2026": Fixture(
        document="sec-ars-resmed-2026.pdf",
        facts="sec-ars-resmed-2026.json",
        statements=(
            Statement(
                page=79,
                columns=("2026-06-30", "2025-06-30"),
                what="consolidated balance sheet",
            ),
        ),
    ),
    "sec-financial-report-3d-systems-2025q1": Fixture(
        document="sec-financial-report-3d-systems-2025q1.xlsx",
        facts="sec-financial-report-3d-systems-2025q1.json",
        statements=(
            Statement(
                sheet="Condensed Consolidated Balance ",
                columns=("2025-03-31", "2024-12-31"),
                what="condensed consolidated balance sheet",
            ),
        ),
    ),
}


@dataclass
class Checked:
    """What happened to one column's figures, in four kinds.

    `unscaled` is the kind the first draft of this tool did not have, and leaving it out
    reported the defect it finds as *"no fact in this feed"* - which reads as a limitation
    of the data and is in fact a figure this build would get wrong by a factor of a thousand.
    """

    where: str
    date: str
    here: list[tuple[str, float]] = field(default_factory=list)
    """Right, at this column's date and at the statement's scale."""
    unscaled: list[tuple[str, float, list[str]]] = field(default_factory=list)
    """The figure is one the filer reported, but at a **different scale** from the one the
    statement declares.

    Two things land here and they are worth telling apart by the scale that fitted. At scale
    1 it is a row the statement's own scale does not apply to - a share count, a per-share
    amount, a percentage - and the statement usually says so itself: ResMed's reads *in
    thousands, except share and per share data*. At any other scale it is the declared scale
    being wrong for the whole statement, which is one mistake rather than a row's worth.

    Without this category the first draft reported both as *"no fact in this feed"*, which
    reads as a limitation of the data and was in fact a figure wrong by a factor of a
    thousand."""
    elsewhere: list[tuple[str, float, list[str]]] = field(default_factory=list)
    """Reported at a different date, which is a figure out of the wrong column."""
    nowhere: list[tuple[str, float]] = field(default_factory=list)
    """No fact at any date in any unit, which this feed cannot distinguish from a figure
    tagged only against a segment."""

    @property
    def figures(self) -> int:
        return len(self.here) + len(self.unscaled) + len(self.elsewhere) + len(self.nowhere)

    @property
    def right(self) -> bool:
        return not self.elsewhere


def load_facts(name: str) -> dict[str, Any]:
    path = FACTS / name
    if not path.exists():
        raise SystemExit(
            f"{path} is not here. The facts are committed beside the fixtures; "
            f"`--fetch <cik>` refreshes them."
        )
    body: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return body


def values_at(facts: dict[str, Any], date: str) -> dict[float, list[str]]:
    """The filer's point-in-time figures at one date, as numbers."""
    return {
        float(value): concepts
        for value, concepts in facts.get("at_date", {}).get(date, {}).items()
    }


SCALES = (1, 1_000, 1_000_000, 1_000_000_000)
"""The scales a statement is ever printed in. Tried in order when the declared one does not
fit, so that a wrong scale is reported as a wrong scale rather than as a figure nobody can
check - which is what it looked like before, and reads as the data's fault."""


def scale_that_fits(
    value: float, declared: int, here: dict[float, list[str]]
) -> int | None:
    """Which scale would make this figure a fact at this date, if the declared one does not.

    `None` where none of them would, which is the honest answer: the figure is either not
    in this feed or not right, and this function cannot tell those apart.
    """
    for scale in SCALES:
        if scale == declared:
            continue
        scaled = value * scale
        if scaled in here or -scaled in here:
            return scale
    return None


def rows_of(fixture: Fixture, statement: Statement) -> list[tuple[int, str, float]]:
    """The reader's own output: which column, what label, what figure."""
    data = (PUBLIC / fixture.document).read_bytes()
    if statement.page is not None:
        from intake.readers.documents import read_document

        doc = read_document(data, fixture.document)
        page = next((p for p in doc.pages if p.number == statement.page), None)
        if page is None:
            return []
        return [
            (column.index, row.label, row.value)
            for table in page.tables
            for column in table.columns
            for row in column.rows
            if row.value is not None
        ]

    from intake.readers.workbook import normalize_workbook

    out: list[tuple[int, str, float]] = []
    for table in normalize_workbook(data, [str(statement.sheet)]):
        for n, (_locator, rows) in enumerate(table.blocks.items(), start=1):
            out.extend((n, row.label, row.value) for row in rows if row.value is not None)
    return out


def check(fixture: Fixture, statement: Statement, facts: dict[str, Any]) -> list[Checked]:
    rows = rows_of(fixture, statement)
    everywhere: dict[float, list[str]] = {}
    for date in facts.get("at_date", {}):
        for value, concepts in values_at(facts, date).items():
            everywhere.setdefault(value, []).extend(f"{date} {c}" for c in concepts)

    out: list[Checked] = []
    for index, date in enumerate(statement.columns, start=1):
        here = values_at(facts, date)
        said = Checked(
            where=(
                f"p{statement.page}/c{index}"
                if statement.page is not None
                else f"{statement.sheet}/c{index}"
            ),
            date=date,
        )
        for column, label, value in rows:
            if column != index:
                continue
            scaled = value * statement.scale
            if scaled in here or -scaled in here:
                said.here.append((label, value))
            elif (fits := scale_that_fits(value, statement.scale, here)) is not None:
                # Right figure, wrong scale applied to it. Asked before the wrong-date
                # question on purpose: a share count at this date matches a *dollar* figure
                # at some other date often enough that checking dates first would call this
                # a wrong-column read, which is a different and more alarming thing.
                at = fits * value
                said.unscaled.append(
                    (
                        label,
                        value,
                        [f"scale={fits}", *(here.get(at) or here.get(-at) or [])],
                    )
                )
            elif scaled in everywhere or -scaled in everywhere:
                said.elsewhere.append(
                    (label, value, everywhere.get(scaled) or everywhere.get(-scaled) or [])
                )
            else:
                said.nowhere.append((label, value))
        out.append(said)
    return out


def report(
    name: str,
    fixture: Fixture,
    out: Any,
    found: dict[int, list[Checked]],
    facts: dict[str, Any],
) -> bool:
    """Write what was found. Given the results rather than computing them, because reading
    a hundred-and-twenty-page filing twice to print it once is two minutes of nothing."""
    ok = True
    out.write(f"\n=== {name}\n")
    out.write(f"    {facts.get('entity')} (CIK {facts.get('cik')})\n")
    out.write(f"    {fixture.document}\n")
    for n, statement in enumerate(fixture.statements):
        out.write(f"    {statement.what}, stated in {statement.scale:,}s\n")
        for said in found[n]:
            out.write(
                f"      {said.where} as of {said.date}: {said.figures} figure(s)\n"
                f"          right, at this date and scale:   {len(said.here)}\n"
                f"          right, but not at that scale:    {len(said.unscaled)}\n"
                f"          reported at a different date:    {len(said.elsewhere)}\n"
                f"          no fact anywhere in this feed:   {len(said.nowhere)}\n"
            )
            for label, value, where in said.elsewhere[:8]:
                ok = False
                out.write(
                    f"          ! {label[:44]:46} {value:>14,.0f}  "
                    f"the filer reports this at {where[0].split()[0]}\n"
                )
            for label, value, where in said.unscaled[:8]:
                fits = int(str(where[0]).removeprefix("scale=")) if where else 1
                unit = str(where[1]).split("|")[-1] if len(where) > 1 else "?"
                if fits == 1:
                    out.write(
                        f"          ~ {label[:44]:46} {value:>14,.0f}  "
                        f"the filer reports exactly this, in {unit} - the statement's "
                        f"scale of {statement.scale:,} does not apply to this row, and "
                        f"applying it would report {value * statement.scale:,.0f}\n"
                    )
                else:
                    out.write(
                        f"          ~ {label[:44]:46} {value:>14,.0f}  "
                        f"matches the filer at a scale of {fits:,}, not the "
                        f"{statement.scale:,} declared - the scale is wrong\n"
                    )
            for label, value in said.nowhere[:8]:
                out.write(
                    f"          ? {label[:44]:46} {value:>14,.0f}  "
                    f"no fact in this feed\n"
                )
            if said.nowhere:
                out.write(
                    "          (a figure with no fact may be tagged against a segment or "
                    "a share class, which this feed does not carry)\n"
                )
    return ok


def fetch(cik: str, out: Any) -> None:
    """Refresh a filer's facts. The one networked path, and an explicit act."""
    import urllib.request

    padded = cik.zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"
    out.write(f"fetching {url}\n")
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=240) as response:
        body = response.read()
    where = FACTS / f"companyfacts-CIK{padded}.json"
    where.write_bytes(body)
    out.write(
        f"wrote {where} ({len(body):,} bytes). Trim it to the dates a filing's statements "
        f"are as of before committing - the whole file is every period the filer has ever "
        f"reported.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", help="check one rather than all of them")
    parser.add_argument("--fetch", metavar="CIK", help="refresh a filer's facts; needs the network")
    args = parser.parse_args(argv)
    out = sys.stdout

    if args.fetch:
        fetch(args.fetch, out)
        return 0

    chosen = {args.fixture: FIXTURES[args.fixture]} if args.fixture else FIXTURES
    if args.fixture and args.fixture not in FIXTURES:
        out.write(f"no fixture {args.fixture!r}; there are {sorted(FIXTURES)}\n")
        return 2

    every = True
    counts = {"here": 0, "unscaled": 0, "elsewhere": 0, "nowhere": 0}
    for name, fixture in chosen.items():
        facts = load_facts(fixture.facts)
        found = {
            n: check(fixture, statement, facts)
            for n, statement in enumerate(fixture.statements)
        }
        for said_all in found.values():
            for said in said_all:
                counts["here"] += len(said.here)
                counts["unscaled"] += len(said.unscaled)
                counts["elsewhere"] += len(said.elsewhere)
                counts["nowhere"] += len(said.nowhere)
        every = report(name, fixture, out, found, facts) and every

    # Said precisely rather than warmly. The first draft of this closed with "every figure
    # matched a figure the filer reported at its own column's date" while five figures had
    # matched nothing at all, which is the kind of summary that gets quoted.
    total = sum(counts.values())
    out.write(
        f"\n{total} figure(s) checked across {len(chosen)} filing(s):\n"
        f"   {counts['here']} right, at the column's own date and the statement's scale\n"
        f"   {counts['unscaled']} right, but the statement's scale does not apply to them\n"
        f"   {counts['elsewhere']} reported at a different date - read out of the wrong column\n"
        f"   {counts['nowhere']} not in this feed, so not checkable here\n"
    )
    if counts["elsewhere"]:
        out.write(
            "\nA figure read out of the wrong column is B-030, this repository's worst "
            "extraction defect, and it is a failure.\n"
        )
    if counts["unscaled"]:
        out.write(
            "\nA figure that only matches at another scale is one of two things. At a scale "
            "of 1 it is a row the statement's own scale does not apply to - a share count, "
            "a per-share amount - which is not an error here and becomes one downstream, "
            "because three places multiply a figure by its scale. At any other scale the "
            "declared scale is wrong for the whole statement.\n"
        )
    return 0 if every else 1


if __name__ == "__main__":
    raise SystemExit(main())

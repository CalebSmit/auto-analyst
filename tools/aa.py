"""The second front door: what a person can ask for from a command line.

Everything this system does is driven from the dashboard, and that is the right shape for
watching a run. It is the wrong shape for the thing the analyst described wanting: *"when
I get home or when I go to lunch, I just want to point it at the right folders, quickly
tell it what to do, and it starts working"*. That is a command, not a page.

So: four subcommands, and the rule each one is held to is narrower than it first looks.

**A command may be a second surface on a capability. It may not be a second answer.**
`where`, `stage` and `owed` all reach the same `AdminConsole` methods the Setup page
reaches - one implementation, two surfaces, and the page and the command cannot come to
disagree because there is only one of them to disagree with. What is refused is a second
*implementation*: `aa status` is not here because `serve.py --check` and
`watch_run.py --once` already answer those questions, and a third renderer of either would
be two things that could drift. That distinction is this build's B-046 under a new name,
and it is worth stating precisely rather than as "it does something the dashboard does not",
which is not quite true of any of the four.

**`review`** dispatches the three reads by what the thing is. A workbook goes to the
formula audit, a Word or Markdown document to the prose checks, a normalized table to the
reasonableness questions, and a folder to all three over everything in it. One command
over a folder is the difference between a check somebody runs and a check somebody means
to run - and it is the one a slash command can be, because the slash command does not have
to know which check a file wants.

**`where`** prints the folder an engagement's documents go in. Small, and it is the thing
you have to know before you can put anything anywhere.

**`stage`** puts documents in that folder, through `AdminConsole.add_file` - the only
writer, which records who put the file there and why and refuses a path that would land
outside. It exists because of where the documents are: client folders live in Box, and a
**Box connector** reads them into Claude Code rather than into this process. The sanctioned
shape for anything outside the boundary is the one Power Automate was held to - *it talks
through a surface, never through the database or the file system* - and this is that
surface. Read from Box, save locally, `stage` it in, and the sweep finds it exactly as it
finds a file a person dropped there.

**`owed`** reads the engagement's folder against its request list and says what the client
still owes. It is the question that decides whether there is anything to do yet, so it is
the one worth being able to ask without opening anything - and it **writes nothing unless
asked**. Refreshing the tracker is a write into a workbook the analyst keeps notes in, and
a command that did that by default would be a command run once.

Nothing here reformats a finding: each check family renders its own report through its own
`report()`, so the command line and the module agree by construction.

    python -m uv run python tools/aa.py review <file-or-folder>
    python -m uv run python tools/aa.py review <folder> --json
    python -m uv run python tools/aa.py where HEND-2026-04
    python -m uv run python tools/aa.py owed HEND-2026-04
    python -m uv run python tools/aa.py owed HEND-2026-04 --write
    python -m uv run python tools/aa.py stage a.pdf b.xlsx --engagement HEND-2026-04 \
        --who "Caleb" --why "pulled from the client's Box folder"
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # this is run as a script, from wherever somebody is standing
    sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

WORKBOOKS = (".xlsx", ".xlsm")
DOCUMENTS = (".docx", ".md", ".markdown", ".txt", ".rst")
TABLES = (".json",)

# What a folder walk will not look at. A lock file Excel leaves behind while somebody has
# the workbook open is not a workbook, and auditing one produces a traceback rather than a
# finding.
IGNORED = ("~$", ".~")

__all__ = ["Reviewed", "main", "review", "which_read"]


@dataclass(frozen=True)
class Reviewed:
    """One file, the read it got, and what that read found."""

    path: Path
    read: str
    body: dict[str, Any]
    text: str
    worst: str
    """The most serious thing found, in the words of the read that found it: `wrong` from
    the formula audit, `slip` from the prose checks, `fail` from the questions - or an
    empty string when the read found nothing."""

    @property
    def found_something(self) -> bool:
        return bool(self.worst)


def which_read(path: Path) -> str:
    """Which of the three reads a file wants, by its suffix.

    By suffix and not by sniffing the bytes, deliberately. A `.json` that is not a
    normalized table should say so as a refusal naming the file, and a `.xlsx` that does
    not open should be reported by the audit that tried - both of which are more useful
    than this function quietly deciding the file is something else.
    """
    suffix = path.suffix.lower()
    if suffix in WORKBOOKS:
        return "formulas"
    if suffix in DOCUMENTS:
        return "prose"
    if suffix in TABLES:
        return "questions"
    return ""


def _files_under(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    found = [
        p
        for p in sorted(target.rglob("*"))
        if p.is_file()
        and which_read(p)
        and not any(p.name.startswith(mark) for mark in IGNORED)
    ]
    return found


def review(
    target: Path,
    *,
    move: dict[str, float] | None = None,
    years: int | None = None,
    convention: bool = False,
) -> list[Reviewed]:
    """Read whatever is there with whichever read it wants.

    Each read is called through its own module and rendered through its own `report()`,
    so what this prints and what `tools/formula_audit.py` prints for the same file are the
    same text. A file whose read raises is reported as a `Reviewed` carrying the refusal
    rather than ending the walk: one unreadable workbook in a client folder of forty must
    not take the other thirty-nine with it.
    """
    from tools import formula_audit, prose_checks, reasonableness

    out: list[Reviewed] = []
    for path in _files_under(target):
        read = which_read(path)
        try:
            if read == "formulas":
                result = formula_audit.audit(
                    path.read_bytes(), include_convention=convention
                )
                out.append(
                    Reviewed(
                        path=path,
                        read=read,
                        body=result.as_dict(),
                        text=formula_audit.report(result, as_json=False),
                        worst="wrong" if result.wrong else ("suspect" if not result.clean else ""),
                    )
                )
            elif read == "prose":
                paragraphs, skipped = prose_checks.read(path)
                reading = prose_checks.check(paragraphs, skipped=skipped)
                out.append(
                    Reviewed(
                        path=path,
                        read=read,
                        body=reading.as_dict(),
                        text=prose_checks.report(reading, as_json=False),
                        worst=_worst_prose(reading),
                    )
                )
            elif read == "questions":
                findings = _questions(path, move=move, years=years)
                out.append(
                    Reviewed(
                        path=path,
                        read=read,
                        body={"qc_findings": findings},
                        text=reasonableness.report(findings, as_json=False),
                        worst="fail" if any(f["result"] == "fail" for f in findings) else "",
                    )
                )
        except Exception as exc:  # noqa: BLE001 - a file that cannot be read is a finding
            out.append(
                Reviewed(
                    path=path,
                    read=read,
                    body={"could_not_read": str(exc)},
                    text=f"  could not be read: {exc}",
                    worst="unread",
                )
            )
    return out


def _worst_prose(reading: Any) -> str:
    for kind in ("slip", "inconsistent", "tell"):
        if reading.of(kind):
            return kind
    return ""


def _questions(
    path: Path, *, move: dict[str, float] | None, years: int | None
) -> list[dict[str, Any]]:
    from registries.taxonomy import load_taxonomy
    from tools import reasonableness

    payload = json.loads(path.read_text(encoding="utf-8"))
    lines = reasonableness.lines_from(payload)
    return reasonableness.run_questions(
        lines, load_taxonomy("coa-taxonomy@1.0.0"), move=move, years=years
    )


# --------------------------------------------------------------- where, and staging


def _served() -> Any:
    """The same composition root the server uses, with no server started.

    Not a second wiring. `tools/serve.py build()` is where this system is assembled, and
    a command line that assembled its own would be a second answer to "what is configured
    here" - which is how two surfaces come to disagree about which folder an engagement's
    files go in.
    """
    needs("fastapi", "sqlalchemy", "cryptography", script="tools/aa.py")
    from tools.serve import build

    return build()


def _where(served: Any, engagement_id: str) -> dict[str, Any]:
    return dict(served.admin.engagement_files(engagement_id))


def _owed(served: Any, engagement_id: str, *, write: bool) -> dict[str, Any]:
    """What the client still owes, read off the folder against the engagement's list.

    Through `AdminConsole.dd_tracker`, which the Setup page's button also calls - so the
    page and the command cannot disagree about what has arrived. `dry_run` is inverted
    from `write` deliberately: reading is the ordinary thing to want and writing the
    tracker is the exception, which is the opposite of how the page's button is used and
    the right default for something typed at a terminal.
    """
    return dict(served.admin.dd_tracker(engagement_id, dry_run=not write))


def _stage(
    served: Any, engagement_id: str, paths: Sequence[Path], *, who: str, why: str
) -> list[dict[str, Any]]:
    """Each document into the engagement's folder, by name, through the only writer.

    The person and the reason are checked once before anything is written. `add_file`
    checks them too and is the authority, but it checks them per file - so a five-file
    stage with a blank reason would otherwise refuse the first and have written nothing,
    which is the right outcome reached in a way that reads like a bug.

    A file that fails after earlier ones have landed leaves those earlier ones there, on
    purpose. This is a person putting documents in a folder; stopping half way is what
    happens when somebody is interrupted, and the sweep handles a folder that is still
    filling - the quiet period exists for exactly that.
    """
    if not who.strip() or not why.strip():
        raise ValueError("staging a file names a person and gives a reason")
    placed = []
    for path in paths:
        placed.append(
            served.admin.add_file(
                engagement_id, path.name, path.read_bytes(), who=who, reason=why
            )
        )
    return placed


# ------------------------------------------------------------------------------- CLI


def _review_command(args: argparse.Namespace) -> int:
    from tools.reasonableness import _tolerances  # noqa: PLC0415

    try:
        move = _tolerances(args.move or [])
    except ValueError as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2
    if not args.target.exists():
        print(f"  no such file or folder: {args.target}", file=sys.stderr)
        return 2

    results = review(args.target, move=move, years=args.years, convention=args.all)
    if args.as_json:
        print(
            json.dumps(
                {
                    "reviewed": [
                        {
                            "path": str(r.path),
                            "read": r.read,
                            "worst": r.worst,
                            **r.body,
                        }
                        for r in results
                    ]
                },
                indent=2,
                default=str,
            )
        )
    else:
        if not results:
            print(
                f"  nothing under {args.target} that any of the three reads knows what to "
                f"do with. They read {', '.join((*WORKBOOKS, *DOCUMENTS, *TABLES))}."
            )
        for result in results:
            mark = result.worst or "nothing found"
            print(f"\n=== {result.path}  [{result.read}: {mark}] ===")
            print(_printable(result.text))
    return 1 if any(r.found_something for r in results) else 0


def _printable(text: str) -> str:
    """Borrowed from the prose checks rather than written again: a client document has a
    character a Windows console cannot encode in it often enough to matter, and printing
    one is a traceback instead of a report."""
    from tools.prose_checks import printable  # noqa: PLC0415

    return printable(text)


def _where_command(args: argparse.Namespace) -> int:
    served = _served()
    try:
        found = _where(served, args.engagement)
    except (KeyError, ValueError) as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2
    finally:
        served.close()

    print(f"  {found['engagement_id']}  {found['client']}  ({found['state']})")
    print(f"  under the watch: {found['relative']}")
    print(f"  on this machine: {found['absolute'] or 'storage is not a folder here'}")
    print(f"  quiet period:    {found['quiet_period_minutes']} minute(s) after the last change")
    if found["files"]:
        print(f"\n  {len(found['files'])} file(s) there now")
        for item in found["files"]:
            print(f"    {item['path']}  ({item['bytes']:,} bytes, {item['modified']})")
    else:
        print("\n  nothing there yet")
    if not found["can_add"]:
        print("\n  `stage` cannot put files here: storage is not a local folder, or the "
              "engagement is archived")
    return 0


def _owed_command(args: argparse.Namespace) -> int:
    served = _served()
    try:
        found = _owed(served, args.engagement, write=args.write)
    except (KeyError, ValueError) as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - a refusal from the console says why
        print(f"  {exc}", file=sys.stderr)
        return 2
    finally:
        served.close()

    counts = dict(found.get("counts") or {})
    items = list(found.get("items") or [])
    outstanding = [i for i in items if i.get("status") == "outstanding"]
    essential = [i for i in outstanding if i.get("essential")]

    print(f"  {found.get('list')}  ({found.get('origin')})")
    if found.get("is_a_starting_point"):
        print(
            "  This list is a starting point for the scope rather than one somebody wrote "
            "for this client. What the client was actually asked for wins over it."
        )
    print(
        f"  {found.get('files_seen', 0)} file(s) in the folder, "
        + ", ".join(f"{n} {k}" for k, n in sorted(counts.items()) if n)
    )

    if essential:
        print(f"\n  Still owed, and the work waits on it  ({len(essential)})")
        for item in essential:
            print(f"    {item['ref']}  {item['text']}")
    if other := [i for i in outstanding if not i.get("essential")]:
        print(f"\n  Still owed  ({len(other)})")
        for item in other:
            print(f"    {item['ref']}  {item['text']}")
    if not outstanding:
        print("\n  Nothing outstanding on this list.")

    if unmatched := list(found.get("unmatched_files") or []):
        print(f"\n  Answered nothing on the list  ({len(unmatched)})")
        print(
            "    Either a document nobody asked for - which may answer something not on "
            "the list - or one the matching failed on. Both want a look."
        )
        for path in unmatched:
            print(f"    {path}")
    if inferred := int(found.get("inferred") or 0):
        print(
            f"\n  {inferred} item(s) were matched by inference rather than by name. The "
            f"tracker says which; they are the ones to check first."
        )

    if found.get("dry_run"):
        print(f"\n  Nothing written. --write refreshes {found.get('tracker')}.")
    else:
        print(f"\n  Tracker refreshed: {found.get('tracker')}")
        print("  Anything a person had written in it was read back in and kept.")
    return 1 if essential else 0


def _stage_command(args: argparse.Namespace) -> int:
    missing = [p for p in args.files if not p.is_file()]
    if missing:
        for p in missing:
            print(f"  no such file: {p}", file=sys.stderr)
        return 2

    served = _served()
    try:
        placed = _stage(served, args.engagement, args.files, who=args.who, why=args.why)
    except (KeyError, ValueError) as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2
    finally:
        served.close()

    print(f"  {len(placed)} file(s) into {args.engagement}, recorded against {args.who}")
    for item in placed:
        was = " (replacing what was there)" if item["replaced"] else ""
        print(f"    {item['file']}  {item['bytes']:,} bytes  {item['digest'][:19]}...{was}")
    print(
        "\n  The sweep finds them, holds them through the quiet period and fingerprints "
        "them like any other file. Nothing here read them."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aa.py",
        description="What a person can ask for from a command line.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("review", help="read a file or a folder with whichever check it wants")
    c.add_argument("target", type=Path)
    c.add_argument(
        "--move",
        action="append",
        metavar="UNIT=N",
        help="a ratio tolerance for the questions, in its own unit: points, days, x. "
        "No defaults; a unit with none is reported as a question nobody asked.",
    )
    c.add_argument("--years", type=int, help="how many years of history this engagement needs")
    c.add_argument("--all", action="store_true", help="include the convention findings")
    c.add_argument("--json", action="store_true", dest="as_json")
    c.set_defaults(run=_review_command)

    c = sub.add_parser("where", help="the folder an engagement's documents go in")
    c.add_argument("engagement")
    c.set_defaults(run=_where_command)

    c = sub.add_parser("owed", help="what the client still owes on this engagement")
    c.add_argument("engagement")
    c.add_argument(
        "--write",
        action="store_true",
        help="refresh the tracker workbook beside the folder. Off by default: it is a "
        "write into a file the analyst keeps notes in, and reading is the ordinary ask.",
    )
    c.set_defaults(run=_owed_command)

    c = sub.add_parser("stage", help="put documents in an engagement's watched folder")
    c.add_argument("files", nargs="+", type=Path)
    c.add_argument("--engagement", required=True)
    c.add_argument("--who", required=True, help="who is putting them there; it is recorded")
    c.add_argument("--why", required=True, help="and why; it is recorded too")
    c.set_defaults(run=_stage_command)

    args = parser.parse_args(argv)
    result: int = args.run(args)
    return result


if __name__ == "__main__":  # pragma: no cover - the CLI's own line
    raise SystemExit(main())

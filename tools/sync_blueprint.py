"""Publish the blueprint to the OneDrive viewing copy. The repo copy is the source.

`docs/architecture.html` is the blueprint. It is edited here, diffed here, reviewed in
the commit that changed it, and it is the copy the tests read and the work machine has.

The OneDrive copy is a convenience for opening the design on another device. It is a
mirror, not a source, and this script pushes to it.

It used to be the other way round, and the reason it changed is in AMENDMENTS.md: an
authoritative file living outside the repo meant every blueprint correction was a
two-step operation, and forgetting the first step reverted the second without saying so.

    python tools/sync_blueprint.py            publish the repo copy to the mirror
    python tools/sync_blueprint.py --check    report drift, change nothing
    python tools/sync_blueprint.py --pull     mirror wins - for an edit made over there
    python tools/sync_blueprint.py --force    publish over a mirror that has diverged
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "architecture.html"
MIRROR = Path(
    "c:/Users/smitc/OneDrive/Documents/Chartwell/Automated Analyst/"
    "Chartwell_Automated_Analyst_Architecture.html"
)
# What we last put in the mirror. It is how "the mirror is stale" is told apart from
# "somebody edited the mirror", which are the same bytes-differ situation otherwise.
RECORD = ROOT / "docs" / ".blueprint-mirror"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def published() -> str | None:
    return RECORD.read_text(encoding="utf-8").strip() if RECORD.exists() else None


def remember(value: str) -> None:
    RECORD.write_text(value + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, change nothing")
    parser.add_argument("--pull", action="store_true", help="copy the mirror over the source")
    parser.add_argument("--force", action="store_true", help="publish over a diverged mirror")
    args = parser.parse_args(argv)

    if not SOURCE.exists():
        print(f"no blueprint at {SOURCE.relative_to(ROOT)} - nothing to publish")
        return 1

    source = digest(SOURCE)

    if not MIRROR.exists():
        if not MIRROR.parent.is_dir():
            # The work machine has the repo and no OneDrive. Publishing must not
            # conjure the folder tree there - the repo copy is the one that matters,
            # and having no mirror is a perfectly good state to be in.
            print(f"no mirror location on this machine ({MIRROR.parent}) - nothing to do")
            return 0
        if args.check or args.pull:
            print(f"no mirror at {MIRROR}")
            return 0
        shutil.copy2(SOURCE, MIRROR)
        remember(source)
        print(f"published {source} -> {MIRROR}")
        return 0

    mirror = digest(MIRROR)

    if args.pull:
        if mirror == source:
            print(f"in sync ({source}) - nothing to pull")
            return 0
        shutil.copy2(MIRROR, SOURCE)
        remember(mirror)
        print(f"pulled  {source} -> {mirror}  into docs/architecture.html")
        print("        the repo copy is the source, so commit this with its reason")
        return 0

    if mirror == source:
        remember(source)
        print(f"in sync ({source})")
        return 0

    diverged = published() is not None and mirror != published()
    if diverged and not (args.force or args.check):
        print(f"REFUSED - the mirror has changed since it was last published ({mirror}).")
        print("          Somebody edited the OneDrive copy. Publishing would discard it.")
        print("          --pull to take those edits, or --force to overwrite them.")
        return 1

    if args.check:
        state = "diverged - it was edited" if diverged else "stale"
        print(f"source {source} | mirror {mirror} ({state})")
        return 1

    shutil.copy2(SOURCE, MIRROR)
    remember(source)
    print(f"published {mirror} -> {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

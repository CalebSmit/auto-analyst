"""`python -m evals <skill> | --all | --coverage [--register WHO]` - what `gate eval` runs.

The gate tool itself stays dependency-free and shells out under uv, the way every
phase check does; this is the process that actually imports the harness.
"""

from __future__ import annotations

import argparse
import sys

from evals import EvalHarness, SkillRegistration


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate eval", description=__doc__)
    ap.add_argument("skill", nargs="?")
    ap.add_argument("--all", action="store_true", help="every shipped skill")
    ap.add_argument("--coverage", action="store_true", help="what is and is not covered")
    ap.add_argument("--register", metavar="WHO", help="register the version on a pass")
    args = ap.parse_args(argv)

    harness = EvalHarness()
    if args.coverage:
        print("\n" + harness.coverage().report() + "\n")
        return 0
    skills = list(harness.shipped()) if args.all else ([args.skill] if args.skill else [])
    if not skills:
        print("  name a skill, or pass --all or --coverage")
        return 2
    status = 0
    for skill in skills:
        card = harness.evaluate(skill)
        print("\n" + card.report())
        if not card.passed:
            status = 1
            continue
        if args.register:
            record = SkillRegistration().register(card, approved_by=args.register)
            print(f"  registered {record.key} by {record.approved_by} at {record.registered_at}")
    print()
    return status


if __name__ == "__main__":
    sys.exit(main())

# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-02.*

## Where the build is

- **0 of 28 phases closed**
- Last green checkpoint: **none yet**
- Current phase: **P01 - Project structure and build-state system** (gate: auto)

## The next action

Work P01. Its full definition is in [BUILD/phases/P01.md](phases/P01.md).

> Create the shape the whole project lives in, and the state system that lets any session - here, or Cursor on the work machine - know where the build is without reading a conversation. No domain logic at all.

Tasks:

- [ ] Repo tree matching the blueprint's own repo listing, every directory with an __init__.py and a README saying what belongs there and what does not
- [ ] uv toolchain: pyproject.toml, Python 3.12 pinned, uv.lock committed
- [ ] ruff + pytest + mypy configured in pyproject, no separate config files
- [ ] BUILD/: plan.json as truth, PLAN.md and STATE.md generated, LEDGER.md and AMENDMENTS.md append-only
- [ ] tools/gate.py: status, check, close, checkpoint, amend, ledger, render
- [ ] CLAUDE.md at the repo root carrying the session rules
- [ ] tests/p01 asserting the structure is what the blueprint says it is

Then:

    python tools/gate.py check P01
    python tools/gate.py close P01

## Before you start

1. Read [LEDGER.md](LEDGER.md) if what you are about to try resembles something
   that has been tried before. It records dead ends so they are not re-walked.
2. Read [AMENDMENTS.md](AMENDMENTS.md) if the plan looks wrong. It probably
   changed for a reason, and the reason is there.
3. Never hand-edit PLAN.md or this file. Both are generated.

## Closed so far

*Nothing yet.*


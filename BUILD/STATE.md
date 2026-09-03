# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **6 of 28 phases closed**
- Last green checkpoint: **C2**
- Current phase: **P07 - The assertion suites** (gate: auto)

## The next action

Work P07. Its full definition is in [BUILD/phases/P07.md](phases/P07.md).

> The 25 invariants become tests that run in CI and before every execution, rather than properties of a picture that can be quietly wrong for months.

Tasks:

- [ ] Export the blueprint's node and edge model to graph/architecture.json, checked into the repo
- [ ] architecture_assertions.py over that graph - the CI suite
- [ ] plan_assertions.py over a compiled plan - runs before every execute
- [ ] All 25 invariants expressed, including invariant 23 as a real graph walk and invariant 24 as reachability
- [ ] Wire both suites into gate check

Then:

    python tools/gate.py check P07
    python tools/gate.py close P07

## Before you start

1. Read [LEDGER.md](LEDGER.md) if what you are about to try resembles something
   that has been tried before. It records dead ends so they are not re-walked.
2. Read [AMENDMENTS.md](AMENDMENTS.md) if the plan looks wrong. It probably
   changed for a reason, and the reason is there.
3. Never hand-edit PLAN.md or this file. Both are generated.

## Closed so far

- **P01** Project structure and build-state system (2026-09-02)
- **P02** Contracts and registries (2026-09-02)
- **P03** Ports and adapters, with one conformance suite (2026-09-02)
- **P04** Event bus, run store, manifest (2026-09-02)
- **P05** Scope resolver (2026-09-03)
- **P06** Graph compiler (2026-09-03)


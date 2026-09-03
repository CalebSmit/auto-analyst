# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-02.*

## Where the build is

- **3 of 28 phases closed**
- Last green checkpoint: **C1**
- Current phase: **P04 - Event bus, run store, manifest** (gate: auto)

## The next action

Work P04. Its full definition is in [BUILD/phases/P04.md](phases/P04.md).

> The record. Every guard writes to it, passes included, so silence is never ambiguous - and the manifest is written unconditionally, including when a run halts.

Tasks:

- [ ] SQLAlchemy models: run, step, event, artifact, review_item, decision
- [ ] A repository port over the store, so SQLite and Postgres are one URL apart
- [ ] Append-only event bus - no update path exists in the API at all
- [ ] Manifest writer wired to run end regardless of outcome
- [ ] The seven run states: queued, running, waiting, quarantined, halted, delivered, superseded

Then:

    python tools/gate.py check P04
    python tools/gate.py close P04

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


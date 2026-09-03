# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **8 of 28 phases closed**
- Last green checkpoint: **C2**
- Current phase: **P09 - Context builder** (gate: auto)

## The next action

Work P09. Its full definition is in [BUILD/phases/P09.md](phases/P09.md).

> Everything a model is shown is assembled in one place and recorded, so any call can be reconstructed exactly.

Tasks:

- [ ] Assemble skill body, declared references, firm standards, retrieved precedents, engagement_profile and the masked payload
- [ ] Content-hash the assembled whole into context_ref
- [ ] Persist the assembled context against the run
- [ ] Progressive disclosure: reference files loaded only once a skill is selected

Then:

    python tools/gate.py check P09
    python tools/gate.py close P09

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
- **P07** The assertion suites (2026-09-03)
- **P08** Step executor, idempotency, resume (2026-09-03)


# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **13 of 28 phases closed**
- Last green checkpoint: **C4**
- Current phase: **P14 - Loop controller, quarantine, diagnostics** (gate: auto)

## The next action

Work P14. Its full definition is in [BUILD/phases/P14.md](phases/P14.md).

> Failure converges on a person or a record, never on silence - and every loop has a maximum you can read off the plan before the run starts.

Tasks:

- [ ] Bounded loop regions with the four in-run loops: guard repair (2), tie-out repair (1), self-verification (1), conflict resolution (1)
- [ ] The input-must-change rule - a retry with unchanged input is the same call at the same price
- [ ] Quarantine holding full context, with independent branches allowed to finish
- [ ] The diagnostic namespace: code, owner, expected, found, what_now
- [ ] A test that every code in registries/errors.py appears in the blueprint's ERRCODES table, and every code in the table exists in the registry

Then:

    python tools/gate.py check P14
    python tools/gate.py close P14

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
- **P09** Context builder (2026-09-03)
- **P10** Policy gate, constraints, guarded runtime (2026-09-03)
- **P11** LLM port, model pin, budget governor (2026-09-03)
- **P12** Privacy: mask, vault, unmask, verify (2026-09-03)
- **P13** Guards and their adversarial fixtures (2026-09-03)


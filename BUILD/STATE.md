# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **14 of 28 phases closed**
- Last green checkpoint: **C4**
- Current phase: **P15 - Confidence router, review queue, decision log** (gate: auto)

## The next action

Work P15. Its full definition is in [BUILD/phases/P15.md](phases/P15.md).

> Decides what a person sees, item by item, and makes their answer the only thing in the system that can write a precedent.

Tasks:

- [ ] Materiality thresholds and the auto-accept confidence bar, both per engagement
- [ ] Checkpoint policy that may only tighten, never loosen a skill's floor
- [ ] Review queue with an SLA and a named owner per engagement
- [ ] Review surface API and the decision log
- [ ] Optimistic locking so two reviewers cannot silently overwrite each other

Then:

    python tools/gate.py check P15
    python tools/gate.py close P15

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
- **P14** Loop controller, quarantine, diagnostics (2026-09-03)


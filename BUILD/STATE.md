# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **11 of 28 phases closed**
- Last green checkpoint: **C3**
- Current phase: **P12 - Privacy: mask, vault, unmask, verify** (gate: auto)

## The next action

Work P12. Its full definition is in [BUILD/phases/P12.md](phases/P12.md).

> Tokens stable per engagement, re-identification deterministic, and no model node anywhere near the vault. The value here is cross-client isolation and precedent portability, not provider trust.

Tasks:

- [ ] Masker over account names and identifying strings
- [ ] Per-engagement vault with a retention field, the only store that can re-identify anything
- [ ] Deterministic unmask in Python - no model has an unmask tool
- [ ] Unmask integrity check as a separate node from the masker, so the check can be tested independently of the thing it checks

Then:

    python tools/gate.py check P12
    python tools/gate.py close P12

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


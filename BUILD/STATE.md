# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **7 of 28 phases closed**
- Last green checkpoint: **C2**
- Current phase: **P08 - Step executor, idempotency, resume** (gate: auto)

## The next action

Work P08. Its full definition is in [BUILD/phases/P08.md](phases/P08.md).

> A retry, a crash resume and a manual re-run after a fix are the same operation - and only the steps whose inputs actually changed are paid for twice.

Tasks:

- [ ] step_key = sha256(step_id, input content hashes, skill@version, model_pin, context_ref, output_schema_version)
- [ ] The idempotency ledger, written inside the same transaction as the step result
- [ ] Execute at the frontier: completed steps satisfied from the ledger
- [ ] Per-step timeout, one transport retry, then quarantine
- [ ] A blocked run checkpoints and exits - no process, no lock, no context window held

Then:

    python tools/gate.py check P08
    python tools/gate.py close P08

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


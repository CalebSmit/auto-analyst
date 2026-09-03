# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **15 of 28 phases closed**
- Last green checkpoint: **C5**
- Current phase: **P16 - Intake: roster, sweep, binding, lock, window** (gate: auto)

## The next action

Work P16. Its full definition is in [BUILD/phases/P16.md](phases/P16.md).

> What gets looked at, when a run actually starts, and the guarantee that an inactive engagement is unreachable rather than merely unchecked.

Tasks:

- [ ] The roster and its three states: active, paused, archived
- [ ] Sweep planner reading the roster - the only thing that decides what is swept
- [ ] Pattern watches (one row, forty clients) and bound watches, with unmatched folders routed to a person and never guessed
- [ ] Fingerprinting, sha256 source_id, and source_version on re-upload
- [ ] Engagement binding that fails closed before anything is read, and the per-engagement lock
- [ ] Intake window: quiet_period 30 min, required_types from the recipe, max_wait 24 h

Then:

    python tools/gate.py check P16
    python tools/gate.py close P16

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
- **P15** Confidence router, review queue, decision log (2026-09-03)


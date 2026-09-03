# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-02.*

## Where the build is

- **1 of 28 phases closed**
- Last green checkpoint: **none yet**
- Current phase: **P02 - Contracts and registries** (gate: auto)

## The next action

Work P02. Its full definition is in [BUILD/phases/P02.md](phases/P02.md).

> Every shape the system passes around, defined once, versioned, and enforced at the boundary rather than restated per skill. Includes the two configuration-sourced inputs a pre-build review found had no producer.

Tasks:

- [ ] figure.schema.json - the envelope: value, unit, currency, scale, period, source_id, locator, source_version, derivation, masked, confidence, produced_by, model_pin
- [ ] One output schema per skill, referencing the envelope rather than restating it
- [ ] event.schema.json and run_manifest.schema.json
- [ ] engagement_profile.schema.json (finding F1): industry classification, size band, fiscal calendar, scale convention, owner-compensation baseline, disposition
- [ ] participant_census as a declared intake document type
- [ ] constraints.yaml - the predicates the Policy Gate evaluates
- [ ] A registry loader that pins version and refuses an unknown one

Then:

    python tools/gate.py check P02
    python tools/gate.py close P02

## Before you start

1. Read [LEDGER.md](LEDGER.md) if what you are about to try resembles something
   that has been tried before. It records dead ends so they are not re-walked.
2. Read [AMENDMENTS.md](AMENDMENTS.md) if the plan looks wrong. It probably
   changed for a reason, and the reason is there.
3. Never hand-edit PLAN.md or this file. Both are generated.

## Closed so far

- **P01** Project structure and build-state system (2026-09-02)


# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-02.*

## Where the build is

- **4 of 28 phases closed**
- Last green checkpoint: **C1**
- Current phase: **P05 - Scope resolver** (gate: auto)

## The next action

Work P05. Its full definition is in [BUILD/phases/P05.md](phases/P05.md).

> Five-layer resolution, deeper shadows shallower, overlays may only tighten. This is what makes 'an engagement can only see the skills its scope resolves to' true by construction rather than by policy.

Tasks:

- [ ] scopes.yaml - practice groups, segments, dispositions
- [ ] LAYER_ORDER: _firm, <practice>/_group, <practice>/_<disposition>, <practice>/<segment>/_segment, <practice>/<segment>/<disposition>
- [ ] The resolver, returning exactly one skill set per scope path
- [ ] The skill index: name and description only, never a skill body
- [ ] Overlay merge with a tighten-only assertion that raises on a loosening

Then:

    python tools/gate.py check P05
    python tools/gate.py close P05

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


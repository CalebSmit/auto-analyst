# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **9 of 28 phases closed**
- Last green checkpoint: **C3**
- Current phase: **P10 - Policy gate, constraints, guarded runtime** (gate: auto)

## The next action

Work P10. Its full definition is in [BUILD/phases/P10.md](phases/P10.md).

> A wrong action can produce a right-looking result. Verification catches a wrong result; only a decision taken before execution catches a wrong act.

Tasks:

- [ ] ProposedAction and the four allow conditions: declared tool, args satisfy every predicate, engagement matches, estimated cost within remaining budget
- [ ] constraints.yaml predicates evaluated, not interpreted
- [ ] The six-name tool namespace (finding F3): recompute and timing_normalizer compute; chart_of_accounts_lookup, precedent_lookup, index_lookup and template_schema_lookup read
- [ ] Every denial recorded as an event with a code and an owner
- [ ] Call-time caps applied by the runtime, not trusted from the caller

Then:

    python tools/gate.py check P10
    python tools/gate.py close P10

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


# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **5 of 28 phases closed**
- Last green checkpoint: **C1**
- Current phase: **P06 - Graph compiler** (gate: auto)

## The next action

Work P06. Its full definition is in [BUILD/phases/P06.md](phases/P06.md).

> Turn a named job recipe into a typed DAG with a plan hash. Nothing executes that has not been through here.

Tasks:

- [ ] The frozen Step dataclass: id, kind, skill, inputs, output_schema, timeout_s, retries, loop, on_failure, max_turns
- [ ] Named job recipes in YAML, compiled to a DAG
- [ ] Topological ordering and parallel-branch identification
- [ ] Declared loop regions with an integer ceiling; undeclared cycles rejected
- [ ] plan_hash over structure, skill versions, model pins, template version, taxonomy version, schema versions and the precedent-store snapshot id

Then:

    python tools/gate.py check P06
    python tools/gate.py close P06

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


# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-02.*

## Where the build is

- **2 of 28 phases closed**
- Last green checkpoint: **none yet**
- Current phase: **P03 - Ports and adapters, with one conformance suite** (gate: auto)

## The next action

Work P03. Its full definition is in [BUILD/phases/P03.md](phases/P03.md).

> Six interfaces and their local adapters, plus a single suite every adapter must pass. This is what makes adding ShareFile later a class rather than a refactor.

Tasks:

- [ ] Six Protocols under ports/, each with the narrowest surface that works
- [ ] storage: local_folder adapter. delivery: local_folder adapter
- [ ] secrets: dotenv adapter, reading presence never printing value
- [ ] queue: in_process adapter
- [ ] llm: a fake adapter that replays recorded fixtures, so phases 4-10 need no API key
- [ ] One conformance suite, parameterised over every registered adapter
- [ ] An import-boundary test: nothing outside ports/ imports an adapter directly

Then:

    python tools/gate.py check P03
    python tools/gate.py close P03

## Before you start

1. Read [LEDGER.md](LEDGER.md) if what you are about to try resembles something
   that has been tried before. It records dead ends so they are not re-walked.
2. Read [AMENDMENTS.md](AMENDMENTS.md) if the plan looks wrong. It probably
   changed for a reason, and the reason is there.
3. Never hand-edit PLAN.md or this file. Both are generated.

## Closed so far

- **P01** Project structure and build-state system (2026-09-02)
- **P02** Contracts and registries (2026-09-02)


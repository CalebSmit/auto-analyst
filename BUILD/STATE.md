# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **16 of 28 phases closed**
- Last green checkpoint: **C5**
- Current phase: **P17 - Readers and the Source Parse Store** (gate: auto)

## The next action

Work P17. Its full definition is in [BUILD/phases/P17.md](phases/P17.md).

> Turn files into an addressable parse that provenance and tie-out can read from - the store finding F2 showed nothing owned.

Tasks:

- [ ] pypdf and python-docx extraction, attaching source_id and a page/table/row locator to every emitted item
- [ ] Workbook reader: structural read of names and headers, one model call selects sheets with reasons, deterministic code normalizes only those
- [ ] Document classifier and the period/scale detector, with an explicit ambiguous flag rather than an assumption
- [ ] The untrusted content boundary
- [ ] The Source Parse Store keyed (run_id, source_id, locator), written once by the readers and never updated, plus its locator resolver

Then:

    python tools/gate.py check P17
    python tools/gate.py close P17

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
- **P16** Intake: roster, sweep, binding, lock, window (2026-09-03)


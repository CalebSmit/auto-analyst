# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **17 of 28 phases closed**
- Last green checkpoint: **C5**
- Current phase: **P18 - First real skill: timing normalization** (gate: human)

## The next action

Work P18. Its full definition is in [BUILD/phases/P18.md](phases/P18.md).

> The first real skill, chosen first because its arithmetic is entirely deterministic: the model proposes an alignment and the tool does every calculation.

Tasks:

- [ ] SKILL.md with frontmatter, procedure, when-to-use, when-not-to-use, escalation
- [ ] Reference files: period-conventions.md, line-item-matching.md
- [ ] The alignment proposal schema - a mapping, never a number
- [ ] t_timing executing the mapping; all arithmetic in the tool
- [ ] Golden fixtures plus the alignment-report fixture set

Then:

    python tools/gate.py check P18
    python tools/gate.py close P18  --signoff "name: what you checked"

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
- **P17** Readers and the Source Parse Store (2026-09-03)


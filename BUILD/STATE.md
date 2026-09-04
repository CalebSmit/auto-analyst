# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **22 of 28 phases closed**
- Last green checkpoint: **C7**
- Current phase: **P23 - Ops console, scorecard, drift, stalls** (gate: auto)

## The next action

Work P23. Its full definition is in [BUILD/phases/P23.md](phases/P23.md).

> Every run ends with a computed verdict against versioned criteria, so no run's outcome is a matter of opinion.

Tasks:

- [ ] FastAPI plus SSE over the event bus
- [ ] The run scorecard: coverage, provenance, tie-out, conflicts, masking, numeric integrity, budget, review outstanding, deliverable QC
- [ ] Versioned acceptance criteria, so 'what counted as working' is answerable for a run six months old
- [ ] Drift monitor over override rate, confidence distribution and guard failure rate
- [ ] Stall detection against the review SLA

Then:

    python tools/gate.py check P23
    python tools/gate.py close P23

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
- **P18** First real skill: timing normalization (2026-09-03) - Caleb: reviewed the synthetic annual_drift alignment (rename, split, merge, one unmatched line) - calls I would have made; good for testing. Real-engagement confirmation and tailoring to my work's Excel models deferred to the P24 pilot.
- **P19** Line-item tagging and the precedent store (2026-09-03) - Caleb: reviewed the 17 category disagreements and 3 flag departures in fixtures/skills/line-item-tagging/disagreements.md - those are the calls I would make. Taxonomy defaults and the authored gold set stand for testing; Chartwell's conventions and the two-analyst baseline deferred to the P24 pilot.
- **P20** EBITDA normalization (2026-09-03) - Caleb: reviewed the Henderson add-back schedule - officer pay tested against the benchmark and always reviewed, related-party rent held for the market-rent fact, settlement and Q3 project as non-recurring with repairs refused as recurring, vehicle and charitable as discretionary, and the verifier sending the Q3 project to review. Those are the calls I would make; nothing material auto-accepted. Real-engagement add-backs deferred to the P24 pilot.
- **P21** Model builder, template registry, release (2026-09-03)
- **P22** Eval and replay harnesses (2026-09-03)


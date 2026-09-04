# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **19 of 28 phases closed**
- Last green checkpoint: **C6**
- Current phase: **P20 - EBITDA normalization** (gate: human)

## The next action

Work P20. Its full definition is in [BUILD/phases/P20.md](phases/P20.md).

> The first skill where a mistake is expensive rather than merely visible - which is why it is high tier, always self-verified, and never auto-accepts anything material.

Tasks:

- [ ] Add-back taxonomy and officer-compensation tests with a cited benchmark
- [ ] recompute called on every proposed amount
- [ ] The self-verification pass as a separate invocation that never sees the first pass's reasoning
- [ ] Materiality routing: above the threshold goes to review regardless of confidence
- [ ] engagement_profile consumed for the owner-compensation baseline (the F1 contract)
- [ ] The self-verification pass as a second procedure and a declared region on the EBITDA step: recipes/monthly-refresh.yaml self_verification:ebitda, harness/procedures VERIFIERS, LOOP.VERIFICATION_PASS
- [ ] Two proposal contracts: skills/ebitda-normalization-proposal@1.0.0 (candidates, no amount) and skills/ebitda-normalization-verification-proposal@1.0.0 (verdicts, no number)

Then:

    python tools/gate.py check P20
    python tools/gate.py close P20  --signoff "name: what you checked"

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


# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-07.*

## Where the build is

- **34 of 36 phases closed**
- Last green checkpoint: **C12**
- Current phase: **P35 - A released run is driven to an ending** (gate: auto)

## The next action

Work P35. Its full definition is in [BUILD/phases/P35.md](phases/P35.md).

> From a file landing in a watched folder to a deliverable in the outbox, with nothing in the path that only exists in a test.

Tasks:

- [ ] A PassRunner that drives one pass of a run through the StepExecutor
- [ ] tools/serve.py starts the worker pool alongside the sweep
- [ ] Delivery on a finished run, and a halted run that says why
- [ ] The C13 integration test: a file in the inbox becomes a workbook in the outbox

Then:

    python tools/gate.py check P35
    python tools/gate.py close P35

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
- **P23** Ops console, scorecard, drift, stalls (2026-09-03)
- **P24** Admin console, preflight, config audit (2026-09-04)
- **P25** Worker pool and the queue port (2026-09-04)
- **P26** Orchestrator agent and triage (2026-09-04) - Caleb: it all looks good
- **P27** The governance chain (2026-09-04)
- **P28** Docker, portability, handoff packet (2026-09-05) - Caleb: podman 6.1.1 here, image built from a clean clone, 1711 passed / 78 skipped inside it. Nothing but .env changes. Work-machine clone still to do.
- **P29** Scope choices in the admin surface (2026-09-05)
- **P30** Registered methodology: cleared once, checked every run (2026-09-06)
- **P31** Methodology per practice group (2026-09-06)
- **P32** The recipe belongs to the engagement (2026-09-07)
- **P33** Registered recipes (2026-09-07)
- **P34** The run executes: the executor meets the dispatcher (2026-09-07)


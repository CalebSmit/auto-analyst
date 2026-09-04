# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-04.*

## Where the build is

- **27 of 28 phases closed**
- Last green checkpoint: **C9**
- Current phase: **P28 - Docker, portability, handoff packet** (gate: human)

## The next action

Work P28. Its full definition is in [BUILD/phases/P28.md](phases/P28.md).

> One image, any host. The portability requirement in its most concrete form - and the packet that makes the move to the work machine boring.

Tasks:

- [ ] Dockerfile and compose: app plus Postgres, one command up
- [ ] The whole suite green inside the container
- [ ] HANDOFF.md: what changes on the work machine and what does not
- [ ] Adapter stubs named for the existing ShareFile and Box connectors, with their port contracts written
- [ ] The work Anthropic key as a .env change and nothing else
- [ ] On the work machine: confirm the timing-normalization alignment on a real engagement's files and tailor the normalized table to the firm's Excel models (deferred from P18 through P25)
- [ ] On the work machine: publish Chartwell's chart-of-accounts conventions as a new taxonomy version (never edit 1.0.0 in place), measure the two-analyst baseline on 200 real line items, rebuild fixtures/skills/line-item-tagging (deferred from P24)
- [ ] On the work machine: have an analyst confirm real-engagement add-backs are defensible and that nothing material was auto-accepted; rebuild fixtures/skills/ebitda-normalization (deferred from P24)
- [ ] On the work machine: read the work model-builder repo, reconcile its named-range binding with tools/write_template.py, register Chartwell's real templates with input schemas under templates/inputs/ (deferred from P24)
- [ ] One command that verifies the whole build and says what it did not run (tools/verify.py)
- [ ] The public-surface snapshot and the regression suite that guards it (tools/surfaces.py, BUILD/surfaces.json, tests/regression)
- [ ] CHANGING.md: the protocol for changing the system after v1
- [ ] A CI workflow that runs the Postgres, Redis and container halves a laptop cannot

Then:

    python tools/gate.py check P28
    python tools/gate.py close P28  --signoff "name: what you checked"

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


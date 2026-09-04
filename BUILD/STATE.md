# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **18 of 28 phases closed**
- Last green checkpoint: **C6**
- Current phase: **P19 - Line-item tagging and the precedent store** (gate: human)

## The next action

Work P19. Its full definition is in [BUILD/phases/P19.md](phases/P19.md).

> The highest-volume skill in the system, and the first one that learns - which is exactly why only a human decision can write to what it learns from.

Tasks:

- [ ] Firm chart-of-accounts taxonomy, versioned
- [ ] The skill: Category, Excluded from A/L, Include in NWC, with confidence and a one-line rationale per item
- [ ] Scope-built precedent retrieval - a repeat client sees its own prior decisions first
- [ ] Write-back gated on a decision id, with no other code path into the store
- [ ] Proposal contract skills/line-item-tagging-proposal@1.0.0: one numeric field (the model's confidence), no figure anywhere; every ref, category and cited precedent in a proposal is verified by the procedure before it becomes output
- [ ] registries/taxonomy.py loads taxonomy/coa-taxonomy@x.y.z.yaml; tools/coa.py and tools/precedent.py are the two gated reads the skill declares

Then:

    python tools/gate.py check P19
    python tools/gate.py close P19  --signoff "name: what you checked"

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


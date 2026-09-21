# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-20.*

## Where the build is

- **86 of 86 phases closed**
- Last green checkpoint: **C53**
- **Every phase is closed and every checkpoint is green.** What is left is on [`OPEN.md`](OPEN.md), and it belongs to a person.

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
- **P07** The assertion suites (2026-09-18)
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
- **P35** A released run is driven to an ending (2026-09-07)
- **P36** Who is asking: identity on both surfaces (2026-09-18)
- **P37** The division focus, and the interview that fills it (2026-09-16)
- **P38** What the research changed (2026-09-16)
- **P39** A citation is checked where it points (2026-09-17)
- **P40** What the second interview changed (2026-09-17)
- **P41** What the third interview changed (2026-09-17)
- **P42** The consoles, easier to use (2026-09-17)
- **P43** Easy to start and use (2026-09-17)
- **P44** The dashboards tell the truth (2026-09-17)
- **P45** Safe to leave open (2026-09-17)
- **P46** The design language, set properly (2026-09-17)
- **P47** Panels that earn their space (2026-09-17)
- **P48** The whole design, painted with one run (2026-09-17)
- **P49** The map, made to work with (2026-09-17)
- **P50** The map, made correct (2026-09-17)
- **P51** The map, drawn like a drawing (2026-09-17)
- **P52** The map, answering what a person asks (2026-09-17)
- **P53** Three silent wrongs (2026-09-17)
- **P54** The interview can finish again (2026-09-17)
- **P55** Built, and wired to nothing (2026-09-17)
- **P56** The register, fillable from what was already said (2026-09-18)
- **P57** Approving a recipe on a machine that has none (2026-09-17)
- **P58** The documented command works, or says why (2026-09-18)
- **P59** The graph owns every loop, in fact (2026-09-18)
- **P60** A quarantine that leaves something behind (2026-09-18)
- **P61** What the admin surface records, and what it offers (2026-09-18)
- **P62** A register that cannot go stale quietly (2026-09-18)
- **P63** An engagement view, and a way to find one client (2026-09-18)
- **P64** An acknowledgement that says what it looked at (2026-09-18)
- **P65** An acknowledgement is a decision, not a default (2026-09-18)
- **P66** Two commands, one answer about the register (2026-09-18)
- **P67** Proved by arithmetic, or seen (2026-09-18)
- **P68** The request list, as the schedule documents arrive against (2026-09-18)
- **P69** Last year's model, rolled forward (2026-09-18)
- **P70** The gate can always say why (2026-09-18)
- **P71** Nothing is built and wired to nothing (2026-09-18)
- **P72** A retry that can happen (2026-09-18)
- **P73** An exception nobody raises (2026-09-18)
- **P74** The scanned page, read locally (2026-09-18)
- **P75** An OCR engine that installs without an administrator (2026-09-19)
- **P76** A real filing, kept as the document that finds things (2026-09-19)
- **P77** The first thing a session reads, made true again (2026-09-19)
- **P78** The packet that meets somebody at work (2026-09-19)
- **P79** Where last year's model is (2026-09-19)
- **P80** Setup, in the analyst's words (2026-09-19)
- **P81** The setup surface, composed rather than assembled (2026-09-19)
- **P82** Nothing a run cannot reach is called built (2026-09-20)
- **P83** A context that says when it will not fit (2026-09-20)
- **P84** The stable prefix, cached (2026-09-20)
- **P85** A comparative statement, read as two columns (2026-09-20)
- **P86** Three kinds of wrong (2026-09-20)


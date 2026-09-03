# Build state

*Generated. This file is the cursor - read it before doing anything else in this repo.*
*Last written 2026-09-03.*

## Where the build is

- **10 of 28 phases closed**
- Last green checkpoint: **C3**
- Current phase: **P11 - LLM port, model pin, budget governor** (gate: auto)

## The next action

Work P11. Its full definition is in [BUILD/phases/P11.md](phases/P11.md).

> One door to a model and one request per step. Per finding F4 this is the Messages API - SKILL.md is a file format we parse, not a framework dependency.

Tasks:

- [ ] Anthropic Messages adapter behind the LLM port
- [ ] A SKILL.md parser: frontmatter, body, reference list - our own, owing nothing to any SDK
- [ ] Model pin including effort; the three tiers (claude-haiku-4-5, claude-sonnet-5, claude-opus-5)
- [ ] max_turns == 1 enforced at the call site, not merely asserted in the plan
- [ ] Outbound payload scan on the one door
- [ ] Token and cost meter, and the four budget ceilings

Then:

    python tools/gate.py check P11
    python tools/gate.py close P11

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


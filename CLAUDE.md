# Automated Analyst — session rules

This project spans many sessions, two machines and two tools. Context ends; the build
must not care. That works only if the repo, not a conversation, holds the state.

## Before anything else

**Read [`BUILD/STATE.md`](BUILD/STATE.md).** It says which phase is current, what is
closed, and the single next action. If it disagrees with what someone told you in
conversation, **STATE.md wins** — it was written by the gate, from what actually passed.

Then, situationally:

- **[`BUILD/LEDGER.md`](BUILD/LEDGER.md)** — read it before attempting anything that
  resembles a retry. It records what was tried and why it failed, so a dead end is walked
  once.
- **[`BUILD/AMENDMENTS.md`](BUILD/AMENDMENTS.md)** — read it when the plan looks wrong.
  It probably changed for a reason, and the reason is there.
- **[`BUILD/phases/PNN.md`](BUILD/phases/)** — the current phase in full: tasks, exit
  criteria, verification.

## The rules

1. **Never hand-edit `BUILD/PLAN.md` or `BUILD/STATE.md`.** Both are generated from
   `BUILD/plan.json`. A hand edit is how a plan and its real state start to disagree.
2. **Never mark a phase done without `gate close`.** The gate runs the checks first and
   writes nothing if they fail. "It works on my machine" is not a state transition.
3. **Change the plan with `gate amend`, never by editing JSON.** The reason gets recorded
   with the change; a silent edit loses the only part that was worth keeping.
4. **Record dead ends with `gate ledger`** the moment you abandon an approach — not later,
   when the reason has faded into "it didn't work".
5. **End every session by updating STATE.md** — `gate render` at minimum. Especially
   mid-phase, because that is exactly when the next session has least to go on.
6. **A red checkpoint blocks the next phase.** It means phases that each passed alone
   disagree with each other, which is the whole reason checkpoints exist. Do not work
   around one.

## The gate

```
python tools/gate.py status                 # where the build is, and the next action
python tools/gate.py check P07              # run a phase's exit criteria, change nothing
python tools/gate.py close P07              # check, then mark done only if it passed
python tools/gate.py checkpoint C3          # re-run every prior phase + an integration test
python tools/gate.py amend P18 "reason" --add-task "..."
python tools/gate.py ledger "what was tried" --cause "..." --rule "..."
```

Phases marked `gate: human` need a recorded sign-off as well as green tests:

```
python tools/gate.py close P18 --signoff "Caleb: checked the alignment on HEND-2026-04"
```

That distinction exists so that "tested" never quietly means "it ran without crashing".

## What this project is

An AI analyst pipeline for Chartwell: DDR extraction and tagging, financial statement
normalization, and model building — the mechanical stages of deal work, done under
guarantees strong enough that an analyst can trust the output without redoing it.

The architecture is settled and lives in a single file:

    docs/architecture.html      <- travels with the repo; this is the one that matters
    tools/sync_blueprint.py     <- refreshes it from the OneDrive working copy

118 nodes, 240 edges, 25 executable invariants, 67 failure modes. **When the code and the
blueprint disagree, that is a finding, not a preference** — resolve it explicitly and
record the resolution with `gate amend`.

## Non-negotiables from the blueprint

These are not style preferences. Each one is an invariant with a test behind it.

- **A skill invocation is one model turn.** `max_turns == 1`. If a skill needs a tool
  result, that is another step in the plan — compiled, keyed and visible.
- **The graph owns every loop.** Every cycle is declared with an integer maximum the
  compiler checks. No agent decides for itself whether to try again.
- **A skill proposes; it never acts.** Tools are reached by name through the Guarded Tool
  Runtime, after the Policy Gate authorises the call. Nothing under `skills/` may import
  anything under `tools/`.
- **No model performs re-identification.** `privacy/` is deterministic Python throughout.
- **No Excel, COM, VBA or Power Query anywhere.** openpyxl writes into a copy of a pinned
  template; Excel recalculates when a person opens the file.
- **Bind by named range, never by cell address.** `B44` is not a contract.
- **Only a human decision writes to the Precedent Store.** A system that learns from its
  own unreviewed output drifts, and does it invisibly.
- **Guards are not configurable.** An admin may raise a review requirement, never lower
  one, and never disable a guard that fails closed.
- **Nothing concludes, signs or certifies.** No schema has a field a concluded value
  could be recorded in. The appraiser signs, outside this system.

## Working style here

- Local only through P24. No cloud, no ShareFile, no Box. The ports exist so that stays
  true without costing anything later.
- The fake LLM adapter replays fixtures, so phases 4–10 need no API key and cost nothing.
- Client data never enters the repo. `fixtures/` is masked or synthetic, always.
- Ask rather than assume when a decision would be expensive to reverse — the blueprint
  records nine such decisions that belong to people, not to code.

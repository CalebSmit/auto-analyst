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
- **[`BUILD/OPEN.md`](BUILD/OPEN.md)** — everything waiting on a person: approvals,
  decisions that are not the code's to make, evidence only the work machine can produce,
  and the questions being held. Read it before asking Caleb anything, and before
  assuming something was forgotten. An answered item moves to **Settled** with a date
  rather than being deleted.
- **[`BUILD/phases/PNN.md`](BUILD/phases/)** — the current phase in full: tasks, exit
  criteria, verification.

## The rules

1. **Never hand-edit `BUILD/PLAN.md`, `BUILD/STATE.md` or `BUILD/phases/PNN.md`.** All
   three are generated from `BUILD/plan.json` by `gate render`. A hand edit is how a plan
   and its real state start to disagree.
2. **Never mark a phase done without `gate close`.** The gate runs the checks first and
   writes nothing if they fail. "It works on my machine" is not a state transition.
3. **Change the plan with `gate amend`, never by editing JSON.** The reason gets recorded
   with the change; a silent edit loses the only part that was worth keeping.
4. **Record dead ends with `gate ledger`** the moment you abandon an approach — not later,
   when the reason has faded into "it didn't work".
5. **End every session by running `gate render`** — it rewrites STATE.md and every phase
   file from the plan. Especially mid-phase, because that is exactly when the next session
   has least to go on.
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

## Running it

```
start.cmd                                  # Windows, for a person: sets up what is missing, starts, opens it
python tools/serve.py --check              # what is wired, what is not, what setup still needs
python tools/serve.py                      # admin at /admin, ops console at /, help at /help
python tools/simulate_firm.py              # a generated firm through the real server, no key
python tools/simulate_firm.py --scripted   # the same, with the review loop walked end to end
```

The two rehearsals are the tests the suite cannot be: real process, real HTTP, files
shaped like an accountant's, and (with `--scripted`) a stand-in answering for the model so
runs reach the review queue, get answered, resume and write precedent. Between them they
found twenty-three bugs the suite passed over. Run both after any change that touches
intake, the driver, the guards or the consoles; a line marked FINDING is something to fix.

`serve.py` reads `.env` into the environment on start (the shell wins; `AA_NO_ENV_FILE=1`
opts out, and the rehearsal sets it). Before that fix, only secrets were read from the file.

`readiness()` in `tools/serve.py` derives what is joined by asking the code, so it does not
need updating when a seam is filled - and it is the honest answer to "does this work yet".
[`docs/USING.md`](docs/USING.md) is the guide for the people who use the tool rather than
build it; keep it true, because a test holds it to the setup path it describes.

## The focus, and `/improve-agent`

The build serves **one division first: valuation / non-ESOP** (`focus:` in
`scope/scopes.yaml`). ESOP is parked - kept, tested and resolvable, not where effort goes.
Other divisions arrive later as data: a scope entry, a folder, and topics for the
interview. Pointing the focus elsewhere is that one entry.

`/improve-agent` (Cursor or Claude Code; both wrappers point at
[`interview/PROTOCOL.md`](interview/PROTOCOL.md)) interviews the analyst one question at a
time and, on stop, turns what it learned into changes through the gate. What it learns
lives in `knowledge/`, committed to the private repo so it travels between machines, and
it may hold client data - **nothing identifying leaves it** for a skill, methodology file
or fixture; `python tools/interview.py scan` must print `clean` before a
session ends. Run `python tools/interview.py status` to see where the interview stands and
what the code says the focus division is still missing.

## What this project is

An AI analyst pipeline for Chartwell: DDR extraction and tagging, financial statement
normalization, and model building — the mechanical stages of deal work, done under
guarantees strong enough that an analyst can trust the output without redoing it.

The architecture is settled and lives in a single file:

    docs/architecture.html      <- the source of truth. Edit it here, commit the change
    tools/sync_blueprint.py     <- publishes a read-only mirror to OneDrive for viewing

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
- Client data enters the repo only under `knowledge/`, and only because the repo is private
  (decided 2026-09-16). `fixtures/` is masked or synthetic, always.
- Ask rather than assume when a decision would be expensive to reverse — the blueprint
  records nine such decisions that belong to people, not to code.

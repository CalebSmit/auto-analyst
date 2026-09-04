# Automated Analyst

An AI analyst pipeline for Chartwell: DDR extraction and tagging, financial statement
normalization, and model building — the mechanical stages of deal work, done under
guarantees strong enough that an analyst can trust the output instead of quietly redoing
the work.

## Start here

```
python tools/gate.py status
```

That prints which phase is current, what is closed, and the single next action. The build
state lives in the repo, not in anybody's head or in a chat log:

| File | What it is |
|---|---|
| [`BUILD/STATE.md`](BUILD/STATE.md) | **The cursor.** Read this first, every session. |
| [`BUILD/PLAN.md`](BUILD/PLAN.md) | 28 phases and 10 checkpoints, with what is closed. |
| [`BUILD/LEDGER.md`](BUILD/LEDGER.md) | Dead ends, so they are walked once. |
| [`BUILD/AMENDMENTS.md`](BUILD/AMENDMENTS.md) | Every plan change, and why. |
| [`CLAUDE.md`](CLAUDE.md) | The rules a session works under. |
| [`BUILD/OPEN.md`](BUILD/OPEN.md) | What is waiting on a person: approvals, decisions, evidence owed. |
| [`CHANGING.md`](CHANGING.md) | **How to change it without breaking it.** Read before the first edit. |
| [`HANDOFF.md`](HANDOFF.md) | What changes on the work machine, and what does not. |

`PLAN.md` and `STATE.md` are **generated** from `BUILD/plan.json` by `tools/gate.py`.
Never edit them by hand — that is how a plan and its real state start to disagree.

## Verifying a change

```
python tools/verify.py            # everything: surfaces, lint, types, blueprint, state, suite
python tools/verify.py --fast     # the first five, four seconds
python tools/verify.py --repeat 2 # the suite twice, to catch order and timing luck
```

Six layers protect a change. The suite says the code still does what it says; the
checkpoints say the phases still agree with each other; 25 architecture invariants say
the design was not violated; 7 plan assertions say a run is legal before a step executes;
the adversarial fixtures say each guard still fires. The sixth is newer and answers a
different question: [`BUILD/surfaces.json`](BUILD/surfaces.json) records every public
surface - contracts, error codes, tool caps, loop ceilings, review floors, the compiled
plan hash of every recipe - and `tests/regression` fails when one moves. Accepting a move
is a recorded decision, not a re-snapshot. [`CHANGING.md`](CHANGING.md) is the protocol.

`verify` always says what it did **not** run. Postgres, Redis and the container each need
something a given machine may not have, and a green verdict means green on what ran.

## The gate

A phase is closed by the gate or it is not closed. `gate close` runs the phase's checks
first and writes nothing if they fail, so "done" always means "done and tested".

```
python tools/gate.py check P07        # run the exit criteria, change nothing
python tools/gate.py close P07        # check, then mark done only if it passed
python tools/gate.py checkpoint C3    # re-run every prior phase + an integration test
```

Every third phase or so there is a **checkpoint**: it re-runs every phase built so far,
together, plus an integration test of its own. A red checkpoint blocks the next phase —
it means phases that each passed alone no longer agree with each other, which is exactly
the failure that is otherwise found months later.

Phases that turn on judgment rather than on a passing test are marked `gate: human` and
need a recorded sign-off as well:

```
python tools/gate.py close P18 --signoff "Caleb: checked the alignment on HEND-2026-04"
```

## Setup

```
python -m pip install uv          # once, if uv is not on this machine
uv sync                           # creates .venv from uv.lock
cp .env.example .env              # then add your Anthropic key
uv run pytest -q
```

Python 3.12. No API key is needed before phase 11 — the fake LLM adapter replays recorded
fixtures, so the early phases cost nothing to run.

Or in a container, with no host Python at all:

```
podman build -t automated-analyst:0.1.0 .     # docker / nerdctl take the same commands
podman run --rm --env-file .env automated-analyst:0.1.0
podman compose up --build                     # app plus Postgres
```

Nothing here is Docker Desktop's, which is not licensed at the firm and was never a
dependency. [`HANDOFF.md`](HANDOFF.md) is the packet: what changes on the work machine
(`.env`, and nothing else), what the three work repos plug into, and what is still owed.

## The architecture

The design is settled and lives in one self-contained HTML file:

[`docs/architecture.html`](docs/architecture.html) - it travels with the repo, so it is
there on the work machine too, and it is the copy the tests read. Edit it here and commit
the change with whatever prompted it. `python tools/sync_blueprint.py` publishes a copy to
OneDrive for opening on another device; that copy is a mirror, never the source.

118 nodes, 240 edges, 25 invariants that are executable rather than decorative, and 67
failure modes with their controls. Open it in a browser; it needs nothing else.

When the code and the blueprint disagree, that is a **finding**, not a preference.
Resolve it explicitly and record the resolution with `gate amend`.

## Where this is going

Phases 1–24 run entirely on this machine: a watched local folder in, a local folder out,
SQLite, no cloud, no credentials beyond one API key. That is deliberate — the ports exist
so the move to ShareFile intake, Box delivery and the firm's own Anthropic account is a
`.env` change and three adapter classes, not a rewrite.

The handoff packet is [`HANDOFF.md`](HANDOFF.md). Two adapters are registered as port
contracts with no implementation here — ShareFile on storage, Box on delivery — so
selecting one before the firm's connector is wired in refuses with
`SCOPE.ADAPTER_NOT_WIRED` rather than falling back to the local folder. Each module's
docstring is the contract the connector has to satisfy.

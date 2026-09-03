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

`PLAN.md` and `STATE.md` are **generated** from `BUILD/plan.json` by `tools/gate.py`.
Never edit them by hand — that is how a plan and its real state start to disagree.

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

## The architecture

The design is settled and lives in one self-contained HTML file:

```
c:/Users/smitc/OneDrive/Documents/Chartwell/Automated Analyst/Chartwell_Automated_Analyst_Architecture.html
```

118 nodes, 240 edges, 25 invariants that are executable rather than decorative, and 67
failure modes with their controls. Open it in a browser; it needs nothing else.

When the code and the blueprint disagree, that is a **finding**, not a preference.
Resolve it explicitly and record the resolution with `gate amend`.

## Where this is going

Phases 1–24 run entirely on this machine: a watched local folder in, a local folder out,
SQLite, no cloud, no credentials beyond one API key. That is deliberate — the ports exist
so the move to ShareFile intake, Box delivery and the firm's own Anthropic account is a
`.env` change and three adapter classes, not a rewrite.

The handoff packet lands in P28.

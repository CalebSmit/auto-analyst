# Changing this system without breaking it

The build is finished; the changes start now. This is the protocol for making one safely.

The short version:

```
python tools/verify.py            # before you start, so you know it was green
... make the change ...
python tools/verify.py            # after, so you know what you moved
```

Everything below is what to do when that second run is not green.

---

## What protects you, and from what

Five layers, and they catch different things. Knowing which one fired tells you what kind
of mistake you made.

| Layer | Catches | Where |
|---|---|---|
| **The suite** | the code no longer does what it says | `tests/p01` … `tests/p28` |
| **Checkpoints** | phases that each pass alone but disagree with each other | `tests/checkpoints/` |
| **Architecture invariants** | the design was violated, not just the code | `graph/architecture_assertions.py`, 25 of them |
| **Plan assertions** | *this run* is illegal, checked before a step executes | `graph/plan_assertions.py`, 7 of them |
| **The surface snapshot** | something everything else depends on moved, and nobody said so | `BUILD/surfaces.json` |

The first four ask whether the code does what it says. The fifth asks whether **what it
says has changed**, which is a different question and the one that otherwise goes unasked
until a change months later quietly alters what a run means.

---

## The surface snapshot

`BUILD/surfaces.json` records thirteen groups: every pinned contract and a digest of its
schema, every error code and its owner, the tool namespace with its caps, the declared
loops with their ceilings, the scope layers, every skill with the four declarations the
dispatcher enforces, the recipes, the run states and legal transitions, the event
vocabulary, the ports and their adapters, the eval gates, the run criteria, the governance
stages — and the **compiled plan hash of every recipe**.

That last one is load-bearing. A plan hash folds in the graph structure, every skill
version, every model pin, every output contract, the scope resolution, the template
binding, the taxonomy and both registry versions. One line moves if any of those do.

When a change moves a surface, `tests/regression` fails and names it:

```
~ constraints.tools.recompute.caps.max_rows: 50000 -> 200000
~ plans.monthly-refresh.plan_hash: sha256:2897... -> sha256:c41f...
- diagnostics.codes: SKILL.BELOW_GATE
```

**A failure here is not automatically a bug.** It is a change to something other work
depends on. Three questions, in order:

1. **Did I mean to move this?** If not, that is the bug. Fix it and the test goes green.
2. **If I did, what else assumes the old value?** A widened cap, a lowered review floor
   and a renamed code all have readers outside this repo — runbooks, saved queries, the
   analyst's expectations.
3. **Is the reason recorded?** `gate amend` is where it goes, not a commit message that
   nobody will find in a year.

Then, and only then:

```
python tools/surfaces.py --check     # read the diff once more
python tools/gate.py amend P28 "why the cap moved"
python tools/surfaces.py --update    # accept it
```

The snapshot is not the authority on what is correct. The reason recorded beside it is.

---

## Adding things

Each of these has a shape the build already expects. Following it means the safety nets
catch your mistake instead of a client's model doing so.

### A skill

Through the governance chain, not by putting a file in `skills/`. `governance/registry.py`
is the only module in the repo that writes there, and `SkillRegistry.unregistered()`
reports anything that appeared by other means.

```
drop → conformance → bench → sandbox → sandbox test → eval harness
     → replay → submit → board → shadow run → registry
```

Eleven stages, each requiring the evidence of every one before it. The bench can fit a
draft to the contract; it cannot produce the fixtures, because evidence does not come
from the thing being tested. See [`governance/README.md`](governance/README.md).

### A contract

A change to a contract is **a new version beside the old one**, never an edit in place.
The old version stays listed in `contracts/registry.yaml` for as long as any recorded run
cites it. The surface snapshot digests every schema, so an in-place edit shows up as a
changed digest under an unchanged id — which is exactly the mistake this catches.

### A tool

Add it to `constraints/constraints.yaml` with its caps, then to the allowlist of the
skills that may call it. The Policy Gate reads that file, and a skill declaring a tool
the constraints do not have fails the build rather than the run.

### A phase, or a change to the plan

`gate amend`, always. Never edit `BUILD/plan.json`, `PLAN.md`, `STATE.md` or a phase file
by hand: all four are generated, and `verify` fails when they are stale.

### An environment variable

Add it to `.env.example` in the same commit. `tests/p28` derives the list of variables the
code reads from the source and fails on any that is undocumented, so the alternative is a
red suite rather than somebody's lost evening.

---

## When something is genuinely wrong

**Record the dead end.** `gate ledger` the moment an approach is abandoned, not later,
when the reason has faded to "it didn't work".

**A red checkpoint blocks the next phase.** It means phases that each passed alone now
disagree. Do not work around one.

**The blueprint and the code disagreeing is a finding, not a preference.** Resolve it
explicitly and record the resolution.

---

## The commands

```
python tools/verify.py                 # everything: surfaces, lint, types, blueprint, state, suite
python tools/verify.py --fast          # the first five, four seconds, no suite
python tools/verify.py --changed       # only the suites the changed packages cover
python tools/verify.py --repeat 2      # the suite twice: order and timing luck
python tools/verify.py --postgres --redis --container    # the opt-in halves

python tools/surfaces.py --check       # what public surface moved
python tools/gate.py status            # where the build is
python tools/gate.py check P28         # one phase's exit criteria
```

`verify` says what it did **not** run, every time. Postgres, Redis and the container each
need something a given machine may not have, and a green verdict means green on what ran.
That is the same honesty the session summary gives you at the end of every test run, and
it exists because a claim nobody has executed is not evidence.

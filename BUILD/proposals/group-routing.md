# Proposal: routing by practice group

**Status: approved 2026-09-05. Building.**
Raised by Caleb 2026-09-05. Written 2026-09-05.

Label each engagement with its practice group so the orchestrator only ever sees that
group's skills; let each group define its own workflows; give each group a methodology
store for how Chartwell does things.

The shape is right and two thirds of it exists. This is what the rest would take, in the
order I would do it, with what would go wrong if it were done in a different order.

---

## What already does this

| The idea | What does it today |
|---|---|
| A folder belongs to a group | A watch covers a client tree; the roster binds each subfolder to an engagement; the engagement carries a `scope_path`; the Scope Resolver narrows the library to it before anything runs |
| "Do this first, then this" | A recipe: named, versioned, compiled to a typed DAG, checked by seven plan assertions |
| Methodology | `foundations/` - attached to every model call, unconditionally, by the one place context is assembled |

**The label belongs on the engagement, not the folder.** An engagement is what carries a
budget, a profile, an owner, a destination, a template pin, a review level and a lock. A
folder is where files land. Two engagements in one client tree is ordinary, and a label on
the folder would be a second source of truth the day that happens.

---

## The six pieces

Ordered. The order is not arbitrary: **E before D** in particular, because it is the
difference between scanning methodology before it reaches a prompt and scanning it after.

### A. The admin surface offers the scope, rather than taking a typed string

*Small. No dependencies.*

`register_engagement` takes `scope_path="valuation/esop/repeat"` as text today. The scope
registry already declares every practice, segment and disposition, and which are `defined`.

- `AdminConsole.scope_choices()` and `GET /api/admin/scopes`: the tree, with undefined
  groups marked as such.
- Registering into an undefined practice or segment is **allowed but reported**: it
  resolves to the firm layer only, which is correct and nearly useless, and preflight
  should say so rather than let it look like a considered answer.
- The scope path stays the single representation. This adds a way to choose one, not a
  second way to store one.

**Touches** `admin/console.py`, `admin/app.py`, `admin/preflight.py`, `tests/p24`.
**Verification** a new preflight check, and a test that an undefined group is visible in
the report rather than silent.

### B. Naming the segments for Consulting and Corporate Finance

*Data, not code. Blocked on the practice leads.*

`scope/scopes.yaml` marks both `defined: false` with a segment literally called `tbd`.
Until they are named, A is a dropdown with one useful entry.

- The names go in `scopes.yaml`, with skill folders created at those layers.
- Corporate Finance also owes the model it builds into: `CF_LBO_Model_v3` is bound at
  `corporate-finance/_group` with no master file and no input schema.
- This moves a public surface, so: `gate amend` with the reason, then
  `python tools/surfaces.py --update`.

**Touches** `scope/scopes.yaml`, `skills/`, `templates/bindings.yaml`, `BUILD/surfaces.json`.

### C. The recipe belongs to the engagement, not the watch

*Medium. Independent of the others.*

Today `Watch.recipe` decides the workflow, so every engagement under one watch shares one.
That is wrong for per-group workflows unless there is a watch per group, which then makes
the watch do two jobs - where to look, and what to run.

- `RosterEntry.recipe: str = ""`, empty meaning "inherit the watch's".
- `Intake.sweep` prefers the engagement's.
- `AdminConsole.set_recipe(engagement_id, recipe, who, reason)`, logged like every other
  config write.
- Preflight already loads the recipe named by the watch; it would check the engagement's.
- The config document gains a field, so it is **`config_document@1.2.0`** with 1.1.0 left
  listed. A contract change is a new version beside the old one, never an edit.

**Touches** `intake/roster.py`, `intake/__init__.py`, `admin/`, `contracts/`, `tests/p16`,
`tests/p24`.
**Verification** two engagements under one watch running different recipes, and the
existing behaviour unchanged when the engagement names none.

### D. Methodology per group: `foundations/` resolved through the scope layers

*Medium. Do E first.*

`foundations/` is flat and firm-wide: three files, every call, unconditionally. Per-group
methodology means the same five-layer walk the skills already use.

```
foundations/_firm/                    valuation-standards.md, qc-conventions.md, ...
foundations/valuation/_group/         how we do valuation work
foundations/valuation/esop/_segment/  ESOP specifics
foundations/consulting/_group/        ...
```

- The Context Builder attaches the firm layer plus the layers this run resolved to, in
  order, exactly as it already does for skill references.
- The three existing files move to `foundations/_firm/`. No content changes.
- **A size ceiling per layer**, in `constraints.yaml`, reported by preflight. This is
  content on **every** model call: methodology that grows unchecked is a token bill on
  every run and a step closer to the per-run ceiling. A ceiling makes that a decision
  rather than a surprise.
- `BUILD/surfaces.json` gains a `foundations` group - layer, filenames, digest - so a
  change to what every prompt carries is a visible change rather than a quiet one.

**Touches** `harness/context.py`, `foundations/`, `constraints/`, `tools/surfaces.py`,
`admin/preflight.py`, `tests/p09`, `tests/regression`.
**Verification** a valuation run carries firm + valuation methodology, a consulting run
carries firm + consulting, and neither carries the other's.

### E. Methodology is scanned for client data, like a dropped skill is

*Small. High value. Do before D.*

A skill draft dropped into governance is scanned for injection and for anything shaped
like a real client file, and held if it trips. `foundations/` is read straight off disk
into every call, and the outbound payload scan only knows the **current** engagement's
identifiers - so a methodology document quoting a worked example from a real deal would
reach every prompt for every client, and nothing would notice.

**Settled by decision 2 below: cleared once, checked every run.** Not a live scan, which
would let a broad regex take a practice group offline; not a warning, which nobody reads.

- **Registering** a methodology file scans it with `governance.conformance.find_client_data`
  and the untrusted boundary, and records its digest against the name of the person who
  cleared it. Same shape as a skill registration, and the same reason: approval is a
  decision, registration is a deployment.
- **The Context Builder refuses** to attach any file whose digest is not on that list. At
  run time this is a hash lookup, so it is deterministic and cannot false-positive.
- **An edit loses its clearance automatically**, because the digest changes. There is no
  path where a file is cleared, edited, and still attached.
- Preflight reports anything uncleared at setup, so it is caught before a run rather than
  by one.

**Touches** `harness/context.py`, `admin/preflight.py`, a small registry beside
`evals/registration.py`, `tests/p09`, `tests/p24`.

### F. A review path for recipes

*Decision first, then medium.*

A skill passes eleven governed stages before it runs on client work. A recipe is a YAML
file in the repo. If MDs author workflows, that asymmetry is what gets used first - not
maliciously, but because a procedure that could not pass the skill chain can often be
expressed as a recipe that reorders skills to the same effect.

Three options, in order of weight:

1. **Leave it.** Recipes are already compiled and asserted; the risk is accepted, and the
   fact that it was a decision is recorded. Cheapest, and defensible while the only authors
   are you.
2. **Registration only.** `recipes/registered.yaml`, written by the Skill Review Board and
   nothing else, and `load_recipe` refuses an unregistered recipe outside tests. Mirrors
   the skill registry without the ten stages before it. **My recommendation.**
3. **The full chain.** Drop, conformance, board, shadow. Correct and probably heavier than
   the risk warrants for a file that can only reorder already-governed skills.

---

## Order, and what breaks if it is different

```
A ─────────────────────────────► independent, do first, it is small
E ──► D ───────────────────────► scan before methodology can reach a prompt
C ─────────────────────────────► independent
B ──► (makes A useful)          blocked on the practice leads
F ─────────────────────────────► decision, then build
```

Doing **D before E** means methodology reaches production prompts before anything checks
it for client data, and the first check would then be an audit rather than a gate.

Doing **A before B** is fine and worth it: the dropdown works for Valuation immediately,
and shows the other groups as undefined, which is honest and is the prompt for the
conversation.

---

## How this enters the build record

The plan is 28 phases ending at checkpoint C10, and `gate amend` cannot add a phase - the
tool has `--add-task`, `--add-exit`, `--drop-task` and no `--add-phase`, which was correct
while the plan was fixed and is now the thing in the way.

**Proposed:** a new block in `BUILD/plan.json` - Block H, *Practice groups and their
workflows* - with one phase per piece above, and `gate amend --add-phase` added to the
tool so it happens on the record rather than by editing JSON. That is a small change to
`tools/gate.py` and its tests, done first.

The alternative is hanging six tasks on P28, which would be wrong: P28 is the handoff, its
sign-off is about portability, and this work is not that.

---

## Decisions

**Approved by Caleb 2026-09-05**, who delegated the four open questions. Here is what was
decided and why, so that the reasoning outlives the decision.

### 1. The shape — approved as written

Six pieces, in the stated order, with the segments (B) staying a conversation rather than
becoming a phase. **B is deliberately not a phase.** A closed phase renders every task it
lists as done, and naming the Consulting and Corporate Finance segments is owned by the
practice leads with no date. Made a phase, it would either block everything behind it or
close as a lie. It stays in the open register, where an unanswered thing can sit honestly.

### 2. Methodology that looks like client data: neither refuse nor warn

I was offered a choice between failing the run and logging a warning, and both are wrong.

**Warning fails on the timescale that matters.** Methodology reaches *every* call for
*every* engagement in its scope. A leak there is not one bad run, it is systemic and
silent, and a warning in a log is read by nobody for months.

**Refusing on a live scan fails on false positives.** The client-data patterns are
deliberately broad and "err toward flagging" — a made-up example with a dollar amount over
a thousand trips one. For a skill draft that is fine: a person is standing there, at
authoring time, and clears it. For methodology at run time it is a production outage in a
practice group, caused by a regex, at the worst possible moment.

**So: clear it once, check the clearance every time.** Methodology is scanned when it is
registered, by a person who names themselves, and the digest of what they cleared is
recorded. The Context Builder then refuses to attach any file whose digest is not on that
list. That is fail-closed *and* deterministic: at run time it is a hash lookup, so it
cannot false-positive, and an edited file loses its clearance automatically because its
digest changes.

It is also the shape the system already uses for skills: **approval is a decision,
registration is a deployment**, and keeping them separate is what stops "someone approved
this" and "this is running on client work" from being the same moment by accident.

### 3. Recipe governance: registration, option 2

The registry, not the full chain. A recipe can only reorder skills that are already
governed, so eleven stages would be theatre; but "which recipes may run on client work"
has no answer today, and that is the actual gap.

The deciding argument is consistency. **Three things reach a live run: skills, recipes and
methodology. Only skills have a registry.** After decision 2, methodology gets one. Giving
recipes the same minimal shape — a version, a digest, a named approver, written by the
board and nothing else — means one pattern with three consumers rather than three
different answers to one question. `evals/registration.py` is already that pattern's last
link for skills; the other two follow it.

### 4. Block H, and `gate extend`

Yes to both, with one correction to what I proposed. Not `amend --add-phase`: **a separate
`gate extend` subcommand**. `amend` takes the id of a phase that exists and changes it;
adding one is a different act with different required fields, and typing it as a flag on
amend would make the bigger act look like the smaller one.

It enforces three rules. Append only, because inserting before a closed phase renumbers
history and makes "phases close in order" false. The id follows the last, so there are no
gaps and no choosing. And a phase must arrive with a block, an intent, a gate, exit
criteria and checks — a phase with no exit criteria can close on nothing.

The alternative was editing `plan.json` by hand, which is the one thing the rules forbid
outright, and for exactly this reason: it is how a plan and its real state start to
disagree.

---

## The phases

Block H, *Practice groups and their workflows*. In build order, which is also close order.

| | | Piece |
|---|---|---|
| **P29** | Scope choices in the admin surface | A |
| **P30** | Registered methodology: cleared once, checked every run | E |
| **P31** | Methodology per practice group | D |
| **P32** | The recipe belongs to the engagement | C |
| **P33** | Registered recipes | F |

B has no phase, by decision 1. It is in the open register and it is the practice leads'.

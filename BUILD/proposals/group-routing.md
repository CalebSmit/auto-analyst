# Proposal: routing by practice group

**Status: for review. Nothing here is built.**
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

- Reuse `governance.conformance.find_client_data` and the untrusted boundary.
- **Two places, deliberately.** Preflight reports it, so it is caught at setup. The Context
  Builder refuses to attach a file that trips, so a document added afterwards cannot slip
  in. Guards fail closed; a methodology file that looks like client data stops the run.
- The alternative - preflight only - leaves the window between setup and the next check.

**Decision needed:** refusing at run time means one bad paragraph halts every run in that
group until it is fixed. I think that is right, and it is the same bargain every other
guard makes. Say if you would rather it warned.

**Touches** `harness/context.py`, `admin/preflight.py`, `tests/p09`, `tests/p24`.

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

## What I need from you

1. **Approve or redirect the shape.** Six pieces, the order, and the split between what is
   built now and what waits for the MDs.
2. **E: refuse or warn** when methodology looks like it contains client data.
3. **F: which of the three** options for recipe governance.
4. **Whether Block H is the right home**, and whether `gate amend --add-phase` is a change
   you want made to the build tool.

Nothing is built until you say. When you do, each piece gets its own phase, its own exit
criteria and its own gate, the same as every phase before it.

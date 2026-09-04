# harness/

**What belongs here.** What wraps a single step: context.py, policy.py, runtime.py,
loops.py. This is the harness - there is no agent framework underneath it.

**What does not.** No orchestration across steps. That is the graph's job.

## context.py - one place, one hash

Nothing calls a model without going through the Context Builder, so "what exactly was in
context?" is a hash lookup rather than an archaeology exercise. The assembled whole is
content-hashed into `context_ref`, stored in the content store, and the hash goes into the
step's idempotency key. A changed precedent changes the key; a resumed run can never hand
back a result the current context would no longer produce.

**What goes in, in this order, every time.** The skill body. Its references, including the
ones an overlay added. The firm's foundations, unconditionally. Retrieved precedents. The
engagement profile. The masked payload. On a repair pass, the guard's structured failure.
The order is fixed because the hash is an identity.

**Progressive disclosure is enforced, not hoped for.** The tree holds frontmatter for
every skill and the body for none. The builder asks for exactly one body - the step's
own - and exactly the references that skill declares. A test wraps the tree to prove it.
A body loaded for an unselected skill is not waste, it is a leak.

**Precedent retrieval is scope-built.** The query is derived from the engagement's
resolved scope, and there is no field on the request a caller could widen it through. What
comes back is checked: a precedent from another practice group, or one that is not masked,
refuses the whole batch rather than the one item - a source that returned it is broken,
and filtering quietly would leave it broken. For a returning client, that client's own
prior decisions come first.

The Precedent Store itself is P19's. Until then `NoPrecedents` answers every query with
nothing, honestly, and the tests use a source they control.

## policy.py - decided before it runs

A wrong action can produce a right-looking result. Verification catches a wrong result;
only a decision taken before execution catches a wrong act. Reading another engagement's
folder returns perfectly valid data, which is exactly why no guard on the output would
notice.

A proposed action is allowed iff all of: the tool is on the caller's declared allowlist;
the arguments satisfy every predicate in `constraints.yaml` that applies; the engagement
is this run's; the estimated cost is within what remains of the budget. Anything else is a
denial, recorded with a code and an owner. There is no "allow with a warning" - a warning
nobody reads is an allow.

**Predicates are evaluated, not interpreted.** The file states each rule in words and each
rule's `id` binds to a Python function. The words are for a reviewer; the function is what
runs. The gate refuses to construct if a predicate has no evaluator, so a rule cannot be
added to the file and silently never enforced.

## runtime.py - one path, caps from the registry

A skill is constructed with wrapped functions only. `bound()` hands back closures for
exactly the caller's allowlist, each routed through the gate; there is no method that
returns an unwrapped tool, so bypassing the gate is not a configuration mistake anyone can
make.

**Caps are applied here, never trusted from the caller.** The gate refuses a caller who
asks for too many rows; the runtime refuses a tool that returns too many. The per-step call
count is something the caller cannot even see, and it is enforced. **A gated read is
authorised exactly as a write is** - one path, every tool.

The six names are `constraints.yaml`'s: recompute and timing_normalizer compute; the four
lookups read. `t_template` is in no skill's allowlist on purpose - a skill that could write
cells could write one the mapping never declared.

## door.py - the one door to a model

Structurally the only way to reach a model, and a test walks the import graph to prove
nothing else calls `.complete()` on a port. Everything that happens on the way out happens
here, in order: one turn (a request carrying a prior assistant message is turn two of
something and does not leave); the outbound payload scan; the budget governor; the port;
the pin (the model that answered is the model that was pinned); the meter.

`max_turns == 1` is enforced here, not merely asserted in the plan. The compiler refuses a
step that *declares* more than one turn; the door refuses a request that *is* one.

## budget.py - four ceilings, halt not throttle

Token spend, currency spend, active wall clock, total loop iterations - from
`constraints.yaml`, checked before every model call with the call's expected cost added in
and again after. Crossing any one raises, records an event with the code and the owner,
and opens a review item naming the ceiling and the number. A run that quietly degrades to
a cheaper model is much harder to reason about afterwards than one that stops and says
why, so there is no method here that throttles, degrades or extends.

## loops.py - the Bounded Loop Controller

Owns every loop, and the ceiling on each. Four in-run loops run here as declared regions
of a compiled plan (guard repair 2, tie-out repair 1, self-verification 1, conflict
resolution 1). Human clarification is a suspend-and-resume and drift re-review is
human-paced; neither is a region and the controller never sees them.

**Input must change.** The next iteration's step key is computed before it is admitted;
a key already seen in this region is refused with `LOOP.INPUT_UNCHANGED`. A skill that
returns the same figure to the same feedback is stopped after one pass, not after the
ceiling - the same call at the same price is a bug, not a retry.

**Every iteration counts twice.** Against the region's maximum and against the run's
`loop_iterations_max`, read from the event stream - the one `level: loop` event per
admitted iteration is what the Cost Meter counts too, so the governor and the manifest
cannot disagree.

**Exhaustion always produces an artifact.** A quarantine record with the full context
(inputs, every admitted iteration and its key, the guard output, the diagnostic that
stopped it) and a review item carrying both positions. Each names the other.

A repair changes the input to the step - the guard's feedback is appended under its own
name - and nothing else. There is no method here that touches a tolerance, a schema or a
ceiling.

## notice.py - the Fixed Notice

When something fails, a fixed message. A closed set of templates for the moments a
person is told the system stopped: blocked release, unreachable source, missing template,
reference-data miss, quarantined step with partial progress, configuration error. No
model is on the path; nothing is generated, so there is nothing to scan. Templates are
checked at import for display-name placeholders only and for anything that looks like a
node id, a path or a key. A missing value is refused rather than defaulted.

## dispatch.py - one skill, one call, tools by allowlist

The Skill Dispatcher runs one compiled skill step. In order: the procedure's `escalate`
(an ambiguous file never reaches a model); the payload masked by the vault before it is
a blob; the context assembled and hashed by the Context Builder; one request through the
door, with the skill's own SKILL.md and references as the system prompt and the assembled
context between the boundary's sentinels as data; the proposal checked against its
contract before any tool runs; the output produced through the runtime's bound tools and
checked against the output contract. Events from `dispatcher` bracket the call.

## procedures/ - the mechanical half of each skill

The skill tree holds SKILL.md files and no Python (a P10 test), so what the code around a
skill does lives here, one module per skill: what to send (labels and locators, never a
value), what the precedent query should rank by (`terms`, masked by the dispatcher before
the query sees them), how to read the answer, and how to turn it into the output through
the tools. `PROCEDURES` maps skill names to them.

`timing_normalization.py` (P18) sends labels and locators and hands the mapping to the
timing tool, which does every sum. `line_item_tagging.py` (P19) sends the pinned taxonomy
and the descriptions, then checks every claim in the proposal before it is output: each
ref against the input, each category against the taxonomy through the gated
`chart_of_accounts_lookup`, each cited precedent against the store through the gated
`precedent_lookup` - and sets `review_required` from rules a model cannot relax (below
the bar, a departure from the default flags or from a cited precedent, `unmapped`).
`ebitda_normalization.py` (P20) is two procedures. The first pass sends the tagged lines,
the periods and the benchmark's provenance - no value - and gets back candidates; the
amount of each candidate-period is the line's own figure, re-derived through the gated
`recompute` before it is a schedule item, the officer-compensation test runs against the
profile's benchmark and cites it, and `review_required` is forced for anything material,
owner-related, fact-dependent, recurring-yet-called-non-recurring, or untied. The
verification pass (`VERIFIERS`, `verifier_for`) is a separate invocation of the same
skill, admitted as an iteration of the plan's `self_verification:ebitda` region: it sees
amounts, citations and excerpts and never the first pass's rationale, and an unsupported
item goes to a person.

`model_load.py` (P21) sends the pinned template's declared inputs and a catalogue of
figure refs - names, lines, periods, no value - and gets back a routing; every
destination is checked against the template through the gated `template_schema_lookup`,
every ref against the catalogue, and every required input is bound or listed. The Model
Builder (`deliver/builder.py`) resolves the figures and the Template Writer
(`tools/write_template.py`) performs every write.

Nothing under this folder imports `tools/`; a procedure reaches a tool by name through
`BoundTools`, and the P10 boundary test says so.

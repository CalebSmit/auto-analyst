# guards/

**What belongs here.** Assertions about a result, one module each: `schema` (the output
contract, forbidden fields included), `provenance` (every figure cites a document this run
read, at a version it holds, at a locator the parse store has), `tieout` (a derived figure
recomputed from the Source Parse Store rows, never from the stated total), `reconcile`
(two skills that disagree about one item, figure or period), `numeric_lock` (the multiset
of numbers and citations before a transform equals the multiset after). Every one emits
`guard.<name>.pass` as well as `guard.<name>.fail`. The unmask verify sits in `privacy/`,
because it belongs to the side of the boundary that holds real values.

**What does not.** No repair logic - a guard reports; the loop controller decides what
happens next. No tool imports - the tie-out gate takes the recompute engine as a parameter,
and nothing here imports `tools.*`. No resolution - `reconcile` records both positions and
prefers neither.

**Tolerance.** The run sets it; a figure's derivation may tighten it and never loosen it.

**Fixtures.** `fixtures/guards/fixtures.yaml` names the blueprint's ten adversarial cases,
each with the guard it targets and the phase that builds that guard. Six of the ten guards
exist after P13; `tests/p13` runs those and reports the other four at the end of every
session until their phase lands.

## untrusted.py - every document is data, never instructions

The Untrusted Content Boundary, before any model call: NFKC-normalise, strip zero-width
and control characters, scan for instruction patterns, wrap in fixed sentinels. A strong
hit fails closed with `INTAKE.INJECTION_DETECTED` - the run stops, the pattern and its
offset are on the record, the document is quarantined. Weak hits are recorded and the
content goes on, between sentinels a document cannot close from the inside. Every agent
prompt carries `SENTINEL_RULE`, which names the sentinels the wrapper actually emits. The
firm's own foundations pass through here too; firm-authored does not mean safe.

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

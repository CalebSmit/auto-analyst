# scope/

**What belongs here.** scopes.yaml - practice groups, segments and dispositions, and
nothing else.

**What does not.** No skill content. The tree of scopes is separate from what resolves
into it.

## Why it is declarative

Adding a practice group is an entry here plus a folder under `skills/`. Deliberately a
two-line change: the firm will add several, and it must not be a project each time.

Keeping the taxonomy declared rather than implicit in folder names is what lets the
resolver validate against it. An engagement scoped to a group nobody declared fails at
the start of the run instead of silently resolving to an empty skill set - and an empty
skill set reads exactly like "nothing applies", which is the wrong answer wearing a
convincing face.

## The two ladders

`review_ladder` and `sensitivity_ladder` are here because "an overlay may only tighten"
is unenforceable unless tighter is defined. Every value in use carries an integer rank,
so the check is a comparison rather than a guess about spellings.

The practical effect is the point: adding a new `hitl` value forces somebody to place it
on the ladder. Where a review level sits relative to the others is a decision, and it
should have to look like one.

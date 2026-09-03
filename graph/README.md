# graph/

**What belongs here.** The run as data: resolve.py, compile.py, execute.py,
assertions.py. The compiler produces a typed DAG and a plan_hash; nothing executes
uncompiled.

**What does not.** No domain knowledge. The graph does not know what EBITDA is.

## resolve.py - Tier 0

Deterministic Python, no model. A scope path walks five layers and comes back as one
set: the applicable skills, the overlays in force, the template to build into, and the
precedent scope that may be retrieved from.

Two rules carry it.

**Deeper shadows shallower, and only by declaring the same skill.** A layer never
removes what a shallower one gave it, so no run loses a firm skill by being specific.

**An overlay may only tighten.** It may raise a review floor, narrow a privacy class and
take tools away; never the reverse. A loosening raises rather than warns, because a
review floor that was quietly lowered is indistinguishable from one nobody set. If the
looser setting is genuinely right it belongs in the skill at the layer where it is true -
reaching up from a deeper folder to relax a shallower promise means the shallower promise
was never worth anything.

`resolution_hash` is what P06 folds into the plan hash, which is what makes "a run
records the exact skill set it was allowed" a fact rather than an intention.

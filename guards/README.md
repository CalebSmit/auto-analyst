# guards/

**What belongs here.** Assertions about a result: schema, provenance, tieout, reconcile, unmask, numeric_lock. Every one emits on pass as well as on failure.

**What does not.** No repair logic. A guard reports; the loop controller decides what happens next.

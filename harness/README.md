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

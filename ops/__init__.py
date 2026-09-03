"""The record, and the surfaces over it.

`models` is the schema, `run_store` the repository over it, `events` the append-only bus
and `manifest` the writer that closes a run out. Nothing here imports from `graph/`,
`harness/` or `skills/`: the record is written to, never consulted for a decision.

Nothing is re-exported from this module on purpose. `from ops.run_store import
open_store` says which of the four a caller depends on; `from ops import open_store`
does not, and by P10 that difference is the difference between a readable import graph
and a package everything touches.
"""

# precedent/

The Precedent Store and the one node that writes to it.

**What belongs here.** `store.py` - scope-built retrieval over masked, approved tagging
decisions, and the single `admit` entry. `writeback.py` - the step that turns a human
decision into an example.

**What does not.** Any other writer. A learner that learns from its own unreviewed output
drifts, and does it invisibly; the single-writer rule is the whole defence, and it is
enforced three ways rather than asked for.

## Retrieval is scope-built

The Context Builder derives a `PrecedentQuery` from the engagement's `ResolvedScope` - it
is the only place one is built - and the store's WHERE clause is built from that query's
practice. A Corporate Finance decision is never in a Valuation result set, so there is
nothing to filter. `client_first` (a repeat client) puts the client's own prior decisions
ahead of the rest of the scope; `scope_only` (a new client) sees the scope's. Neither
crosses a practice.

Within the scope, rows are ranked by a deterministic lexical similarity to the step's
masked descriptions. The blueprint says embedding index; through P24 the build is local
and keyless, so the ranker is token overlap. It orders rows the scope already admitted
and can be replaced without touching the scope rule.

`precedent_lookup` (`tools/precedent.py`) is the same store reached by a skill's
procedure through the Guarded Tool Runtime. The gate checks the declared scope is the
run's practice before the tool sees the call.

## Exactly one writer, three ways

1. **The API.** `PrecedentStore.admit` is called by `PrecedentWriteback.write` and by
   nothing else; a test walks the tree. `write` starts from a `(run_id, item_id)` and
   reads the decision from the log - it cannot be handed an example to store.
2. **The store.** `admit` re-reads the decision it is handed before it writes: it has to
   exist, to write precedent (accepted or corrected - a rejection teaches nothing to
   copy), and to name a person.
3. **The database.** `precedent` carries a composite foreign key into `decision` and a
   BEFORE INSERT trigger that checks `writes_precedent` and `decided_by` - on SQLite and
   on Postgres. A raw INSERT fails the same way the API does. The table is append-only
   like the log it hangs off.

## Masked before storage

The write-back masks the description and the rationale with the engagement's vault and
runs the Outbound Payload Scan over the result. A description the masker could not
clear is not written (`PRIVACY.UNMASKED_PRECEDENT`) and the item stays un-learned until
it is corrected. That is the blueprint's failure mode 2414, and the reason the store is
shareable across clients at all.

## What the plan hash sees

`snapshot_id()` hashes the set of precedent ids. It goes into `PlanContext`, so two runs
that would see different examples cannot share a plan hash.

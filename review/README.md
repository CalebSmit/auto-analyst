# review/

**What belongs here.** What a person sees, item by item, and the only thing in the system
that can write a precedent: the Checkpoint Policy, the Confidence Router, the Review
Queue, the Analyst Review Surface API and the Decision Log. Deterministic Python over the
run store. No tool, no model.

**What does not.** Anything that decides for a person. The router routes; the queue holds;
the surface records what a named reviewer said. There is no machine path to a decision
row, and the Precedent Store (P19) reads only from decisions.

## policy.py - raise the bar, never lower the floor

Per engagement, from the profile's `checkpoint_policy` block. An owner and an SLA are
required; a materiality threshold may sit at or below the firm floor in
`constraints.yaml`; a per-skill review floor may sit at or above what the skill declares
on the review ladder in `scopes.yaml`. Anything looser is refused with
`POLICY.OVERLAY_LOOSENS`, the same code an overlay would get. There is no auto-accept
default: a policy that sets no bar auto-accepts nothing.

The policy has exactly one reader, the router. A test walks the imports to prove no
guard, harness stage or graph module reads it.

## router.py - the one node that reads the policy

Item-level. Block when the skill's effective level puts its whole output in front of a
person (rank 30 and up); review when the skill marked the item, when it is material,
when it is in an always-review category, differs from the prior year, binds future years,
has no confidence or sits below the bar; auto-accept otherwise - and record the
auto-accept, so the Sampling Audit can draw from what nobody was asked to look at. A
tighter policy routes every item at least as strictly as a looser one; a test runs the
grid.

## queue.py - an inbox of items, not of runs

Each item carries the source excerpt, the proposal, the confidence and the reasons, with
the engagement's owner and a due time from its SLA. `escalate_overdue` records
`PROCESS.REVIEW_SLA_BREACH` against the owner and decides nothing. The queue has no method
that closes an item.

## surface.py - judgment first, one decision, then the run resumes

`show` returns the source and the question; `reveal` returns the proposal and the
confidence and records that it was asked for. `decide` needs a reason on an edit, a
rejection or an escalation, and the corrected value on an edit. It takes the item version
the reviewer saw: a mismatch is refused with the other reviewer's decision attached
(`PROCESS.STALE_DECISION`), at the surface and again at the store. Once nothing on a
waiting run is open, the run goes back to running and a `run.resume` job is submitted;
the executor picks it up at the frontier.

## log.py - append-only

Decisions carry the proposal the reviewer saw, the corrected value if any, the skill,
the reason and the person. The table refuses updates and deletes at the ORM and at the
database, like the event table. The override rate per skill is what the Drift Monitor
reads; `precedent_candidates` - the accepted and corrected decisions, and only those - is
what the Precedent Write-back (`precedent/writeback.py`) sweeps. Nothing else turns a
decision into an example, and nothing turns anything else into one.

# What happened overnight, and what to do first

*2026-09-18. Delete this file once you have read it — everything in it is also in
[`BUILD/OPEN.md`](BUILD/OPEN.md), which is the permanent record.*

## Done for you

Both of the first two steps are done; you do not need to run anything to start.

**The register.** `interview.py scan` now exits 0. `suggest` found four candidates and not
one is a client - Gordon Growth, Managing Director, Claude Code, Secrets Port, all method or
system vocabulary. The acknowledgement records exactly that, so anyone can re-run `suggest`
and check it:

> `# reviewed 2026-09-18 by smitc: reviewed the four candidates suggest found - Gordon
> Growth, Managing Director, Claude Code, Secrets Port - all method or system vocabulary;
> no client, person, place or entity has been named in an interview yet`

It expires the moment you log another session, which is the point.

**The methodology and the recipes were already cleared and approved here - by the test
suite.** Running the suite clears and registers everything as a side effect, under the name
`tests: the repo's own foundations`. Both registers are gitignored, so a clone still starts
clean and the design holds. But it means two things:

- **This machine cannot rehearse the work laptop.** It is unblocked for a reason that will
  not exist there. On the work machine you *will* have to clear the three methodology files
  and approve a recipe, and nothing will have done it for you. The Approve button is on
  Setup, beside where it says a workflow is not approved.
- Clearance is write-once per digest, so it could not be re-recorded under your name. That
  is correct behaviour, not a failure.

So: **run `/improve-agent` whenever you like.** Nothing is in the way.

## What was wrong with the interview, and why

`interview.py scan` is the check `CLAUDE.md` names as the thing keeping a client's name
inside `knowledge/`. **It had never once done that job.**

Until Wednesday night it printed `clean` over an empty register, unconditionally, through
all three of your sessions. P53 made it refuse instead — and I got the refusal wrong: it
counted the committed `knowledge/README.md` as evidence that an interview had happened, so
it fired on clones nobody had ever interviewed. There was no state of the repo in which it
could return 0.

Both defects survived a full green suite, because the tests read the *source* of the
function looking for a string, and called the scan with an empty name list and asserted
that finding nothing in nothing is nothing. Those are gone. Every test now runs the command.

## What else changed

Nine phases, P54–P62, each closed through the gate with its own checkpoint. In the order
they matter to you:

**Things a person meets.** Every command in `docs/USING.md` and `CLAUDE.md` died with
`ModuleNotFoundError` outside an activated shell — the first thing a clone on the work
machine would have hit. The docs now give commands that work, and a tool run without its
environment prints the line to type instead of a traceback. And **nothing could approve a
recipe on a fresh machine**: no route, no button, no command, so a clean clone loaded no
recipe, activated no engagement and started no run, with nothing to click. There is now an
Approve button on Setup that goes through the board and records your name and reason.

**Things that were built and wired to nothing.** The Precedent Store was handed to
everything except the thing that reads it, so every served run assembled context with no
precedent at all — an answer you gave on one engagement was never shown to the model on the
next, which is the whole point of the store. The release path read a field that has never
existed. Every guard failure threw its diagnostic code into a message string, so no guard
failure had ever appeared in the failure breakdown.

**The engine.** `guard_repair`, `tieout_repair`, `self_verification` and
`conflict_resolution` are declared on every recipe with ceilings the compiler checks — and
not one had ever run, because the exception that starts a loop was raised only by a test
double. The guard-triggered half now works. And a quarantined run left *nothing* behind:
no record, no review item, nobody told. `on_failure`, declared on every step of every
recipe, was read by nothing, so `halt`, `review` and `quarantine` all meant the same thing.
All three now differ.

**What using it turned up.** Approving a recipe "succeeded" and wrote no register row -
the register is write-once per digest, correctly - while the board still appended a
REGISTERED entry to the governance chain, so the chain named one person and the register
another. And the guard on `BUILD/OPEN.md` was pinning two commands that had already been
run, so correcting the register broke the test meant to keep it honest, and that test argued
for putting the stale text back. Both fixed; the register guard now asks the plan whether an
item is still live rather than checking for particular sentences.

## Three things I did not decide for you

On [`BUILD/OPEN.md`](BUILD/OPEN.md) §4b:

1. **`self_verification` is declared on a skill that cannot verify.** Every recipe declares
   it on `tagging`; only `ebitda-normalization` has a verifier. Making the runner demand the
   pass quarantines *every run* at tagging — correct, and also everything stopping. Either
   build the tagging verifier through the governance chain, or drop the declaration and move
   the plan hash. A test fails when the gap closes, so whoever closes it is told to finish
   the wiring.
2. **`conflict_resolution` can never be entered** — needs a guard nobody calls and spans two
   steps where the executor re-runs only the head.
3. **P01's done mark still rests on an old verdict.** Two of its checks were running the
   wrong interpreter. P07 and P36 were reopened and re-closed properly; P01 cannot be
   reopened at all — its own structure test uses the first open phase to decide where the
   build is, so reopening it makes every later package look like work running ahead of the
   plan. Its checks are corrected and pass; the caveat is recorded rather than hidden. See
   [`BUILD/LEDGER.md`](BUILD/LEDGER.md).

## State

62 of 62 phases closed, every checkpoint green through C35, both rehearsals reporting
"findings — none", `verify.py` green. Everything is committed and pushed; the repo is still
private.

Your four decisions of this morning are in [`BUILD/OPEN.md`](BUILD/OPEN.md) under Settled.
Three of them are still to build: corrections that amend the run they were made on, the
tagging verifier, and the `run_driver` node in the blueprint.

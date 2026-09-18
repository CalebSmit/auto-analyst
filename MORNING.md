# What happened overnight, and what to do first

*2026-09-18. Delete this file once you have read it — everything in it is also in
[`BUILD/OPEN.md`](BUILD/OPEN.md), which is the permanent record.*

## Start here

```
python -m uv run python tools/interview.py status
```

It now tells you, before the first question, whether the session will be able to close.

Then run `/improve-agent`. The one thing that needs you is the identifier register, and it
is a minute's work rather than an act of recall:

```
python -m uv run python tools/interview.py suggest
```

reads the answers already in `knowledge/` and proposes anything shaped like a name, with
where it appeared. Add the real ones with `register "Name"`. **On this repo it proposes
four candidates and not one of them is a client** — "Gordon Growth", "Managing Director",
"Claude Code", "Secrets Port". Your three sessions were about how the work is done, not
whose work it was, so there has been nothing to register.

That is a legitimate state and the scan now has a way to say so:

```
python -m uv run python tools/interview.py register --none "no client has been named yet"
```

It records that **you** looked, under your name and today's date, and it stops counting the
moment another session is logged. I did not run it for you: it records that a person
checked, and I am not a person who can have checked.

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

Seven phases, P54–P60, each closed through the gate with its own checkpoint. In the order
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

60 of 60 phases closed, every checkpoint green, both rehearsals reporting "findings — none",
`verify.py` green on all six checks. Everything is committed and pushed; the repo is still
private.

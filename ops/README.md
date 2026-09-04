# ops/

**What belongs here.** The record and the surfaces over it: models.py, events.py,
run_store.py, manifest.py, cost.py, scorecard.py (with criteria/), stall.py, drift.py,
analytics.py, console/.

**What does not.** No business logic. If the console computes something, the scorecard
should own it.

## The verdict is computed, not claimed (P23)

`scorecard.py` scores every run against `criteria/run_criteria@<version>.yaml` - the
blueprint's ten rows as data, never edited in place - and the manifest (now
`run_manifest@1.1.0`) records the verdict, the criteria version and every measurement.
Five verdicts: `pass`, `pass_with_exceptions`, `halted`, `blocked`, `partial`.

Two rules carry the weight. **Silence is never a pass**: a criterion the record cannot
measure is `not_measured`, which keeps the verdict off `pass`. **The claim is checked**:
`close_out` asks the scorecard to score the run as ending the way the caller says before
it ends the run, and `PROCESS.OUTCOME_CONTRADICTED` refuses a pair the record does not
support - `clean` has to be earned, a run a guard refused is `halted` not `blocked`.
`close_out` itself still has no branch on state or outcome; the check lives in
`RunScorecard.check_claim`.

## Readers of the record

`stall.py`, `drift.py`, `analytics.py` and `console/` read the store and the bus and
hold nothing a run needs. The console's trace (`console/trace.py`) is one reducer over
the event stream - live and replay are the same fold - and node state comes from the
event's *type*, never its level. The stall detector raises `alert.*` events once per
episode with a diagnostic code and an owner; it decides nothing about the run. The
drift monitor flags a sustained move per skill and per scope and writes nothing; the
governance chain (P27) opens the re-review.

## Three rules, and where each one is actually enforced

**The event table is append-only.** Not by discipline — by the API (nothing on the bus or
the store can change an event), by an ORM flush guard (a diagnostic, in the same words on
both backends), and by `BEFORE UPDATE` / `BEFORE DELETE` triggers on SQLite and Postgres.
The last one is the only version that is still true when somebody opens a psql prompt.
Correct the record by emitting a further event; a trace that can be edited is not
evidence of anything.

**A run ends exactly one way.** `SqlRunStore.transition` refuses a terminal target and
points at `end_run`; `end_run` is what `manifest.close_out` wraps. So there is one door
out of a run and a manifest is behind it — including for a halted run, which is the one
somebody will actually ask about. `close_out` contains no conditional that mentions the
state or the outcome, and a test enforces that, because "written unconditionally" is
easy to say and easy to lose to a well-meaning `if`.

**Only a person closes a review item.** There is no `resolve()` on `ReviewItem`. The only
thing that moves one to `decided` is a `Decision`, and a `Decision` cannot exist without
a `decided_by`. Every guarantee about the Precedent Store rests on that column.

## SQLite and Postgres

One URL apart, by `AA_DB_URL`. SQLite locally through P24; the repository port is what
keeps that from costing anything later.

The claim is only worth what the tests check, so the conformance suite is parameterised
over both backends. SQLite always runs. Postgres runs under `pytest --postgres`, and when
it does not, the session says so in words with a count — a skip nobody reads is the same
as no test. Asking for `--postgres` with no server reachable is a **red run**, not a
skipped one.

Two things exist only to stop the backends quietly disagreeing: foreign keys are turned
on for SQLite (they ship off), and timestamps are stored as RFC 3339 UTC text rather than
as datetimes, so a manifest is byte-identical whichever database produced it.

### Running the Postgres half

    python tools/postgres.py start
    python -m uv run pytest tests/p04 -q --postgres

    python tools/postgres.py check     # both of the above, in one

No container and no Windows service. The server is the portable PostgreSQL binaries
extracted into `%LOCALAPPDATA%\pgsql17`, with its data directory beside them - it starts
when asked, needs no admin rights, does not survive a reboot, and deletes with one
`rmdir`. `python tools/postgres.py stop` when you are done with it.

It holds nothing but fixtures: every table is dropped and recreated around each test, and
client data never enters this repo in any form.

Setting one up from scratch, or on the work machine, is four commands - download
`postgresql-<version>-windows-x64-binaries.zip` from EnterpriseDB, extract it to
`%LOCALAPPDATA%\pgsql17`, `initdb -D <that>\data -U postgres --pwfile=... -A
scram-sha-256`, then `createdb -U postgres analyst_test`. Not through winget: see
BUILD/LEDGER.md. `AA_PG_HOME` points the helper somewhere else, and `AA_TEST_PG_URL`
points the suite at an entirely different server.

## The ledger, and why one transaction

`commit_step` writes the ledger row and the step result together. The alternative has a
window in it: ledger first, and a resumed run believes a step finished that has no result;
step first, and it re-executes work already paid for. Both are silent.

A step key is the primary key, so a second write for one is refused by the database rather
than by a check somebody has to remember. That is what makes a retry, a crash resume and a
manual re-run the same operation.

**One door.** `finish_step` handles the endings that produce nothing - failed,
quarantined, skipped, not reached. It refuses `COMPLETED`, because a step that could claim
completion without a result would be one the resume frontier re-executes anyway while the
run looked finished.

## blobs.py - refs, never values

Content-addressed storage for step results. The address *is* the hash of the content, so
the store is write-once by construction and there is no update operation, because there is
nothing an update could mean. The hash is checked on read: content addressing is only a
guarantee if it is verified on the way out.

Not the Storage Port. That one is the read side of client intake - `list`, `read`, `stat`
over documents somebody sent us. This is the system's own intermediate results, addressed
by content rather than by path.

## The clock that stops

`active_seconds` is what a run is accountable for, and it stops while a person is
thinking. A run waiting on a reviewer holds no process, no lock and no context window, so
it burns no budget either - otherwise the ceiling measures how quickly people answer email
rather than how long the work takes.

## Guard passes are events

`emit_guard` takes a result, not just a failure, and requires a `checked` count. The
manifest's `guard_events` is assembled from exactly this stream, so a pass that was never
emitted cannot appear in the record — and a guard that stopped running shows up as
silence somebody can see, rather than as a clean report.

## cost.py - the meter

Derived, never estimated. The API returns token counts with each response; the meter
prices them against `RATES_USD_PER_MTOK` in `ports/llm` and writes the charge to the run.
It agrees with the usage the API reports because it has no other input to disagree with.
`spend()` is what the governor reads, and it reads loop iterations off the event stream so
the governor and the manifest cannot disagree.

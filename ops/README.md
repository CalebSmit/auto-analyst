# ops/

**What belongs here.** The record and the surfaces over it: models.py, events.py,
run_store.py, manifest.py, console/.

**What does not.** No business logic. If the console computes something, the scorecard
should own it.

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

## Guard passes are events

`emit_guard` takes a result, not just a failure, and requires a `checked` count. The
manifest's `guard_events` is assembled from exactly this stream, so a pass that was never
emitted cannot appear in the record — and a guard that stopped running shows up as
silence somebody can see, rather than as a clean report.

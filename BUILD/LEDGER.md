# Ledger — what did not work

*Append-only. Written by `gate ledger`. Read this **before** attempting anything that
resembles a retry.*

The purpose is narrow: a dead end should be walked once. Every entry records what was
tried, why it failed, and the rule that came out of it. Entries are never deleted — an
approach that failed in month one is exactly what someone will re-propose in month four.

Record an entry the moment an approach is abandoned, not later. The reason fades into
"it didn't work" within about a day, and that sentence helps nobody.

```
python tools/gate.py ledger "what was tried" \
    --cause "why it actually failed" \
    --rule  "what to do instead" \
    --phase P13
```

---

## 2026-09-02 — Seeded from the blueprint's own rejected options

Not failures from this build, but decisions already taken with reasons attached. They are
here because each one is a thing somebody will reasonably suggest again.

**Excel add-in, VBA, or COM automation (`xlwings`) to reach the firm's models.**
*Why not:* needs Excel installed and an interactive session on the host. Breaks in a
container, breaks on Linux, breaks in any cloud — a direct contradiction of the
portability constraint the whole architecture is organised around. An add-in also has to
be installed and versioned on every analyst's machine.
*Rule:* openpyxl writes into a copy of a pinned template. Excel recalculates when a person
opens the file, which is the only moment recalculation is needed.

**Power Query as the pipeline's route into the model.**
*Why not:* pull-based, and it lives *inside* the workbook — the pipeline would publish a
source and then wait for somebody to press Refresh. Wrong direction of control, and a
refresh cannot be guarded or audited.
*Rule:* legitimate only as an optional *delivery format* — a flat results table an
analyst's own live model can pull from — which is a different thing from building the
deliverable.

**Binding template inputs by cell address.**
*Why not:* `B44` is not a contract. Somebody inserts a row, every mapping below it shifts
by one, and the deliverable is *plausibly wrong* — which no reviewer catches by eye.
*Rule:* named ranges and Excel Tables only, and registration fails loudly when a required
range is absent.

**Letting a skill retry a guard failure with unchanged input.**
*Why not:* that is not a retry, it is the same call again at the same price.
*Rule:* every loop pass must change something in the input, and the loop controller
enforces it.

**Auto-resolving a cross-skill conflict by preferring the higher confidence score.**
*Why not:* confidence is a model's self-report. A disagreement is information, and
averaging it away destroys the most useful signal the system produces.
*Rule:* conflicts go to a person with both positions and both sources.

---

*Nothing from the build itself yet — P01 has not closed.*

## 2026-09-03 - winget install PostgreSQL.PostgreSQL.17

**Phase:** not phase-specific

**Why it failed:** EnterpriseDB's CDN answers winget's downloader with HTTP 403. The same URL fetched fine with a browser user-agent, so it is agent filtering rather than a network block or a bad package.

**Rule:** Install Postgres on Windows from the portable binaries zip (get.enterprisedb.com/postgresql/postgresql-<v>-windows-x64-binaries.zip) rather than through winget. Extract, initdb, pg_ctl start - no installer, no admin rights, no Windows service, and it deletes with one rmdir. Invoke-WebRequest needs -UseBasicParsing on PowerShell 5.1 or it blocks on the IE first-run prompt.


## 2026-09-04 - Measuring how long a step took, and whether two steps overlapped, with time.monotonic() in the P25 pool tests

**Phase:** P25

**Why it failed:** On Windows under Python 3.12 time.monotonic() is GetTickCount64 and advances every 15.6 ms. Steps shorter than a tick read as zero-length, and intervals that merely touch inside one tick read as overlapping - a two-thread pool measured as four runs at once, and in another run as one. The test passed in isolation by luck of tick alignment and failed in the full suite.

**Rule:** Time anything sub-second with time.perf_counter() (QueryPerformanceCounter, microsecond resolution). And prove concurrency with a barrier the parties must reach together, not with sleeps and clocks - a serial pool times out at the barrier, which is a fact rather than a measurement.


## 2026-09-05 - Chaining 'git commit' after a piped test command with &&

**Phase:** P28

**Why it failed:** The pipeline's exit status is the last command's, not pytest's: 'pytest ... | tail -3' exits 0 even when the suite is red, so the && ran and a failing test was committed. The failure was real - a test that asserted verify exits clean, which is false while the tree is mid-edit and the state check correctly reports stale generated files.

**Rule:** Never chain a state-changing command behind a piped test run. Capture the exit code first (PIPESTATUS, or run the suite unpiped), or run the commit as its own step after reading the result. And a test that shells out to a tool must not assume the working tree is clean - assert on what the report says, not on the exit code alone.


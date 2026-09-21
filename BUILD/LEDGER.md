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


## 2026-09-06 - Running the test suite through the generated pytest.exe console script

**Phase:** P30

**Why it failed:** Windows Application Control refuses to start .venv/Scripts/pytest.exe - a launcher generated at install time, unsigned and unknown to the policy - with 'os error 4551'. Every gate check and every verify run failed on a machine where the suite itself was green, which is the worst kind of failure: the tool saying red about something that is not.

**Rule:** Invoke a Python tool as a module - python -m pytest - not through its generated console script. A managed corporate laptop is more likely to carry that policy than a personal one, so this is the form that travels.


## 2026-09-18 - Reopening P01 with 'gate amend P01 --reopen' to re-close it on a corrected check

**Phase:** not phase-specific

**Why it failed:** tests/p01/test_structure.py::test_no_package_is_built_before_its_phase asks open_phases()[0] where the build is. With P01 open that is P01, so every package built by a later phase reads as work running ahead of the plan - twelve failures - and P01's own checks include that test. It cannot pass while P01 is open, and P01 cannot close until it passes.

**Rule:** P01 is the one phase that cannot be reopened: it defines where the build is for every structural check. Correct its checks with 'gate amend' in place and record why the phase was not re-closed on them. Any other phase reopens cleanly - P07 and P36 both did.


## 2026-09-20 - tests/p23::test_is_it_healthy_what_should_we_fix_is_it_improving_is_anything_stuck failed once inside tools/verify.py at about 00:05 on 2026-09-20, and has not failed since. Tried to reproduce it four ways: the test alone, the test with tests/checkpoints/c50, the whole suite filtered with -k p23, and the whole suite unfiltered. All four green, including the unfiltered one that is the same command verify.py runs.

**Phase:** not phase-specific

**Why it failed:** Not established, and the guesses were checked rather than believed. The ISO-week bucket in Analytics._outcomes was the first suspect because the test unpacks a single week and the run crossed midnight - but 2026-09-19 and 2026-09-20 are both W38, so no bucket could split. The 30-day window is not near a boundary either. What is true and worth knowing: tests/p23/conftest.py's Clock starts at the real wall clock on purpose - 'the store stamps steps and events with wall time, and silence is measured against those stamps' - and ops/run_store stamps ended_at with now_iso(), so this test is time-coupled by construction rather than by accident. A second suspect is tests/checkpoints/c50, which edits guards/__init__.py on disk while the suite runs; it restores in a finally and the tree was observed restoring itself, and no mechanism was found by which p23 could read it.

**Rule:** Do not spend another session reproducing this one by re-running the suite; it has been run four ways. If it recurs, capture the assertion line first - verify.py summarises and drops it, so run pytest directly with --tb=long and keep the output. The two things to check at that point are whether ended_at and the fixture clock disagree across a day boundary, and whether anything in the process reads a production file from disk.


## 2026-09-20 - Checked which diagnostic-code family prefixes were legal by grepping registries/errors.py for them, and read back CLIENT. as precedent for CLIENT.CONTEXT_TOO_LARGE.

**Phase:** not phase-specific

**Why it failed:** The grep was run after the code had already been added, so it returned my own edit. The file was the only evidence consulted and it had been contaminated by the thing it was being asked about. The real list is in docs/architecture.html's ERRCODES table, which is the source of truth, and it names ten families of which CLIENT is not one - so the error was reachable in one place and I looked in another.

**Rule:** When checking a convention before adding to it, read something that existed before the edit: git show HEAD:<file>, or the blueprint, or a test that asserts the rule. A grep of the working tree after an edit proves the edit exists. Two tests catch this particular case - tests/p14::test_every_registry_code_is_in_the_blueprints_table and the diagnostics registry's own self_check - and both are reached only by a checkpoint, not by the phase that adds the code.


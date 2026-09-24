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


## 2026-09-20 - Closed three pinned defects this session (B-030 in P85, B-041 in P86) and each time the phase's own checks and its own checkpoint were green while an earlier checkpoint's integration test was red - C44 for the first, C40 for the second - found only by tools/verify.py.

**Phase:** not phase-specific

**Why it failed:** gate checkpoint re-runs every prior phase and not the integration tests of earlier checkpoints. That is deliberate and right, because re-running every checkpoint from every checkpoint grows with the square of the build. But a test that pins a defect is usually written in a checkpoint rather than in the phase that found it, precisely so that a change to the code meets it - so the tests most likely to fail when a defect is closed are exactly the ones a later checkpoint does not run. mypy is in the same position: it runs in verify.py and in nothing a phase does, and P85 closed with an unannotated local.

**Rule:** Closing a defect that something pins is not finished at gate close or at gate checkpoint. Run tools/verify.py before trusting it, and grep the tests for the backlog id first - a pinned defect usually names its B-number - so the tests that are about to fail are known rather than discovered. The same applies to any phase that adds a gate, empties an allowlist, or changes a diagnostic code.


## 2026-09-21 - Both reachability scans (tests/p71, tests/p82) took a hand-written tuple of shipped packages, and tests/p82 treated a package's own __init__.py as evidence that its submodules were reached.

**Phase:** not phase-specific

**Why it failed:** A new package (report/) was on neither list, so nothing in it was scanned at all; and even once listed, its three modules read as wired because report/__init__.py imports them, while nothing anywhere imports report. A scan whose subject list is hand-maintained goes stale silently, and a package that vouches for itself defeats the check entirely.

**Rule:** Derive the package list from the tree, as tests/p28 already did, and make reachability a fixpoint: an __init__'s imports count as evidence only once the package itself is reached by something outside it. Doing this found three pre-existing defects the old scan could not see - the whole orchestrate package, deliver.workpaper and governance.chain.


## 2026-09-21 - A revert harness that restores a file by rewriting its original text, when the replacement is the same number of bytes.

**Phase:** not phase-specific

**Why it failed:** Python invalidates a cached .pyc on mtime plus size. A one-character-for-one-character revert restored within the same filesystem timestamp leaves both unchanged, so the interpreter keeps serving bytecode compiled from the MODIFIED source. Two P92 tests then failed against a file that was correct on disk, and the failure survived re-running the suite - which reads as a real defect and is not one.

**Rule:** A revert harness must invalidate bytecode after restoring: bump the file's mtime (os.utime) or delete __pycache__ for the touched package. If a test fails against a file whose contents look right, clear __pycache__ before believing it.


## 2026-09-21 - The report update removed the whole span an anchor owns, including the anchor's own block.

**Phase:** not phase-specific

**Why it failed:** The anchor block is the appendix's heading, and it carries the report's heading style and - when somebody has marked one - the bookmark. Removing it worked exactly once: the first press deleted the heading it had bound to, and every later press refused with BINDING_MISSING because the anchor was no longer in the document. A unit test on a single press could not see it. C55 found it, because pressing twice is the ordinary case - the data gets corrected, or the quarter turns.

**Rule:** Keep the anchor's own block and replace only what is under it. Drop a leading heading from the source when it repeats the anchor name, so a source document that carries its own title does not produce two. And report the number of blocks actually removed rather than the size of the span, because a count one larger than the truth is worse than no count.


## 2026-09-22 - P98's bare-year column detection was written and tested against a hand-made single-line header - '2021  2022  2023' - and shipped green. Run against the real client projections tab it found nothing at all.

**Phase:** not phase-specific

**Why it failed:** Two readers produce the text this module parses and they disagree about what a line is. A document reader puts a header row on one line; survey_workbook collects header cells into a flat list, so the same row arrives as six lines of one heading each. The fix looked only at the line with the most headings, which is the document shape, and no line in the workbook shape had more than one.

**Rule:** When a fix is for a file that is in the folder, drive the test from what the real reader emits for that file, not from a string written by hand to look like it. Here that meant calling survey_workbook on the actual workbook and reading its headers, which takes a minute and would have failed immediately.


## 2026-09-22 - engagement_profile@1.1.0 was created in P106 with its $id bumped and its schema_version const left at engagement_profile@1.0.0, so a profile declaring the new version failed the new version's own check. Fixed in place rather than by cutting a @1.2.0.

**Phase:** not phase-specific

**Why it failed:** The $id was the thing I checked, because the registry checks the $id. The const says the same fact a second time and nothing compared them, so half a version bump passed every test in the build.

**Rule:** When a contract version is cut, every place inside the schema that names its own version moves together - $id and any const or enum on schema_version. A test asserts they agree, because two statements of one fact drift. Fixing @1.1.0 in place is allowed only because it had never been committed and had never validated a document; a version anything cites is fixed by cutting the next one.


## 2026-09-22 - The Input Help template's front page was edited in place rather than cut as @1.1 - the page's text is part of the workbook's bytes, so the pinned template's content hash changed under the same version.

**Phase:** not phase-specific

**Why it failed:** The page described a workbook that stopped existing two phases ago: P108 made every figure carry its full precision and P112 made a missing one say 'not found' in its own cell, and the page still promised two decimals and a blank.

**Rule:** Allowed here only because this template was created in P101, has never been committed, and has never produced a deliverable for a real engagement - the same test the engagement_profile const passed. The moment a real workbook cites a template version, a change to its face is a new version. The real Model Template - MASTER 2026 is still owed and will replace this outright.


## 2026-09-22 - C63 found tests/p80 and tests/p107 contradicting each other: p80 asserted the literal words 'Seven steps, in order.' and P107 added two steps and wrote 'Nine'. Both were green alone. This is the seventh roll-call test (B-066) and the first one a checkpoint caught rather than a person.

**Phase:** not phase-specific

**Why it failed:** The count in the prose is a fact about the checklist on the day it was written, asserted as though it were a rule. Every earlier instance was found by a phase failing to close; this one survived because p80 is not in any later phase's check list, so only a checkpoint that re-runs everything could see it.

**Rule:** A count beside a list is derived from the list, never typed twice. tests/p80 now counts the checklist's entries and looks up the word. B-066 asked for a convention rather than a scan; this is the shape it should take - assert the relationship, not the value.


## 2026-09-22 - C65 found tests/p31 asserting len(CHECKS) == 14 and the blueprint saying 'Fourteen checks' - two copies of one number, and P114's new preflight check made both wrong at once. The ninth roll-call test, and the second one a checkpoint caught rather than a person.

**Phase:** not phase-specific

**Why it failed:** The count was written down twice, in the code's test and in the design of record, and neither derived from the list. CLAUDE.md says code and blueprint disagreeing is a finding; this is the shape that finding takes when the disagreement is a number.

**Rule:** When a test ties prose to code, assert that they agree and derive one from the other - never assert each separately. tests/p31 now reads len(CHECKS) and looks up the word the blueprint should be using.


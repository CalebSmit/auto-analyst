---
description: Put a client's documents into an engagement's watched folder and get the run going, then tell me what it is waiting on
argument-hint: "<engagement id> <folder or files> [why they arrived]"
---

Get documents into the system and started, then tell me where it stopped and why.

## 1. Find out whether this machine can do it at all

```
python -m uv run python tools/serve.py --check
```

Read the answer rather than summarising it. Two things decide whether to go on:

- **`NOT INSTALLED` is software somebody installs.** If OCR is not working and the
  documents include scanned PDFs, say so now - with `AA_OCR_ADAPTER=none` a scan reads as
  nothing, correctly, and the run will report empty pages rather than fill anything in.
- **`NOT WIRED` is a join this build has not made.** Different problem, and not one I can
  fix by trying again.

If the methodology is not cleared, nothing will start. Tell me to clear it at `/admin`
rather than working around it.

## 2. Find the folder

```
python -m uv run python tools/aa.py where <engagement>
```

This prints the path under the watch, the path on this machine, what is there now, and
the quiet period. If the engagement is not on the roster, **stop and tell me** - setting
one up is a decision with a client name, a scope path and a recipe in it, and it belongs
on the Setup page where it is recorded against me.

## 3. Put the documents there

```
python -m uv run python tools/aa.py stage <files...> --engagement <id> \
    --who "Caleb" --why "<where they came from>"
```

`--why` is required and it is recorded, so make it the truth: *"pulled from the client's
Box folder 2026-10-02"*, not *"staged"*.

**If the documents are in Box**, read them with the Box connector first and save them to a
temp folder, then stage from there. That is the sanctioned shape and it is not a
workaround: anything outside this system talks to it through a surface, never through the
database or the file system directly, which is the same line Power Automate was held to.
Do not write into the watched folder yourself - `stage` goes through the one writer that
records who put a file there.

Before staging, tell me what you are about to stage and wait for me to say yes if there
are more than five files or if any of them might not belong to this engagement. A document
in the wrong client's folder is the one mistake here that is expensive to undo.

## 4. Then leave it alone and tell me what happened

The sweep finds the files, holds them through the quiet period, fingerprints them and
releases a run. Nothing needs pressing.

```
python -m uv run python tools/watch_run.py --once
```

Report: which step is going, how long against the bound that step declared, what has been
spent against the ceiling, what is waiting on a person, and anything the stall detector
raised. **Do not loop on this.** Run it once, tell me, and stop - if I want it watched I
will ask, and the dashboard at `/` does it better than you re-reading a file.

If the run has stopped, say which of these it is, because they are different things:

- **waiting on a person** - a review item. Tell me what it is asking.
- **a guard refused** - nothing partial escaped. Name the guard and the diagnostic code.
- **a step with no procedure** - `qc-tieout` and `ddr-tagging` have none. That is the
  system saying what it cannot do, not a failure, and it is on `BUILD/OPEN.md`.
- **the scale was ambiguous** - thousands or units. It escalates before any model sees
  the figures. That is the design and most first runs on real files do it.

## 5. When it has produced something

Run `/review` over the outbox folder. Do not tell me a workbook is fine without having
read its formulas.

Anything I typed after the command: $ARGUMENTS

# intake/

**What belongs here.** What gets looked at, when a run actually starts, and the guarantee
that an inactive engagement is unreachable rather than merely unchecked: the roster, the
configuration store and its change log, the sweep planner, the local intake source,
engagement binding, fingerprinting, the intake window and the engagement lock.
Deterministic Python over the Storage Port and the run store. No model.

**What does not.** Reading a file's contents. Nothing here opens a file before Engagement
Binding has said whose it is, and nothing here parses one at all - the readers are P17's.

## The order a file meets them

1. **roster.py** - three states. *active* is swept and runs start; *paused* is known,
   nothing starts, files accumulate; *archived* is not swept at all, binding kept for the
   record. No delete; no method touches a run. Every state change is a row in the change
   log with who, when and why.
2. **config.py** - one versioned document per environment (`config_document@1.0.0`),
   validated on every write, every changed field logged. Watches (bound or pattern),
   intake timing, filename conventions for document types, per-engagement overrides that
   only tighten. Two watches on one path are refused before anything is swept.
3. **sweep.py** - reads the roster and the watches and produces (location, engagement)
   pairs. A pattern watch maps subfolders to engagements through the roster's `folder`
   binding; a subfolder nobody claims is reported unclaimed and never guessed at.
4. **local.py** - lists what is under a location through the port. Lists only.
5. **bind.py** - the file's path must be under the target's folder and the engagement
   must be active *now*; otherwise `INTAKE.NO_ENGAGEMENT`, before any read. The document
   type comes from the filename conventions; no match, or two matches, means *held*.
6. **fingerprint.py** - sha256 as `source_id`, size, mime, path, `received_at` (the sweep
   that first saw it), and `source_version` per (engagement, filename). Same bytes again
   are not a new version; different bytes under the same name are version 2.
7. **window.py** - quiet (no arrival for `quiet_period`) and complete (the recipe's
   `intake.required_types` present), or past `max_wait` with a recorded coverage gap and a
   review item. Releases exactly one run over the whole current set, never a delta.
8. **lock.py** - one run per engagement. The lock is a primary key; the second insert
   fails and joins a visible queue. Release hands the lock to the next in line. A lock
   held past its timeout is an incident (`PROCESS.RUN_STALLED`), never cleared here.

`launch.py` is the release: register the run, take the lock or queue, record every
source and every gap, mark the files consumed, and mark any earlier run that consumed an
older version of a file as superseded by this one - its manifest retained, never
overwritten.

**Invariant 24** is proven twice in `tests/p16`: by a walk of the blueprint graph, and by
sweeping a folder tree where the off-roster engagements' files are never listed, never
stat'd, never read and start no run.

## readers/ - from files to an addressable parse

`documents.py` (pypdf, python-docx) and `workbook.py` (openpyxl) write blocks to the
Source Parse Store: one table of a document under `p{page}/t{table}`, one numeric column
of a sheet under `Sheet!C{first}:C{last}` with the sheet row as each row's ordinal. The
store's resolver answers any locator inside a block - `TB_FY25!B44:B47`, `p14/t2/r7` -
through one interface, so provenance, tie-out and the numeric lock never know which kind
of file a figure came from. Hidden text (under 4pt) is surfaced apart, not dropped.

The workbook reader surveys structure, lets a selector choose sheets *with reasons*, and
normalises only those; `Selection.accounting_for` makes every sheet either selected or
skipped with a reason, whatever the selector forgot. `ModelSheetSelector` is the one model
call, over the survey wrapped as data - the cells never enter it.

`classify.py` is a closed set with "other" first-class: "other" opens a review item.
`periods.py` decides scale, currency, period type and year end from cues it can read,
or names each one it cannot in `ambiguous`. Thousands versus units is never assumed.

# Automated Analyst — session rules

This project spans many sessions, two machines and two tools. Context ends; the build
must not care. That works only if the repo, not a conversation, holds the state.

## Before anything else

**Read [`BUILD/STATE.md`](BUILD/STATE.md).** It says which phase is current, what is
closed, and the single next action. If it disagrees with what someone told you in
conversation, **STATE.md wins** — it was written by the gate, from what actually passed.

Then, situationally:

- **[`BUILD/LEDGER.md`](BUILD/LEDGER.md)** — read it before attempting anything that
  resembles a retry. It records what was tried and why it failed, so a dead end is walked
  once.
- **[`BUILD/AMENDMENTS.md`](BUILD/AMENDMENTS.md)** — read it when the plan looks wrong.
  It probably changed for a reason, and the reason is there.
- **[`BUILD/OPEN.md`](BUILD/OPEN.md)** — everything waiting on a person: approvals,
  decisions that are not the code's to make, evidence only the work machine can produce,
  and the questions being held. Read it before asking Caleb anything, and before
  assuming something was forgotten. An answered item moves to **Settled** with a date
  rather than being deleted.
- **[`BUILD/phases/PNN.md`](BUILD/phases/)** — the current phase in full: tasks, exit
  criteria, verification.

## The rules

1. **Never hand-edit `BUILD/PLAN.md`, `BUILD/STATE.md` or `BUILD/phases/PNN.md`.** All
   three are generated from `BUILD/plan.json` by `gate render`. A hand edit is how a plan
   and its real state start to disagree.
2. **Never mark a phase done without `gate close`.** The gate runs the checks first and
   writes nothing if they fail. "It works on my machine" is not a state transition.
3. **Change the plan with `gate amend`, never by editing JSON.** The reason gets recorded
   with the change; a silent edit loses the only part that was worth keeping.
4. **Record dead ends with `gate ledger`** the moment you abandon an approach — not later,
   when the reason has faded into "it didn't work".
5. **End every session by running `gate render`** — it rewrites STATE.md and every phase
   file from the plan. Especially mid-phase, because that is exactly when the next session
   has least to go on.
6. **A red checkpoint blocks the next phase.** It means phases that each passed alone
   disagree with each other, which is the whole reason checkpoints exist. Do not work
   around one.
7. **Do not leave something built and wired to nothing.** It is this build's most repeated
   defect — P55 found three, P60 one, P72 one more, and every one was found by a person
   reading rather than by a test. Two scans now look for it: `tests/p71` fails on a public
   function nothing calls, `tests/p73` on an exception class production never constructs.
   Both take an allowlist, and an entry without a reason fails as loudly as the defect.
   If a seam is deliberately unjoined, say so in the backlog and point the allowlist at it.

## The gate

```
python tools/gate.py status                 # where the build is, and the next action
python tools/gate.py check P07              # run a phase's exit criteria, change nothing
python tools/gate.py close P07              # check, then mark done only if it passed
python tools/gate.py checkpoint C3          # re-run every prior phase + an integration test
python tools/gate.py amend P18 "reason" --add-task "..."
python tools/gate.py ledger "what was tried" --cause "..." --rule "..."
```

Phases marked `gate: human` need a recorded sign-off as well as green tests:

```
python tools/gate.py close P18 --signoff "Caleb: checked the alignment on HEND-2026-04"
```

That distinction exists so that "tested" never quietly means "it ran without crashing".

## Running it

```
start.cmd                                  # Windows, for a person: sets up what is missing, starts, opens it
python -m uv run python tools/serve.py --check              # what is wired, what is not, what setup still needs
python -m uv run python tools/serve.py                      # admin at /admin, ops console at /, help at /help
python -m uv run python tools/simulate_firm.py              # a generated firm through the real server, no key
python -m uv run python tools/simulate_firm.py --scripted   # the same, with the review loop walked end to end
python -m uv run python tools/simulate_files.py             # every document case through the real server
python -m uv run python tools/watch_run.py                  # what a run is doing, while it does it
python -m uv run python tools/watch_run.py --once           # one look, to paste somewhere
```

`watch_run.py` is the answer to "is it working or is it stuck" during a real run: the step
that is going, how long it has been going against the bound its own step declared, what has
been spent against the ceiling, what is waiting on a person, and anything the stall detector
raised. It reads and writes nothing.

## When the firm's model arrives

The one file this build has been waiting on since P24 is `Model Template - MASTER 2026`,
and what it is waiting on it *for* is four hundred lines of YAML - the named ranges, and
what each one means. CLAUDE.md used to say the named ranges "are not knowable from a
photograph". They are knowable from the file:

```
python -m uv run python tools/read_template.py <model.xlsx> --sheet Input --inventory
python -m uv run python tools/read_template.py <model.xlsx> --sheet Input --version 2026.1 --out draft.yaml
```

It writes the inventory - every defined name, the sheet and cell behind it, and whether
that cell is empty, a number, a formula or a block - and a **draft input schema** in the
shape that `TemplateInputs.load` in [`deliver/registry.py`](deliver/registry.py) reads.

**Every `line:` in that draft is marked `REVIEW` and the draft will not load until the
markers are gone.** Reading `Revenue_FY1` as the line *Revenue* in period *FY1* is reading
a naming convention, and a convention is something a firm has rather than something a file
states. A schema this filled in silently would bind the firm's model by inference from the
spelling of its ranges, and the first symptom would be a figure written into the wrong row
of a workbook that opens perfectly. `tests/p129` generates a draft, strips the markers the
way a reviewer would, and loads it - so the shape is proved, and the judgement is yours.
`--scale` defaults to 1 for the same reason: a workbook states a layout and never its units.

## The second front door

The dashboard is the right shape for watching a run and the wrong one for *"point it at
the right folders, quickly tell it what to do, and it starts working"*. That is a command.

```
python -m uv run python tools/aa.py review <file-or-folder>   # whichever of the three reads each file wants
python -m uv run python tools/aa.py where HEND-2026-04        # the folder this engagement's documents go in
python -m uv run python tools/aa.py owed HEND-2026-04         # what the client still owes; writes nothing
python -m uv run python tools/aa.py stage a.pdf b.xlsx --engagement HEND-2026-04 --who "Caleb" --why "from Box"
```

`review` **dispatches**, so one command over a client folder reads the workbooks for
formulas, the documents for prose and the tables for the questions - which is what lets one
slash command be enough. `owed` reads the folder against the engagement's request list and
says what is still missing, essential items first. `stage` is the **join a Box connector
needs** - read the client's folder with the connector, save locally, stage it in, and the
sweep finds it exactly as it finds a file a person dropped there.

**The line these are held to.** A command may be a second *surface* on a capability:
`where`, `owed` and `stage` all reach the same `AdminConsole` methods the Setup page
reaches, so the page and the command cannot drift because there is one implementation. What
is refused is a second *answer* - there is deliberately no `aa status`, because
`serve.py --check` says what is wired and `watch_run.py --once` says what a run is doing,
and a third renderer of either is B-046's defect under a new name.

**The slash commands** in `.claude/commands/` are thin wrappers over those: `/review`,
`/intake`, `/owed`, `/where-things-stand`, and `/improve-agent`. `tests/p128` holds each of
them to naming a tool that exists, a subcommand that parses, a flag something takes, and
the environment prefix - because a slash command is read by a model that will *try* the
line rather than by a person who would notice it was wrong.

## The reads a reviewer makes

Checks the analyst asked for, over the things that leave this system. Each is
**deterministic Python** and each **reports rather than repairs** - a tool that silently
widened a SUM to what it guessed was meant would be the most dangerous thing in this
repository.

```
python -m uv run python tools/formula_audit.py <workbook.xlsx>          # the formulas a workbook gets wrong
python -m uv run python tools/formula_audit.py <workbook.xlsx> --all    # and the cross-sheet address references
python -m uv run python tools/prose_checks.py <report.docx>             # the tells, the slips, the two spellings
python -m uv run python tools/prose_checks.py <notes.md> --fix --out fixed.md
python -m uv run python tools/reasonableness.py <table.json> --move points=5 --move days=10
```

**The workbook.** Nine checks in three severities: *wrong* is arithmetic the file
disagrees with itself about - a total whose range stops a row short of its block, a total
counting another total, a saved total that does not equal what it adds; *suspect* is a
pattern break - a plug in a row of formulas, a copy that landed a row off; *convention* is
a cross-sheet reference by address, which on the firm's own model fires everywhere and so
is off unless asked for. It does not gate. It runs on every workbook a run releases -
recorded as `release.audited`, never as a refusal, because a formula in the firm's own
pinned template being wrong is not this build's call to make. The console's deliverables
panel has a **Check formulas** button that re-derives the audit from the released bytes,
which matters because the footing check cannot run until Excel has saved the file once.

**The prose.** It also runs where the prose actually moves: setting up an appendix reads
the words arriving and puts the findings beside the change, in the preview, before anything
is written - and it can never stop the appendix from moving, because whether a sentence
should say something else is the analyst's judgement. Three kinds: *tells* (an em dash, the register vocabulary, the three-item
rhythm, a bolded lead-in, sentences that never vary in length), *slips* (a word typed
twice, a space before a comma, a bracket that never closes), and *the two spellings of one
thing* - `the Company` beside `the company`, $1.2 million beside $1,200,000, two date
formats. Only a slip is a non-zero exit, because a tell is a judgement and nobody's commit
should fail over an em dash. `--fix` makes four mechanical substitutions, needs `--out` or
`--in-place`, never edits a `.docx`, and never touches code in a Markdown file.

**The figures.** The questions a reviewer asks on first looking at the numbers, over the
normalized table: a line that implies another and the other is not there (depreciation
with no fixed assets, interest with no debt - the first question an MD asks and the one
that feeds the debt tab), a ratio that moves (gross and operating margin, days receivable,
days inventory, days payable, the current ratio), and the shape of the history. **Every
finding is a question, never a verdict** - a margin that moves eight points is a problem in
one industry and a Tuesday in another, and the code cannot know which. Nothing in it
concludes anything about a valuation, and `tests/p127` holds it to that over its own
output. Every tolerance is the caller's, in the ratio's own unit, with no defaults:
materiality belongs to the practice. A unit with no tolerance is reported as a question
nobody asked rather than left out. It does not duplicate `statement_checks.movements`,
which is the single-line version; it asks what no single-line check can see. Its run-path
wire waits on the qc-tieout procedure (B-004), so today the command line is the way in.

**The one thing it states rather than asks** is a ratio its own arithmetic cannot have
produced: a gross margin above 100 points, days below zero, a current ratio below zero.
That is not a verdict about the business - it is a statement about the table, and the
ordinary cause is signed amounts where these are defined on magnitudes. It names the
negative rows and asks nothing about how the figure moved, because every such question
would be a difference between two figures that do not mean anything. Found by running it
over a table shaped like a trial balance, which reported twelve confident questions about
a margin of 173.6 points (P137).

All three were calibrated against things with nothing wrong with them, and that mattered
more than finding things: the first prose run over this repo's own four longest documents
reported about 150 findings of which almost none were about the writing, and the first
reasonableness run asked the same six questions three times each. One check - the Oxford
comma - could not be made precise and was taken out rather than shipped (B-086). A check
whose findings are mostly not findings teaches a reader to skip the section it is in.

## Is every figure right

The three reads above ask whether a workbook's arithmetic agrees with itself, whether the
prose reads as a person's, and what a reviewer would ask of the numbers. None of them asks
whether the **figures are the figures**, and until P161 nothing did - a total that re-adds
and a balance sheet that balances prove arithmetic, which eight wrong rows adding correctly
also satisfy.

```
python -m uv run python tools/check_against_filer.py              # every public fixture
python -m uv run python tools/check_against_filer.py --fixture sec-ars-resmed-2026
python -m uv run python tools/check_against_filer.py --fetch 0000943819    # needs the network
```

The SEC publishes the filer's own numbers as structured data, so `Assets` at 2025-12-31 is
521,728,000 - the 521,728 on page 56 of the filing times the thousand it says it is in. That
is ground truth from the same regulator for the same document, and it needs **no
label-to-concept mapping**, which is the part that would have made it hard: the question is
not which concept a row is, it is whether every figure the reader produced is one the filer
reported *at the date that column is as of*. A figure out of the wrong column is still a
figure the filer reported - that is B-030, this build's worst extraction defect - and
matching by date is the only thing that sees it.

Four answers per figure, and the last two are the useful ones: right at this date and scale;
right but only at another scale; reported at a different date, which is the wrong column and
is a failure; or in no fact at all, which this feed cannot tell from a figure tagged against
a segment. It found B-131 by itself.

**Over three filings and two filers: 194 right, 0 out of the wrong column.** The number worth
having is ResMed's, because the reader had never been run on that document - the other filing
was read until it read correctly, which is how it should be and is why its score says less.

It is **offline**: the facts are committed under `fixtures/public/filer-facts/`, trimmed to
the dates each filing's statements are as of, because a tool that needed `data.sec.gov` would
answer differently on a train and a test that needed it would fail for a reason that is not
about the code. What it cannot see is written in its own docstring, because a measurement
whose limits are not recorded gets quoted as though it had none.

**Which column is which year.** The reader was throwing the answer away. A statement prints
`December 31, 2025` over one column and `2024` over the other, and `_headings` in
[`intake/readers/layout.py`](intake/readers/layout.py) places those by where they sit - but it
was handed *the last band above the figures*, and on a real statement that is always `ASSETS`
or `Current assets:` or `Cash flows from investing activities:`, never the dates. By the
second block of a balance sheet the header is five bands up. So 70 of 119 tables over two
filings came out unnamed, the period detector reported `0 of 5 tables name their columns`, and
**every comparative statement escalated to a person on every filing** for want of a band two
bands further up. The years are read from the nearest band above that dates *every* column,
and a bare year is required because the wider rule reads a date out of prose - `at December
31, 2025, and 2024.` crosses three columns, and no share-of-words threshold separates that
sentence from a real header. Nothing that named its columns changed; the figures did not move.

**And a table that lost a column must not settle.** `_columns` establishes a column only from
money-shaped figures, so a column of small or nil amounts falls one short of `COLUMN_NEEDS` and
is never built - and every figure to its right then sits at a column index belonging to another
year. The investing block of 3D's cash flow statement holds `(16,121)`, a dash, `96` and
`(3,000)` in its 2024 column, and `96` is four figures short of needing a comma. So the column
is dropped, three figures are lost, and 2023's land where 2024's belong - which the filer says
in its own words, because `ProceedsFromDivestitureOfBusinesses` is **96** over 2024 and **194**
over 2023 and the reader put the 194 at column two. That is B-030 in a cash flow statement.
Non-consecutive years are what catch it: a two-column table dated 2025 and 2023 under a header
reading `2025 2024 2023` says a column between them was never built. Two tables over 232 pages.
It is **reported, not repaired** - rebuilding the column is a guess, and saying its indices
cannot be trusted is a fact.

**A total that says which way it points.** Every tie-out in `intake/readers/footing.py`
passes a statement whose every sign is inverted: rows of -12,000 and -3,000 under a total of
-15,000 re-add, two sides agree at -521,728, cash rolls forward to a negative balance. A cash
flow section is all-negative, so a column read with every sign flipped foots exactly - and
arithmetic cover is the evidence that will decide whether a person looks. What catches it is a
statement about the table, not about the business: `Total assets` is not negative, `Net cash
used in financing` is not positive. The whole of the rule is the line between a label that
cannot honestly go either way and one that can, and the second kind says nothing - `Net cash
provided by (used in)`, `Net income`, `Gross profit`, a proceed inside a roll-forward, an
expense that one page prints positive and the next negative. Calibrated over 2,373 rows of the
three filings: 69 read, none contradicted. One contradiction withdraws the **whole block's**
cover, because on a flipped column the rows with no direction word look right. It reads 2.9%
of rows and they are the grand totals; a flip confined to a section with no direction line
still passes, and that is written down rather than left to be found.

**The one multiplication asks the unit first.** P162 gave a share count `unit: shares,
scale: 1`, and `harness/restate.py` divided it by a thousand anyway on the way into the
workbook - it read `scale` and never `unit`, and rewrote the scale to the template's so that
`deliver/builder.py`'s own refusal for a figure at the wrong scale could never fire. Six lines
in three modules multiplied a figure by its scale and two lines in the repository read its
unit. Now `amount_of` and `expect_unit` in `harness/restate.py` are the one way a figure
becomes a number: a figure that is not money is left as it came and listed as such on the
restatement event, a cell bound to one is refused with the unit in the sentence, and the
narrative prints `135,361,000 shares`. The proof is not a search for a word - `tests/p165`
makes `_moved` raise and watches every site fail.

**The files a client actually sends.** Sixty-three malformed, hostile and degenerate files
went through the readers; every refusal came back as one of the two intended codes, and every
finding was on a file that was *read*. P166 closed the ones a real client file hits first. A
CSV telling two decimal stories decides nothing and says so, and a cell written the other way
under a settled convention is left as text and named - `1.234,56` beside `402,000` used to
read the second as 402.0 with nothing said. `(12,000 )`, `12,000-` and the unicode minus are
the negatives they are, and a parenthesis without its pair yields no figure rather than a
positive one, so the footing sees a dropped row instead of a flipped sign. A page with no text
layer is said to be one, on the report and the `intake.read` event, so a scan nothing read
cannot pass for a file that held no figures. And the refusals say the true thing: a protected
workbook or PDF is *protected*, a PDF under an .xlsx name is a PDF, a tab-separated file named
.xls is read, a UTF-16 export is read. None of the admitted shapes occurs on the three public
filings, which read to the row as they did. What is still unbounded - a million-row sheet, a
200 MB shared-strings member - is B-146.

## Methodology, not procedures

The analyst's decision of 2026-10-05: **`dcf-build`, `gpc-scrub` and `cost-of-capital` are
not procedures this tool runs.** The firm's own model already does the DCFs - exit multiple
or Gordon Growth, CAPM or build-up, beta relevered to a target structure - and takes its WACC
inputs; comps are screened by a person in Capital IQ, by keyword and by industry. What the
model needs is **knowledge it consults when deciding how to handle something in the model**,
and the mechanism for that already existed: `foundations/` is scope-walked into every context
and cleared by digest.

So the knowledge lives in two places with one content. [`knowledge/methodology/`](knowledge/methodology/)
holds six files - EBITDA adjustments, the working-capital exclusions and normal level,
guideline company screening, the cost-of-capital inputs, report writing - each with *what we
know* (every item cited to the interview session it came from), *what the model should do
with it* (rules, only where the interviews support them) and *what is still unknown* (the
precise questions the work laptop answers). `foundations/valuation/_group/` holds each file's
rules section **verbatim**, and that is what a valuation run attaches once a person clears it
at `/admin`. `tests/p167` holds each pair together, so the two cannot drift. The three skills
keep their frontmatter and say in their bodies what superseded them; nothing in production
reads a skill's status, so nothing changed at run time. The interview topic map feeds the
knowledge files now, so the next session on the work laptop writes where the model reads.
Two of the six are mostly questions - no interview ever asked about working capital - and a
short honest file beats a long plausible one.

**A laptop closes.** A server runs until somebody stops it; a laptop closes at six. The queue
is in-process and memory-only, so a run that was mid-pass when the process ended had a job the
next process had never heard of - and `stranded()` only looked for jobs the queue called
*failed*. The console refused Resume and Halt with `RUN.HELD`, nothing picked it up at start,
and the engagement lock stayed held so every later run on that client queued behind it for
good. P168: a running run whose job the queue has no memory of is stranded, said so on the
record, and picked back up before the first sweep - resume is replay and the ledger makes the
replay idempotent. Preflight gained a sixteenth check - a warning on the fixture replayer, a failure on a
missing key - because the fake model adapter passed the other fifteen and the first real
run failed with a sentence for a developer. And
`serve.py --check` says where the record is: one SQLite file under `runs/`, not in git, the
whole of what the tool knows - copy it to back it up.

Three more commands, written down here because until P82 each one's invocation existed only
in its own docstring - so a person could not find them and the reachability scan could not
tell them from dead code:

```
python -m uv run python tools/synthesize_templates.py   # rebuild the two synthetic Excel templates
python -m uv run python tools/bootstrap_scaffold.py     # write the first scaffold of a package
python -m uv run python -m evals                        # the eval harness, over the candidate skills
```

The two rehearsals are the tests the suite cannot be: real process, real HTTP, files
shaped like an accountant's, and (with `--scripted`) a stand-in answering for the model so
runs reach the review queue, get answered, resume and write precedent. Between them they
found twenty-three bugs the suite passed over. Run both after any change that touches
intake, the driver, the guards or the consoles; a line marked FINDING is something to fix.

**Run them on a fresh clone too, not only here.** They passed for weeks on this machine and
failed at every activation on a clone (P169, 2026-10-06), because they had been relying on
`recipes/registered.yaml` - which the test suite writes and git ignores. They approve the
workflow they run through `POST /api/admin/recipes/{name}/approve` now, the way the Setup
page does, and `tests/p169` drives `set_up` against a machine that has nothing. The same
rehearsal found that preflight was calling a never-approved recipe *does not compile*, that
`templates/*.xlsx` is not in git and nothing in the manual install path produced them, and
that a rehearsal killed mid-run leaves its server process behind (B-158).

The consoles answer only to this machine: the request gate in `ui/who.py` refuses a foreign
`Host` or `Origin` before a route runs (a page the browser has open can reach `127.0.0.1`), and
uvicorn is given `proxy_headers=False` so the peer address cannot be rewritten by a header.
Pages build no handler out of data - values reach a handler through `data-` attributes and the
`ACTIONS` table, because a client's line item is whatever the client typed.

`serve.py` reads `.env` into the environment on start (the shell wins; `AA_NO_ENV_FILE=1`
opts out, and the rehearsal sets it). Before that fix, only secrets were read from the file.

**On a machine doing real work, set `AA_OCR_ADAPTER`.** Every PDF this firm's clients send
is a scan and they send a lot of them, so with the default (`none`) most of the inbound path
reads as nothing — correctly, because a page that yields nothing is reported rather than
filled in, but it reads as nothing all the same. `rapidocr` is a wheel and needs no
administrator; `tesseract` needs its executable on PATH. `serve.py --check` says which of
them is actually working, by trying it. A screenshot, a photograph of a page or a `.tiff`
goes down the same path: it is a page with no text layer, which is what a scan is.

**Setting it now actually buys the figures.** Until P155 it bought the *text* and nothing
else. The port returned lines, an engine returns a cell at a time — `Total assets`, then
`521,728`, then `608,846` — and the row builder wanted a line carrying a label and all of
its figures, so a scanned balance sheet came out as 122 fragments, **no tables and no rows**,
with 295 of its 296 figures read correctly and every one discarded. A row is a band of the
page and a column is a band too; the engine's boxes come through the port now and both kinds
of page go through the one reader in `intake/readers/layout.py`. The same page scanned and
from its text layer now gives the same 61 rows, the same totals and the same balance sheet.

**Open the page and look.** The suite was green through every console defect this build has
had, and P170 was found the same way as the others: the analyst opened the whole-design view
and every order number on the nodes was a quarter-circle, because the badge hung outside a
box that clips its own overflow. It sits inside the node now, the nodes a run touched carry
the console's panel elevation, and the elevation tokens are three layers so every panel
lifts the same way. `tests/p170` measures the badge's extent from the sheet's own numbers at
both ends of the fluid root rather than trusting a sentence about it. To look yourself:
`simulate_firm.py --scripted --keep` leaves a record under `runs/_rehearsal/`, and
`serve.py --port 8033` with `AA_DB_URL` pointed at it paints the map with real runs.

**The dashboard has some life in it now (P171).** The analyst's words: plain, and it looked
generated. What changed is atmosphere and motion with a purpose, all of it in the brand's
colours and off the two scales: lit paper, three slow lights under the masthead, a signature
rule along the top of every panel, panels that arrive in a beat each, figures that land, a
breathing dot on anything still happening, a light along a bar that is measuring something
in motion, a feed line that slides in, and the run's trail on the map travelling the way the
run went. One rule turns all of it off: `prefers-reduced-motion`. And one skill is one row on
the Analytics board, with its practice groups under it - the table had been keyed by (skill,
group) and listed every skill twice with nothing saying why.

**A panel in two rows is white space in the three beside it (P172).** On a grid every panel
in a row is stretched to that row's height, which is what makes a band read as one shelf.
A panel spanning *two* rows has its height shared out across rows nothing else is in, so
everything beside it is stretched to a height nothing in its own band asked for. The run
detail is unbounded - one row per decision a person made, and the Analytics board on the
same screen says **34 is the median** - so at 1366px the Runs panel was 2,794px around
259px of content, Waiting on a person 1,400px around 92, and the page 3,369px. Now: the
decisions are one line and a disclosure, the panel is a stream, both boards are laid out in
bands with no row spans, and the page is 1,385px with every band exact. The Analytics board
was already right and nobody had noticed why - its areas are plain rows. Spanning columns
costs nothing and both boards still do it.

**And the reason a run stopped is on the run.** `qc: "no procedure for 'qc-tieout'"` was in
`/api/runs/{id}` all along and was drawn only by the Run trace panel, two bands and three
thousand pixels below the run it was about; the quick way to it was the whole-design view
and **Go to the stop**. One renderer draws it in both places and the caller says which
diagnostics it wants. `/` goes to a page's find box on every surface that has one, written
once in the shared shell, because the map has answered that key since P49 and the consoles
answered nothing. The glossary has a box, and it searches what a word *means* as well as
its name - somebody who has read *stopped on itself* on a run types that, and the word is
**Quarantined**. An engagement's watched folder is made when the engagement is made, so the
files dialog, `aa stage` and a Box connector are not all pointed at a directory that does
not exist on the one day they are most likely to be used.

**Sweep the page, do not read it (P173).** A script that walks every element the four pages
paint - at 1366, 1900 and 1024 - and measures the contrast of every text node against what is
*actually painted behind it*, every control's target size, and every box against the panel
that clips it, found 106 things reading could not. The worst was on Setup: `.r .sub` held
`white-space:nowrap` from the day the first thing in it was a timestamp, and a check's detail
is a sentence - so the model-adapter row's label was crushed to one word a line eleven lines
tall and its status pill was pushed 630px outside a panel that clips its overflow. Nine
places had already overridden that `nowrap` by hand, which is the declaration being wrong.
Also: 98 node names at 2.86:1 in the ink reserved for placeholders, 17 controls under the
24px a target needs, a scale with a dead step and three headings choosing their own within
0.08rem, eight bare pixel lengths on a page whose root is fluid, and a quarantined run saying
the word three times in three vocabularies. All fixed; `tests/p173` asks each as a question
about the source and `c98` asks it of what the server serves.

**Two rules whose order is the answer.** The target minimum needs `display:inline-flex`, and
that outranks the `display:none` the user-agent sheet gives `[hidden]` - so three buttons the
pages hide came back, and that was found by looking at the board. `in CSS` cannot see an
ordering, so the checkpoint reads the served bytes and asserts the restoring rule comes
after. And one about the method: the revert harness could test an edit against the *previous*
edit's bytecode, because two breaks on one file both set mtime+1 and the cache matched. A
strictly increasing mtime and a purge of the edited module's cache close it; P172's and C97's
guards were all re-proved through the corrected one (B-176).

**Walked against its own runbook (P174).** The repository was cloned from GitHub as a work
laptop would clone it and `docs/WORK-LAPTOP.md` was followed line by line. Two sentences were
not true: it sent a reader to the sixteenth check for a warning that is the third of sixteen,
and it did not mention that step one always prints a vault failure - which it must, because
the step that sets `AA_VAULT_KEY` is step two. That failure was an exception class name above
eight green lines; it reads as the setup step it is now. `tests/checkpoints/c99` holds every
command the runbook gives and every check it names to the code, from the prose as well as the
fenced blocks, because most of them are in prose.

**The checks on the remote had never once been green (P175).** Twenty-one runs since the
repo got a remote on 18 September, no successes. Nobody looked, and *that* is the lesson:
`verify.py` is what stands in for CI here and it skips exactly the three things CI runs -
postgres, redis, container - saying so honestly every time. An honest sentence nobody reads
is a silent one. Two causes, neither about CI:

- **One tool reached uv the way uv is not installed.** `pip install uv` leaves a module and
  a binary; the installer at astral.sh leaves only a binary, where `python -m uv` is nothing.
  `verify.py` hard-coded the module and died in zero seconds, six times. `gate.py::resolve`
  and `start.ps1` had always asked; `verify.py`, `postgres.py` and `_environment.py` now do.
  **This is a work-laptop defect**: every documented command here carries `python -m uv run`,
  so on a machine that installed uv the documented way, the documented spelling is the one
  that fails. The runbook says to drop the `python -m`.
- **The image was built from the machine beside it.** A `.dockerignore` pattern is anchored
  to the context root unless it opens `**/`, so `__pycache__/` matched one directory that
  does not exist and **7,509 Windows-compiled `.pyc` files went into a Linux image**, where
  Python preferred them to the source. The failures read `C:\dev\automated-analyst\...`.

With both fixed the image's real failures appeared - forty tests asking the *repository* a
question (the backlog, `knowledge/`, the register, git) from inside an artifact that
deliberately ships none of them. `needs_a_checkout` has existed for that since P28 and had
four callers. It has forty now, two of them in fixtures because a fixture raises before any
test body runs. Three guards keep a skip from becoming a way of not running things, and all
three proved nothing in their first form - including one that let a break through entirely,
because **a test that skips is not a test that fails**. Inside the image: 5,068 passed,
nothing failed.

**One backend of two.** The first job that ever reached a database found that `precedent` -
the one table only a human decision may write to - could never have been created on Postgres.
Its masked check was written `masked = 1 OR masked = true`, which is somebody covering both
backends and covering neither: SQLite compares a boolean to an integer happily, so the first
half worked on the only backend anybody ran, and Postgres has no `boolean = integer` operator
at all, so it refused the expression while *planning* the CREATE TABLE and took the whole
statement with it. 130 refusals, and every one of the 65 store conformance tests failing for
want of a table.

`tests/p04` is thorough and had been saying so in its own summary every time it ran -
*SQLite passing is not evidence the Postgres path works. This suite is green on one backend
of two.* An honest sentence nobody reads is the same as a silent one, which is the second
time that has been the finding (P175 was the first).

The instructive part is in the same class. The triggers beside that constraint ask the same
portability question and answer it correctly, per dialect - `format(true='1')` for SQLite,
`format(true='true')` for Postgres. The constraint could not be parameterised that way,
being one entry in `__table_args__`, so it got the same understanding expressed as a hope.
So **neither test asks about source text**: `tests/p176` compiles the schema for each
dialect, and `tests/checkpoints/c101` takes every statement `create_all` would send to each
backend through a mock engine - triggers and functions included, which no table's compiled
form reaches - and asks the boolean question of all of it. Both need no server, which is the
whole point: *does this schema exist on Postgres* is now something a laptop answers in
milliseconds.

**And a check that cannot finish is a check that does not run.** The same job was cancelled
at thirty minutes on every attempt, which reads like a hang and was arithmetic: five gates
and then the whole suite twice, inside a bound written when the suite was a fraction of its
size. The measurement was never taken because a timeout is reported as a failed check with
no failing test in it. It is taken now, from the Postgres container's own log - which GitHub
dumps at `Stop containers` and which therefore survives a cancellation when the step's
buffered stdout does not: 4m51s of gates, 15m01s a pass, 34m53s of work in a thirty-minute
bound. Both bounds in `verify.yml` name the run they were measured from, and `tests/p176`
holds each one against what that job's own run line asks for.

One level up from all of it: the revert harness read pytest's **exit code 5** - *no tests
collected* - as a failure and therefore as a proof, so a break aimed at a renamed test came
back `proved` on a run in which nothing executed. The thing checking the checks was not
checking. It found one real false pass once corrected, in a rewritten prior-phase test whose
name claimed more than it asked.

**It ran, and then it told us four things (P177).** With the bound raised, the Postgres job
finished for the first time in this repository's life - 31m44s - and said
`POSTGRES RAN - 65 store conformance test(s)` and `REDIS RAN - 8 queue adapter test(s)`,
both green. Two sentences this build had been writing as plans since P04 are evidence now.

Then it failed on four things, and every one had been true for weeks while passing on the
machine it was written on. That is the whole lesson of the phase, so they are listed as one:

- **A green commit went red the next morning.** `BUILD/STATE.md` carried `*Last written
  <today>*`, and the `state` step runs `gate render` and fails if `BUILD/` came back
  changed. Both halves are right and together they are a 24-hour fuse: render a day later
  and the file differs, so the verifier reports `state was stale` about a file nobody
  touched - on every machine, since the gate was written. Nothing had ever run that check a
  day after a commit. CI did, by being a day late. The line is `last_moved(plan)` now, so
  the render is a function of the plan and nothing else.
- **The first step asked a gate a question about bytes.** `tools/surfaces.py` snapshots what
  each recipe *declares* and did it through `load_recipe`, which refuses a recipe the board
  has not approved. Approval lives in `recipes/registered.yaml` - gitignored on purpose, and
  written by a session fixture - so **no clone could reach step two**, and this machine never
  noticed because that file had been lying in the working tree since September. Split now:
  `declared_in(path)` is what the file says, `load_recipe(name)` is that plus the gate. Not
  an exemption flag, which `load_recipe` deliberately refuses to have; a second function with
  a narrower job, held to one allowlisted caller by `tests/p33`.
- **A test asserted what the host's mime table happens to know** - that the platform does
  *not* know `webp`, true on Windows and in a slim image and false on an Ubuntu runner. Its
  own message said *if the platform learns webp, this line is stale rather than wrong*. The
  claim is made directly now: `mimetypes` is patched to answer wrongly for everything and the
  declared table is unmoved.
- **A guard about something other than what it guards.** Two tests here read
  `.github/workflows/verify.yml`, which the image does not ship. One had no guard and was the
  single failure inside an image of 5,097 passing tests. The other called `needs_a_checkout`,
  which asks about `.git` - a different absence that happens to coincide. P175's scan could
  not catch either, because it opens `if "needs_a_checkout(" not in text: continue` and so
  asks whether the guard comes *first*, never whether a file needs one. `tests/p177` asks the
  rule that covers both: **a read of a path the image does not ship is guarded by a condition
  that names that path.**

Two about method, both found by chasing a result that did not make sense instead of
accepting it. The portability assertion printed `run.stdout[-8000:]`, and the last eight
thousand characters of a pytest run are its *skip report* - so the image's one failure could
not name itself and had to be deduced. And `revert_lib` decided a file's line endings by
asking whether CRLF appeared anywhere in it, which a **mixed** file defeats; it called a
sound break `NO MATCH`. Anything appended to a file here must match that file's endings.

The thing worth keeping: **a check is only a check where it can run.** All four of these
passed locally and could only fail somewhere else - on a clone, in an image, on Linux, or
tomorrow. `tests/checkpoints/c102` builds a tree out of `git ls-files` alone and runs the
verifier's collectors inside it, which is the only way to ask that question without
accidentally including whatever this working tree has had lying around for a month.

**And then both jobs were green (P178).** Run 37738346007: 65 store conformance tests
against a real Postgres 17, 8 queue adapter tests against a real Redis 7, and the image
built with the whole suite passing inside it. Three claims this build had only ever made as
plans. The proof they *ran* rather than skipped is the verifier's own summary - `did not
run: container.`, where every developer machine says `postgres, redis, container`.

The same green run showed that **the measurement which fixed the bound was itself taken
from a job that never finished.** A cancelled run leaves no step output, so B-186's figures
were inferred from intervals in the Postgres container's log, and were wrong twice over:
*4m51s of gates* was the gates (32.3s) plus four minutes of the first pass before anything
touched a database, and *15m01s a pass* was timed while the 65 Postgres tests were failing
in milliseconds against a table that could not exist. A real pass is 20m54s and the job is
41m51s, so the guard required 37 minutes where the work is 43 - **it would have approved a
40-minute bound for a 42-minute job**, which is the defect it was written to prevent. The
bound survived only because the headroom was argued for on exactly that risk; the reasoning
was right and the arithmetic was not.

So a figure here has to come from a run in which that job *finished*, and `tests/p178`
holds it - **per job, not per run**, which the first version got wrong and its own test
said immediately: on 37717781284 the verify job was cancelled while the container job
completed in 35m22s, so one bound may cite it and the other may not. The figures are quoted
in the format `verify.py` prints them, so the next person matches them against a log rather
than trusting a paraphrase, and `c101` imports `p176`'s constants instead of keeping a
second copy - two copies of a wrong number is how one gets fixed and the other does not.

The habit worth taking from the four phases: **break every new guard and watch it go red.**
Five in this block needed a second form, and the two in the C103 checkpoint failed the same
way as each other - each asserted a *token from* its claim rather than the claim. One said
it held the suite to *saying what SQLite alone is not evidence of* and checked only the
phrase `one backend of two`; the other said it held the verifier to *saying which stages it
skipped* and checked for `did not run`, which also appears in the unrelated `--fast` line.
Both stayed green with the thing they were about deleted.

**The model-setup skill has a place to land.** Section 8 of `docs/WORK-LAPTOP.md` says where
(`skills/valuation/_group/model-setup/`), what its front matter must declare, which slot each
of its two paths fills (`model-load`; `prior-year-rollforward`), and that everything in it
naming a client goes under `knowledge/model-setup/` instead. `tests/p171` holds the section
to paths and names that exist.

`readiness()` in `tools/serve.py` derives what is joined by asking the code, so it does not
need updating when a seam is filled - and it is the honest answer to "does this work yet".
A seam marked NOT INSTALLED waits on software a person installs; NOT WIRED is a join this
build has left unmade, and they are different problems.
[`docs/USING.md`](docs/USING.md) is the guide for the people who use the tool rather than
build it; keep it true, because a test holds it to the setup path it describes.

## The focus, and `/improve-agent`

The build serves **one division first: valuation / non-ESOP** (`focus:` in
`scope/scopes.yaml`). ESOP is parked - kept, tested and resolvable, not where effort goes.
Other divisions arrive later as data: a scope entry, a folder, and topics for the
interview. Pointing the focus elsewhere is that one entry.

`/improve-agent` (Cursor or Claude Code; both wrappers point at
[`interview/PROTOCOL.md`](interview/PROTOCOL.md)) interviews the analyst one question at a
time and, on stop, turns what it learned into changes through the gate. What it learns
lives in `knowledge/`, committed to the private repo so it travels between machines, and
it may hold client data - **nothing identifying leaves it** for a skill, methodology file
or fixture; `python -m uv run python tools/interview.py scan` must print `clean` before a
session ends. Run `python -m uv run python tools/interview.py status` to see where the interview stands and
what the code says the focus division is still missing.

The scan checks `knowledge/identifiers.txt`, and it refuses rather than passing over an
empty one. `interview.py suggest` reads the answers already recorded and proposes what has
the shape of a name; `interview.py register NAME` adds one. **The register holds real
client names now** — the fourth session named six clients, an auditor and two locations —
so the scan is a real search rather than an acknowledgement standing in for one. It caught
a leak the first day it had names to look for.

If a session genuinely names nobody, a person records that with
`interview.py register --none "..."`. It needs words of your own: the note is the decision,
and the code will not write one for you. It records the sessions it was made over and
expires as soon as another is logged, and it refuses to replace an acknowledgement that
still stands rather than overwriting somebody's record. **Never invent a name to fill the
register.**

## What this project is

An AI analyst pipeline for Chartwell: DDR extraction and tagging, financial statement
normalization, and model building — the mechanical stages of deal work, done under
guarantees strong enough that an analyst can trust the output without redoing it.

**What version 1 is, which is narrower.** The analyst set the scope in the fourth interview
session (2026-09-18): *"gathering data and putting it into the same format every time so it
is really easy for me to do the work in the model. Version 1 of this is not for you to run
the actual model."* It fills an **input-help workbook** matching the model's input format
and never touches the real model. So `gpc`, `cost-of-capital`, `dcf-build` and `qc-tieout`
are out of version 1's path, and building them is not progress toward it.

**The centre of gravity is the repeat client.** 75% of engagements are repeat clients, and
for those *everything starts from last year's version of itself* — the model, the WS
grouping, the Input tab, the request list. That is one mechanism applied four times, not
four features. Only two Input fields change in a year (valuation date, latest fiscal year
end), the WS line items are carried forward rather than re-decided — so for three quarters
of the work **the prior workbook is the chart of accounts**, not `taxonomy/`.

The architecture is settled and lives in a single file:

    docs/architecture.html      <- the source of truth. Edit it here, commit the change
    tools/sync_blueprint.py     <- publishes a read-only mirror to OneDrive for viewing

118 nodes, 240 edges, 25 executable invariants, 67 failure modes. **When the code and the
blueprint disagree, that is a finding, not a preference** — resolve it explicitly and
record the resolution with `gate amend`.

## Non-negotiables from the blueprint

These are not style preferences. Each one is an invariant with a test behind it.

- **A skill invocation is one model turn.** `max_turns == 1`. If a skill needs a tool
  result, that is another step in the plan — compiled, keyed and visible.
- **The graph owns every loop.** Every cycle is declared with an integer maximum the
  compiler checks. No agent decides for itself whether to try again.
- **A skill proposes; it never acts.** Tools are reached by name through the Guarded Tool
  Runtime, after the Policy Gate authorises the call. Nothing under `skills/` may import
  anything under `tools/`.
- **No model performs re-identification.** `privacy/` is deterministic Python throughout.
- **No Excel, COM, VBA or Power Query anywhere.** openpyxl writes into a copy of a pinned
  template; Excel recalculates when a person opens the file.
- **Bind by named range, never by cell address.** `B44` is not a contract.
- **Only a human decision writes to the Precedent Store.** A system that learns from its
  own unreviewed output drifts, and does it invisibly.
- **Guards are not configurable.** An admin may raise a review requirement, never lower
  one, and never disable a guard that fails closed.
- **Nothing concludes, signs or certifies.** No schema has a field a concluded value
  could be recorded in. The appraiser signs, outside this system.
- **A figure is proved by arithmetic, or it is seen.** The analyst's rule, given on
  2026-09-18 and built in P67: a figure read out of a client document is accepted unseen
  only when it carries its source locator *and* every total it feeds re-adds. Everything no
  arithmetic covers is shown — every one, not only what changed. Evidence, not a confidence
  score, because the failure that matters is a confidently wrong OCR read, which no
  probability catches and a total that stops adding up does.
- **OCR is local, and that is not a preference.** Masking needs text; text from a scan
  needs OCR; OCR by a vision model would put the unmasked client document in front of a
  model *before* masking could happen. `tests/p74` walks the imports to prove nothing on
  that path can reach one.

## Working style here

- Local by default, and local on the work laptop. No cloud; the Box and ShareFile adapters
  exist and are proved against fakes only (B-056). The ports exist so that stays true
  without costing anything later.
- The fake LLM adapter replays fixtures, so the suite needs no API key and costs nothing -
  and preflight's `model_answers` check warns about a machine left on it (P168).
- Client data enters the repo only under `knowledge/`, and only because the repo is private
  (decided 2026-09-16). `fixtures/` is masked, synthetic, or **public** - a document a
  regulator publishes, kept under `fixtures/public/` with where it came from and when.
  Never a document a client sent. The rule has always been that no client data enters
  the repo; masked and synthetic were the two ways to satisfy it, and a real SEC filing
  is a third that finds what a synthetic one cannot (P76).
- Ask rather than assume when a decision would be expensive to reverse — the blueprint
  records nine such decisions that belong to people, not to code.

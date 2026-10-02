# Using the Automated Analyst

This is the guide for the people who *use* the system rather than build it: an analyst
whose files it processes, a managing director setting up how their group works, and
whoever runs it day to day. Nothing here needs Python.

If you are here to change the code, you want [`../CHANGING.md`](../CHANGING.md) instead.

---

## What it is, in one paragraph

Files land in a watched folder. The system works out which engagement they belong to,
waits until a set looks complete, masks anything that identifies a real person or company,
and runs a series of narrow skills over the masked version — reading the trial balance,
aligning periods, tagging line items, proposing add-backs, filling a model template. A
person reviews what it proposes. It never concludes, signs or certifies anything: the
appraiser does that, outside this system.

**What makes it different from asking a chatbot.** Every step is planned before anything
runs, every number is traced to the cell it came from, every tool call is authorised
against a list, and anything the system is not confident about is routed to a person
rather than guessed. When it cannot do something, it says so and stops. It does not
improvise.

---

## Right now: what works and what does not

Read this before anything else, because the honest answer matters more than a demo.

| | |
|---|---|
| **Setting up** — engagements, practice groups, folder labels, methodology, budgets, review levels | Works |
| **Intake** — a watched folder is swept, files are bound to an engagement, held until the set is complete, and released as a run | Works |
| **Watching** — runs, steps, cost, the review queue, alerts | Works |
| **Running the work** — a released run is picked up and driven through its plan | Works |
| **Finishing every job** — two skills have no mechanical half yet | **Not yet** |

A file landing in a watched folder now becomes a run that is picked up and driven: the
workbooks are read into rows, the payload is masked, the model is called through the door,
the guards check what comes back, and anything the system is not sure about goes to a
person. What it cannot yet do is *finish*, and the reason is specific rather than vague.

Two of the skills the shipped recipes name have no mechanical half written yet —
**`qc-tieout`**, which both recipes end with, and **`ddr-tagging`** in the full intake. A
run that reaches one of those stops there, with the step named in the record. That is the
system saying what it cannot do rather than delivering something nobody checked, and it is
on [`../BUILD/OPEN.md`](../BUILD/OPEN.md) as skill work rather than plumbing.

You will also see runs stop for a reason that is not a gap at all: a workbook whose scale
is ambiguous — thousands or units — escalates to a person before any model sees it, rather
than guessing. That is the design, and it is what most first runs on real files will do.

You can check this yourself at any time; it is derived from the code, not from this page:

```
python -m uv run python tools/serve.py --check
```

---

## Starting it

**On Windows, double-click `start.cmd` in the project folder.** That is the whole of it. The
first time, it installs what is missing, creates `.env`, generates the mask vault key, asks
once for the Anthropic API key (typed into the window, not shown, kept only in `.env` on
that machine - press Enter to go without one), makes the inbox and outbox folders, and opens
the dashboard in the browser. After that it just starts. Close the window to stop it.
`tools\start.ps1 -SetupOnly` prepares everything and runs `--check` without starting.

Which page it opens is the server's answer rather than a fixed address: a machine that has
no configuration yet lands on **Setup**, because every step of a first morning starts there,
and a machine that is set up lands on **Activity**.

Or by hand:

```
python -m uv run python tools/serve.py
```

Either way, the settings in `.env` are read when it starts - the model adapter, the folders,
the database - and a value already set in the shell wins over the file. (The rehearsal sets
`AA_NO_ENV_FILE=1` so a developer's `.env` never reaches a generated firm.)

Then open:

- **http://127.0.0.1:8000/admin** — setup, engagements, practice groups, methodology
- **http://127.0.0.1:8000/** — the ops console: runs, steps, cost, the review queue
- **http://127.0.0.1:8000/analytics** — across every run: is it working, and what to fix
- **http://127.0.0.1:8000/help** — what to do, in order, and what the words on the pages mean

Each links to the other two. They answer different questions and are read at different
times: the admin page when you are setting something up, the console while a run is
happening, analytics weekly by whoever is deciding whether this is worth continuing.

`--no-sweep` starts the consoles without watching any folder. `--check` builds everything,
starts nothing, and prints what is ready — the right first command on a new machine.

Everything the admin page does goes through the same API a script would use, so there is
nothing you can do in the browser that is not also on the record. Every change asks for
your name and keeps it.

> **Who a change is recorded against.** The name in the change log is the one the system
> resolved, not one the browser sent. The page does not ask you for it — it shows it, in
> the top right, so you can see whose name is going on what you are about to do. On this
> machine that name is the operating-system user, and there are no accounts, because a
> machine with one person on it does not need them.
>
> The server also answers only to this machine's own names, and refuses a request that
> arrives under any other `Host` or from another page's `Origin`. That is not paranoia about
> the network: a web page the browser happens to have open can reach `127.0.0.1`, and without
> those two checks it could read every client name and download every released workbook.
>
> That is also why it binds to `127.0.0.1`. The local-user adapter **refuses any request
> that did not come from this machine**, so binding the surface to a network address does
> not quietly work: it needs an identity adapter that authenticates, which is the firm's
> provider - Entra ID, most likely, if Azure is confirmed - behind the same port. Set
> `AA_IDENTITY_NAME` when the operating-system user is not a name the firm would recognise.

---

## For a managing director: setting up how your group works

Three things belong to you and are not the code's to decide.

### 1. Label the folders with your practice group

An engagement is given a **scope path** — practice group, segment, disposition, e.g.
`valuation/esop/repeat`. That one label decides which skills the run has, which
methodology it carries, which model template it fills, and which past decisions it may
learn from. You pick it from a list on the admin page; nobody types it.

A group that has not been described yet resolves to the firm layer only, and the page
says so rather than showing a short list that looks like a considered answer.

### 2. Write your group's methodology

`foundations/` holds how the work is done. The firm's standards are at `_firm/`; your
group's go in a folder of its own:

```
foundations/_firm/                       every run there is
foundations/valuation/_group/            every valuation run
foundations/valuation/esop/_segment/     ESOP work specifically
```

A valuation run carries the firm's methodology and valuation's, and never consulting's.
This is general knowledge — how we scope, what we reconcile first, what we always
document — not instructions for a particular engagement.

**Somebody has to read each file and clear it before it is used.** Methodology reaches
every model call for every client, so the system scans it for anything that looks like a
real engagement's data, records who cleared it, and checks the file has not changed since.
Editing a cleared file un-clears it automatically. You do this on the admin page, and it
takes seconds.

There is a size limit per layer, reported at setup. Methodology is carried on every call,
so it costs money on every run; the limit makes growth a decision rather than a surprise.

### 3. Say what order the work happens in

The order of steps is a **recipe**. Today recipes are written into the repo; making one a
property of the engagement is phase P32, and requiring an approved recipe before client
work is P33. When your group wants a different sequence — *tag first, then normalise, then
build* — that is the conversation to have, and it becomes a recipe with your name on it.

---

## For an analyst: what you do

1. **Put the client's files in the engagement's folder.** Nothing else. No renaming
   convention to remember, no form to fill. On Setup, the engagement's **files** button
   shows that folder's full path (with a copy button), what is in it now, and takes files
   by drag and drop - the same as putting them in the folder, recorded against your name
   with each file's digest. It only writes where storage is a folder on this machine.
2. **Wait.** The system holds a set until it stops changing (30 minutes by default), so
   half-uploaded folders do not start half-runs.
3. **Answer what it asks.** Anything below its confidence floor, anything material, and
   anything a guard flagged comes to you as a review item under **Waiting on a person** on
   the Activity page; the Activity tab on every page shows how many are waiting, and so
   does the browser tab's title. **Review** opens the item: the question, the lines of the
   source it came from and why it came to a person — then **Show the proposal** for what
   the system suggests and how confident it is. Showing it is recorded, and Accept and
   Correct are not offered until you have. The run stops at that step and waits; nothing
   after it is built on an answer nobody gave. **Accept** it, **Correct** it (edit the
   proposed values), **Reject** it, or **Escalate** it; anything but accepting needs a
   reason, a correction needs the corrected value, and a decision on an item somebody else
   already decided is refused. The panel's *link to this item* opens the same item for a
   colleague you want to answer it. When the last open item
   on a run is answered, the run resumes on the next sweep — usually within a minute — from
   the step after the one it stopped at, replaying what it already did rather than paying
   for it twice.
4. **What your answer does.** An accepted or corrected tag or add-back becomes precedent:
   masked, and shown to the model on a later engagement in the same practice group as an
   example of how the firm decides. Only a decision a person made gets there; an item the
   system has no example shape for yet (a template input with nothing to bind) is refused
   on the record, not learned.
5. **Check the deliverable.** It arrives in the output folder as a workbook built from the
   firm's template, and the run's detail on Activity lists it under **Delivered** with a
   **Download**, beside the run manifest under **Record**. The same detail says which model
   produced it, what it spent against its ceiling, and - under **Decided on this run** -
   every question a person answered, what was proposed, what they decided and why. The download is checked against the digest recorded at release, so a file
   edited in the outbox afterwards is refused rather than passed off as the deliverable.
   Every figure traces back to a source file, sheet and cell.

**What it will never do**: conclude a value, sign anything, decide something material on
its own, or learn from its own unreviewed output. Only a decision a person actually made
becomes precedent.

### Checking a workbook, a report, or a whole folder

Three checks you can point at anything, whether this system made it or not. They are
useful on last year's model, on a client's own spreadsheet and on a report you are part
way through, and none of them changes the file.

```
python -m uv run python tools/aa.py review "C:/Clients/Northgate/2026"
```

That reads each file with whichever check it wants: a workbook goes to the formula audit,
a Word or Markdown document to the prose checks, a normalized table to the reasonableness
questions. One command over a client folder, and you do not have to know which is which.

**The formulas.** The one the suite could never catch: a total whose range stops a row
short of the block above it. It opens cleanly, prints a plausible number and is wrong by
one line. The audit also finds a total that counts another total, a typed number sitting in
a row of formulas, and a formula that breaks the pattern its neighbours share. Findings
come in three strengths - *wrong* means the file disagrees with itself and is provable;
*suspect* means a pattern break worth an eye; *convention* means a cross-sheet reference by
cell address, which on the firm's own model is everywhere and is off unless you ask for it.
It **never edits the workbook**.

**The prose.** Em dashes first, then the vocabulary and the rhythms that read as
machine-written; the mechanical slips (a word typed twice, a space before a comma, a
bracket that never closes); and the two spellings of one thing - *the Company* beside *the
company*, $1.2 million beside $1,200,000, two date formats in one document. Only the slips
are a failing exit, because an em dash is a judgement and no commit should fail over one.

```
python -m uv run python tools/prose_checks.py "draft.md" --fix --out fixed.md
```

`--fix` makes four mechanical substitutions and nothing else. It will not rewrite a
sentence, it will not touch a code block, it refuses a `.docx` outright (a paragraph's text
is split across runs that carry the formatting, and a substitution across a run boundary
loses the formatting after it), and it needs `--out` or `--in-place` - overwriting your
report is not a default.

**The figures.** The questions a reviewer asks on first looking at the numbers:
depreciation with no fixed assets, interest expense with no debt, tax in a loss year, a
margin or a working-capital ratio that has moved. **Every one is a question, not a
verdict** - whether a margin moving eight points is a problem depends on the business, and
the tool has no way to know. Nothing in it concludes anything about a valuation. The
tolerances are yours and have no defaults: a ratio you give no tolerance for is reported as
a question nobody asked rather than quietly left out.

Also on the run's detail on Activity: a **Check formulas** button beside each delivered
workbook. It re-reads the released file, which matters because one of the checks - whether
a saved total equals the cells it adds - cannot run until Excel has opened and saved the
file once.

### Asking from a terminal instead of a page

```
python -m uv run python tools/aa.py where HEND-2026-04    # the folder, and what is in it
python -m uv run python tools/aa.py owed HEND-2026-04     # what the client still owes
```

`owed` reads the folder against the engagement's request list and lists what is missing,
essential items first, plus any document that answered nothing on the list. It **writes
nothing**; `--write` refreshes the tracker workbook beside the folder, and anything you
wrote in that tracker is read back and kept.

If the client's documents are somewhere else - Box, a download folder - put them in with:

```
python -m uv run python tools/aa.py stage a.pdf b.xlsx --engagement HEND-2026-04 --who "your name" --why "where they came from"
```

Same thing as dropping them in the folder, recorded against you with each file's digest.

**What reaches the model, and what does not.** The client's name is masked before any
model sees it — the full name and each distinctive word of it on its own, so
"Henderson Income Statement.xlsx" names nobody. Anything shaped like a social security
number or an EIN stops the run before it leaves, whether or not anyone declared it. The
firm's own names — the reviewer on the engagement profile — are not client data and are
not masked. A file with a sentence aimed at the model in it is refused at intake, and the
run ends halted with that refusal as its reason.

**Seeing where a run went.** On a run's detail, **See the whole design** opens the whole
system at full size: all 118 parts where the design of record puts them, the lines between
them, and each part coloured by what this run did there — mint for done, plum for failed,
gold for the ones it never got to because it stopped first, and a dashed outline for the
ones this run had no use for. It opens on the place it stopped, at a size the labels can be
read at; **Where it ran** goes back to the whole run and **Show everything** to the whole
system.

The heading is the engagement, not the diagram: how many of the steps it planned are done,
what state the run is in, how long it took and what it cost. With nothing selected, the
panel answers the questions you came with — where it stopped and why, what it got through,
what it never got to, and what to do now, with the button that does it.

Each part the run went through carries its place in the order, and the arrows beside that
number walk the run one at a time (`n` and `p` from the keyboard). A dotted trail shows
where the run went next when the design has no line for that hop — which is most of them,
and worth knowing rather than drawing over. Clicking a part says what it is for, how long
it took there, what the run recorded against it in plain words, and — as links you can
follow — what feeds it and what it feeds. The find box takes a name, an id or a practice
group (`/` reaches it), and the key at the bottom left shows and hides by what happened,
so "just the failures" is one click.

All of it works from the keyboard, and the link in the address bar follows what you are
looking at: `#map=run_...` for the run, `#map=run_.../part_id` for one part of it.
**Copy a link to this** puts it on the clipboard, which is what to paste into a message
when the question is about that part.

**What the run's own page tells you afterwards.** Under **Decided on this run**: every
question a person answered, what the system had proposed, what they decided, their reason,
and whether they revealed the proposal before deciding or not. That last one is there because
a decision made without looking is a decision the record should be able to show. Beside it:
which model produced the run, what it spent against its ceiling, each step and how many
attempts it took, and - under **Record** - the run manifest.

**One thing it does not do yet.** A correction or a rejection is recorded, and it teaches
later runs through precedent. It does not amend *this* run's output: the step resumes from
what the model first produced. That is on [`BUILD/OPEN.md`](../BUILD/OPEN.md) as a decision
for the practice, and until it is answered the console does not claim otherwise.

**What to do when it stops.** It stops rather than guesses, and it says why in words with
a code — `CONFIG.METHODOLOGY_UNCLEARED`, `PRIVACY.UNMASKED_IDENTIFIER`. Every code carries
a "what to do now". If the answer is not obvious, the code is the thing to quote.

---

## For whoever runs it

### First day on a new machine

```
start.cmd                                 # Windows: all of the next three, then starts
uv sync                                   # install
cp .env.example .env                      # then add the Anthropic API key

python -m uv run python tools/serve.py --check             # what is ready, what is not
python -m uv run python tools/simulate_firm.py             # a generated firm through the real thing
python -m uv run python tools/simulate_firm.py --scripted  # the same, with the review loop walked end to end
python -m uv run python tools/serve.py                     # start it
```

The `python -m uv run` prefix is what puts the project's own dependencies on the path. A
bare `python -m uv run python tools/serve.py` works only in a shell where the virtualenv is already
activated; run without one it now tells you this rather than raising `ModuleNotFoundError`
about a library you have never heard of.

**Run the rehearsal before the first real engagement.** `tools/simulate_firm.py` starts
the real server, sets up three invented clients through the same API the page uses, puts
randomly generated workbooks shaped like an accountant's through it, drops a hostile file
and a stray folder, and tries the edge cases against the live surface. It prints what
happened at every step and ends with a list of findings — which should be empty. It found
nine bugs the test suite could not, because every fixture the suite had was shaped like a
test. Nothing in it is a real client.

**Run it again with `--scripted`.** Without a key the runs stop at the model door. With
`--scripted`, a scripted analyst answers every skill from the request — not analysis,
a stand-in shaped like it — so the runs go through timing, tagging, EBITDA and model-load,
stop for a person at each step with something to decide, are answered the way a reviewer
would answer on the Activity page, resume, and write precedent. That walk found fourteen
more bugs, among them a step the second client had "already done" because it was the first
client's, and a review queue nothing fed. It costs nothing and needs no key. It refuses to
run outside a rehearsal: the front door will not start on the scripted adapter unless
`AA_REHEARSAL=1` is set beside it, which the flag does for you.

Then, on the admin page, in this order:

1. **Initialise the environment.** A fresh install has no configuration; the page offers
   the button.
2. **Add a watch** — the folder tree to sweep — and a **destination** for deliverables.
3. **Clear the methodology.** Preflight fails until somebody has.
4. **Register an engagement** — its id, the client, the practice group picked from the
   list, the watch, the destination and its folder. It starts paused. A rush job can be
   given a shorter quiet period than the environment's, never a longer one.

   **The folder has to be exactly as deep as the watch looks.** A pattern watch at depth 2
   sweeps `<root>/<a>/<b>`, so its engagements are filed two levels down —
   `Henderson Manufacturing/2026 Valuation`, not `Henderson Manufacturing`. The form says
   how deep for whichever watch is selected, and registering refuses a folder that can
   never be swept; before it did, a folder one level too shallow gave a green Setup page,
   a correct-looking configuration, and no run, with nothing anywhere saying why.
5. **Complete its engagement profile.** The page offers a form with everything the
   system already knows filled in; the blanks are judgments — the industry code, the size
   band, the owner-compensation benchmark, who reviews and how quickly. The engagement list
   says beside each engagement what its profile still lacks, and `/admin#profile=<id>` opens
   the form directly for whoever owns the missing judgements. The JSON is one click away
   for anything the form does not cover. Three skills read
   it, so preflight will not activate an engagement without one.
6. **Activate it**, and check preflight passes for it first. It will tell you what is
   missing if it does not.

The model bindings — which model template each practice group builds into — come from
`templates/bindings.yaml` and are seeded when you initialise. Change them on the page or
in that file; a group bound to nothing falls through to the firm's default.

### Preflight

Fourteen checks over the live configuration, run before an engagement is activated and any
time you press the button. It is the difference between a setup mistake found now and a
run that fails at three in the afternoon. Each failure names the engagement it blocks and
what to do about it; a failure with no engagement named blocks everything.

### When something is wrong

- **The activity page** shows every run, its scorecard, the review queue and alerts. If it
  is down, runs continue — it reads the event log and drives nothing. Every page fits one
  screen: nothing is below the fold, and a panel with more than fits scrolls inside itself.
  Opening a run puts it in the address bar, so the link can be pasted to a colleague and
  opens on that run; with no link, the page opens on the run most likely to need you. Runs
  are listed by client, with their scope, how long ago they last did something, and - for
  one that stopped - the reason, in the three colours that carry meaning: mint fine, gold
  attention, plum a problem.
- **The run trace**, on that page, paints the whole design with what one run actually did:
  mint where a node passed, plum where one failed with its diagnostic underneath, a ring on
  whatever is running, and everything the run never touched left neutral. *Never ran* and
  *passed* are the two answers it matters most not to confuse, which is why the untouched
  nodes are shown rather than omitted.
- **The analytics page** answers the four questions that decide whether this is worth
  continuing: is it healthy (first-pass yield, where runs stop), what to fix first
  (failures ranked, each with the owner the diagnostics registry gives it — the largest
  class is usually client data, and no engineering removes that), is it getting better
  (auto-accept and override rates beside the human baseline, which reads `unmeasured`
  until two analysts have measured it on real line items), and is anything stuck.
- **Every run has a manifest**: what was in context, which model, which skill versions,
  which template, what each guard said. "Why did it do that" is a lookup, not an
  investigation.
- **A quarantined run** — one that stopped on itself, a step that failed in a way retrying
  will not fix — has two buttons on the Activity page. **Resume** picks it up again from
  where it stopped, replaying what it already did, once the cause is fixed: a corrected
  file, a cleared methodology, a key. **Halt** ends it, with a reason that is recorded, and
  writes its manifest. Neither touches a run a worker is holding, and neither works on a
  run a newer run has already replaced.
- **A file that launches nothing.** Files are typed from their names — `TB`, `trial
  balance`, `income statement`, `balance sheet`, `financials`, `IS`, `BS`, `FS` and the
  like, whole words only, so `IS 2025.xlsx` counts and `analysis.xlsx` does not. A client's
  forecast is its own type (`forecast`, `projection`, `budget`, `pro forma`) and never
  enters the historical table; a name that matches both - `Income Statement Forecast.xlsx`
  - is held rather than guessed. A name no convention claims is *held*: recorded, never
  guessed at, and it starts no clock. The Setup
  page's preflight names every held file and what to do — rename it, or add the name's
  token to the conventions on the Setup page. Nothing that is not cleared here can
  contribute a figure.
- **A run that stops on the client's name.** The client's name and its distinctive words
  are masked before the model sees anything, and the outbound scan stops any run in which
  one still appears — including inside the firm's own text. A worked example or a
  methodology file that names a client, even a synthetic one, will stop every run for that
  client; the fix is the file, not the guard. Ordinary words in a client's name — *Case*,
  *Summit*, *General* — are not treated as identifying on their own, so the firm's own
  vocabulary cannot trip it.
- **Nothing is deleted.** The event log is append-only and the run store keeps every
  version.

### What it costs

Each run has a budget ceiling and each step has one, from the firm's constraints; and an
engagement can carry its own, set on the Setup page, checked against everything that
engagement has spent across its runs. A run that would cross any of them halts and asks
rather than continuing and billing, and says which ceiling. Cost per run and per engagement
is on the Activity page.

**Roughly, on a real folder.** Thirteen documents from an actual engagement produced a
128 KB payload at timing, 102 KB at tagging and 305 KB at model-load. On the mid tier
(`claude-sonnet-5`, $2 per million in and $10 out) that is on the order of **a dollar for
one clean pass**, and a few dollars once the review loop has sent a step back once or
twice. The firm ceiling of $40 a run is a backstop, not a budget; set the engagement's own
to something you would not mind spending twice.

Those were measured before the payloads stopped being pretty-printed, and every one of
them is now about an eighth smaller. The dollar figure is unchanged, because whitespace is
the cheapest thing in a prompt. What it bought is headroom: the assembled context for a
step is refused above 400 KB, model-load is the step nearest that line, and how near it
comes is a function of how many line items the client has. A bigger client is the way this
run refuses, and there is now more room before it does.

### Watching a run while it happens

```
python -m uv run python tools/watch_run.py
```

Which step is going, how long it has been going against the bound its own step declared,
what has been spent, what is waiting on a person, and anything the stall detector raised.
`--once` prints a single look, which is the thing to paste when asking somebody what is
wrong. It reads and writes nothing, so it is safe to leave running beside a real run.

The first thing worth knowing: after the last file lands, nothing happens until the folder
has been quiet for the engagement's quiet period — thirty minutes by default. Shorten it
on the engagement's settings if you are testing and do not want to wait.

---

## The rules that are not configurable

Some things an administrator cannot change, on purpose. They are enforced by tests, not by
convention.

- **A skill proposes; it never acts.** Tools are reached by name through a guarded runtime
  after a policy gate authorises the call.
- **No model ever re-identifies masked data.** Unmasking is deterministic Python.
- **Client data never leaves the boundary unmasked**, and the outbound scan checks it
  every time.
- **Only a human decision becomes precedent.** A system that learns from its own
  unreviewed output drifts, invisibly.
- **An administrator may raise a review requirement, never lower one**, and may never
  disable a guard that fails closed.
- **Nothing concludes, signs or certifies.** No schema has a field a concluded value could
  be written to.

---

## Where the rest of it is written down

| | |
|---|---|
| [`../BUILD/STATE.md`](../BUILD/STATE.md) | What is built, what is next |
| [`../BUILD/OPEN.md`](../BUILD/OPEN.md) | What is waiting on a person, including you |
| [`architecture.html`](architecture.html) | The whole design: 118 components, every failure mode and its control. Open it in a browser |
| [`../HANDOFF.md`](../HANDOFF.md) | Moving it to another machine |
| [`../CHANGING.md`](../CHANGING.md) | Changing it without breaking it |

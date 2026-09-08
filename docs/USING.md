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
python tools/serve.py --check
```

---

## Starting it

```
python tools/serve.py
```

Then open:

- **http://127.0.0.1:8000/admin** — setup, engagements, practice groups, methodology
- **http://127.0.0.1:8000/** — the ops console: runs, steps, cost, the review queue
- **http://127.0.0.1:8000/analytics** — across every run: is it working, and what to fix

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
   convention to remember, no form to fill.
2. **Wait.** The system holds a set until it stops changing (30 minutes by default), so
   half-uploaded folders do not start half-runs.
3. **Answer what it asks.** Anything below its confidence floor, anything material, and
   anything a guard flagged comes to you as a review item on the Activity page — with the
   question, where it came from, and (on request) what it is proposing. The run stops at
   that step and waits; nothing after it is built on an answer nobody gave. **Accept** it
   or **Reject** it with a reason; a rejection or a correction without a reason is refused,
   and so is a decision on an item somebody else already decided. When the last open item
   on a run is answered, the run resumes on the next sweep — usually within a minute — from
   the step after the one it stopped at, replaying what it already did rather than paying
   for it twice.
4. **What your answer does.** An accepted or corrected tag or add-back becomes precedent:
   masked, and shown to the model on a later engagement in the same practice group as an
   example of how the firm decides. Only a decision a person made gets there; an item the
   system has no example shape for yet (a template input with nothing to bind) is refused
   on the record, not learned.
5. **Check the deliverable.** It arrives in the output folder as a workbook built from the
   firm's template. Every figure traces back to a source file, sheet and cell.

**What it will never do**: conclude a value, sign anything, decide something material on
its own, or learn from its own unreviewed output. Only a decision a person actually made
becomes precedent.

**What reaches the model, and what does not.** The client's name is masked before any
model sees it — the full name and each distinctive word of it on its own, so
"Henderson Income Statement.xlsx" names nobody. Anything shaped like a social security
number or an EIN stops the run before it leaves, whether or not anyone declared it. The
firm's own names — the reviewer on the engagement profile — are not client data and are
not masked. A file with a sentence aimed at the model in it is refused at intake, and the
run ends halted with that refusal as its reason.

**What to do when it stops.** It stops rather than guesses, and it says why in words with
a code — `CONFIG.METHODOLOGY_UNCLEARED`, `PRIVACY.UNMASKED_IDENTIFIER`. Every code carries
a "what to do now". If the answer is not obvious, the code is the thing to quote.

---

## For whoever runs it

### First day on a new machine

```
uv sync                                   # install
cp .env.example .env                      # then add the Anthropic API key
python tools/serve.py --check             # what is ready, what is not
python tools/simulate_firm.py             # a generated firm through the real thing
python tools/simulate_firm.py --scripted  # the same, with the review loop walked end to end
python tools/serve.py                     # start it
```

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
5. **Complete its engagement profile.** The page offers a skeleton with everything the
   system already knows filled in; the blanks are judgments — the industry code, the size
   band, the owner-compensation benchmark, who reviews and how quickly. Three skills read
   it, so preflight will not activate an engagement without one.
6. **Activate it**, and check preflight passes for it first. It will tell you what is
   missing if it does not.

The model bindings — which model template each practice group builds into — come from
`templates/bindings.yaml` and are seeded when you initialise. Change them on the page or
in that file; a group bound to nothing falls through to the firm's default.

### Preflight

Thirteen checks over the live configuration, run before an engagement is activated and any
time you press the button. It is the difference between a setup mistake found now and a
run that fails at three in the afternoon. Each failure names the engagement it blocks and
what to do about it; a failure with no engagement named blocks everything.

### When something is wrong

- **The activity page** shows every run, its scorecard, the review queue and alerts. If it
  is down, runs continue — it reads the event log and drives nothing. Every page fits one
  screen: nothing is below the fold, and a panel with more than fits scrolls inside itself.
  Opening a run puts it in the address bar, so the link can be pasted to a colleague and
  opens on that run.
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
  like, whole words only, so `IS 2025.xlsx` counts and `analysis.xlsx` does not. A name no
  convention claims is *held*: recorded, never guessed at, and it starts no clock. The Setup
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

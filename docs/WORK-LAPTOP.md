# The work laptop: from clone to first run

Written 2026-10-06 for the morning this repository is cloned onto a Chartwell machine. It is
the order to do things in, what each step writes, and what will refuse you until the step
before it is done. Everything here is also in [`USING.md`](USING.md) at greater length; this
is the short path. Where a step was not rehearsed on a fresh clone it says so.

## 1. Clone and install

```
git clone https://github.com/CalebSmit/auto-analyst.git
cd auto-analyst
python -m uv sync
python -m uv run python tools/synthesize_templates.py    # the three template workbooks
python -m uv run python tools/serve.py --check
```

`templates/*.xlsx` is not in git - a template is generated from its input schema, so the
synthesizer is the step that puts the files there. Skip it and `--check` lists every
practice group under *no model set up here*, with the command in the sentence. `start.cmd`
runs it for you. On a fresh clone `--check` ends with *nothing is set up yet on this
machine* and exits 1: that is the expected first answer, not a fault, and it turns to 0
once the environment is initialised and preflight passes.

**The first line it prints is about the vault, and it is expected.** `--check` runs before
the step below that sets `AA_VAULT_KEY`, so on the first morning there is never a key yet and
it says so: *no run can be picked up yet - the mask vault will not open*, with the command
that generates a key. Everything under it still reports honestly; `start.cmd` generates the
key for you and this line goes.

`uv` has to be on PATH; `start.cmd` installs it if it is not. The `python -m uv run` prefix
is what puts the project's dependencies on the path - every command in every document
carries it, and `tests/p58` holds them to it. `--check` is the honest answer to "does this
work yet": every seam it prints as `[ok]` is joined; NOT INSTALLED waits on software;
NOT WIRED is a join this build has not made. On a fresh clone expect two things it says
plainly: the model port is `fake`, and scans read as nothing until an OCR engine is named.

**`start.cmd` / `tools/start.ps1 -SetupOnly` ask for the API key interactively.** Run them in
a terminal you are sitting at; run non-interactively they wait on that prompt.

**The fresh-clone rehearsal was run to the end on 2026-10-07** - `git clone` from GitHub,
`uv sync`, `synthesize_templates`, `--check`, then both rehearsals against the clone's own
server, then the four consoles opened on it. Both rehearsals reported **no findings**, and
every page swept clean. What it found was the two sentences above: the ordinal for
`model_answers`, and the vault line nothing warned you about (P174).

The run before it, on 2026-10-06, found four things, all fixed as P169: the rehearsals never
approved a recipe (they had been riding on the register the test suite leaves behind on a
developer's machine), preflight called a never-approved recipe *does not compile*, the files
rehearsal said nothing launched without saying why, and the install step above did not
produce the templates. Step 3's second item - approve a recipe - is the one that was missing
from every automated path; it is still yours to do by hand.

**One thing the rehearsal leaves behind, so it does not surprise you.** Running either
rehearsal in the clone writes `foundations/cleared.yaml` and `recipes/registered.yaml` -
both gitignored - so afterwards the Setup page shows the methodology already cleared and a
recipe already approved, under the rehearsal's name rather than yours. On a clone you have
not rehearsed in, step 3's items two and three are genuinely yours to do. Delete those two
files to get the first morning back.

## 2. Set the two adapters a work machine needs

Copy `.env.example` to `.env` and set:

```
AA_LLM_ADAPTER=anthropic_messages
ANTHROPIC_API_KEY=...            # the firm's key; the name the adapter declares
AA_OCR_ADAPTER=rapidocr          # a wheel, no administrator needed
AA_VAULT_KEY=...                 # start.ps1 generates one; the pool will not start without it
```

Without the first two, **preflight warns on the `model_answers` check** - *the model adapter
answers from a model, and its key is present*, third in the list of sixteen - and
fails it outright once an answering adapter is named without its key. That is deliberate: before P168 a machine on the fake adapter set up an engagement,
passed preflight, launched a run and failed at its first skill step with a sentence written
for a developer. Without `AA_OCR_ADAPTER`, every scanned PDF reads as nothing and is
*reported* as a scan nothing read (P166), which is correct and useless. `serve.py` reads
`.env` on start; the shell wins where both set a value.

## 3. Start it, and do the three things a fresh machine owes

```
python -m uv run python tools/serve.py        # admin at /admin, the ops console at /, help at /help
```

On the Setup page, in this order - each is a gate the next waits on:

1. **Initialise the environment**, add a **watch** (the folder tree to sweep) and a
   **destination** (where deliverables go).
2. **Approve a recipe.** `recipes/registered.yaml` is not in git, so a fresh clone has no
   approved recipe and nothing launches until one is approved under your name. Version 1's
   recipe is `valuation-input-prep`.
3. **Clear the methodology.** `foundations/cleared.yaml` is not in git either: a clearance
   is a person's act and is never shipped. There are **ten** files - the firm's three under
   `foundations/_firm/`, the valuation group's six under `foundations/valuation/_group/`
   (EBITDA adjustments, the working-capital exclusions and normal level, guideline company
   screening, the cost-of-capital inputs, report writing), and the non-ESOP segment's one.
   Read each, then clear it at `/admin`. Half an hour. Until every file a run resolves is
   cleared, preflight is red and no run starts.
4. **Register an engagement** - id, client, practice group (`valuation / non-esop /
   repeat` or `non-repeat`), watch, destination, folder - and **activate** it. Preflight runs
   on activation and refuses with a sentence naming what is missing.

Then drop the client's files into the engagement's folder (`python -m uv run python
tools/aa.py where <ENGAGEMENT>` prints it). A run waits for the quiet period and for the
recipe's required document types, then launches; `python -m uv run python tools/watch_run.py
--once` says what it is doing.

## 4. Where your data is

Everything the tool knows - runs, every figure it read, every decision, every precedent, the
roster and the configuration - is **one SQLite file**: `runs/run_store.db` under the clone
(or wherever `AA_DB_URL` points). It is not in git. A reclone, a `git clean` or a wiped
folder loses all of it. `serve.py --check` prints the path; copy that file somewhere safe on
a schedule. The mask vault is a second small database beside it, and `.env` holds the keys.

## 5. Teaching it what the firm knows

This is the part the work machine exists for. Three places, three kinds of knowledge:

- **`knowledge/methodology/`** - six files the model's rules come from. Each has *what we
  know* (cited to an interview), *what the model should do with it*, and *what is still
  unknown* - the questions to answer here, where the real documents and the firm's model
  are. Answer one by moving it into *what we know* with its source, update the rules if it
  changes them, copy the rules section into the matching `foundations/valuation/_group/`
  file, and clear that file again. [`knowledge/methodology/README.md`](../knowledge/methodology/README.md)
  says how; `tests/p167` holds the pair together.
- **`/improve-agent`** (Cursor or Claude Code) - the interview. It asks one question at a
  time from `interview/topics.yaml`, records answers under `knowledge/`, and turns what it
  learns into changes through the gate. The topics that fed the retired compute skills feed
  the methodology files now. Run `python -m uv run python tools/interview.py status` first:
  it says where the interview stands and what version 1 still lacks.
- **The firm's model.** `python -m uv run python tools/read_template.py <Model Template -
  MASTER 2026.xlsx> --sheet Input --inventory` writes every defined name and what sits
  behind it, and `--version 2026.1 --out draft.yaml` writes the draft input schema. Every
  line in the draft is marked `REVIEW` and will not load until you have read it - the schema
  binds the firm's model by named range, and a name is a convention, not a statement.

- **Your model-setup skill.** Section 8 says where it goes, what its front matter must
  declare, and which of its two paths the build already has a slot for.

**Before any session ends:** `python -m uv run python tools/interview.py scan` must print
`clean`. `knowledge/identifiers.txt` holds the client names the scan looks for; add a new
client's name there the day you first type it. Nothing identifying leaves `knowledge/`.

## 6. What to expect on the first real files

- A file no document type claims by name is **held**, and the sweep prints it; the Setup
  page's conventions say which name tokens bind to which type.
- Every extracted figure goes to a person unless a total it feeds re-adds from its rows -
  and a total whose sign contradicts its label withdraws that cover (P164). Expect to see
  most of the first statement.
- A CSV telling two decimal stories, a protected workbook, a PDF under a spreadsheet name, a
  tab-separated file named `.xls`, a UTF-16 export: each gets the sentence that is true of
  it (P166). "Ask the client for a readable copy" now means the file is actually broken.
- If the laptop closes mid-run, the next start picks the run back up and says so (P168).
- `docs/USING.md` §"Right now" lists what does not work yet; `BUILD/OPEN.md` lists what
  waits on a person, which from this machine is mostly you.

## 7. Known limits, so they are not discoveries

`.doc`, `.xlsb` and `.msg` are refused by name until a real sample exists. Nothing bounds
intake size (B-146). A rejection in the review queue is recorded and does not yet change the
run it was made on (B-152). ShareFile is proved only against a fake (B-056). The delivery
templates repository the branding will come from was not found under this GitHub account on
2026-10-06 - say where it is and the report-writing file gets its first real section.

## 8. Bringing the model-setup skill

You have a skill - a file and a folder - that sets the firm's model up from scratch out of
client documents, and sets it up for a repeat client by reading last year's model. This is
where it goes and what has to be true of it, so the day it arrives is a copy and not a port.

**Where.** `skills/valuation/_group/model-setup/SKILL.md`, with its supporting documents in
`skills/valuation/_group/model-setup/references/`. The valuation group is the layer because
the model is the valuation practice's model; a skill written at the firm layer would be
offered to consulting and corporate finance, which do not build into it. The skill tree
([`skills/README.md`](../skills/README.md)) reads the folder on the next start.

**The front matter it needs.** `registries/skills.py` refuses a SKILL.md missing any of
these, because each is something the Policy Gate or the dispatcher enforces: `name`,
`version`, `status`, `scope`, `title`, `description`, `tier`, `inputs`, `outputs`, `tools`,
`data_sensitivity`, `hitl`, `output_contract`. Copy the block from
[`skills/valuation/_group/model-load/SKILL.md`](../skills/valuation/_group/model-load/SKILL.md)
and change the values; `scope: valuation/_group`, `data_sensitivity: masked_only`, and
`status: draft` until the board has registered it - a draft is read into the index and
dispatched by nothing, which is the right state for a skill on its first day here.

**The two paths it already knows about.** From-scratch is `model-load` territory: the
input schema under `templates/inputs/` says which named range each line binds to, and
`python -m uv run python tools/read_template.py <model.xlsx> --sheet Input --inventory`
writes every defined name in the firm's model so the skill's instructions can name them.
Repeat-client is `prior-year-rollforward` in `skills/valuation/_repeat/` - a skeleton today,
and the slot your "look at the old model" procedure fills: the prior workbook is the chart
of accounts for three quarters of the work, and that skill is where the build already
expects that to be said.

**What may not go in the skill.** Anything that names a client. The skill tree is read by
the model on every run and `python -m uv run python tools/interview.py scan` refuses a
client's name anywhere outside `knowledge/`. Worked examples with real names, last year's
models, the engagements you learned the procedure on - those go under
[`knowledge/model-setup/`](../knowledge/model-setup/), which is committed, private, and
never reaches a prompt. The skill cites them by what they are, not who they were.

**What the methodology files already hold.** The six files under `knowledge/methodology/`
are where the model's *rules* live - EBITDA adjustments, working capital, screening, the
cost-of-capital inputs, report writing. Your skill is the *procedure* that applies them in
the workbook. Where the skill states a rule the files do not have, move the rule into the
file (and its `foundations/` twin) and let the skill point at it; the rules reach every
model call that way, and the skill stays about the model.

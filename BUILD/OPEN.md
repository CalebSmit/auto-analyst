# Open: what is waiting on you

Everything blocked on a person, in one place, so nothing is carried in a chat log or in
somebody's memory. Four kinds, by what unblocks them.

Each entry says what I need, why it is blocked, and what happens the moment I have it.
Nothing here is a nag: several are deliberately unanswered because the answer is a
judgment that is not the code's to make.

**Where this fits.** [`STATE.md`](STATE.md) says where the build is. [`PLAN.md`](PLAN.md)
says what is left to do. This file says what is left to *decide*, and by whom. When an
item is answered, the answer goes into the record it belongs to - a `gate close --signoff`,
a `gate amend`, a task ticked - and the entry moves to **Settled** at the foot with a
date, rather than being deleted.

---

## 1. Waiting on your word

| | What I need | Why it is blocked | When you answer |
|---|---|---|---|
| **The firm's house style, as rules** | `tools/prose_checks.py` reads a report for the marks of machine-written prose and for the two spellings of one thing, and every rule in it is one **this build inferred**: that the house dash is a spaced hyphen rather than an em dash, that `the Company` is a defined term and `the company` is a slip, which register words are tells. The checks run where the prose actually moves - setting up an appendix reports them in the preview - so they are in front of somebody on every report. | A house style is a thing a firm has and a thing a file cannot state. Writing the firm's down as a guess would be this build setting the convention it is supposed to be checking against, and the first symptom would be an analyst told that correct prose is wrong - after which nothing else the tool says about a report gets read. | The rules go into the checks, and the inferred ones come out. It is the `report-and-deck` interview topic (B-091): which dash, how amounts are written, how the valuation date is referred to, and which terms are capitalised because they are defined. `tests/checkpoints/c73` asserts the topic is still open, so this cannot be quietly treated as answered. |
| **What counts as a move** | `tools/reasonableness.py` asks what a reviewer asks of the numbers - a margin that has moved, days receivable that have moved, a current ratio that has moved - and it has **no default tolerance for any of them**. A ratio you give no tolerance for is reported as a question nobody asked rather than quietly left out, which is honest and is not an answer. | It is the same decision as the materiality threshold in section 2, in a second place, and it is per *unit*: points for a margin, days for a working-capital ratio, turns for the current ratio. One number across all three is right for one of them. A default here would be this build setting a materiality threshold, which section 2 says belongs to the practice. | The numbers go on the engagement or in the practice's policy, the command stops needing them typed, and the questions get asked of every table rather than of the ones somebody remembered to pass a flag to. |
| **What is on the restricted-use deck** | Nothing. `report/` is Word-only - `python-docx` is a dependency, `python-pptx` is not, and nothing in this build has ever opened a `.pptx` - while the restricted-use PowerPoint is a thing you build at work beside the report. | `report/` works because it binds by **name**: a bookmark or a heading, never a paragraph index. The deck equivalent is a named placeholder or a named shape, and which one your template uses is not knowable from here. A deck path built on a guess would bind by slide index, which is `B44` with a different spelling - and the failure mode is an exhibit landing on the wrong slide in a deck that opens perfectly. | It is a straight port of a pattern that already works: find the place by name, move the content with the things that make it render, never edit the file that was read. Recorded as B-094, and the second half of the `report-and-deck` topic asks for it. |
| **The model, now that there is a tool waiting for it** | `Model Template - MASTER 2026`, which this file has carried since P24. What changed is what happens when it arrives: `tools/read_template.py` reads every defined name, the cell behind it and whether that cell is empty, and writes a draft input schema in the shape the registry loads. The four hundred lines of YAML are no longer the work. | Not blocked on a decision any more - blocked on the file, plus about an hour of your reading. Every `line:` in the draft is marked `REVIEW` and the draft **will not load** until the markers are gone, because reading `Revenue_FY1` as the line *Revenue* in period *FY1* is reading a naming convention, and a convention is a thing a firm has. | Run it against a blank copy, answer the `line:` values, save it as `templates/inputs/<file>@<version>.yaml` and bind it at a scope on Setup. Then B-008 and the roll-forward's Excel half (B-036) both unblock. |
| **What a correction does to the run it was made on** | Today: nothing. A reviewer's `answer` is read in exactly two places, both in `precedent/writeback.py`, and both teach *later* runs. The step this run resumes on is satisfied from the ledger - the model's original output - so a corrected value does not reach the deliverable, and a **rejected** proposal is delivered anyway. The console says "corrected: ... the run resumes on the next sweep", which reads as though it took effect. | It is a design decision with three defensible answers, and it is yours: (a) a rejection quarantines the step and the run stops for a person; (b) a correction re-derives the step's output from the answer and commits a new ledger entry under a new step key; (c) both. (b) is the one that changes what a deliverable contains, so it needs your word, not an inference from mine. Found by the AI-architecture review, 2026-09-17; the behaviour is confirmed in the code, not assumed. | I build the answer you give, and the review surface stops promising what it does not do. Until then the console says plainly that a decision is recorded and does not amend this run. |
| **A run records work against a node the design does not have** | Every run emits against `run_driver`, and the blueprint has no such node. P48 draws all 118 nodes beside everything a run recorded, which is the first thing that has ever compared the two - so the map reports it under "not on this map" rather than dropping it. | Two defensible answers, and the choice is a design one: the blueprint gains a node for the worker that carries a run (it already draws `step_executor`, `orchestrator` and `queue_port` around it), or the driver emits against one of those instead. The first is an edit to the design of record; the second changes what every existing run's trace says. | I make the change and re-export, and the map has nothing left to report. |
| **How much review is the right amount** | P86 measures it for the first time: on the Henderson fixture `ebitda-normalization` sends **eleven of eighteen** add-backs to a person, a rate of 0.61. Nothing said so before - the evals reported recall and agreement, which a skill can score well on by routing everything and answering nothing. The two failure kinds beside it are gated at zero, because a figure whose locator does not resolve is not a figure and a recompute either falls inside the practice's tolerance or does not; this one is not gated, because what it is allowed to be is a judgement about how much of the analyst's day the tool is meant to give back. | It is the pilot's question rather than the code's. A threshold typed here would be a number nobody decided, sitting in the file that decides whether a skill may register. | `sent_to_a_person_rate` becomes a gate in `evals/gates.yaml` with the number you set, and a skill that routes more than that stops registering. Until then it is reported on every scorecard and gates nothing. |
| **Where the unmask belongs** | Nothing in production imports `privacy/unmask.py` or `privacy/verify.py` - the whole unmask half of the privacy band reaches nothing, while masking is wired in six places. So every run masks and no run has ever resolved a token back. Three things say that is wrong rather than deliberate: the blueprint asserts every deliverable is dominated by `unmask_verify`, `guards/__init__.py` calls the integrity check "the sixth guard", and `deliver/builder.py` opens by claiming its inputs are unmasked. It has not bitten because no run has reached `release`; when one does, `DeliverableQC` - which *is* wired - will fail the workbook for a residual token, and be right. Found 2026-09-20 by P82's reachability scan. | Two defensible places and the choice is a design one. **(a) On the release path, before QC**: the deliverable is unmasked and verified once, and tokens stay in the review queue, so a reviewer sees `CLIENT_a1b2` where the client's name belongs. **(b) On each step's output as it returns from the model**: a reviewer reads real names, and what precedent records changes - precedent is masked on purpose, so this needs care. The blueprint draws both nodes between the model band and the deliverable, which points at (a), but pointing is not deciding. | I wire it where you say and the run that first reaches release delivers instead of quarantining on its own workbook. Recorded as B-043. |
| ~~Version 1 has no recipe it can finish~~ | **Answered 2026-09-21 (session 5).** The deliverable is a *separate workbook laid out like the model*, not the model: "It won't go directly into the model... so I can just copy and paste the data over." And the layout may be **guessed now and corrected later** - which the refusal in section 4d does not contradict, because that refusal was about binding a guessed template at the focus scope, where a wrong guess changes what every non-ESOP run writes into the firm's own model. This writes into a workbook of our own, so a wrong guess costs a re-layout. | - | B-033 and B-034 no longer wait on `Model Template - MASTER 2026`. |
| **Two skills have no mechanical half** | `qc-tieout`, which both shipped recipes end with, and `ddr-tagging` in the full intake. Each needs a procedure - the deterministic half that says what the model is shown and what it must return - beside the four that have one. | Skill work rather than plumbing: the run reaches the step and stops there with it named, which is correct and is not finishing. Everything around them is joined - a released run is picked up, driven, masked, checked and recorded. **Two things looked at on 2026-09-18 (P63) that B-004 needs from you before it can be built honestly.** (a) *The tolerance.* `tools/statement_checks.run_checks` takes one and has no default on purpose - "materiality belongs to the practice". The engagement policy already carries `materiality.amount`, set at /admin and **defaulting to 0**, so a penny's difference would fail every check. Whether QC's tolerance is that same figure or its own is a practice decision. (b) *The movement threshold* has no source at all: `references/movement-thresholds.md` is a placeholder. Absent one, movements are not evaluated, and the checklist must say so rather than omit them silently. And the skill body itself is a rewrite, so it goes **through the governance chain** and ends at a board approval, which is your act, not mine. | A run of `monthly-refresh` reaches `release` and a workbook lands in the outbox. |
| ~~P28 sign-off~~ | **Signed 2026-09-05**, and this row outlived it: *"podman 6.1.1 here, image built from a clean clone, 1711 passed / 78 skipped inside it. Nothing but `.env` changes."* What is still owed is the work-machine clone itself, which is in §4 where evidence only that machine can produce belongs. | - | done |
| **The P26 sign-off wording** | Optional. The recorded sign-off reads "Caleb: it all looks good", which does not say what you checked. | Nothing is broken. It is a thin line in a permanent record, beside three others that name what was reviewed. | `gate amend P26 --reopen`, then close again with fuller words. The three checks re-run first. |
| **Egress from Azure to the Anthropic API** | Confirmation from IT that a container in Azure may reach `api.anthropic.com`. | The 2026-09-05 decision is to call the Anthropic API directly from wherever the system runs. A refusal is the one thing that would force a provider-hosted route, and with it the model-pin change. | Nothing changes and the decision stands. If it is refused, the Foundry adapter and the platform-aware pin get scoped. |
| **Which identity provider** | Which provider vouches for a name at the firm - Entra ID if Azure is confirmed - and who is allowed to activate an engagement, change a budget or clear methodology. | P36 built the port and a local adapter: the name on every change is now the operating-system user, and the adapter refuses any request that did not come from this machine, so binding the surface to a network address does not quietly work. What it cannot do is authenticate somebody at the firm. | An adapter behind `ports/identity/`, and `AA_IDENTITY_ADAPTER` names it. Nothing else changes: the admin surface does not know which provider answers. |
| **A real Redis** | A reachable server, once. | The queue adapter has only ever run against an in-memory fake. That proves its use of RQ, not Redis. | `pytest --redis` goes green and the session summary stops saying FAKED. |
| **Clearing the firm's methodology** | Somebody at Chartwell reads `foundations/qc-conventions.md`, `tagging-policy.md` and `valuation-standards.md` and clears each one under their own name. | P30 made methodology cleared-once, checked-every-run, and a clone starts with nothing cleared on purpose - a clearance records that a person read a file, so shipping one would record a decision nobody made. The suite clears them for itself; a real install does not. | `POST /api/admin/methodology/{name}/clear` with your name, or `AdminConsole.clear_methodology`. Preflight stops saying every run is blocked. |

---

## 2. Decisions that are yours, not the code's

The blueprint names nine. **No answer to any of them is recorded in this repo**, which is
a statement about the record rather than about you - if a decision has been made, tell me
and it goes in.

| Decision | Who the blueprint names | By when |
|---|---|---|
| Name an accountable owner for review quality | MD sponsor | Before phase 1 |
| Confirm the client engagement letters permit processing on the firm's Claude account | MD + risk | Before phase 1 |
| Fund the baseline measurement: two analysts, ~200 line items, about a day | MD sponsor | Before phase 1 |
| Set the mask vault retention policy | Risk / IT | Before phase 1 |
| Set materiality thresholds and the auto-accept confidence bar | Practice lead + QC | Before phase 2 |
| Name the segments for Consulting and Corporate Finance | Practice leads | Before those groups onboard |
| Name a skill owner and a reviewer per practice group | MD sponsor | Before phase 2 |
| Decide who sits on the Skill Review Board | MD sponsor | Before phase 2 |
| Confirm ShareFile and Box access, and who owns the credentials | IT | Before phase 3 |

Three of those have a direct consequence in the code today:

- **The auto-accept bar.** Half of this decision is answered and half is not, so the row
  above stays live. **Answered 2026-09-18 (P67), for figures read out of a client
  document, and not as a number:** such a figure is accepted unseen only when it carries
  its source locator *and* every total it feeds re-adds; anything no arithmetic covers is
  shown, every one of them, not only what changed since last year. That is a rule about
  evidence, which is the right instrument when most of the input is OCR'd scans - a
  confidently wrong read is what a probability cannot catch and a failed footing can.
  **Still owed: the materiality threshold**, and the bar for a *judgement* a skill
  proposes, which is still a number and still unset - so those items all go to a person.
- **The vault retention policy** is a placeholder of 730 days in `.env.example`.
- **The Consulting and Corporate Finance segments** are scaffolded and empty, so those
  scope paths resolve to the firm layer only. Correct, but not useful.

---

## 3. On this machine, before the work machine

Small, and none of it blocked on anybody but you.

| | What is owed | Why it is worth doing here |
|---|---|---|
| **Run the rehearsal, twice, then one real engagement** | `python tools/simulate_firm.py` first - a generated firm through the real server, ending in a list of findings that should be empty. Then `python tools/simulate_firm.py --scripted`: the same firm with a scripted analyst answering for the model, so the runs reach the review queue, are answered the way a reviewer would answer, resume, and write precedent - it should report both runs went through timing, tagging, EBITDA and model-load, paused for a person and resumed, and wrote precedent. Then start it, set up an engagement at `/admin`, drop a couple of workbooks in its folder and watch the activity page. | The first rehearsal found nine bugs the suite could not; the second found fourteen more, including a run that reused another client's normalized table and a review queue nothing fed. Run both on any machine before real files go in. Expect a real run to stop at the model door until an API key is in `.env`, and at `qc-tieout` after - both are the system working. |
| **Keep client names out of the firm's own text** | Before clearing a methodology file or adding a skill reference, read it for a client's name. The EBITDA skill's worked examples named the synthetic fixture client, and every run for that client stopped on the outbound scan - correctly. | The scan reads the firm's text beside the payload. A reference naming a real past client would stop every run for that client, and the fix is the file. Precedent is the place approved examples live, masked; a reference is not. |
| **Clear the methodology** | Read the three files in `foundations/_firm/` and clear each one at `/admin`. Ten minutes. | Until somebody does, preflight fails and no run can start. Doing it here is also the rehearsal for doing it at work. |
| **Set up one engagement end to end** | Initialise the environment at `/admin`, add a watch, a destination and one engagement with a synthetic client folder. | It is the only way to find out whether the dashboard makes sense to somebody who did not build it - which is the question, and you are the closest available reader. |
| **A real Redis, once** | Start a server and run `pytest --redis`. | The queue adapter has only ever run against an in-memory fake. |
| **Postgres, once** | `pytest --postgres` against a local server. | Sixty-five store conformance tests are green on one backend of two. |

---

## 4. Evidence only the work machine can produce

These are tasks on P28. They are not code waiting to be written; each is evidence
somebody has to gather, and none of it can be gathered here. P28 closes on the proof
this machine could give; these stay owed against the work machine, and P30 onward
does not wait for them.

| | What is owed | Deferred from |
|---|---|---|
| **Timing alignment** | Confirm the alignment on a real engagement's files, and tailor the normalized table to the firm's Excel models. | P18, through P24 and P25 |
| **The firm's chart of accounts** | Publish Chartwell's conventions as a new taxonomy version - never edit `coa-taxonomy@1.0.0` in place - measure the two-analyst baseline on 200 real line items, and rebuild `fixtures/skills/line-item-tagging`. | P19, through P24 |
| **Real add-backs** | An analyst confirms the add-backs proposed on a real engagement are defensible and that nothing material was auto-accepted; rebuild `fixtures/skills/ebitda-normalization`. | P20, through P24 |
| **The model builder** | Read the work repo, reconcile its named-range binding with `tools/write_template.py`, and register the real templates with their input schemas. | P24 |
| **The work-machine clone** | Clone the repo there, run the suite in the container, and confirm nothing but `.env` had to change. Proven here on podman 6.1.1; unproven there. | P28 |

Two more, smaller:

- **`CF_LBO_Model_v3`** is bound at `corporate-finance/_group` with no master file and no
  input schema. Preflight reports it as `CONFIG.TEMPLATE_UNREGISTERED` every time.
  Register it or unbind it.
- **The human baseline override rate** is unmeasured, so the analytics compare against
  "unmeasured" rather than against a number. It comes from the baseline measurement above.

---

## 4c. Found on 2026-09-18 by running the interview's own commands

Three defects in `tools/interview.py`, all found by invoking it rather than reading it, and
all in the path the next session walks. Fixed the same day (P64, P65); recorded because two
of them destroyed real records in this repo before they were fixed, and because what they
have in common is worth remembering.

| | What was wrong | Where it went |
|---|---|---|
| ~~An acknowledgement covered sessions that came after it~~ | **Done 2026-09-18, P64.** The empty-register acknowledgement expired by date, and a session logged the same calendar day counted as covered. That was deliberate - the legitimate flow is to finish a session and then record that nobody was named, which happens on one day - but it also covered a session that had not happened when the line was written. Acknowledge in the morning, interview in the afternoon, and `scan` prints `clean` over answers nobody looked at. `CLAUDE.md` and `PROTOCOL.md` both already said it expires "as soon as another session is logged"; the code did not. A date cannot separate the two orderings, so the acknowledgement now records the sessions it was made over. | - |
| ~~`register --none` destroyed a recorded decision~~ | **Done 2026-09-18, P65.** With no text it supplied a note of its own, and `record_review` replaced any standing acknowledgement silently, exiting 0. One careless invocation during this build destroyed the register's real acknowledgement. Both rules it needed already exist elsewhere in this repo: a methodology clearance cannot be written by the code, and P57 refuses to re-approve a recipe at bytes already approved because that records a decision which changed nothing. Renewing a *stale* acknowledgement is still allowed, because that is the act. | - |
| ~~Two ways to find `knowledge/`~~ | **Done 2026-09-18, P65.** The module attribute `KNOWLEDGE`, which a caller can redirect, and parameter defaults bound at definition, which silently cannot. A CLI handler relying on the second reached the real folder however the first was set - which is how a test in this build wrote to the repo's own `coverage.yaml` and downgraded a topic from covered to partial. Every handler now names the folder it works on, and `tests/p65::test_no_command_touches_the_real_knowledge_folder` fingerprints the real directory around every command. | - |

**What the three have in common.** Each was invisible to the test suite because the suite
exercised the functions and not the command, or exercised the command against state that
happened to make the bug unreachable. The rehearsals exist for exactly this reason on the
server side; the interview had no equivalent until now.

---

## 4b. Found on 2026-09-17, not yet fixed

Three reviews - an engine defect hunt, a read of the tool as the analyst who has to use
it, and a security audit - ran over the whole system. Three findings were fixed the same
night (P53). These are the rest. Each was reproduced against the code before it was
written down; none is a suspicion.

| | What is wrong | Why it is not fixed yet | Size |
|---|---|---|---|
| **Self-verification is declared on a skill that cannot verify** | The blueprint's loop table gives the trigger as *"every DDR tagging and EBITDA output, always"*, and every shipped recipe declares `self_verification` on `tagging` as well as `ebitda`. Only `ebitda-normalization` has a verification procedure: `verifier_for("line-item-tagging")` raises. P59 made the guard-triggered loops real and found this on the way - making the runner demand the pass is two lines, and doing it quarantines **every run** at tagging with "no verification pass", which is the system correctly refusing to pretend a declared control ran, and is also every run stopping. So the control has never run on any output, on any run, since it was declared. | **Two defensible answers and the choice is yours.** (a) Build the tagging verifier - skill work, through the governance chain, and the honest reading of the blueprint. (b) Drop `self_verification` from the tagging step - a recipe change, so the plan hash moves and every registered recipe needs re-approving. I will not pick: (a) is a new skill and (b) removes a control the design asks for. Pinned by `tests/p59::test_self_verification_is_declared_on_a_skill_that_cannot_verify`, which **fails when the gap closes**, so whoever closes it is told to wire the raiser in. | medium |
| **`conflict_resolution` can never be entered** | Declared on `monthly-refresh` over `[tagging, ebitda]`. Two things stop it: `guards/reconcile.py` is never called outside tests, and the region spans two steps while the executor re-runs only the head. | Neither is in P59's reach - the first is a guard nobody calls, the second is executor machinery that does not exist. Recorded rather than silently skipped. | medium |
| ~~Every declared loop is dead code~~ | **Done 2026-09-18, P59.** `RepairNeeded` was raised in exactly one place in the repository - a test double - so `guard_repair`, `tieout_repair`, `self_verification` and `conflict_resolution` were declared on every recipe and not one had ever run. The guard-triggered half is joined: a schema, provenance or tie-out rejection on a step whose recipe declares the matching region asks the controller for an iteration, from the dispatcher - the only object holding the masker, since the guard's failure travels into the model's context. The two that remain are the rows above, each needing a decision rather than a fix. | - | done |
| ~~`on_failure` is never read~~ | **Done 2026-09-18, P60.** Parsed, validated, carried on every `Step`, folded into every plan hash, and read zero times by anything that executed - so `halt` on intake, mask and release, `review` on qc, and `quarantine` on the rest all ended a step identically. Now: `review` opens a review item so a person is told, `quarantine` does not, and `halt` ends the run terminally through `close_out` in the driver, because the executor must never move a run to a terminal state - there is one door out and a manifest is behind it. | - | done |
| **The delivery path has never executed** *(landmine removed 2026-09-18, P55)* | `workers/driver.py` read a release gate off the wiring and `RunWiring` has never had one, so the line would have raised `AttributeError` into an undiagnosed quarantine the first time any run reached `release`. It is now built from `w.store`, `w.bus` and `w.delivery`, which the wiring already carries - a field would have been the same bug waiting. **What has still never executed is a release**, because both shipped recipes end at `qc-tieout`, which has no mechanical half. | Needs the qc-tieout procedure (B-004), which is skill work rather than plumbing. The landmine is gone; the path is still unexercised. | small |
| ~~Precedent retrieval is off in the only production wiring~~ | **Done 2026-09-18, P55.** `serve.py` built the Precedent Store, handed it to the lookup tool and to `RunWiring`, and not to the Context Builder eighteen lines below - so every served run assembled context with `NoPrecedents()` and an answer given on one engagement was never shown to the model on the next. The served graph now names it in one place where the argument is required rather than defaulted, `readiness()` reports the seam, and `tests/p35/conftest.py`, which reproduced the omission, asserts against it. | - | done |
| ~~Guard quarantines lose their diagnostic code~~ | **Done 2026-09-18, P55 and P60.** Every `GuardFailed`, `PolicyDenied`, `ScanFailed` and `BudgetExceeded` arrived holding `.diagnostic.code` and had it stringified into the message, while `ops/analytics.py` ranks the failure breakdown by the column - so no guard failure had ever appeared in it. Transport exhaustion had no code at all and now has `PROCESS.TRANSPORT_EXHAUSTED`, in the registry and in the blueprint's own table. | - | done |
| ~~Nothing can be registered on a fresh machine~~ | **Done 2026-09-18, P57.** `recipes/registered.yaml` is gitignored because it records that somebody approved a workflow, and the only writer was called from two test files and nothing else - so a clean clone loaded no recipe, activated no engagement and started no run, with nothing to click. There is now an Approve button on Setup and a route beside the methodology clearance, both going **through the board**: the approver's name and reason land on the governance chain, a recipe edited afterwards loses its approval, and nothing but the board writes the register. | - | done |
| **The identifier register is empty** | `knowledge/identifiers.txt` holds three comment lines and no entries, so `interview.py scan` checked nothing and printed `clean` unconditionally - the check CLAUDE.md names as what keeps client data inside `knowledge/`. P53 made it refuse rather than lie; P54 made the refusal honest (it was firing on clones nobody had interviewed, because it counted the committed `knowledge/README.md` as an answer) and moved the warning to `status`, which runs before the first question rather than after the last. **P64 found the mechanism was still not right**: the acknowledgement expired by date with the same day counting as covered, so a session run after an acknowledgement made earlier that day inherited it - and `scan` would have printed `clean` over it. CLAUDE.md and PROTOCOL.md both already said it expires "as soon as another session is logged", which is what it does now: an acknowledgement records the sessions it was made over. The one in the register today predates that and is read conservatively, so it covers the three sessions logged before 2026-09-18 and expires the moment session four is logged. **The mechanism is now right; the names are still owed.** | The file needs the names, and inventing them is not mine to do. First thing in the next interview - `status` now says so at the top of the session. | minutes |
| **People are never declared to the masker** | `workers/driver.py` declares the client's company name and its distinctive words, and `del profile  # nothing in the profile is a client identifier today` is honest - the engagement profile schema has no field naming a person. The vault has a `PERSON` kind that production has never issued. P53 closed the route by which that leaked (the Precedent Store now refuses an example that reads as naming a person), but the masker still cannot mask an owner's name on the outbound path. | Which names an analyst actually has to hand - officers, owners, related parties, lenders - is an interview question, not a guess. It needs a profile field and a form, and the answer should come from the practice. | medium |
| ~~A phase check in the wrong shape passes for nothing~~ | **Done 2026-09-18.** Four, not three: `uv sync --frozen` and `gate.py render` (P01), `export_architecture --check` (P07), `pytest tests/p35/test_round_two.py` (P36). P07 and P36 were reopened, corrected and re-closed, so their done marks now rest on a verdict the project interpreter produced. **P01 could not be**: `tests/p01/test_structure.py` asks `open_phases()[0]` where the build is, so reopening the first phase makes every later package read as running ahead of the plan, and its own checks include that test - it cannot pass while P01 is open. Its checks are corrected in place and pass; its done mark still rests on the old verdict, which is recorded in `AMENDMENTS.md` rather than hidden. See [`LEDGER.md`](LEDGER.md). The one remaining bare check, `gate.py render`, is deliberate: P58 made gate.py's independence from the project environment a tested property, because it is the tool that installs and checks the others. | - | done |

---

## 4d. What the fourth interview session changed, and what it is waiting on

2026-09-18. The session redefined version 1: it gathers and organises data into an "input
help" workbook the analyst types from, and does not run the model. Three pieces were built
(P67, P68, P69, checkpoint C38). What is not built is waiting on one of two things, and
neither is code.

| | What is waiting | Why it is not built |
|---|---|---|
| **The firm's real model** | `Model Template - MASTER 2026`. The input-help workbook has to match its input format, and the roll-forward's Excel half has to bind its named ranges. | The analyst will supply it. Building a guessed template and binding it at the focus scope would change what every non-ESOP run writes, on a guess, to be replaced days later. The tab strip and the Input, WS, IS and D structures are recorded in `knowledge/sessions/2026-09-18-1.md`; the named ranges are not knowable from a photograph. |
| ~~A local OCR engine~~ | **Done 2026-09-18, P74**, once the analyst confirmed one can be installed at work. The eighth port, `AA_OCR_ADAPTER`, with a `none` default that refuses rather than returning an empty page. It is local because masking needs text and text from a scan needs OCR - OCR by a vision model would put the unmasked document in front of one before masking could happen, and an import walk now proves nothing on the path can. **Installed on the build machine 2026-09-21**: `rapidocr-onnxruntime` and `pypdfium2` into `.venv`, with `AA_OCR_ADAPTER=rapidocr` in `.env` - `serve.py --check` reports the seam ok. On the two scanned PDFs of the first real client folder it read every page at about 0.97 mean confidence. Two things follow. First, installing it turned `tests/p75` red, because the test that asserts the adapter refuses by name when the wheel is missing had never forced the wheel to be missing - it had passed for twenty phases only because no machine in this build had an engine (fixed in P96's session; the absence is forced now, and there is a companion test that the engine actually reads). Second, **it reads words run together** - `BOARDMEETINGMINUTES` - and `privacy/mask.py` locates a declared name by plain substring, so a name OCR has joined to its neighbour is not masked and the payload scan shares the blind spot. Recorded as **B-061**, and it is the thing to fix before a scan's text reaches a model. **Still owed on the work machine:** install the same two wheels there, and measure what it reads against a hand-keyed engagement (B-011) - 0.97 on two redacted scans is an encouraging number and not a measurement, because nothing checked it against the truth. `serve.py --check` reports the seam. |
| **The per-engagement request item lists** | The seven sections are stable and are now in `intake/request_list.py`; the items inside them are written per engagement. | The only one in hand belongs to a client. The analyst has many examples on the work computer. |
| **A producer for the acceptance rule's evidence** | `extracted` and `arithmetic_cover` are read by a tested rule and set by nothing. | Recorded as B-040, and `tests/checkpoints/c38` fails if something starts setting them without the backlog being updated. The producer needs the OCR adapter to have read something and a mapping from a passing tie-out to the figures it covers - the second is the real work. |

---

## 5. Questions I am holding

Not blocking anything today. Each would change what I build next.

1. **The orchestrator's confidence.** I gave the plan proposal no numeric confidence at
   all: "nothing fits" is categorical and routes to triage. A threshold is a policy
   decision and nobody has agreed one. If you want a number and a bar instead, say so and
   it is an amendment rather than a rewrite.
2. **Who reviews what, in the code.** The Skill Review Board routes by scope layer today,
   deriving the group from the path. The moment real reviewer names exist, that becomes a
   roster rather than a derivation.
3. **What "done" looks like for a pilot engagement.** The run scorecard computes a verdict
   against ten criteria. Whether `released_with_review` is an acceptable outcome for a
   real deliverable, or whether the bar is `clean`, is a practice decision I have not been
   given.
4. **How much of the DDR work you actually want first.** The blueprint covers extraction,
   tagging, normalization and model building. The build has proven the vertical on three
   skills. Which engagement type you point it at first will decide what the next skills
   are. *(Answered 2026-09-16: mature operating company valuation - see Settled.)*
5. **When extraction is trusted enough to leave a person out of it.** Proposed from the
   research (2026-09-16, [`docs/research/ai-in-valuation.md`](../docs/research/ai-in-valuation.md)),
   not decided: **at least 95%** of clean statement line items extracted correctly *with the
   right locator*, measured against historicals an analyst keyed by hand; **below 90%** on
   the firm's real document mix, a person stays in the extraction loop and scope narrows to
   cleaner documents. And for the skills: first-draft add-back schedules and DCF inputs that
   a senior analyst accepts with minor edits on **at least 70%** of engagements. The numbers
   are the research's starting proposal; the bar is the practice's to set, and it needs one
   hand-keyed engagement as ground truth before it can be measured at all.
6. **Is report narrative ever in scope?** The research's third stage drafts descriptive
   report sections (company description, methodology narrative, changes in financial
   condition) from the structured store, every figure linked to its source. The blueprint
   stops before the report, and the MD decides whether a report is written. The movement
   flags built in P38 are the deterministic raw material either way; drafting prose from
   them is a scope change for a person to make, not a default.
7. **Does an engagement have a valuation date, and where does it come from?** B-026 asked
   the new engagement line to show one, and there is no such field: the engagement
   profile's two `as_of` dates belong to `size_band` and `fiscal_calendar`, and neither is
   a valuation date. P63 built the line without it rather than putting a date on the screen
   that nothing in the system means, and
   `tests/p63::test_no_engagement_line_carries_a_valuation_date` is what stops one being
   added quietly later. What I need is whether the date is set when the engagement is set
   up or arrives with the engagement letter, whether it ever moves, and whether one
   engagement can carry more than one. Then it is a profile field, a form field beside it,
   and that test changing.
8. **Build or buy a slice.** The research's verdict is to build ingestion and the firm's
   methodology, and to consider buying a valuation engine (Valutico) or a quality-of-earnings
   specialist (Finsider, askOdin). That is a procurement and risk decision. Nothing built
   forecloses it: a bought capability arrives as an adapter behind an existing port.

---

## 5b. What five reviews of the dashboards left unbuilt

2026-09-17. Five reviews - a valuation MD, a frontend engineer, an AI-systems architect, a
working analyst and a security engineer. What was wrong and cheap is built (P44, P45). What is
left needs either a decision, data the firm has not produced yet, or more building than the
finding is worth today. Each is on `knowledge/backlog.md` where it is the analyst's, and here
where it is the practice's.

| What | Why it is not built | What unblocks it |
|---|---|---|
| **The Sampling Audit** | The blueprint names it as the only defence against a confidently wrong, internally consistent, correctly sourced classification - *"no guard catches this"* - and it does not exist. `hitl.item.auto_accepted` is emitted with confidence and locator precisely so a sample can be drawn from what nobody was asked to look at. | A rate: how many auto-accepted items a week you are willing to look at, and by whom. Then it is a draw from the record and ordinary review items. |
| **Review quality, per person** | Analytics reports override rates by skill, never by reviewer, and never reports the two signals the review surface was built to capture: items accepted without the proposal ever being revealed, and items decided seconds after revealing it. The data is now on the run detail; the aggregate is not. | Your word on whether the firm wants it measured per person at all. It is a real control and it reads as surveillance; the MD's call, not mine. |
| ~~An engagement view~~ | **Done 2026-09-18, P63.** Everything was indexed by run - the system's unit, not the work's - so "where does Northgate stand" meant reading every row and noticing the ids repeating. The runs panel now folds by engagement, newest run on top at both levels, with a find box over client, engagement, scope and run id that redraws what the browser already holds rather than asking again. `Console.engagements()` folds the same rows the panel reads, so the two cannot disagree. The one thing B-026 asked for and did not get is the **valuation date**: no such field exists, and inventing one was refused - it is question 7 above. | - |
| **What the client still owes** | Nothing on any screen says which documents have arrived and which are missing, though historicals are the gate the whole job waits on. | The expected set per engagement type, which is B-009's coverage report. |
| **Model checks under their own names** | The scorecard's *tie-out* is footing - every total re-added from the rows it cites. The analyst's *tie-out* is net income ties, balance sheet balances, cash agrees. Same word, different test, and a green pill would be read as the second. `tools/statement_checks.py` already computes the second. | Nothing technical; it needs the qc-tieout procedure to exist so the checks run on a real run. B-004. |
| **Precedent, visible** | An answer given on one client is shown to the model on another in the same practice group. The safeguards are strong (masked, human-only, append-only) and there is no screen that shows what precedent exists or which precedents shaped a proposal. | A decision on what a reviewer should be shown at the point of deciding, and whether a wrong precedent is retired by superseding it. |
| **The assembled prompt, readable** | The blueprint promises *"what was the model actually looking at is a lookup rather than an investigation"*. Every context is content-addressed and recorded; there is no route that reads one back. | A decision on who may read a masked context back, since masking is not a security boundary. |

---

## 6. New information, and what it changes

**2026-09-04, from Caleb:** work will *probably* use **Microsoft Azure** for cloud
hosting, and **Power Automate** is available. Nothing is confirmed, so the blueprint has
not moved: the design of record does not change on a maybe.

### What Azure changes in the code: nothing

Five of the six ports already name an Azure service in the blueprint's own cloud column.
Each is an adapter beside the ones that exist, written the way `sharefile` and `box`
were - a module under `ports/`, registered, with the contract in its docstring.

| Port | Today | On Azure | Work |
|---|---|---|---|
| Storage (in) | watched folder | Blob, or ShareFile unchanged | one adapter |
| Delivery (out) | output folder | Blob or SharePoint, or Box unchanged | one adapter |
| Secrets | `.env` | Key Vault | one adapter |
| Job queue | in-process, Redis + RQ | Service Bus | one adapter |
| Compute | local process | Container Apps | config, plus the image that exists |
| State store | SQLite | Azure Database for PostgreSQL | **one URL** |

The state store is the one that costs nothing at all: the run store is a repository behind
`AA_DB_URL`, and the conformance suite already runs against both backends.

### The one gap Azure opens

The blueprint's LLM row names **Bedrock and Vertex** as the cloud options. It does not
name Azure, because reaching Claude on Azure means **Microsoft Foundry**, which the
blueprint predates. That matters more than a missing table cell:

> **A model pin names a model, not a platform.** `claude-opus-5 @ effort=high` is folded
> into every plan hash and written into every manifest. If the same pin can be served by
> the Anthropic API on one run and Foundry on another, two runs can share a plan hash,
> reach different infrastructure and legitimately disagree - which is exactly the failure
> the precedent-snapshot fix was made to close.

**Question for you:** if Claude comes through Foundry, the pin should carry the platform.
That is a contract change (`run_manifest`), a compile change (the hash), and an adapter.
Say the word and it is scoped; until then nothing is assumed.

### Foundry or the Anthropic API directly

Asked 2026-09-05. Not urgent - nothing before phase 3 needs it - but it decides whether
the model-pin work above happens at all.

**What this build actually asks of the API.** Very little, which is the good news. One
request, one response, a system prompt and a single user message, `stop_sequences`,
`metadata`, and the usage numbers back. No tools, no PDF input, no streaming, no batches.
But **every call** sets two things: `thinking: {"type": "adaptive"}` and
`output_config: {"effort": ...}` from the pin. Those two are the ones that differ.

| What the build uses | Anthropic API | Microsoft Foundry |
|---|---|---|
| Messages, one turn | GA | GA |
| Prompt caching | GA | GA |
| **Adaptive thinking** | GA | **beta** |
| **Effort, from the model pin** | GA | **beta** |
| Token counting | GA | beta |
| `inference_geo` (data residency control) | **GA** | **not supported** |
| Message Batches (not used yet; a nightly sweep could) | GA | not supported |

Three things worth weighing beyond the table:

1. **The firm's Anthropic account is already sanctioned for client data.** The blueprint
   says so, and the only open question there is the narrower one about individual
   engagement letters. Foundry is a new procurement and a new risk review; the direct API
   is a path that already exists.
2. **Data residency runs the opposite way to the intuition.** If keeping data in a stated
   region is the reason to go to Azure, note that the first-party API has a residency
   control and Foundry does not. What Foundry gives instead is a *network* story: traffic
   stays inside the tenant, private endpoints, no egress to a third-party endpoint. If IT's
   objection is egress rather than residency, that is the real argument for it.
3. **New models and features land first-party first.** This build pins a model and folds
   the pin into every plan hash, so a platform that gets a model later means the firm's
   runs lag - and a pin that is unavailable fails the run at startup by design.

**Decided 2026-09-05: the Anthropic API directly, not Foundry if it can be avoided.**
Recorded in the blueprint's LLM port row. The model-pin-names-a-platform work is therefore
**not needed** - it comes back only if the fallback below is taken.

The original recommendation, for the record: Everything this build uses is GA there, the account is
already approved, and the LLM port means the choice stays reversible for the cost of one
module. If IT rules out egress, the Foundry adapter is a day's work plus the pin change -
and at that point the pin must name the platform, because two providers behind one pin is
two runs that share a plan hash and can legitimately disagree.

### Where Power Automate may go, and where it must not

It is genuinely useful at the edges, and genuinely dangerous inside the boundary. The line
is not a preference - each item below is an invariant with a test behind it.

**Fine, and probably worth doing:**

- notify a reviewer that a run is waiting, and chase an overdue one;
- move a client file into the watched folder when it lands in SharePoint or an inbox;
- carry an approval *request* to a person, and a link back to the review surface;
- post a run's outcome into a Teams channel, from the event stream.

**Never, and the reason:**

| Not this | Because |
|---|---|
| Write to the run store or the vault | The event table is append-only and the vault is the only thing that can re-identify. A flow with the connection string routes around both. |
| Close a review item or record a decision | Only a `Decision` with a named `decided_by` moves an item, and every precedent guarantee rests on that column. |
| Approve a skill, or write into `skills/` | `governance/registry.py` is the only writer, and it refuses without the whole chain. |
| Put a file in a client folder | One release, one inbound edge, through the idempotency ledger. A second writer makes "delivered exactly once" false. |
| Re-run, retry or resume anything | The graph owns every loop, with an integer ceiling the compiler checks. |

The safe shape: **Power Automate sits outside and talks through a surface** - the admin or
ops API, or a watched folder - never through the database, the outbox or the file system.
Given a connection string it becomes a second, ungoverned writer, and every guarantee in
the Assurance tab becomes conditional on nobody having built a convenient flow.

**Answered, 2026-09-05:** Power Automate sits **outside**. It notifies and moves files;
it does not drive the pipeline. Nothing about the pipeline changes, and no flow is ever
given a database connection string or write access to the outbox.

---

## 7. Proposed next: routing by practice group

**2026-09-05, from Caleb.** Label each watched folder with a practice group in the admin
dashboard so the orchestrator only sees that group's skills. Then work with the MDs and
each group to define workflows - "do this first, then this". Then give each group a
methodology folder for how Chartwell does things.

Two thirds of this is built. The map:

| The idea | Where it lives today | What is missing |
|---|---|---|
| A folder belongs to a group | The roster binds folder to engagement, the engagement carries `scope_path`, and the Scope Resolver narrows the library before anything runs | Nothing structural. The admin surface takes a typed scope path; it should offer the practice, segment and disposition as **choices from the scope registry** |
| "Do this first, then this" | A **recipe**: named, versioned, compiled into a typed DAG and checked by 7 plan assertions | The recipe is chosen by the *watch*, so every engagement under one watch shares it. Per-group workflows need either a watch per group, or the recipe moved onto the engagement |
| Methodology per group | `foundations/` - three files, attached to **every** model call, unconditionally | It is flat and firm-wide. Per-group methodology means resolving `foundations/` through the same five layers the skills already use |

### The blocker, and why the timing is good

`scope/scopes.yaml` marks Consulting and Corporate Finance `defined: false`, with segments
named `tbd`. Label a folder "consulting" today and it resolves to the firm layer only -
correct, and useless. **Naming those segments is one of the nine decisions in §2**, owned
by the practice leads. Caleb's conversation with the MDs is exactly the mechanism for
answering it, so the two should happen together.

### Two risks worth deciding before building

1. **Recipes have no governance chain.** A skill passes eleven stages before it can run on
   client work. A recipe is a YAML file in the repo. If MDs are going to author workflows,
   that asymmetry is the thing that will be exploited first - a procedure that could not
   pass the skill chain becomes a recipe that reorders skills to the same effect. Either
   recipes get a review path, or the difference is a decision somebody has made on purpose.
2. **Foundations are never scanned for client data.** A skill draft dropped into governance
   is scanned for injection and for anything shaped like a real client file. `foundations/`
   is read straight off disk into every call, and the outbound payload scan only knows the
   *current* engagement's identifiers - so a methodology document citing a worked example
   from a real deal would reach every prompt for every client, unnoticed. Whoever writes
   methodology needs the same scan the skill drop folder has.

**A plan exists and is waiting on you:**
[`proposals/group-routing.md`](proposals/group-routing.md). Six pieces, the order they
have to happen in, and four decisions it needs before anything is built.

### What is needed from the MD conversations

- The **segments** for Consulting and Corporate Finance, and for Corporate Finance the
  model it builds into (`CF_LBO_Model_v3` is bound with no master and no input schema).
- For each group, the **engagement types** that deserve their own workflow, and for each of
  those the steps in order. That is what becomes a recipe.
- Who **owns** each group's methodology, and who reviews a change to it.
- Whether a group's workflow may differ by disposition - a repeat client and a first-year
  engagement are already different layers in the resolver, and can be different recipes.

---

## Settled

*Answered items move here with a date and where the answer is recorded, rather than being
deleted - a decision nobody can find later is one that gets made again.*

| Date | What | Where it is recorded |
|---|---|---|
| 2026-09-04 | P26 signed off | `BUILD/plan.json`, and the closed-phase list in STATE.md |
| 2026-09-04 | Prove the container on this machine before tailoring at work | This file, §1 |
| 2026-09-05 | Power Automate sits outside the boundary: notify and move files, never drive | This file, §5 |
| 2026-09-05 | Model access is the Anthropic API directly, not Foundry if avoidable | The blueprint's LLM port row; this file, §5 |
| 2026-09-05 | The container proof, on podman 6.1.1 rather than Docker Desktop. It found two portability bugs and two bad tests. | [`HANDOFF.md`](../HANDOFF.md) §2; the P28 amendment in [`AMENDMENTS.md`](AMENDMENTS.md) |
| 2026-09-16 | The build serves **valuation / non-ESOP** first; ESOP is parked, not removed; other divisions come later as data | `focus:` in `scope/scopes.yaml`; the P37 amendment in [`AMENDMENTS.md`](AMENDMENTS.md) |
| 2026-09-16 | The repo goes to a **private** GitHub repository, cloned to the work laptop and worked on in Cursor | The P37 amendment |
| 2026-09-16 | `/improve-agent` runs in **both Cursor and Claude Code**, from one protocol | [`interview/PROTOCOL.md`](../interview/PROTOCOL.md) |
| 2026-09-16 | What the interview learns lives in **`knowledge/`, ignored by git**, never committed | `.gitignore`; `tools/interview.py scan` |
| 2026-09-16 | *Superseded the same day:* `knowledge/` is **committed** to the private repo so the interview travels between this machine and the work laptop. Client names still never leave it for a skill, methodology file or fixture | `.gitignore`; the second P37 amendment |
| 2026-09-16 | The interview **may read real client documents** (Caleb's call). This covers the interview only; whether engagement letters permit processing on the firm's account stays open in §2, and whichever AI provider Cursor routes to must be one the firm has approved for client data | [`interview/PROTOCOL.md`](../interview/PROTOCOL.md) §3 |
| 2026-09-16 | **The pilot engagement type is a mature operating company valuation** (DCF, GPC, guideline M&A transactions). Answers §5 question 4 | `recipes/mature-company-valuation.yaml` (draft, unregistered); `knowledge/workflow.md` |
| 2026-09-16 | **AI access at work:** Claude (Claude Code) and any Cursor model. Whether an Anthropic API key is available on the firm's account is still open | `knowledge/profile.md` |
| 2026-09-17 | **Caleb holds an Anthropic API key on the firm's account.** A live run with the real model needs only that key in `.env` on the work machine (never committed); until then the model door stops every run, correctly | `knowledge/profile.md`; `.env.example` |
| 2026-09-16 | The interview **builds when told to stop**: it proposes a list, builds what is approved through the gate, and leaves the rest in the backlog | [`interview/PROTOCOL.md`](../interview/PROTOCOL.md) §5 |
| 2026-09-17 | **Recipe approval is an admin route, through the board.** `POST /api/admin/recipes/{name}/approve` calling `SkillBoard.register_recipe` with the approver's name, plus a button on Setup - the methodology-clearance pattern exactly. Approval stays a governed act; it stops being impossible. Not a button that writes the file directly, which is the shortcut P33 exists to close | §4b; the phase that builds it |
| 2026-09-17 | **`on_failure: halt` is terminal** - the blueprint's reading. The run ends `HALTED` with a manifest and nothing partial escapes; it is not the `Blocked` path and is not resumable. The executor never moves a run to a terminal state, so the driver closes it out | §4b; `constraints.yaml`; the phase that builds it |
| 2026-09-17 | **`on_failure: review` quarantines *and* opens a review item.** The run stays `QUARANTINED`: a failed guard is something a person is told about, not something a reviewer waves through by approving it | §4b |
| 2026-09-18 | **A correction amends the run it was made on, and a rejection stops it.** Both halves: a rejected proposal quarantines the step and the run stops for a person; a correction re-derives that step's output from the answer and commits a new ledger entry under a new step key. This is what the review surface already claims and what a reviewer assumes they are doing | §1; the phase that builds it |
| 2026-09-18 | **The tagging verifier gets built**, rather than the declaration being dropped. The blueprint's reading stands: every DDR tagging and EBITDA output, always - a separate invocation that sees the tagged lines and the source rows and never the first pass's reasoning. Skill work, through the governance chain | §4b; the phase that builds it |
| 2026-09-18 | **The blueprint gains a node for the worker that carries a run.** `run_driver` is a real part of the system the drawing was missing; the design of record changes and every existing run's trace stays true. Not the other way round - pointing the driver at `step_executor` would make the drawing right by making the record wrong | §1; `docs/architecture.html` |
| 2026-09-18 | **A working auto-accept bar, Caleb's and revisitable: 0.90 confidence**, with owner-related categories and anything material always reviewed regardless. Set now so the queue is usable while the system is tested, not because the practice has agreed a number - the practice lead and QC still own the real one, and the sampling audit that would make any bar safe does not exist yet | §2; the engagement profile |
| 2026-09-17 | **The four wrong-shaped phase checks are reopened, fixed and re-closed**, not amended in place, so each phase's done mark rests on a verdict the project interpreter actually produced | §4b; `AMENDMENTS.md` |

## The connections, and the first real report  (added 2026-09-21, P93)

Nothing in P87-P93 has reached a real Box tenant, a real ShareFile account or a real
Chartwell report. Every test runs against a transport that replays documented behaviour,
or a document generated for the purpose. That proves the code's use of an API and the
shape of a document; it is not evidence that a credential, an app permission, a folder id
or a heading is right at work.

**P93 is `gate: human` and stays open until this is done, on the machine with the
credentials.**

1. **Box.** `.env` needs `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, `BOX_USER_ID` and
   `AA_BOX_INBOX_FOLDER_ID`, and the Box app needs **Generate User Access Tokens**
   enabled - without it Box refuses the token with `unauthorized_client`, which the
   adapter names in the refusal because it is the most likely thing to be wrong. Press
   **Test it** on Setup and record which of the four steps answered.
2. **ShareFile.** The app registration needs the callback this server actually receives
   on - `http://127.0.0.1:8000/api/admin/sharefile/callback` - and must ask for **offline
   access**, or the login lasts an hour and stops. Press **Sign in**, authenticate in the
   browser, then **Test it**.
3. **The Update button.** Press it once and check what copied. Press it again: the second
   press must report everything as already there. If it copies twice, stop and say so.
4. **One real report.** Set one up from last year's, point one appendix at its Word
   document, and press **Preview** before **Update**. Open the result in Word and look at
   the layout - the styles, any numbered list, any image.

**And the thing only a real report can settle.** The appendix registry in
`report/appendices.py` holds six anchor strings guessed from the fifth interview session:
`Appendix C - Economic Conditions` and so on. The real report's headings are probably
worded differently. Whatever they actually are, write them down - the registry is data so
that correcting it is a setting rather than a phase, and if nobody records it, it gets
rediscovered every period.

Still owed after that, for B-057: where each appendix's source document lives, and whether
a source .docx *is* the appendix whole or contains it as a region.

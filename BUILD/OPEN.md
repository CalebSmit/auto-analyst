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
| **What a correction does to the run it was made on** | Today: nothing. A reviewer's `answer` is read in exactly two places, both in `precedent/writeback.py`, and both teach *later* runs. The step this run resumes on is satisfied from the ledger - the model's original output - so a corrected value does not reach the deliverable, and a **rejected** proposal is delivered anyway. The console says "corrected: ... the run resumes on the next sweep", which reads as though it took effect. | It is a design decision with three defensible answers, and it is yours: (a) a rejection quarantines the step and the run stops for a person; (b) a correction re-derives the step's output from the answer and commits a new ledger entry under a new step key; (c) both. (b) is the one that changes what a deliverable contains, so it needs your word, not an inference from mine. Found by the AI-architecture review, 2026-09-17; the behaviour is confirmed in the code, not assumed. | I build the answer you give, and the review surface stops promising what it does not do. Until then the console says plainly that a decision is recorded and does not amend this run. |
| **A run records work against a node the design does not have** | Every run emits against `run_driver`, and the blueprint has no such node. P48 draws all 118 nodes beside everything a run recorded, which is the first thing that has ever compared the two - so the map reports it under "not on this map" rather than dropping it. | Two defensible answers, and the choice is a design one: the blueprint gains a node for the worker that carries a run (it already draws `step_executor`, `orchestrator` and `queue_port` around it), or the driver emits against one of those instead. The first is an edit to the design of record; the second changes what every existing run's trace says. | I make the change and re-export, and the map has nothing left to report. |
| **Two skills have no mechanical half** | `qc-tieout`, which both shipped recipes end with, and `ddr-tagging` in the full intake. Each needs a procedure - the deterministic half that says what the model is shown and what it must return - beside the four that have one. | Skill work rather than plumbing: the run reaches the step and stops there with it named, which is correct and is not finishing. Everything around them is joined - a released run is picked up, driven, masked, checked and recorded. | A run of `monthly-refresh` reaches `release` and a workbook lands in the outbox. |
| **P28 sign-off** | Your word that the container proof is enough to call v1 portable. The image builds and the whole suite passes inside it on this machine (podman 6.1.1, 1711 passed, 78 skipped) - the clone onto the work machine is the part still outstanding. | P28 is `gate: human`. The gate refuses to close it on green tests alone, and I will not invent your words. | `gate close P28 --signoff "..."`, then `gate checkpoint C10`, and v1 is done. |
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

- **The auto-accept bar** has no default. A checkpoint policy that sets no bar
  auto-accepts nothing, which is safe and noisy. Until it is set, every item goes to a
  person.
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

## 4b. Found on 2026-09-17, not yet fixed

Three reviews - an engine defect hunt, a read of the tool as the analyst who has to use
it, and a security audit - ran over the whole system. Three findings were fixed the same
night (P53). These are the rest. Each was reproduced against the code before it was
written down; none is a suspicion.

| | What is wrong | Why it is not fixed yet | Size |
|---|---|---|---|
| **Every declared loop is dead code** | `RepairNeeded` is raised in exactly one place in the repository - `tests/p14/conftest.py:190`. Every real guard fails through `guards.report()`, which raises `GuardFailed`, which lands in the bare `except Exception` at `graph/execute.py:473` and quarantines at once. So `guard_repair`, `self_verification` and `tieout_repair` - declared on every recipe - have never run. And `RunStore.hold()`, the only writer of a quarantine record, is called only from inside `LoopController.exhaust`, which that path never reaches: **the quarantine store is permanently empty**, against `constraints.yaml`'s own rule that exhaustion always produces an artifact. | It is the deepest of the three, and it fails *loudly* - you get a quarantine - where the three that were fixed were all silent wrongness. "The graph owns every loop" is a non-negotiable, so this is a blueprint/code disagreement and wants a phase, not a patch. | medium |
| **`on_failure` is never read** | Parsed at `graph/recipes.py:233`, validated at `graph/plan_assertions.py:216`, carried on `Step`, rendered on the plan - and read zero times by anything that executes. `on_failure: halt` on `release` and `on_failure: review` on `qc` both behave as plain quarantine. | Same family as the loops and the same fix site (`_quarantine` dispatching on the step). Worth doing together. | small |
| **The delivery path has never executed** | `workers/driver.py:528` reads `w.release_gate`, and `RunWiring` has no such field (confirmed against `dataclasses.fields`). `ports.get_delivery()` is truthy so the `and` does not short-circuit: the line raises `AttributeError`, which the executor swallows into a quarantine with no diagnostic code. It has never fired because no run has reached `release`. | One line, but it wants the phase that makes a run reach `release` at all - otherwise it is a fix nothing exercises. | small |
| **Precedent retrieval is off in the only production wiring** | `tools/serve.py:433` builds `ContextBuilder(tree, blobs, bus, store=store)` and never passes `precedents=`, so every served run assembles context with `NoPrecedents()`. The store is built, handed to `RunWiring` and to the lookup tool, and not to the thing that reads it. `tests/p35/conftest.py:110` makes the same omission, so the nearest end-to-end test reproduces the bug rather than catching it. | One keyword argument. Held with the group above because the same session should add the readiness seam that would have caught it. | small |
| **Guard quarantines lose their diagnostic code** | `graph/execute.py:473` passes `str(failure)` with no `diagnostic_code=`, so every `GuardFailed`, `PolicyDenied`, `ScanFailed` and `BudgetExceeded` arrives with `failure.diagnostic.code` in hand and throws it into a message string. `ops/scorecard.py` and `ops/analytics.py` both aggregate by `diagnostic_code`, so no guard failure appears in the failure-code breakdown. | Same site as the loops. | small |
| **Nothing can be registered on a fresh machine** | `recipes/registered.yaml` is gitignored on purpose, and the only writer is `SkillBoard.register_recipe`, called from eleven test files and nowhere else. No route, no button, no CLI. On a clean clone no recipe loads, preflight check 10 fails, no engagement activates and no run starts - with nothing to click. `knowledge/backlog.md` B-002 says "a person registers it at /admin"; there is nothing there. | The shape of the fix is a decision: a `POST /api/admin/recipes/{name}/approve` beside the methodology clearance that already exists, or an off-machine command if the practice wants approval to happen elsewhere. **This is the first thing that will stop you on the work machine.** | small |
| **The identifier register is empty** | `knowledge/identifiers.txt` holds three comment lines and no entries, so `interview.py scan` checked nothing and printed `clean` unconditionally - the check CLAUDE.md names as what keeps client data inside `knowledge/`. P53 made it refuse rather than lie; P54 made the refusal honest (it was firing on clones nobody had interviewed, because it counted the committed `knowledge/README.md` as an answer) and moved the warning to `status`, which runs before the first question rather than after the last. **The mechanism is now right; the names are still owed.** | The file needs the names, and inventing them is not mine to do. First thing in the next interview - `status` now says so at the top of the session. | minutes |
| **People are never declared to the masker** | `workers/driver.py` declares the client's company name and its distinctive words, and `del profile  # nothing in the profile is a client identifier today` is honest - the engagement profile schema has no field naming a person. The vault has a `PERSON` kind that production has never issued. P53 closed the route by which that leaked (the Precedent Store now refuses an example that reads as naming a person), but the masker still cannot mask an owner's name on the outbound path. | Which names an analyst actually has to hand - officers, owners, related parties, lenders - is an interview question, not a guess. It needs a profile field and a form, and the answer should come from the practice. | medium |
| **A phase check in the wrong shape passes for nothing** | **Four**, not three - re-counted 2026-09-17 against `plan.json`: `python -m uv sync --frozen` (P01), `python tools/gate.py render` (P01), `python tools/export_architecture.py --check` (P07), and `python -m pytest tests/p35/test_round_two.py -q` (P36). The gate only rewrites commands beginning `python -m uv run ` (`gate.py:117` returns anything else unchanged), so these run whatever `python` PATH resolves to - the system interpreter, with no dependencies, unless the gate happens to be run from an activated shell. Found because four new phases written the same way reported FAIL for eight suites that all passed. | The four new ones were corrected. **Decided 2026-09-17: reopen, fix, re-close** - `gate amend` would rewrite them in place and leave the phase marked done on a verdict the broken check produced. Scheduled as its own phase. | small |

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
7. **Build or buy a slice.** The research's verdict is to build ingestion and the firm's
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
| **An engagement view** | Everything is indexed by run. An analyst thinks in clients, and a repeat client has several runs on one engagement. There is no screen that answers "where does Northgate stand". | Nothing - it is build work, and it is the largest single thing the analyst review asked for. Queued as B-026. |
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
| 2026-09-17 | **The four wrong-shaped phase checks are reopened, fixed and re-closed**, not amended in place, so each phase's done mark rests on a verdict the project interpreter actually produced | §4b; `AMENDMENTS.md` |

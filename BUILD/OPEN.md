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
| **P28 sign-off** | You clone onto the work machine, run the suite in the container, and confirm nothing but `.env` had to change. | P28 is `gate: human`. The gate refuses to close it on green tests alone, and I will not invent your words. | `gate close P28 --signoff "..."`, then `gate checkpoint C10`, and v1 is done. |
| **The container proof** | Either approve a Podman install here, or point this repo at a remote so CI can do it. | The sandbox blocked the download, and no OCI runtime is installed. The image has never been built. | I build the image, run the whole suite inside it, and fill in the runtime and version in [`HANDOFF.md`](../HANDOFF.md) §2. |
| **The P26 sign-off wording** | Optional. The recorded sign-off reads "Caleb: it all looks good", which does not say what you checked. | Nothing is broken. It is a thin line in a permanent record, beside three others that name what was reviewed. | `gate amend P26 --reopen`, then close again with fuller words. The three checks re-run first. |
| **Egress from Azure to the Anthropic API** | Confirmation from IT that a container in Azure may reach `api.anthropic.com`. | The 2026-09-05 decision is to call the Anthropic API directly from wherever the system runs. A refusal is the one thing that would force a provider-hosted route, and with it the model-pin change. | Nothing changes and the decision stands. If it is refused, the Foundry adapter and the platform-aware pin get scoped. |
| **A real Redis** | A reachable server, once. | The queue adapter has only ever run against an in-memory fake. That proves its use of RQ, not Redis. | `pytest --redis` goes green and the session summary stops saying FAKED. |

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

## 3. Evidence only the work machine can produce

These are tasks on P28. They are not code waiting to be written; each is evidence
somebody has to gather, and the phase cannot honestly close without them.

| | What is owed | Deferred from |
|---|---|---|
| **Timing alignment** | Confirm the alignment on a real engagement's files, and tailor the normalized table to the firm's Excel models. | P18, through P24 and P25 |
| **The firm's chart of accounts** | Publish Chartwell's conventions as a new taxonomy version - never edit `coa-taxonomy@1.0.0` in place - measure the two-analyst baseline on 200 real line items, and rebuild `fixtures/skills/line-item-tagging`. | P19, through P24 |
| **Real add-backs** | An analyst confirms the add-backs proposed on a real engagement are defensible and that nothing material was auto-accepted; rebuild `fixtures/skills/ebitda-normalization`. | P20, through P24 |
| **The model builder** | Read the work repo, reconcile its named-range binding with `tools/write_template.py`, and register the real templates with their input schemas. | P24 |

Two more, smaller:

- **`CF_LBO_Model_v3`** is bound at `corporate-finance/_group` with no master file and no
  input schema. Preflight reports it as `CONFIG.TEMPLATE_UNREGISTERED` every time.
  Register it or unbind it.
- **The human baseline override rate** is unmeasured, so the analytics compare against
  "unmeasured" rather than against a number. It comes from the baseline measurement above.

---

## 4. Questions I am holding

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
   are.

---

## 5. New information, and what it changes

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

## Settled

*Answered items move here with a date and where the answer is recorded, rather than being
deleted - a decision nobody can find later is one that gets made again.*

| Date | What | Where it is recorded |
|---|---|---|
| 2026-09-04 | P26 signed off | `BUILD/plan.json`, and the closed-phase list in STATE.md |
| 2026-09-04 | Prove the container on this machine before tailoring at work | This file, §1 |
| 2026-09-05 | Power Automate sits outside the boundary: notify and move files, never drive | This file, §5 |
| 2026-09-05 | Model access is the Anthropic API directly, not Foundry if avoidable | The blueprint's LLM port row; this file, §5 |

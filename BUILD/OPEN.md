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

## Settled

*Answered items move here with a date and where the answer is recorded, rather than being
deleted - a decision nobody can find later is one that gets made again.*

| Date | What | Where it is recorded |
|---|---|---|
| 2026-09-04 | P26 signed off | `BUILD/plan.json`, and the closed-phase list in STATE.md |
| 2026-09-04 | Prove the container on this machine before tailoring at work | This file, §1 |

# Amendments

*Append-only. Every change to the plan, and why. Written by `gate amend` — do not edit
by hand, and never delete an entry: an amendment that turned out to be wrong is more
useful than one that was quietly removed.*

Read this when the plan looks wrong. It probably changed for a reason.

---

## 2026-09-02 — Founding decisions

These were taken before P01 opened, from the architecture blueprint and from Caleb's
answers during planning. Recorded here because a decision without its reason becomes a
convention nobody will question later.

**Why:** the plan needed a starting position on the things that are expensive to change
after week three.

- **Repo lives at `C:\dev\automated-analyst`, not in the OneDrive folder.** A synced
  `.git` and `.venv` on Windows is a file-lock and corruption hazard, and this project
  writes thousands of run artifacts. The blueprint HTML and `project-context.md` stay in
  OneDrive; this repo points at them.
- **Toolchain: `uv`, Python 3.12 pinned, `uv.lock` committed.** One tool for version,
  venv and locking, and a lockfile that reproduces exactly on the work machine without
  needing Poetry installed there first.
- **SQLite behind a repository port for P01–P24; the same conformance suite runs against
  Postgres in Docker from C2 onward.** This is the ports pattern the architecture already
  uses, applied to the state store, so the swap is a URL — and running both is what stops
  SQLite-only SQL creeping in unnoticed.
- **`.env` plus the secrets port from day one.** At handoff, moving to the firm's
  Anthropic account is a `.env` change and nothing else.
- **Named job recipes produce the plan until P26; the LLM orchestrator arrives last.**
  Debugging plan compilation and a model's plan proposal simultaneously means trusting
  neither. The blueprint has `job_recipes` seeding the orchestrator, so this is a
  sequencing choice rather than a departure.
- **The three existing work repos — model builder, ShareFile connector, Box connector —
  are adapters to write at handoff, not dependencies to satisfy.** The model builder is an
  input to P21 and should be read before the Template Writer is written; it may already
  solve the named-range binding.

---

## 2026-09-02 — Four findings from the pre-build review, folded into the plan

**Why:** a review of the blueprint before any code was written found four things that
would have surfaced weeks into the build. All four were fixed in the blueprint as well,
so the HTML and this plan agree.

- **F1 — `engagement_profile` had no producer.** EBITDA Normalization, GPC Scrub and Cost
  of Capital all declare it as a required input; nothing emitted it. Repurchase Obligation
  declares `participant_census`, likewise. Invariant 23 had already decided the answer —
  configuration writes the engagement record — so this was a missing *contract*, not a
  missing design. **Lands in P02** as a schema, and in **P24** as a preflight check at
  activation.
- **F2 — nothing owned the parse that provenance and tie-out read from.** The figure
  envelope carries a `locator`; provenance asserts the `source_id` is in the intake
  manifest; the recompute engine re-derives totals *from the source rows*. All three need
  a persisted, addressable parse that outlives the step that produced it, and no node
  owned it. **Lands in P17** as the Source Parse Store, keyed `(run_id, source_id,
  locator)`, written once and never updated. This was the most expensive of the four to
  have found late.
- **F3 — the tool namespace is six names and three of them are gated reads.** Skills
  declare `recompute`, `timing_normalizer`, `template_schema_lookup`,
  `chart_of_accounts_lookup`, `precedent_lookup`, `index_lookup`; the map has three tool
  *nodes*. The other three resolve to data resources. Not a defect, but building the
  runtime for compute tools alone would have been. **Lands in P10.**
- **F4 — the stack picked the Claude Agent SDK for the reasons single-turn forbids.** The
  SDK was justified by subagents with per-invocation tool allowlists and native
  progressive disclosure; `max_turns == 1` removes both, and the Guarded Tool Runtime
  dispatches every tool because the Policy Gate must see it. What stays valuable is
  `SKILL.md` as a *file format*, which owes nothing to any SDK. **Lands in P11:** the LLM
  port speaks the Messages API, we parse skill files ourselves, and the Agent SDK is an
  optional adapter rather than a dependency in the first three months. MCP for Box is
  unaffected and arrives with delivery.

A fifth, smaller finding — five stale node and edge counts in the blueprint's own prose
and its `NODECLASS` table — was corrected in the HTML and is now checked by a harness.

## 2026-09-02 - P02 Contracts and registries

**Why:** Two things the phase turned up that the plan did not say. First, the blueprint's repo listing places the contract and constraint DATA but names no home for the code that loads it: contracts/ cannot hold Python by its own charter, and harness/graph/guards/ops are each wrong for a thing all four of them read. The three registries got their own package. Second, a cross-check against the blueprint's own skill frontmatter found its tool table's usage count for recompute is stale.

- task added: registries/ package: the loaders for contracts, constraints and (from P07) diagnostics
- check added: python -m uv run ruff check .

## 2026-09-02 - P01 Project structure and build-state system

**Why:** Three gate tests in tests/p01 hardcoded P02 and C1 as their out-of-order targets. That made them assert the gate was broken the moment P02 legitimately closed, and the checkpoint one would have silently started RUNNING checkpoint C1 once P03 closed rather than testing a refusal. They now derive their targets from plan.json. A test that has to be edited every phase is a test that eventually gets edited into agreeing with whatever happened.

- exit criterion added: The gate tests derive their targets from plan.json rather than naming a phase, so they stay true as phases close

## 2026-09-02 - P01 Project structure and build-state system

**Why:** The blueprint's source of truth moves into the repo. docs/architecture.html is now the copy that is edited and committed; the OneDrive file becomes a published mirror for viewing on another device, and sync_blueprint.py pushes rather than pulls. The old direction made every blueprint correction a two-step operation across a boundary git cannot see - edit in OneDrive, then sync - and skipping the first step reverted the second silently. That is precisely the class of failure the build-state system exists to prevent, so the design of record should not have been the one file exempt from it. The mirror is guarded: publishing refuses if it changed since it was last published, and --pull brings a deliberate edit back.

- exit criterion added: The blueprint is authoritative in the repo, and sync_blueprint.py publishes to the mirror rather than pulling from it
- blueprint: 'c:/Users/smitc/OneDrive/Documents/Chartwell/Automated Analyst/Chartwell_Automated_Analyst_Architecture.html' -> 'docs/architecture.html'

## 2026-09-02 - P01 Project structure and build-state system

**Why:** Phase files were written once by the scaffolder and never regenerated, so an amendment left BUILD/phases/PNN.md describing a plan that no longer existed - and CLAUDE.md sends every session to read the current one. gate render now writes them from plan.json alongside PLAN.md and STATE.md, and the scaffolder delegates to it rather than keeping a second copy of the template. Regenerating immediately surfaced existing drift: every phase file told you to verify with 'python -m pytest tests/pNN', which is the system Python, while the plan's actual checks use 'python -m uv run pytest'.

- exit criterion added: BUILD/phases/PNN.md are generated by gate render from plan.json, not maintained by hand

## 2026-09-02 - P03 Ports and adapters, with one conformance suite

**Why:** P03 builds a ports/compute directory the blueprint's repo listing did not show, though its own Delivery tab has always listed Compute as one of the six ports and the phase's builds field names compute_target. Made it a real port rather than a comment: it reports where a run executed into the manifest, and how much concurrency exists to the worker pool in P25 - both otherwise places where 'we always run locally' hard-codes itself quietly. Blueprint corrected to match. Adding ruff to the phase checks for the same reason it was added to P02.

- task added: ports/compute: a Protocol and a local_process adapter, so the run manifest can record where the work happened
- check added: python -m uv run ruff check .

## 2026-09-02 - P04 Event bus, run store, manifest

**Why:** Docker is not installed on this machine, and AMENDMENTS.md already scheduled the Postgres run for C2 onward - so the phase demanded at P04 what the founding decision put at C2. Caleb chose to keep the founding schedule. The engineering that matters lands here in full: the repository port, both backends, and one conformance suite parameterised over them. Only the execution against a live server waits, and it is never a silent skip - the suite reports Postgres as NOT RUN when no server is reachable, and C2 requires it green.

- exit criterion added: The store conformance suite is parameterised over SQLite and Postgres, passes on SQLite, and reports the Postgres run as not-run rather than skipping it silently when no server is reachable

## 2026-09-02 - P04 Event bus, run store, manifest

**Why:** Completes the previous amendment. The superseded criterion is removed rather than left in place: a phase that closes with an exit criterion nobody met is how 'done' stops meaning anything, and leaving it would make the gate's PASS a lie by omission. The Postgres requirement is not dropped - it moves to C2, where it is now recorded.

- exit criterion dropped: The same suite passes against Postgres in Docker, not only SQLite

## 2026-09-02 - C2 A plan compiles and hashes

**Why:** The Postgres run moves here from P04, where Docker was not available and the founding decision had already scheduled it 'from C2 onward'. C2 is the right home: it is the first checkpoint after the store exists, and a checkpoint is precisely where phases that each passed alone are made to agree. Running both backends is what stops SQLite-only SQL creeping in unnoticed, which is the whole reason the repository port exists.

- proves: 'A recipe compiles; identical inputs give an identical plan_hash and a changed precedent snapshot changes it' -> 'A recipe compiles; identical inputs give an identical plan_hash and a changed precedent snapshot changes it; and the store conformance suite passes against Postgres in Docker as well as SQLite'
- check added: python -m uv run pytest tests/p04 -q --postgres

## 2026-09-02 - P01 Project structure and build-state system

**Why:** The no-domain-logic-yet test hardcoded five packages that must hold nothing but __init__.py. True at P01, and false one package at a time from P04 onward - the same defect as the hardcoded gate targets fixed earlier: a test that must be edited every phase eventually gets edited into agreeing with whatever happened. Each package now names the phase that first builds it, and the check binds only packages whose phase has not been reached yet. A package the current phase exists to build is the work, not a violation. It retires itself package by package and still catches somebody writing the mask engine during P05.

- exit criterion added: Each package names the phase that first builds it, and the ahead-of-plan check binds only packages whose phase has not been reached

## 2026-09-02 - P04 Event bus, run store, manifest

**Why:** P02 and P03 both run ruff as a phase check and P04 did not, which meant a lint regression introduced here would not be caught until the next phase closed. Also records the blueprint resolution: the Run Store node said 'Postgres.' flat, while the plan builds SQLite behind a repository port through P24 - resolved in favour of the plan, and docs/architecture.html now says repository-behind-a-Protocol, one URL apart. Two smaller blueprint corrections went with it: the ops/ repo listing gained models.py, and the PROCESS.* diagnostics row gained the four codes the run store raises.

- check added: python -m uv run ruff check .

## 2026-09-03 - P05 Scope resolver

**Why:** The first exit criterion said seven scope combinations. The declared taxonomy admits eight - three practice groups, four segments between them, two dispositions - and the seven are the blueprint roster's distinct scope paths, which are those eight minus consulting/tbd/non-repeat, a combination no engagement happens to use today. Resolved in favour of the taxonomy: the criterion now names the cross product, because a combination nobody has used yet is exactly the one that will be wrong the first time somebody scopes an engagement into it. tests/p05/test_resolve.py asserts both, and names the seven live ones separately. Also adds ruff to the checks, which P02, P03 and P04 all run and P05 did not.

- exit criterion added: Every scope combination the declared taxonomy admits - eight today, including the one no engagement uses yet - resolves to exactly one skill set, with no skill in it twice
- exit criterion dropped: All seven scope combinations resolve to exactly one skill set
- check added: python -m uv run ruff check .

## 2026-09-03 - P06 Graph compiler

**Why:** Blueprint finding, resolved in favour of the code. The Step contract declared 'loop: str | None' - one region per step. The compiler found a step that is genuinely in two: self-verification applies to every EBITDA output, and guard repair applies when that same output fails its schema check. A single field could only say one of them, which would leave the other region bounding a step that did not know it was inside one. Step now carries 'loops: tuple[str, ...]' and docs/architecture.html says so, with the reason beside the contract. The nesting rule that makes it safe is stated too: the dependency graph must be acyclic on its own, and each declared region must close a cycle over exactly the steps its back edge returns over - which is also why the compiler cannot check this with a single strongly-connected-components pass, since SCC merges a nested region into its parent. Also adds ruff to the checks, matching P02 through P05.

- check added: python -m uv run ruff check .

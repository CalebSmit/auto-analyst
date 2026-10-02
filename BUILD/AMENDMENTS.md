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

## 2026-09-03 - P28 Docker, portability, handoff packet

**Why:** Caleb's constraint, recorded now rather than discovered at P28: no Docker Desktop subscription. That licence applies to Docker Inc's desktop product above 250 staff or 10M USD revenue, and Chartwell may cross the revenue line. It does not apply to the Dockerfile format, the OCI image format, Podman, Rancher Desktop or Docker Engine on Linux - all free for commercial use, all able to build and run this image. The exit criterion said 'docker compose up', naming one vendor's command inside a requirement whose entire purpose is portability. Replaced with a tool-neutral criterion that Podman, Rancher Desktop, containerd or Docker CE all satisfy. The Dockerfile itself stays: it is a build recipe, not a licensed artifact, and podman build reads it unchanged.

- exit criterion added: The image builds and the whole suite passes inside it with no host Python involved, using any OCI-compatible runtime - podman, containerd, Rancher Desktop or Docker Engine. No step depends on Docker Desktop, and HANDOFF.md names the runtime actually used
- exit criterion dropped: docker compose up then pytest is green with no host Python involved

## 2026-09-03 - C2 A plan compiles and hashes

**Why:** The proves statement said 'against Postgres in Docker', which is now inaccurate and would mislead whoever reads the record later. Postgres 17.11 runs natively on this machine from the portable binaries - no container, no Docker Desktop, per Caleb's licensing constraint recorded on P28. What the checkpoint proves is unchanged: the same conformance suite passes on both backends. How the server is started is an environment detail and does not belong in a statement about what was proved.

- proves: 'A recipe compiles; identical inputs give an identical plan_hash and a changed precedent snapshot changes it; and the store conformance suite passes against Postgres in Docker as well as SQLite' -> 'A recipe compiles; identical inputs give an identical plan_hash and a changed precedent snapshot changes it; and the store conformance suite passes against a real Postgres server as well as SQLite'

## 2026-09-03 - P07 The assertion suites

**Why:** Two blueprint findings, both resolved in favour of the code, and one gap left open on purpose. First: the ASSERTS pseudocode read node fields the NODES model does not carry - g.nodes_where(group='source', is_intake=True) and g[e.dst].fail_closed. is_intake is a real design fact and three nodes now declare it (sharefile, local_intake, email_watcher). fail_closed needed no new field: group=='guard' already marks the fourteen nodes that fail closed, so invariant 23 uses it. Second: the repo listing said graph/assertions.py, singular, where the phase tasks and the blueprint's own ASSERTS block both name two files. Two it is, and the listing now says so alongside architecture.json. The gap: four intake nodes that run a model (doc_classifier, period_detector, workbook_reader, email_watcher) have no drawn edge from the LLM Port, so invariant 2 carries an explicit exemption list with a written reason each, asserted to be exactly right. They read raw documents inside the Untrusted Content Boundary before masking, which is a different path from the payload path - but whether that path needs its own door is a design question for a person, not something an assertion should paper over. Also adds the export drift check and ruff to the phase checks.

- check added: python tools/export_architecture.py --check
- check added: python -m uv run ruff check .

## 2026-09-03 - P08 Step executor, idempotency, resume

**Why:** Two findings and one behaviour change to a closed phase, all recorded here because P08 caused them. First, a blueprint finding: the Step contract showed the idempotency key as a property of Step, computing it from self.inputs content hashes and self.context_ref. A compiled Step cannot have either - it is built before anything runs, and its refs are symbolic. The key is now a function, step_key(step, inputs, context_ref), taking the compiler's half from Step.key_material() and the runtime half from the executor. docs/architecture.html shows it that way, with the split labelled. Second: ops/blobs.py is a new module the listing did not have. Steps pass content-addressed refs rather than values, which the exit criterion requires, and the refs have to resolve to something. Third, a change to P04's surface: run_store.finish_step now refuses StepStatus.COMPLETED and directs the caller to commit_step, which writes the result into the ledger in the same transaction. The resume frontier reads the ledger, so a step able to claim completion with no result there would be one a resume re-executes while the run looked finished. Same one-door shape as transition and end_run. tests/p04 and the C2 integration test were updated to complete steps the real way, which exercises the ledger rather than a status field. Also adds ruff to the phase checks.

- check added: python -m uv run ruff check .

## 2026-09-03 - P09 Context builder

**Why:** Four things beyond the phase's own files, recorded here because P09 caused them. First: foundations/ is a new top-level folder the repo listing did not have. The task says the builder attaches firm standards to every call, and they have to come from somewhere; three skeleton standards are there now, honest about being placeholders the practice group writes, and the listing names the folder. Second: an overlay-added reference lives beside the overlay at its own layer, not beside the skill it modifies - dol-adequate-consideration.md sits at valuation/esop/_segment while ebitda-normalization sits at valuation/_group. SkillTree.reference now takes the resolved reference list and the layers in force, and searches them deepest first. Third: record_artifact is idempotent on (run, name, hash). A resumed run rebuilds contexts it built before, and recording them twice made an idempotent pass look like it did something. Fourth, and the one C3 turns on: StepExecutor.execute now runs the plan assertions before every pass, the resume included, so a plan read back from a checkpoint or mutated between passes gets the same check the compiler gave it. Also adds ruff to the checks.

- check added: python -m uv run ruff check .

## 2026-09-03 - P10 Policy gate, constraints, guarded runtime

**Why:** One collision surfaced, deliberately left for a person, and recorded here so it does not get resolved by accident. The blueprint's repo listing names tools/ as the executable tool namespace - normalize.py, recompute.py, write_template.py - and CLAUDE.md's non-negotiable is that nothing under skills/ may import anything under tools/. But tools/ in this repo has held the build tooling since P01: gate.py, sync_blueprint.py, export_architecture.py, postgres.py. When P13 and P18 write recompute.py and normalize.py they will land beside the gate script. Not harmful today, and the import boundary P10 enforces does not care what else is in the folder, but it is two meanings for one name and the day somebody greps for a tool they will find the build system. Options are to move the dev scripts to build/ or scripts/, or to put the tool namespace somewhere the blueprint does not currently name. Either is cheap now and a rename with history attached later; the choice belongs to Caleb. Also: the Diagnostics Registry is a view over registries/errors.py rather than a second declaration site, so a code can only be declared once; and ruff joins the checks.

- check added: python -m uv run ruff check .

## 2026-09-03 - P11 LLM port, model pin, budget governor

**Why:** Three findings, two resolved toward the blueprint and one map correction. First: the blueprint's Budget Governor names four ceilings - token spend, currency spend, wall clock, total loop iterations - and constraints.yaml had model_calls_max where the blueprint has tokens. The blueprint is the design of record, so per_run now carries tokens_max (3,000,000) and the governor checks exactly the four the blueprint names; model calls stay in the manifest's cost block as a count, not a ceiling. Second: tests/p01's package map said privacy/ is first built by P12, but this phase's builds list includes payload_scan and the repo listing puts it in privacy/. The map now says P11, with mask, vault and unmask still P12's. Third: harness/door.py, harness/budget.py and ops/cost.py are new modules the listing did not have; the door is what the blueprint calls the Python wrapper around the LLM Port that is structurally the only way to reach a model, and a test walks the import graph to assert nothing else calls a port. Also: RATES_USD_PER_MTOK pins the blueprint's rate table beside TIER_MODELS, so the meter is arithmetic over reported usage and nothing else. Ruff joins the checks.

- check added: python -m uv run ruff check .

## 2026-09-03 - P12 Privacy: mask, vault, unmask, verify

**Why:** Four things beyond the phase's own files. First: privacy/verify.py is a fifth module the listing did not name. The task says the integrity check is a separate node from the masker so it can be tested apart from the thing it checks, and a separate node is a separate module; the check takes sets and a string and a test hands it a wrong set to prove it notices. Second: cryptography joins the dependencies for Fernet - the vault is encrypted at rest per the blueprint, the key comes through the Secrets Port, and the standard library has no AEAD cipher. Third: the retention period is a placeholder of 730 days and the code says so. Setting the policy is Risk / IT's decision before phase 1 in the blueprint's own decisions table, and the column and the purge exist so that decision has somewhere to land. Fourth, a defect the tests found: the first vault issued tokens that were never written, because its session helper was a bare Session context manager, which closes and discards rather than commits. Fourteen tests failed at once and every one of them was that. The run store's commit-on-exit shape is now used, and the docstring names the mistake. Ruff joins the checks.

- check added: python -m uv run ruff check .

## 2026-09-03 - P13 Guards and their adversarial fixtures

**Why:** Only six of the ten fixture guards exist after P13 (payload_scan, unmask_verify, tieout, numeric_lock, provenance, budget_governor); untrusted_boundary, loop_controller, engagement_lock and deliverable_qc are built by P17, P14, P16 and P21. The criterion as written could not be true until P21. All ten fixtures and case files land now, with the phase that owns each guard named in the table, so a later phase inherits a fixture rather than writing one.

- exit criterion added: All ten fixtures exist with their target guard and owning phase named; each fixture whose guard is built fires it and only it; the rest are reported by phase at the end of every test session, never skipped silently
- exit criterion dropped: Each of the ten fixtures fires the right guard, and only that guard

## 2026-09-03 - P13 Guards and their adversarial fixtures

**Why:** The Recompute Engine is a tool (blueprint node t_recompute) and lives at tools/recompute.py, in the folder that also holds the dev scripts (gate.py, postgres.py) - the P10 name collision, now with a real tool in it. The tie-out guard takes the engine as an injected callable and imports nothing under tools/, so the boundary test holds. Resolving the folder split is still the user's call.

- check added: python -m uv run ruff check guards ops/source_parse.py tools/recompute.py tests/p13

## 2026-09-03 - P14 Loop controller, quarantine, diagnostics

**Why:** P13 finding: ten error codes the registry has carried since P04-P11 (PRIVACY.UNMASKED_PRECEDENT; PROCESS.LATE_RESULT, PLAN_REFUSED, DIAGNOSTICS_INVALID; SCOPE.UNKNOWN_CONTRACT, CONTRACT_INDEX_INVALID, UNKNOWN_CONSTRAINTS, UNKNOWN_ADAPTER, MODEL_PIN_UNAVAILABLE, MISSING_CREDENTIAL) had never reached the blueprint's ERRCODES table, and SKILL.UNKNOWN_SOURCE was new in P13. All added by hand at P13 close. Nothing checks that table against the registry, which is how the gap grew silently over nine phases - P14 owns diagnostics, so the assertion lands there.

- task added: A test that every code in registries/errors.py appears in the blueprint's ERRCODES table, and every code in the table exists in the registry

## 2026-09-03 - P14 Loop controller, quarantine, diagnostics

**Why:** The blueprint's ERRCODES table names eight codes nothing had raised yet (LOOP.EXHAUSTED, LOOP.INPUT_UNCHANGED, PROCESS.REVIEW_SLA_BREACH, PROCESS.RUN_STALLED, DELIVER.QC_FAILED, DELIVER.TEMPLATE_MISSING, INTAKE.UNKNOWN_TYPE, INTAKE.NO_ENGAGEMENT). The two LOOP codes are raised here; the other six are declared in the registry now, with owner and what_now, so the table-vs-registry test holds in both directions and the phases that raise them (P16, P21, ops) inherit an actionable message rather than writing one under pressure.

- check added: python -m uv run ruff check harness graph guards registries ops tests/p14
- check added: python -m uv run mypy harness graph guards registries ops

## 2026-09-03 - P14 Loop controller, quarantine, diagnostics

**Why:** The Fixed Notice is a module of its own, harness/notice.py, which the blueprint's repo listing did not name (it listed loops.py under harness/ but placed the notice nowhere). Listed now. Templates are checked at import for display-field-only placeholders and internal-looking text; substitution is a single-pass placeholder replace, never str.format, so a value containing braces is text.

- task added: harness/notice.py: the Fixed Notice template set, checked at import for display names only

## 2026-09-03 - P21 Model builder, template registry, release

**Why:** P14 finding: a quarantine now halts only dependent steps, and a step that never started has no inputs, so no honest step_key - and run_manifest@1.0.0 requires every listed step to carry a sha256 key. Halted steps are therefore absent from the manifest's steps list rather than listed as not_reached, which the blueprint's StepStatus note asks for. The executor's report and the quarantine record say what was halted; the manifest does not. Resolving it means the manifest reading the plan (order and step ids) rather than only the step table, which belongs with the release-side manifest work here.

- task added: Manifest lists every plan step, with never-started ones as not_reached and no invented key (P14 finding)

## 2026-09-03 - P15 Confidence router, review queue, decision log

**Why:** The five review nodes live in a package of their own, review/ (policy, router, queue, surface, log), which the blueprint's repo listing did not name; listed now. The Checkpoint Policy is carried on the engagement profile: engagement_profile@1.0.0 gains an optional checkpoint_policy block (owner, sla_hours, auto_accept_confidence, always_review_categories, review_floors) - additive, so every existing profile stays valid, and recorded here because a contract change goes through review. Two PROCESS codes are new: STALE_DECISION (the optimistic lock) and RATIONALE_REQUIRED (no silent override). The decision table is append-only three ways like the event table. There is deliberately no auto-accept default: a policy that sets no bar auto-accepts nothing.

- check added: python -m uv run ruff check review tests/p15 tests/checkpoints/c05
- check added: python -m uv run mypy review ops registries

## 2026-09-03 - C5 Every guard fires on its own fixture

**Why:** Seven of the ten fixture guards exist after P15 (loop_controller joined the six from P13); the untrusted boundary, engagement lock and deliverable QC are built by P17, P16 and P21. The checkpoint test runs every fixture whose guard is built through every built guard and reports the rest by phase, so its claim is true now and stays true as the last three land.

- proves: 'All ten adversarial fixtures fire the right guard, every loop is bounded, and every failure carries code, owner and what_now' -> 'Every adversarial fixture whose guard is built fires that guard and only that guard (seven of ten after P15, the rest reported by phase), every loop is bounded by an integer the registry allows, and every failure carries code, owner and what_now'

## 2026-09-03 - P16 Intake: roster, sweep, binding, lock, window

**Why:** The eight intake nodes live in a package of their own, intake/ (roster, config, sweep, local, bind, fingerprint, window, lock, plus launch.py for the release), which the blueprint's listing did not name; listed now. The Configuration Store needed a contract to validate against: config_document@1.0.0 is new (watches, intake timing, filename-to-document-type conventions, destinations, per-engagement overrides). Recipes gain an intake.required_types block, which is what the window waits for; it is not key material, so no plan hash moves. Two codes are new: INTAKE.WATCH_OVERLAP (config) and PROCESS.ENGAGEMENT_LOCKED (the fixture's). Arrival is defined as the sweep that first sees a file, on the system's clock, and the window counts from that. The recipe's source_documents input stays untyped: its shape is the run manifest's sources rows, written by launch.py, and typing the recipe input belongs with P17's readers, which own what a source becomes once read - the P06 note that said P16 was one phase early.

- check added: python -m uv run ruff check intake tests/p16
- check added: python -m uv run mypy intake ops registries graph

## 2026-09-03 - P17 Readers and the Source Parse Store

**Why:** The readers live in intake/readers/ (documents, workbook, classify, periods) and the Untrusted Content Boundary in guards/untrusted.py, both now in the listing. The Source Parse Store gained its locator resolver: readers write blocks (one table of a document, one numeric column of a sheet) and any locator inside a block resolves through one interface - a figure may cite TB_FY25!B44:B47 without the reader having written that key. Hidden text is decided by effective font size under 4pt (pypdf exposes size, not colour); the fixture's 1pt white text fires on size, and the zero-width half of the criterion is shown through a Word run, because a Type1 PDF font cannot carry U+200B. The classifier and the period detector are the deterministic halves; the small model call the blueprint allows for their residue lands with the dispatcher (P18), which owns the door and the identifier list. Scanned pages are reported, not OCR'd - the OCR path is an adapter for later, recorded here rather than stubbed. One code is new: INTAKE.INJECTION_DETECTED.

- check added: python -m uv run ruff check intake guards ops tests/p17
- check added: python -m uv run mypy intake guards ops

## 2026-09-03 - P18 First real skill: timing normalization

**Why:** The mechanical half of a skill has a home: harness/dispatch.py is the Skill Dispatcher (a blueprint node no phase had claimed) and harness/procedures/ holds one module per skill. The blueprint's SKILL.md frontmatter declared scripts/align_periods.py under the skill folder, but P10 made 'no Python under skills/' a test, so the script became harness/procedures/timing_normalization.py and the scripts key left the frontmatter. The proposal is its own contract, skills/timing-normalization-proposal@1.0.0, kind skill_proposal, with no numeric property anywhere - a test walks the schema. The tool is tools/normalize.py, the name the blueprint's listing already used for t_timing. Two findings outside the phase: the masker's account-number-by-shape rule matched ISO dates and digit runs inside sha256 hashes (a P12 rule), so a period end in the payload was masked and then found unmasked in the engagement profile by the outbound scan; dates and hex-embedded runs are now excluded, and the P12 tests still hold. And the engagement_scoped predicate needs every tool call to carry engagement_id, which the tool accepts and ignores. The skill's status is draft: registered is the governance chain's word (P27).

- check added: python -m uv run ruff check harness tools/normalize.py tests/p18 tests/checkpoints/c06
- check added: python -m uv run mypy harness tools/normalize.py

## 2026-09-03 - P24 Admin console, preflight, config audit

**Why:** P18 sign-off covers the synthetic annual_drift case only. Caleb reviewed the rename, split, merge and the one unmatched line and would have made the same calls - good for testing. A real engagement's files and the firm's own Excel models do not exist in this build until the pilot, so the real-engagement half of P18's human check is owed here, along with tailoring the skill's output to those models.

- task added: Confirm the timing-normalization alignment on a real engagement's files, and tailor the normalized table to the firm's Excel models (the half of P18's sign-off deferred from the synthetic case)

## 2026-09-03 - P19 Line-item tagging and the precedent store

**Why:** P19 findings, resolved in favour of the blueprint's invariants. (1) The taxonomy loader lives in registries/taxonomy.py, not tools/coa.py: the tagging procedure builds its payload before any tool is bound and needs the pinned category list, and P10's boundary test forbids anything under harness/ importing tools/ - so the loader is a registry over taxonomy/ data and tools/coa.py is only the name the runtime binds. (2) The Precedent Store's index is deterministic lexical similarity (token overlap) through P24, not the embedding index the blueprint names: the build is local and keyless. The ranker only orders rows the scope's WHERE clause already admitted, so swapping it for an embedding port later changes nothing about where the store looks; blueprint impl text updated to say so. (3) PrecedentQuery gained a terms field so retrieval can rank by the step's masked descriptions; the scope fields are unchanged and still derived only from the ResolvedScope, and the dispatcher masks every term with the same masker as the payload. (4) The single-writer rule is enforced three ways rather than one: the API (PrecedentWriteback.write takes a decision id and nothing an example could be passed through), the store (admit re-reads the decision), and the database (a composite foreign key into decision and a BEFORE INSERT trigger checking writes_precedent and decided_by, on SQLite and Postgres). (5) New codes SCOPE.UNKNOWN_TAXONOMY, SKILL.UNKNOWN_LINE_ITEM, SKILL.UNKNOWN_PRECEDENT, PROCESS.PRECEDENT_NO_DECISION, in the registry and the blueprint table. (6) The 400-item gold set is authored, not measured: the blueprint's two-analyst baseline needs the firm's analysts and a real chart, neither of which exists before P24; the sign-off is on the 17-row disagreement list, not on the 95.8% figure.

- task added: Proposal contract skills/line-item-tagging-proposal@1.0.0: one numeric field (the model's confidence), no figure anywhere; every ref, category and cited precedent in a proposal is verified by the procedure before it becomes output
- task added: registries/taxonomy.py loads taxonomy/coa-taxonomy@x.y.z.yaml; tools/coa.py and tools/precedent.py are the two gated reads the skill declares
- exit criterion added: The precedent table itself refuses a row without a qualifying human decision - foreign key and BEFORE INSERT trigger on both backends - so a raw INSERT fails the same way the API does

## 2026-09-03 - P24 Admin console, preflight, config audit

**Why:** P19 deferral. coa-taxonomy@1.0.0 carries synthetic defaults and the 400-item tagging gold set is authored rather than measured. The blueprint's plan is that the first golden set is the 200 line items two analysts agreed on, with their disagreements as the edge cases; that needs Chartwell's analysts and a real chart of accounts, which the pilot is the first place to have.

- task added: Publish Chartwell's own chart-of-accounts conventions as a new taxonomy version (never edit 1.0.0 in place), measure the two-analyst baseline on 200 real line items, and rebuild fixtures/skills/line-item-tagging from it

## 2026-09-03 - P20 EBITDA normalization

**Why:** P20 findings, resolved in favour of the blueprint. (1) monthly-refresh declared self_verification on tagging only; the blueprint's loop table says the trigger is 'every DDR tagging and EBITDA output, always' and the Runtime tab's note says a step can sit in two regions with EBITDA as the example. The recipe now declares self_verification:ebitda as well - five regions - and P06 and C2 tests were updated from four. (2) The verification pass is a second Procedure (EbitdaVerification, harness/procedures VERIFIERS) dispatched through the same Skill Dispatcher as a separate model call, admitted by the loop controller as an iteration of that region; its trigger is a new non-failure code LOOP.VERIFICATION_PASS so the iteration is on the loop ledger. The verifier's payload carries amounts, citations, excerpts and the cited rows, and never the first pass's rationale or confidence; the SKILL.md carries a Verification pass section the same system prompt serves. (3) The proposal has no amount: a candidate names a line and its periods, the amount is the line's own figure from the normalized historicals, and recompute re-derives it through the gated runtime before it is a schedule item. The blueprint's example of a model stating 486,200 against rows B44:B51 is therefore caught one step earlier - the model cannot state it at all. (4) The ESOP overlay tightens this skill's hitl to all_addbacks_require_review; the dispatcher's escalation carries the resolved kind, and the tests assert that rather than the frontmatter's. (5) The engagement profile is a context section of every call and carries the benchmark amount by design; the skill's own payload carries the benchmark's basis, source and date only. (6) The recall fixture is authored - eighteen analyst add-backs on the synthetic Henderson case, seventeen recalled - and the sign-off is on that case; a real engagement's add-backs wait for the P24 pilot.

- task added: The self-verification pass as a second procedure and a declared region on the EBITDA step: recipes/monthly-refresh.yaml self_verification:ebitda, harness/procedures VERIFIERS, LOOP.VERIFICATION_PASS
- task added: Two proposal contracts: skills/ebitda-normalization-proposal@1.0.0 (candidates, no amount) and skills/ebitda-normalization-verification-proposal@1.0.0 (verdicts, no number)
- exit criterion added: The verification pass never sees the first pass's rationale or confidence, proven by the request the verifier receives

## 2026-09-03 - P24 Admin console, preflight, config audit

**Why:** P20 deferral. The EBITDA add-back gold list is authored on the synthetic Henderson case; the human check for P20 asks for add-backs on a real engagement, which the pilot is the first place to have.

- task added: Have an analyst confirm the add-backs proposed on a real engagement are defensible and that nothing material was auto-accepted; rebuild fixtures/skills/ebitda-normalization from what they identified

## 2026-09-03 - P21 Model builder, template registry, release

**Why:** P21 findings, resolved in favour of the blueprint. (1) The note said to read the model builder repo from work before writing the Template Writer; that repo is not on this machine and was not read. The writer here binds by named range through openpyxl's defined names and refuses a cell address, which is the blueprint's requirement; anything the work repo already solves better is reconciled at the P24 pilot, recorded there. (2) CONFIG is a new diagnostic family: the task named CONFIG.TEMPLATE_INPUTS_MISSING and the blueprint's preflight example uses it, but the ERRCODES table had no CONFIG row. Added the row with TEMPLATE_INPUTS_MISSING and CELL_ADDRESS_BINDING, both owner config. (3) The templates on disk are synthetic, built by tools/synthesize_templates.py from templates/inputs/<file>@<version>.yaml, which is the mapping schema the registry asserts against - 43 required inputs on the ESOP model so the blueprint's 41-of-43 example is a real test. The master is never opened for writing; the registry pins its bytes by hash and refuses one that changed. (4) The workpaper narrative is rendered by code from locked structured data through P24 rather than by a style-only model pass: the build is keyless, and the numeric lock over the prose is the guarantee either way. Rendered from flags, never from free-text rationale, so no number the lock has not seen reaches the prose. (5) The manifest lists never-started steps as not_reached with a null key and zero attempts - run_manifest@1.0.0 now allows exactly that shape, in place, since no recorded run cites the old one. The template pin goes in versions.template_version, the field the contract already had. (6) The release event and the ledger row are one transaction: the bus gained draft(), which builds and validates an event without storing it, and the run store persists it with the ledger row. A first cut left the persistence in draft() and wrote every release event twice; the transaction test caught it.

- task added: The idempotency ledger table and record_release in the run store; EventBus.draft for an event persisted inside another transaction
- task added: Synthetic templates under templates/ from templates/inputs/ schemas via tools/synthesize_templates.py; the Template Registry pins masters by hash
- exit criterion added: The release event and the ledger row are written in one transaction, proven by a ledger failure leaving no release event behind

## 2026-09-03 - P24 Admin console, preflight, config audit

**Why:** P21 deferral. The Template Writer was built against synthetic templates; the work model builder repo the P21 note names was not available here.

- task added: Read the work model builder repo and reconcile its named-range binding with tools/write_template.py; register Chartwell's real templates under new versions with their input schemas under templates/inputs/

## 2026-09-03 - P22 Eval and replay harnesses

**Why:** P22 findings. (1) The Skill Registry node is P27's, but 'a skill below its gate cannot be registered' needs a registration to refuse; evals/registration.py is that last link, recording a version in skills/registered.yaml only from a scorecard that cleared every gate, with the approver named and the scorecard hashed. P27's chain (sandbox, submit, board, shadow) leads into it. (2) The blueprint's gate table includes shadow disagreement for line-item-tagging, which the offline harness cannot measure; gates.yaml carries it with measured_by: shadow_run, and the scorecard, the coverage report and the registration record all say it is owed rather than leaving the row out or counting it passed. (3) Replay needed the dispatcher to record what a step was given: it now writes inputs:<step> and proposal:<step> blobs beside output:<step> and names all three on skill.completed. Replay restores a step from those and the run store; it imports nothing from privacy/, ports/delivery or deliver/, so it never sees the vault or a released artifact. (4) The Skill Registry code SKILL.BELOW_GATE was added to the registry and the blueprint table. (5) Two things the exit criteria did not name were built because the criteria needed them: an ephemeral eval world so gate eval runs the gated runtime outside any engagement, and gate eval delegating to python -m evals under uv so the gate tool itself imports nothing from the project.

- task added: evals/gates.yaml as the named numeric form of the blueprint's gate table, with owed gates marked by the control that measures them
- task added: The dispatcher records inputs and proposal blobs per skill step; the Replay Harness restores a step from them
- exit criterion added: A gate the offline harness cannot measure is reported as owed - on the scorecard, in coverage and on the registration record - never as passed

## 2026-09-03 - P23 Ops console, scorecard, drift, stalls

**Why:** Finding: the manifest contract had no field for the scorecard's verdict or the criteria version the blueprint's run_scorecard -> run_manifest edge records. Bumped to run_manifest@1.1.0 (1.0.0 stays listed) with a required scorecard block; the four-valued outcome stays as the run's state fact and the five-valued verdict sits beside it, checked against it at close-out (PROCESS.OUTCOME_CONTRADICTED). Two consequences for existing tests: a delivered run whose record leaves criteria unmeasured cannot be closed out clean, and a run nothing refused is blocked, not halted.

- task added: Criteria versioned as data under ops/criteria/, pinned by ops/scorecard.py, never edited in place

## 2026-09-03 - P23 Ops console, scorecard, drift, stalls

**Why:** Finding: period coverage cannot be measured from the record as the nodes emitted it - no event carried the periods a run normalized. The dispatcher now records a procedure's summary(output) on skill.completed (labels and counts, never a figure), and timing-normalization supplies one.

- task added: Skill summaries on skill.completed for the scorecard: periods and reported gaps from timing-normalization

## 2026-09-03 - P24 Admin console, preflight, config audit

**Why:** Finding from P23: event@1.0.0 and run_manifest@1.0.0 both pattern diagnostic_code without the CONFIG family P21 added, so a CONFIG.* code on an event fails validation. run_manifest@1.1.0 carries the fix; the event contract needs the same bump before preflight or config audit can emit a CONFIG code.

- task added: Bump event@1.0.0 to 1.1.0 with CONFIG in the diagnostic_code pattern before preflight emits one

## 2026-09-03 - P27 The governance chain

**Why:** Finding from P23: the drift monitor computes and reports flags but the cross-run loop it feeds (sustained drift -> skill board re-review) belongs to the governance chain. The monitor writes nothing; P27 opens the re-review from DriftMonitor.report().

- task added: Open a re-review on the skill board from a DriftMonitor flag (the drift_re_review loop)

## 2026-09-04 - P24 Admin console, preflight, config audit

**Why:** Finding: the model bound to each scope layer lived only in templates/bindings.yaml, which no admin surface could edit. config_document@1.1.0 (1.0.0 stays listed) now carries model_bindings, destination adapters and credential names, expected credentials with expiry (never a value), and per-engagement review level and profile - the profile validated against engagement_profile@1.0.0 on every write. The Scope Resolver takes bindings from the store; bindings.yaml is the checked-in seed. event@1.1.0 admits the CONFIG family. Preflight reports the checked-in CF_LBO_Model_v3 binding as CONFIG.TEMPLATE_UNREGISTERED: no master and no input schema exist for it yet.

- task added: Register CF_LBO_Model_v3 with an input schema, or unbind corporate-finance/_group, once Corporate Finance names its model

## 2026-09-04 - P25 Worker pool and the queue port

**Why:** The four P24 tasks that need real engagement files, a real taxonomy, an analyst's add-back review and the work model-builder repo cannot be done on this machine with synthetic fixtures; they move to the pilot phase where that material exists.

- task added: Confirm the timing-normalization alignment on a real engagement's files and tailor the normalized table to the firm's Excel models (deferred from P18/P24)
- task added: Publish Chartwell's chart-of-accounts conventions as a new taxonomy version, measure the two-analyst baseline on 200 real line items, rebuild fixtures/skills/line-item-tagging (deferred from P24)
- task added: Have an analyst confirm real-engagement add-backs and that nothing material was auto-accepted; rebuild fixtures/skills/ebitda-normalization (deferred from P24)
- task added: Read the work model-builder repo, reconcile its named-range binding with tools/write_template.py, register Chartwell's real templates with input schemas (deferred from P24)

## 2026-09-04 - P25 Worker pool and the queue port

**Why:** Building the pool surfaced three disagreements between the code and the blueprint, each resolved toward the blueprint. (1) The blueprint's run states say queued is 'nothing is allocated; position visible' and running is 'a worker holds it', but the Engagement Lock moved a run to running when it granted the lock and the Review Surface did the same when the last item was decided - before any worker existed. Both transitions now live in the executor's pass, the one place a worker actually takes a run up; the lock grants and the surface re-enqueues, and a run waiting for a free worker shows as queued with a position. The RUNSTATE rows were reworded to say the pool's second cause of queued (every worker busy). Tests in p15, p16, c06 and c08 that acted as the worker now say so and take the run up themselves. (2) The Job Queue Port could not answer 'how far back' - position() and depth() were added to the Protocol so the queued state can be honest and backpressure is a reported fact; both adapters implement them and the P03 conformance suite covers them. (3) The pool needed a home: workers/pool.py, added to the blueprint's repo listing. Also: PROCESS.WORKER_LOST for a run whose worker died (owner system; resume is replay); the in-process adapter is now a bounded thread pool sized by the Compute Target that never runs two jobs of one engagement together; the Redis + RQ adapter runs the P03 suite and the P25 pool over an in-memory fake unless --redis names a server, and the session summary says which. The four pilot tasks carried here from P24 are untouched - they need real files, a real taxonomy, an analyst and the work model-builder repo, none of which exist on this machine - and they stay open on the record rather than being ticked by closure.

- check added: python -m uv run ruff check .
- check added: python -m uv run mypy workers ports intake ops registries graph review

## 2026-09-04 - P24 Admin console, preflight, config audit

**Why:** These four tasks need real engagement files, Chartwell's own chart of accounts, an analyst's review of real add-backs and the work model-builder repo. None exists on this machine, and a closed phase renders every task it lists as done, so P24 has shown them ticked since it closed and P25 would too. They move to P28, the handoff, where the work material exists and where Caleb's sign-off is what marks them done. gate amend gained --drop-task for exactly this: a task a phase cannot do moves, on the record, rather than sitting ticked.

- task dropped: Confirm the timing-normalization alignment on a real engagement's files, and tailor the normalized table to the firm's Excel models (the half of P18's sign-off deferred from the synthetic case)
- task dropped: Publish Chartwell's own chart-of-accounts conventions as a new taxonomy version (never edit 1.0.0 in place), measure the two-analyst baseline on 200 real line items, and rebuild fixtures/skills/line-item-tagging from it
- task dropped: Have an analyst confirm the add-backs proposed on a real engagement are defensible and that nothing material was auto-accepted; rebuild fixtures/skills/ebitda-normalization from what they identified
- task dropped: Read the work model builder repo and reconcile its named-range binding with tools/write_template.py; register Chartwell's real templates under new versions with their input schemas under templates/inputs/

## 2026-09-04 - P25 Worker pool and the queue port

**Why:** These four tasks need real engagement files, Chartwell's own chart of accounts, an analyst's review of real add-backs and the work model-builder repo. None exists on this machine, and a closed phase renders every task it lists as done, so P24 has shown them ticked since it closed and P25 would too. They move to P28, the handoff, where the work material exists and where Caleb's sign-off is what marks them done. gate amend gained --drop-task for exactly this: a task a phase cannot do moves, on the record, rather than sitting ticked.

- task dropped: Confirm the timing-normalization alignment on a real engagement's files and tailor the normalized table to the firm's Excel models (deferred from P18/P24)
- task dropped: Publish Chartwell's chart-of-accounts conventions as a new taxonomy version, measure the two-analyst baseline on 200 real line items, rebuild fixtures/skills/line-item-tagging (deferred from P24)
- task dropped: Have an analyst confirm real-engagement add-backs and that nothing material was auto-accepted; rebuild fixtures/skills/ebitda-normalization (deferred from P24)
- task dropped: Read the work model-builder repo, reconcile its named-range binding with tools/write_template.py, register Chartwell's real templates with input schemas (deferred from P24)

## 2026-09-04 - P28 Docker, portability, handoff packet

**Why:** These four tasks need real engagement files, Chartwell's own chart of accounts, an analyst's review of real add-backs and the work model-builder repo. None exists on this machine, and a closed phase renders every task it lists as done, so P24 has shown them ticked since it closed and P25 would too. They move to P28, the handoff, where the work material exists and where Caleb's sign-off is what marks them done. gate amend gained --drop-task for exactly this: a task a phase cannot do moves, on the record, rather than sitting ticked.

- task added: On the work machine: confirm the timing-normalization alignment on a real engagement's files and tailor the normalized table to the firm's Excel models (deferred from P18 through P25)
- task added: On the work machine: publish Chartwell's chart-of-accounts conventions as a new taxonomy version (never edit 1.0.0 in place), measure the two-analyst baseline on 200 real line items, rebuild fixtures/skills/line-item-tagging (deferred from P24)
- task added: On the work machine: have an analyst confirm real-engagement add-backs are defensible and that nothing material was auto-accepted; rebuild fixtures/skills/ebitda-normalization (deferred from P24)
- task added: On the work machine: read the work model-builder repo, reconcile its named-range binding with tools/write_template.py, register Chartwell's real templates with input schemas under templates/inputs/ (deferred from P24)

## 2026-09-04 - P26 Orchestrator agent and triage

**Why:** Building the orchestrator surfaced four things the blueprint did not settle, each resolved and recorded. (1) The repo listing had no home for the orchestrator, triage or the run plan - orchestrate/ added to it (orchestrator.py, plan.py, triage.py, manifest.py). (2) Three contracts are new and contract additions go through review: run_plan_proposal@1.0.0 (what the model may return), run_plan@1.0.0 (the artifact the blueprint called 'a JSON artifact in the run store' without a schema) and triage@1.0.0 (whose shape the blueprint gave in prose as {assessment, suggested_skill?, escalation_reason?}). (3) The proposal carries no number at all - no figure, no timeout, no ceiling and deliberately no confidence. The blueprint calls triage 'the low-confidence fallback', which invites a score and a threshold; a threshold is a policy decision rather than a model's, and nobody has agreed one. So 'no confident match' is categorical: match: none routes to triage. If a numeric confidence is wanted later that is an amend, not a default. (4) The graph owns every loop, so a composed plan's loop regions come from a table in orchestrate/plan.py with every ceiling read from constraints.yaml, and the proposal has no field to ask for an iteration. A cross-skill region is dropped rather than forced when the proposed shape does not enclose the path between its members - a loop only ever permits an extra iteration, so a plan without one iterates less, never more. Also: match: recipe loads the named recipe from disk rather than trusting the model's restatement of it; the Ops Console gained /api/runs/{id}/plan and an optional content store, because the blueprint says the run plan is shown live and there was no way to read it back; ops.blobs.put_json became a module function since the ContentStore Protocol carries put alone.

- check added: python -m uv run ruff check .
- check added: python -m uv run mypy orchestrate workers ports intake ops registries graph review

## 2026-09-04 - P27 The governance chain

**Why:** Four findings, each resolved and recorded. (1) The blueprint's repo listing had no home for the governance chain: governance/ added, with the eleven modules named. (2) The eval harness scored the wrong thing. EvalHarness takes its version from the live SkillTree, so a candidate drafted in the sandbox was scored as the version already registered, and the registry then wrote a definition whose version disagreed with the ledger row it had just written. The chain now builds the harness over the sandbox tree, so what is scored is the candidate. (3) evals/gates.yaml stated the shadow gate as 'below 8% over 20 real runs' and carried only the 8% as a number - the run count, which is the whole of 'sustained rather than one good day', existed only in prose. Gate gains a runs field, gates.yaml carries 20, and ShadowDeployment.for_gate builds from it rather than from a constant. (4) Three SKILL codes are new and the blueprint's ERRCODES row now lists them: GATE_SKIPPED (a stage with no evidence behind it, owner process), CLIENT_DATA_IN_DRAFT (a draft carrying something shaped like a real client file, owner client-data), SHADOW_INSUFFICIENT (the threshold not sustained, owner process). Design decisions worth the record: the governance store is an append-only hash-chained JSONL outside the repo rather than a table in the run store, because a draft is untrusted content and nothing about governance belongs in a git history - the chain of hashes is what gives a file the guarantee the run store gets from database triggers. The client-data patterns live in governance/conformance.py rather than being imported from privacy/, so governance has no reason to reach the masking layer. A candidate's position is folded from the record rather than held on an object, so nothing advances because something in memory said it had. And the chain is linear: every stage requires every stage before it, which is what makes 'remove any one gate and the path breaks' a test rather than a diagram.

- check added: python -m uv run ruff check .
- check added: python -m uv run mypy governance evals orchestrate workers ports intake ops registries graph review

## 2026-09-04 - P28 Docker, portability, handoff packet

**Why:** Four findings, each resolved and recorded. (1) Eleven environment variables the shipped code reads were not in .env.example: AA_WORKDIR, AA_SKILLS_INTAKE_ROOT, AA_REDIS_URL, AA_REDIS_QUEUE and AA_PG_HOME arrived with P25 and P27 without being documented, and six connector credentials are new here. 'A clean clone plus .env with no undocumented step' was not true. tests/p28 now derives the list from the source, so a variable added without being documented fails the suite rather than somebody's first evening with the repo. (2) The import-boundary test - the one test the whole ports arrangement rests on - scanned a hand-written list of ten packages. Seven built after P03 (deliver, evals, precedent, admin, workers, orchestrate, governance) were never added, so the portability guarantee had quietly stopped covering most of the repo. SCANNED is now derived from the repo itself. (3) P03's conformance suite assumed every registered adapter has an implementation. The two handoff adapters are port contracts for the firm's existing ShareFile and Box connectors, registered so that selecting one is a refusal somebody can read rather than an unknown name or - far worse - a silent fallback to the local folder. ports.ready() is what the conformance suite runs over, ports.contracts() is the rest, and SCOPE.ADAPTER_NOT_WIRED is the refusal (owner config, in the blueprint's SCOPE row). (4) No OCI runtime is installed on this machine - docker, podman, nerdctl, finch and rancher are all absent - so the image has never been built here. The Dockerfile and compose file are checked statically; the build and the in-container suite are opt-in behind pytest --container, and the session summary says in words that the image was not built, the same honesty the Postgres and Redis runs get. HANDOFF.md says the same and leaves a line for the runtime actually used. Also built: a two-stage Dockerfile from uv.lock --frozen, non-root, client paths on volumes; compose.yaml with Postgres and a health check, plain OCI with no Docker Desktop extension, named pipe, host gateway or mounted socket; tools/postgres-init.sh for the conformance database; and HANDOFF.md, which names every environment difference, the three work repos and their port contracts, and everything still owed.

- check added: python -m uv run ruff check .
- check added: python -m uv run mypy governance evals orchestrate workers ports intake ops registries graph review admin deliver precedent

## 2026-09-04 - P28 Docker, portability, handoff packet

**Why:** Caleb asked for regression protection before he starts tailoring the system at work: 'when I ask for updates or give additional information, nothing will break'. The build already had five layers of it - the phase suites, the checkpoints, the 25 architecture invariants, the 7 plan assertions and the adversarial fixtures - but every one of them asks whether the code does what it says. None asked whether what it says has changed, which is the question that goes unasked until a change months later quietly alters what a run means. So: BUILD/surfaces.json records thirteen public surfaces collected from the live registries - every contract and a digest of its schema, every error code and owner, the tool namespace with its caps, the declared loops with their ceilings, the scope layers, every skill with the four declarations the dispatcher enforces, the recipes, the run states and legal transitions, the event vocabulary, the ports and adapters, the eval gates, the run criteria, the governance stages, and the compiled plan hash of every recipe. That last entry is load-bearing: a plan hash folds in structure, skill versions, model pins, output contracts, the scope resolution, the template binding, the taxonomy and both registry versions, so one line moves if any of them do. tests/regression fails on any difference and names it in words; accepting one is gate amend then surfaces --update, in that order, because the snapshot is not the authority on what is correct - the reason recorded beside it is. tools/verify.py is the one command: surfaces, lint, types, blueprint freshness, state freshness, the suite, and the suite again under --repeat to catch order and timing luck. It says in words what it did not run, the same honesty the Postgres, Redis and container runs already get. CHANGING.md is the protocol. .github/workflows/verify.yml runs the Postgres, Redis and container halves this machine cannot, the day the repo gets a remote. Two findings while doing it: guards, harness, privacy and tools had never been type-checked by any phase's checks - the first three passed immediately, and tools/gate.py needed 35 mechanical annotations, which it now has, so mypy covers every shipped package. And tests/regression was in no phase's check list, so the gate would not have run it; it is a P28 check now.

- task added: One command that verifies the whole build and says what it did not run (tools/verify.py)
- task added: The public-surface snapshot and the regression suite that guards it (tools/surfaces.py, BUILD/surfaces.json, tests/regression)
- task added: CHANGING.md: the protocol for changing the system after v1
- task added: A CI workflow that runs the Postgres, Redis and container halves a laptop cannot
- exit criterion added: A change that moves a public surface fails a test naming it, and accepting it is a recorded decision
- check added: python -m uv run pytest tests/regression -q

## 2026-09-05 - P28 Docker, portability, handoff packet

**Why:** Caleb decided on 2026-09-05: model access is the Anthropic API directly, not Microsoft Foundry if it can be avoided. Recorded in the blueprint's LLM port row, whose cloud column previously named Bedrock and Vertex and no decision. The reasoning, checked against current platform availability rather than recalled: this build sends one turn with a system prompt and sets adaptive thinking and effort from the model pin on every single call, and both of those are GA on the first-party API and beta on Foundry. Data residency runs opposite to the intuition - the first-party API has an inference_geo control and Foundry has none - so the only genuine argument for a provider-hosted route is network egress, not residency. And the firm's Anthropic account is already sanctioned for client data, so the direct path is one that exists rather than a new procurement. Consequence for the build: the model-pin-names-a-platform work is not needed. It was raised because a pin folded into every plan hash that can be served by two providers lets two runs share a hash, reach different infrastructure and legitimately disagree - the same failure the precedent-snapshot fix closed. With one provider that cannot happen. It returns only if the fallback is taken. The one thing that could overturn this is IT refusing egress from Azure to api.anthropic.com; that is now a question in BUILD/OPEN.md rather than an open architectural choice. Hosting on Azure does not move model access with it: compute, storage, secrets, queue and database all move independently of where Claude is served from. Also settled the same day: Power Automate sits outside the boundary - it notifies and moves files, never drives the pipeline, and no flow is given a database connection string or write access to the outbox.

- blueprint: 'docs/architecture.html' -> 'docs/architecture.html'

## 2026-09-05 - P28 Docker, portability, handoff packet

**Why:** The 2026-09-05 decision to stay on the Anthropic API has exactly one condition attached, and a condition nobody owns is one nobody checks. It becomes a task: IT confirms a container in Azure may reach api.anthropic.com. If it is refused, the provider-hosted adapter and the platform-aware model pin get scoped; if it is granted, the decision stands and nothing changes. Deliberately not worded 'On the work machine' - it is a question for IT rather than evidence gathered at a desk, and the four work-machine tasks stay four.

- task added: With IT: confirm a container in Azure may reach api.anthropic.com, since model access stays on the Anthropic API directly (decided 2026-09-05)

## 2026-09-05 - P29 Scope choices in the admin surface

**Why:** Caleb approved the group-routing proposal on 2026-09-05 and delegated its four open decisions. This is the first of five phases in a new block; the reasoning for all four decisions is in BUILD/proposals/group-routing.md. Today the admin surface takes a scope path as free text, so setting up an engagement means typing 'valuation/esop/repeat' exactly right, and choosing a practice group that has no segments defined resolves silently to the firm layer - correct, and indistinguishable from a considered answer. The scope registry already declares every practice, segment and disposition and which are defined; this makes it the source of the choices rather than a thing to be matched by hand.

- phase added: P29 Scope choices in the admin surface (Block H - Practice groups and their workflows, gate: auto)
- exit criterion: The admin surface offers every declared practice, segment and disposition, and marks the undefined ones
- exit criterion: An engagement whose scope resolves to the firm layer only is visible in the preflight report
- exit criterion: The scope path remains the single stored representation: choosing one adds no second source of truth

## 2026-09-05 - P30 Registered methodology: cleared once, checked every run

**Why:** Decision 2 of the group-routing proposal. Methodology reaches every model call for every engagement in its scope, and nothing checks it for client data - the outbound payload scan only knows the current engagement's identifiers, so a worked example from a real deal in a house-rules document would reach every prompt for every client unnoticed. A live scan was rejected: the client-data patterns deliberately err toward flagging, and a regex that can take a practice group offline mid-run is a worse failure than the one it prevents. So the scan happens once, at registration, by a named person, and what is recorded is the digest of what they cleared. The Context Builder then checks a hash rather than re-running a judgment. An edited file loses its clearance because its digest changes. This is the same shape skills already use, and it is built before the per-group methodology of P31 so that nothing can reach a prompt uncleared.

- phase added: P30 Registered methodology: cleared once, checked every run (Block H - Practice groups and their workflows, gate: auto)
- exit criterion: A methodology file carrying something shaped like client data cannot be cleared
- exit criterion: An edited file loses its clearance automatically, because the digest changes
- exit criterion: The Context Builder refuses an uncleared file, and the refusal names it
- exit criterion: The run-time check is a hash lookup, so it cannot fail on a false positive

## 2026-09-05 - P31 Methodology per practice group

**Why:** Piece D of the group-routing proposal. foundations/ is flat and firm-wide: three files attached to every call unconditionally. Per-group methodology means the same five-layer walk the skills already use, so a valuation run carries the firm and valuation methodology and a consulting run carries the firm and consulting's, and neither carries the other's. Two things come with it. A size ceiling per layer, because this is content on every model call and methodology that grows unchecked is a token bill on every run and a step toward the per-run ceiling. And an entry in the surface snapshot, so a change to what every prompt carries is a visible change rather than a quiet one. Built after P30 so nothing reaches a prompt uncleared.

- phase added: P31 Methodology per practice group (Block H - Practice groups and their workflows, gate: auto)
- exit criterion: A valuation run carries the firm and valuation methodology and not consulting's
- exit criterion: A group with no methodology of its own still carries the firm's
- exit criterion: Methodology past its size ceiling is refused at setup, not discovered in a bill
- exit criterion: A change to what every prompt carries moves the surface snapshot

## 2026-09-05 - P32 The recipe belongs to the engagement

**Why:** Piece C of the group-routing proposal. The recipe - the order work happens in - is a field on the watch, so every engagement under one watched tree shares one workflow. Per-group workflows would need a watch per group, which makes the watch do two jobs: where to look, and what to run. Moving the recipe onto the engagement with the watch's as the default keeps one watch over a client tree while letting each engagement run its own sequence. The config document gains a field, so it is config_document@1.2.0 with 1.1.0 left listed: a contract change is a new version beside the old one, never an edit in place.

- phase added: P32 The recipe belongs to the engagement (Block H - Practice groups and their workflows, gate: auto)
- exit criterion: Two engagements under one watch run different recipes
- exit criterion: An engagement naming no recipe behaves exactly as it does today
- exit criterion: A recipe that does not load is refused at setup, naming the engagement

## 2026-09-05 - P33 Registered recipes

**Why:** Decision 3 of the group-routing proposal. A skill passes eleven governed stages before it runs on client work; a recipe is a YAML file in the repo. That asymmetry is what gets used first once MDs author workflows, because a procedure that could not pass the skill chain can often be expressed as a recipe that reorders governed skills to the same effect. The full chain would be theatre for a file that can only reorder things already governed, but 'which recipes may run on client work' has no answer today and that is the real gap. Registration only: a version, a digest, a named approver, written by the Skill Review Board and nothing else. With P30 this makes one pattern with three consumers - skills, methodology, recipes - rather than three answers to one question.

- phase added: P33 Registered recipes (Block H - Practice groups and their workflows, gate: auto)
- exit criterion: An unregistered recipe cannot run on client work
- exit criterion: A recipe edited after registration loses it, because the digest changes
- exit criterion: Registration names the person who approved it, and refuses without one

## 2026-09-05 - C11 Practice groups, end to end

**Why:** Block H adds five phases past C10, and every block of work ends in a checkpoint: phases that each pass alone can still disagree with each other, which is the whole reason checkpoints exist. This one covers the group-routing work end to end - an engagement labelled by choosing a practice group, running its own workflow, carrying its own cleared methodology and no other group's.

- checkpoint added: C11 after P33, covering P29, P30, P31, P32, P33
- proves: An engagement is set up by choosing its group, runs that group's workflow, and carries that group's cleared methodology and nobody else's

## 2026-09-05 - C11 A group's methodology, and nobody else's

**Why:** C11 was sealed after P33, covering all five phases of Block H, and a checkpoint covers at most four - small on purpose, because one that spans half a block cannot say which phase stopped agreeing with the others. Block H splits cleanly in two anyway: P29 to P31 are about methodology reaching the right runs, P32 and P33 are about workflow. C11 now covers the first three and C12 the last two.

- title: 'Practice groups, end to end' -> "A group's methodology, and nobody else's"
- proves: "An engagement is set up by choosing its group, runs that group's workflow, and carries that group's cleared methodology and nobody else's" -> "An engagement is set up by choosing its practice group, and carries that group's cleared methodology and no other group's"
- after: P33 -> P31

## 2026-09-05 - C12 A group's workflow, and only approved ones

**Why:** The second half of Block H: the workflow a group runs, and which workflows may run at all. Split from C11 because a checkpoint covers at most four phases and Block H has five - and the split is a real seam rather than an arbitrary one, since P29 to P31 are about methodology reaching the right runs and P32 to P33 are about the order that work happens in.

- checkpoint added: C12 after P33, covering P32, P33
- proves: An engagement runs its own group's workflow, and a workflow nobody approved does not run at all

## 2026-09-05 - P29 Scope choices in the admin surface

**Why:** Two findings while building. (1) The blueprint's preflight node said ten checks and there are now eleven: the new one names an engagement whose practice group or segment is declared but not defined, so the scope resolves to the firm layer only. Code and blueprint disagreeing is a finding, so the node's description was corrected rather than left. (2) SCOPE.GROUP_UNDEFINED is a new code, owner config, and it moved the surface snapshot - which is the snapshot doing its job. It is a warning rather than a failure on purpose: resolving to the firm layer is correct behaviour for a group nobody has described yet, and refusing activation on it would make the tool the reason an engagement waits on a conversation between practice leads. What it must never be is silent, because a short list of skills looks exactly like a considered answer. Also recorded: scope_choices() measures what each path would actually resolve to rather than reading the registry's own defined flag, because those two can disagree - a group declared defined with nothing yet written for it - and the resolver is the one that decides what a run gets.

- task added: Correct the blueprint's preflight node: eleven checks, not ten

## 2026-09-05 - P28 Docker, portability, handoff packet

**Why:** Running the suite inside the image found three things a laptop cannot show. Two were real portability bugs: file-type detection fell through to the host mimetypes registry, which answers differently on Debian than on Windows, and the Excel templates are generated rather than tracked, so a clean clone had none. One was a test asserting the compute target had no image tag, which is true on a laptop and false in a container - and the tag being reported there is the manifest doing its job. Fixed by declaring the extension-to-MIME table in intake/fingerprint.py, generating templates from a session fixture, and reading AA_IMAGE from the environment. Adding the criterion that would have caught all three.

- task added: Prove it on a runtime that is not Docker Desktop and name it in HANDOFF.md
- exit criterion added: No test asserts a value that is a fact about one host - file types, generated artefacts and the compute target's image tag are read from a declared table or the environment, so a correct container does not fail

## 2026-09-05 - P28 Docker, portability, handoff packet

**Why:** The proof asked for was on this machine, and that is what was done: podman 6.1.1, image built from a clean clone, 1711 passed and 78 skipped inside it. The human check still described a clone onto the work machine, so signing it would have recorded something that had not happened. The work-machine clone is not dropped - it joins the four tasks already deferred there, which is where evidence nobody on this machine can gather belongs.

- human check: 'You clone the repo onto the work machine, run the suite in the container, and confirm nothing but .env had to change.' -> 'You confirm the container proof done here is enough to call v1 portable: the image built from a clean clone on an OCI runtime that is not Docker Desktop, and the whole suite green inside it. The clone onto the work machine is a task deferred to the work machine, not a condition of this phase.'
- task added: On the work machine: clone the repo, run the suite in the container, and confirm nothing but .env had to change

## 2026-09-06 - P30 Registered methodology: cleared once, checked every run

**Why:** Methodology gets two diagnostic codes, so two public surfaces move. CONFIG.METHODOLOGY_UNCLEARED is the run-time refusal when foundations/ holds a file that is not the cleared version; CONFIG.METHODOLOGY_UNSAFE is the clearance refusal when a file carries something shaped like an engagement's data or an instruction to the model reading it. Both are config-owned, because both are somebody re-reading a document rather than a bug. The blueprint's CONFIG row and the preflight node were updated in the same change, and the preflight count went from ten to twelve there - it had said ten since P29 added the eleventh and nothing read that line.

- task added: Two diagnostic codes and the blueprint rows that carry them

## 2026-09-06 - P30 Registered methodology: cleared once, checked every run

**Why:** The register lives in registries/ rather than governance/, where the plan assumed it. Two reasons, both about the run-time path: the Context Builder consults this on every model call, and importing the governance package would pull the whole eleven-stage chain - including its edge back into harness.door - into that path; and registries/ is where the things a run reads live, beside contracts, scopes, skills and constraints. The clearance act still uses governance's scanners, imported inside the method that scans, so the dependency exists only when somebody is clearing something. The phase check gains registries so the phase type-checks its own code.

- check added: python -m uv run mypy registries

## 2026-09-06 - P31 Methodology per practice group

**Why:** Three surfaces move. constraints.ceilings gains per_methodology_layer, a byte ceiling per layer of foundations/ - this is content on every model call of every run that walks through the layer, so unchecked growth is a standing cost nobody can attribute months later; its note says why the number is the number, which is why the note itself moves too. CONFIG.METHODOLOGY_TOO_LARGE is the refusal preflight raises for it. And the snapshot gains a foundations group - layer, filenames, bytes and one digest over the layer in the order the Context Builder attaches it - because nothing else in the snapshot moved when somebody added a paragraph to a document that every prompt carries, which is exactly the kind of change it exists to make visible.

- task added: A byte ceiling per layer, its diagnostic, and the foundations group in the snapshot

## 2026-09-07 - P34 The run executes: the executor meets the dispatcher

**Why:** The build reached v1 with every component tested and nothing composed. There were app factories nobody called, a worker pool nobody started, and a sweep loop that only ran inside tests - and no test asked whether the parts added up to something a person could start, so nothing said so. tools/serve.py is the composition root that was missing and it starts what can be started: the admin surface, the ops console and the intake sweep. What it cannot start is execution, because graph.execute.StepRunner - the seam the executor was built against in P08 and that P09 was meant to fill - has no production implementation. Every component behind that seam is built and tested. This phase joins them, and names the gap so it stops being invisible.

- phase added: P34 The run executes: the executor meets the dispatcher (Block I - The system runs, gate: auto)
- exit criterion: A skill step of a compiled plan executes through the SkillDispatcher, carrying the run's scope, engagement profile and identifiers
- exit criterion: Which procedure a step runs is derived from the plan and the skill, in one place, never chosen per run by a caller
- exit criterion: Blocked, RepairNeeded and TransportFailure each reach the executor meaning what the executor defines them to mean
- exit criterion: Nothing under skills/ is imported by the runner, and the boundary test still passes

## 2026-09-07 - P35 A released run is driven to an ending

**Why:** A joined StepRunner still needs something to call it on a real run. The worker pool takes a PassRunner it has never been given, and tools/serve.py starts the consoles and the sweep but not the pool - so a run released by intake sits with its lock taken and nothing driving it. This is the second half of the same gap: from a file landing in a watched folder to a deliverable in the outbox, with no test double anywhere in the path.

- phase added: P35 A released run is driven to an ending (Block I - The system runs, gate: auto)
- exit criterion: A run released by intake is picked up and driven to a delivered or halted ending, on a real store, with no test double in the path
- exit criterion: tools/serve.py starts the pool and its readiness report says execution is wired
- exit criterion: Two engagements progress at once while one engagement stays serialised behind its lock
- exit criterion: A blocked run waits for a person and resumes from its frontier rather than restarting

## 2026-09-07 - C13 The system runs

**Why:** Block I joins the two halves that were never joined: the executor to the dispatcher, and the pool to a released run. Either alone leaves the system unable to do the thing it was built for, so they are checked together - and the check is the one thing the component suites cannot ask, which is whether a file landing in a folder becomes a deliverable without anybody in a test writing the middle.

- checkpoint added: C13 after P35, covering P34, P35
- proves: A file landing in a watched folder becomes a deliverable in the outbox, with nothing in the path that exists only in a test

## 2026-09-07 - P34 The run executes: the executor meets the dispatcher

**Why:** Naming the seam in the phase itself rather than only in the reason. An amendment explains a change to somebody reading the history; the phase file is what somebody reads when they pick the work up, and the one identifier that makes this findable in the code is the protocol's name.

- task added: Implement graph.execute.StepRunner in harness/runner.py - the seam P08 built against and P09 was meant to fill

## 2026-09-07 - P35 A released run is driven to an ending

**Why:** A phase with no tasks is a phase nobody can pick up. The exit criteria say what has to be true; these say what to build.

- task added: A PassRunner that drives one pass of a run through the StepExecutor
- task added: tools/serve.py starts the worker pool alongside the sweep
- task added: Delivery on a finished run, and a halted run that says why
- task added: The C13 integration test: a file in the inbox becomes a workbook in the outbox

## 2026-09-07 - P36 Who is asking: identity on both surfaces

**Why:** The review found that neither surface has any authentication, and that the who on every recorded change is a string the client supplies. On a laptop bound to 127.0.0.1 that is correct and costs nothing. At the firm it means anybody who can reach the port can activate an engagement or clear methodology, and that the name on every entry in the change log is unverified - which makes the audit trail decorative exactly where it is supposed to be load-bearing. The blueprint does not mention identity at all, so this is a gap in the design of record rather than a disagreement with it. The exit criteria below do not presume an identity provider, because that decision is the firm's and Entra ID is only likely, not confirmed.

- phase added: P36 Who is asking: identity on both surfaces (Block I - The system runs, gate: auto)
- exit criterion: Neither surface serves anything outside a loopback bind without an authenticated identity
- exit criterion: The who on every config write, activation, clearance and review decision is the authenticated identity, and a client-supplied name is refused rather than trusted
- exit criterion: The identity provider is behind a port like every other deployment choice, so the local run stays a local run with no accounts
- exit criterion: A review decision records the identity that made it, and the precedent store will not accept one without

## 2026-09-07 - C13 The system runs

**Why:** Identity belongs inside the same checkpoint. A system that runs and a system nobody unauthorised can drive are the same claim at the firm, and splitting them would let one pass while the other is open.

- after: P35 -> P36

## 2026-09-07 - P36 Who is asking: identity on both surfaces

**Why:** Tasks, so the phase can be picked up by somebody who was not in this conversation.

- task added: An identity port, with a local adapter that names the operating-system user and refuses outside a loopback bind
- task added: who taken from the authenticated identity on every write, and a client-supplied name refused
- task added: The review surface and the precedent store record the identity that decided
- task added: The blueprint gains identity: it does not mention it at all today

## 2026-09-07 - P31 Methodology per practice group

**Why:** The foundations digest moves, and the reason is a portability bug the container proof caught. A methodology file was hashed with read_bytes, so the same three files gave one digest on a Windows checkout and another inside a Linux image - a byte per line. That is worse than a moving snapshot: a file cleared at the firm on a laptop would read as edited the moment the same repo ran in a container, stopping every run for a change nobody made, and the assembled context would differ byte for byte between the two, which is two idempotency keys for one question. The rest of the system already avoided this without saying so, because a skill body reaches context through read_text and Python translates newlines. registries.methodology.body_of is now the one place that decides what a methodology file is: decoded as text, encoded back with newlines as LF, which is also the byte sequence the model is shown.

- task added: One definition of a methodology file's bytes, so a clearance travels between a laptop and a container

## 2026-09-07 - P32 The recipe belongs to the engagement

**Why:** The contract registry gains config_document@1.2.0, so two public surfaces move: the id list and the schema digest. 1.1.0 stays listed and stays readable - a document is now validated against the version it declares rather than against one constant, because checking every document against the newest version would make each new version retroactively invalidate every document already written, which is the opposite of leaving the old one listed.

- task added: config_document@1.2.0 in the registry, and a document validated against the version it declares

## 2026-09-07 - P33 Registered recipes

**Why:** SCOPE.RECIPE_UNREGISTERED is the refusal when a recipe is not approved for client work, or is not the version that was approved. Config-owned, because the answer is to take the workflow through the board rather than to change any code. The blueprint's SCOPE row carries it too.

- task added: SCOPE.RECIPE_UNREGISTERED, and the blueprint row that carries it

## 2026-09-07 - P36 Who is asking: identity on both surfaces

**Why:** The ports surface gains identity: a seventh port, with a local_user adapter that answers with the operating-system user and refuses any request that did not come from this machine. That refusal is the safety of the whole arrangement - binding the surface to a network address without a provider that authenticates does not quietly work - and it is why identity is a port rather than a check in the admin app: which provider vouches for a name at the firm is a deployment choice, and the surface must not know which.

- task added: The identity port and its local_user adapter, in the ports surface

## 2026-09-08 - P36 Who is asking: identity on both surfaces

**Why:** Round two of the final review: a scripted analyst behind the model door found the review queue unfed, the precedent write-back uncalled, the served runtime without tools, a ledger key that let one client's steps satisfy another's, the manifest refusing its own precedent snapshot, an engagement budget nothing enforced, and files held in silence. Public surfaces changed: decision, resume and halt routes on the ops console, a fourteenth preflight check, the scripted LLM adapter, the rehearsal's --scripted flag, and the manifest contract admitting precedent_snapshot.

- task added: Round two of the final review, with something answering for the model: the review loop closes, decisions become precedent, the ledger names the run, the engagement budget is enforced, held files are reported, and the rehearsal walks the whole loop with --scripted (tests/p35/test_round_two.py)
- check added: python -m pytest tests/p35/test_round_two.py -q

## 2026-09-08 - P36 Who is asking: identity on both surfaces

**Why:** The three consoles now carry Chartwell's brand tokens and fit one screen each; the blueprint's trace wording no longer names traffic-light colours, because the colours are the firm's

- task added: Consoles styled from the brand sheet (Chartwell Templates/shared/brand.css) and laid out to fit one screen per page, panels scrolling inside themselves

## 2026-09-16 - P37 The division focus, and the interview that fills it

**Why:** Caleb, 2026-09-16: the build now serves the non-ESOP valuation division first, because that is the division he works in, with other divisions added later as data. Most of what the system knows about how the work is done is synthetic; the way it becomes his is an interview run from a slash command in Cursor or Claude Code, one question at a time, recorded in a git-ignored knowledge folder and turned into changes through the build's own rules when he says stop. Decided with him: private GitHub repo; Cursor and Claude Code both; knowledge in a git-ignored folder in the repo; ESOP kept but parked; real client documents may be read by the interview; build on stop.

- phase added: P37 The division focus, and the interview that fills it (Block J - Making it his, gate: auto)
- exit criterion: A focus that names an undeclared or parked segment fails the registry load
- exit criterion: Both slash commands run the same protocol, and neither holds behaviour of its own
- exit criterion: The interview's state is read from files, never from a model's memory: coverage, follow-ups, backlog and sessions
- exit criterion: No identifier on the local watch list appears in any file git would commit, and knowledge/ is ignored

## 2026-09-16 - C14 Making it his

**Why:** P37 opens a new block: the build pointed at one division, and the interview that makes it the analyst's. It sits on the scope registry (P05), the admin surface (P29) and the procedure table (P34), so it gets a checkpoint of its own rather than waiting for the block to grow.

- checkpoint added: C14 after P37, covering P37
- proves: The focus division is offered first and can be scoped into, the interview describes it in the resolver's terms, and what the interview learns cannot reach a committed file

## 2026-09-16 - P37 The division focus, and the interview that fills it

**Why:** Caleb, 2026-09-16: knowledge/ is committed, not ignored. The repo is private, and the interview has to travel between this machine and the work laptop through git; a folder copied by hand is one that ends up out of date on one of them. The boundary that still matters is inside the repo: a client name in knowledge/ is fine, the same name in a skill, methodology file or fixture reaches every prompt for every client. The scan now checks everything outside knowledge/.

- task added: knowledge/ committed so the interview travels with the private repo, excluded from the container image
- task dropped: knowledge/ ignored by git and by the container build, with only its README committed
- exit criterion added: No identifier on the watch list appears in any file outside knowledge/, and knowledge/ travels with the repo
- exit criterion dropped: No identifier on the local watch list appears in any file git would commit, and knowledge/ is ignored
- status: done -> open

## 2026-09-16 - P37 The division focus, and the interview that fills it

**Why:** Caleb, 2026-09-16: the first /improve-agent session ran here (eleven high-level questions) and he asked for a base to be built from it. Three things the answers justified: the interview map was wrong for this division (pre-revenue is a quarter of the work, not an edge case, and the forecast, the debt tab and the internal value review had no topic); the pilot he chose - a mature operating company valuation - has an order of work that maps onto skills that exist, so it gets a draft recipe, unregistered, with the forecast and M&A transactions named as missing rather than invented; and how the group works gets a draft methodology file that a person must still clear. Nothing identifying left knowledge/.

- task added: A draft pilot recipe, recipes/mature-company-valuation.yaml, in the analyst's order: historical financials the only required document, comps before WACC before the DCF, the model checks last; unregistered
- task added: Draft non-ESOP methodology at foundations/valuation/non-esop/_segment/how-we-work.md, passing the clearance scan and not cleared
- task added: The interview map corrected from the first session: forecast, debt tab and model checks, internal value review, pre-revenue and purchase price allocation topics
- task added: A next-session question queue at the top of knowledge/followups.md, asked first
- exit criterion added: The pilot recipe compiles for both non-ESOP scopes and waits only for historical financials
- check added: python -m uv run pytest tests/p06 tests/p31 tests/p33 -q
- status: done -> open

## 2026-09-16 - P38 What the research changed

**Why:** Caleb, 2026-09-16: research on AI in valuation practice, to be woven in without questions. Read against the build, it mostly describes the architecture already here - extract with provenance, compute in code, one skill per deliverable, a person signs. What it added: a failure preserved with both numbers rather than smoothed (the QoE tools), which makes the analyst's three model checks buildable now as deterministic code; and, read against the pilot, a defect - a client forecast was bound as historical financial statements with full confidence, so a forecast arriving first could release a run on projected years. Benchmarks, report narrative and build-or-buy are a person's decisions and are held in OPEN.md; declined ideas and the reasons are in docs/research/ai-in-valuation.md.

- phase added: P38 What the research changed (Block J - Making it his, gate: auto)
- exit criterion: The three model checks pass on statements that tie, fail with both numbers on ones that do not, and never pass on missing evidence
- exit criterion: A client forecast shaped like financial statements is classified as a forecast, and cannot satisfy a recipe waiting for historicals
- exit criterion: Every category in the taxonomy has a declared direction, so a new one is caught by a test rather than a run

## 2026-09-16 - P38 What the research changed

**Why:** Closing the forecast defect at the classifier alone left two gaps. Intake binds a document type from the filename before anything reads it, and the default conventions had no forecast type, so a file named Income Statement Forecast bound as financial statements. And every file in a run's set reaches timing normalization, so even a correctly labelled forecast would have been shown to the model building the historical table. Both are now closed in code: forecast conventions in the first setup (a name matching two types is held for a person), and the timing procedure holds forecasts out of the table and escalates a set with only forecasts.

- task added: Forecast filename conventions in the admin's first setup, so a name matching both a statement and a forecast is held rather than bound
- task added: The timing-normalization procedure holds forecasts out of the historical table - payload, tool input and escalation - and escalates a set with no historical file
- exit criterion added: A forecast in a run's file set never reaches the model or the tool that builds the historical table
- check added: python -m uv run pytest tests/p18 tests/p24 -q
- status: done -> open

## 2026-09-16 - C15 What the research changed

**Why:** P38 changed the classifier, the binder's default conventions and the timing procedure at once - three older phases' code - so it gets its own checkpoint rather than riding on C14's.

- checkpoint added: C15 after P38, covering P38
- proves: On a system started the way a person starts it, a client forecast cannot pass for historical statements by name, by contents or at the historical table, and the model checks can place every category the tagging skill writes

## 2026-09-17 - P39 A citation is checked where it points

**Why:** Caleb, 2026-09-17: the full LlamaIndex post behind the research (a due-diligence agent built on LiteParse), to use what fits. Its core is citation verification: a cited number is trusted only once it is found on the cited page, and an unverified one is shown rather than hidden. Read against this build, the Provenance Check did half of that - it required the cited location to exist and never looked at the number there. Tracing where that guard runs, to change it, found the larger problem: the dispatcher called only the schema check, so the Provenance and Tie-Out Checks - both step guards the blueprint marks as existing now - were built, tested and used by the eval harness, and never called on a live run. That is a disagreement between the code and the blueprint, resolved here in the blueprint's favour: both are wired at the composition root, tie-out at the run's recorded tolerance or zero when none is recorded.

- phase added: P39 A citation is checked where it points (Block J - Making it his, gate: auto)
- exit criterion: A figure read off the page with a number its cited rows do not carry fails the Provenance Check, naming both
- exit criterion: A live run's skill outputs pass through the Provenance and Tie-Out Checks, and a tampered output is stopped by the right one
- exit criterion: Every guard the blueprint marks as a fail-closed step guard either speaks on a rehearsal run or is named as silent

## 2026-09-17 - C16 A citation is checked where it points

**Why:** P39 wired guards into the live dispatcher at the composition root - a change to what every run does, reaching back to P10, P13 and P34 - so it gets its own checkpoint, and one that asks the assembled system rather than the guard.

- checkpoint added: C16 after P39, covering P39
- proves: The system a person starts calls every output guard the blueprint runs on a skill step, and every adversarial fixture fires its own guard

## 2026-09-17 - P40 What the second interview changed

**Why:** Caleb, 2026-09-17, second /improve-agent session: eleven answers, then 'build as much as possible' of what they justified. Three corrections to things built on assumptions the answers overturned - the EBITDA procedure's one-time test was looser than the analyst's (an item in every period was the only one flagged; the analyst's rule is one or two periods and not the years before, confirmed with management); the pilot recipe made WACC wait for the comps and let the DCF ignore them (the analyst: comps, transactions and WACC are independent, and the comps' multiples support the DCF's exit multiple); and the draft methodology said a client forecast is adjusted after due diligence (the analyst: it is used unchanged, except interest expense from the debt tab). And one addition: forecast driver baselines, the arithmetic half of a firm-built forecast. The suite's own recipe registration assumed a shipped recipe never changes; it now registers a changed one as the next version.

- phase added: P40 What the second interview changed (Block J - Making it his, gate: auto)
- exit criterion: An add-back proposed as one-time that appears in more than two periods, or in the earliest period, is reviewed by a person
- exit criterion: The pilot's comps and WACC compile to the same level and the DCF compiles after both
- exit criterion: Forecast driver baselines are computed from a real normalized table, every value with its sources and every missing value with its reason

## 2026-09-17 - C17 What the second interview changed

**Why:** P40 changed a P20 procedure, a P37 recipe and the suite's registration fixture, and added a tool that reads P18 and P19's table - enough reach for its own checkpoint.

- checkpoint added: C17 after P40, covering P40
- proves: The analyst's one-time rule holds on a real EBITDA schedule, and the table that schedule read gives forecast driver baselines with their sources

## 2026-09-17 - P40 What the second interview changed

**Why:** The analyst corrected session 2026-09-17-1 in 2026-09-17-2: the data for comps, transactions and WACC is pulled side by side, but beta is the comps' median unlevered beta, so the WACC is not final until the comp set is. Version 2 of the pilot recipe made wacc independent of gpc on the first answer; that was wrong whenever CAPM is used. P41 builds version 3; this criterion is replaced with the corrected one.

- exit criterion added: The pilot's WACC compiles after the comps, and the DCF after both (corrected 2026-09-17-2, built in P41)
- exit criterion dropped: The pilot's comps and WACC compile to the same level and the DCF compiles after both
- status: done -> open

## 2026-09-17 - P41 What the third interview changed

**Why:** Caleb, 2026-09-17, third /improve-agent session: fourteen answers, and all four proposed builds approved. The session corrected my own change of the day before - the WACC is not independent of the comps, because beta is the comp set's median unlevered beta, relevered - so the pilot recipe goes to version 3. The methodology draft takes in the session: cost of capital, the debt note and its fallbacks, the exit multiple, repeat clients, fair market value on a controlling basis, source precedence, what the MD reviews. The beta arithmetic becomes a tool, with the relevering formula a required argument because the firm's formula is unconfirmed. And the analyst's rules for disagreeing sources - audited over internal, most recent within a kind, an older audited file against a newer internal one to a person - are applied in the timing normalizer, which until now took no figure on any disagreement. The contract does not change: a settled disagreement stays in the alignment report, marked, and only open ones become review items.

- phase added: P41 What the third interview changed (Block J - Making it his, gate: auto)
- exit criterion: A disagreement the analyst's rules settle has a figure from the right source that ties and cites it, and is still listed in the alignment report
- exit criterion: An older audited source against a newer internal one, a tie in arrival, or an unknown arrival time takes no figure and reaches a person
- exit criterion: Beta is never relevered without a named formula, and the median names every comp it used and left out

## 2026-09-17 - C18 What the third interview changed

**Why:** P41 carried an audit flag and an arrival time from the reader through the driver into the timing normalizer - four phases' code on one path - and changed the pilot recipe again, so it gets its own checkpoint.

- checkpoint added: C18 after P41, covering P41
- proves: An audit opinion read from a PDF is on the record, disagreeing statements are settled by the analyst's rules only where they apply without doubt, and the pilot's cost of capital waits for the comps

## 2026-09-17 - P42 The consoles, easier to use

**Why:** Caleb, 2026-09-17: make the dashboards look better and easier to use, and keep finding improvements. Read by screenshot against a rehearsal firm, the consoles were consistent but hard to act on: runs listed by hash with no client, every state the same grey, nothing open until clicked, a review item accepted from the list without its source or proposal ever shown - which bypassed the review surface's own order - and every question asked through a browser pop-up. The reworking found two bugs: a finished run's live feed reconnected and replayed its whole history over and over, because a closed EventSource reconnects on its own; and a refused resume, halt or decision failed silently, because the page handed a caught error to a function that reads a response. A third was caught before it shipped: a shared helper took a name the Analytics page already declared, which would have stopped that page's script entirely.

- phase added: P42 The consoles, easier to use (Block J - Making it his, gate: auto)
- exit criterion: No page uses a browser pop-up, declares a name twice, or ships a script that does not parse
- exit criterion: A review item's proposal is shown only on request, and accepting or correcting is not offered before it
- exit criterion: A finished run's stream is closed rather than replayed, and a refused action is reported
- exit criterion: Runs and review items name the client, and an engagement names what its profile still lacks

## 2026-09-17 - C19 The consoles, easier to use

**Why:** P42 joined the console to the roster at the composition root and rebuilt pages owned by three earlier phases; the pages were tested as strings, so the checkpoint runs them against the data they render and the routes they call.

- checkpoint added: C19 after P42, covering P42
- proves: Runs and review items name the client the roster knows, every served page is one clean script namespace that asks nothing through a pop-up, and the review panel's round trip works through the real routes

## 2026-09-17 - P43 Easy to start and use

**Why:** Caleb asked for a deep dive on making the tool very easy for him to use. Walking it as he would found three gaps: nothing on the page set up a watch or a destination, a client's files could only be placed by working out a folder path, and settings written in .env (the model adapter, folders, database) were silently ignored on a local start because only secrets were read from the file.

- phase added: P43 Easy to start and use (Block J - Making it his, gate: auto)
- exit criterion: A file added from the page lands only in its engagement's folder, by name, on local storage, for an engagement that is not archived, and the change is recorded with its digest
- exit criterion: A deliverable downloads only if it is inside the delivery folder and matches the digest recorded at release
- exit criterion: A setting in .env reaches a locally started server, and a value in the real environment wins
- exit criterion: Help is linked from every page, its glossary names only words the pages use, and the start script parses

## 2026-09-17 - C20 Easy to start and use

**Why:** P43 closes the ease-of-use deep dive: the start path, the page and the folders meet at the composition root, and that join needs its own proof.

- checkpoint added: C20 after P43, covering P43
- proves: A setting written only in .env reaches the composed server, a person sets up a watch and destination and adds a client's file from the page into the folder the sweep reads, recorded against them, and Help is served beside every console

## 2026-09-17 - P44 The dashboards tell the truth

**Why:** Five reviews of the dashboards - a valuation MD, a frontend engineer, an AI architect, a working analyst and a security engineer - found the record holds far more than the screens show, and that three things on screen are not true: a clean run is painted in the colour that means 'needs attention', an empty Analytics page claims nothing has failed when nothing has run, and the inbox asks for answers on runs a newer file has already replaced.

- phase added: P44 The dashboards tell the truth (Block J - Making it his, gate: auto)
- exit criterion: Every verdict the scorecard can emit maps to a tone, and a passing run is not painted as needing attention
- exit criterion: No empty state claims a rate or an absence that has no denominator behind it
- exit criterion: A run's decisions are readable over HTTP and on the page, with the reveal recorded beside each
- exit criterion: An item on a superseded run is not offered for answering
- exit criterion: Alerts and SLA escalation happen with no browser open

## 2026-09-17 - P45 Safe to leave open

**Why:** The security review found the console trusts a request header for the only authentication input it has, accepts any Host so a page the operator visits can drive it by DNS rebinding, and renders client-file text into single-quoted inline handlers that esc() does not escape - which is stored XSS from a workbook, and breaks every button on a client called O'Brien. The engineer's review found the same escaping gap plus a set of failures that read as calm: a server that is down renders as 'no runs yet', a finished-looking page that has silently stopped streaming, and modals that wire themselves to each other's fields.

- phase added: P45 Safe to leave open (Block J - Making it his, gate: auto)
- exit criterion: No page builds a script handler out of data, and esc() escapes every character that could close one
- exit criterion: A request with a foreign Host or Origin is refused, and the ops routes carry the identity check on their own
- exit criterion: When a load fails the page says so, and no empty state or skeleton stands in for it
- exit criterion: A dialog opened over another does not take the first one's fields, and a decision cannot be sent twice

## 2026-09-17 - C21 The dashboards, reviewed

**Why:** P44 and P45 answer five reviews of the dashboards: what they say is now what the record says, and the console is safe to leave open on a machine that holds client work. The join between the composition root, the run store and both consoles is where those changes meet.

- checkpoint added: C21 after P45, covering P44, P45
- proves: A request under another name is refused before a route runs, reading the console writes nothing, a run's decisions are readable with the reveal beside each, an item on a replaced run is asked of nobody, and every served page says when it cannot reach the server

## 2026-09-17 - P46 The design language, set properly

**Why:** Caleb's words: it looks like an AI made it, and it needs to look professional and expensive. The stylesheet had grown by accretion - arbitrary gaps, one grey type size for nearly everything, a saturated badge on every row, and a hundred and eighteen bordered chips for a run that touches eight of them. The palette also failed its own promise: the grey the explanatory prose was set in sat at 3.4:1 on the paper behind it.

- phase added: P46 The design language, set properly (Block J - Making it his, gate: auto)
- exit criterion: Every ink token meets its stated contrast against the surface it is read on, computed rather than asserted
- exit criterion: No page defines a colour or a type size of its own; both come from the tokens
- exit criterion: The keyboard has a visible focus ring, and motion respects a reduced-motion preference

## 2026-09-17 - C22 The design language

**Why:** P46 rewrote the stylesheet every surface is built on and touched two pages' markup; what a browser is actually served is where that has to be proved.

- checkpoint added: C22 after P46, covering P46
- proves: Every served page carries the one stylesheet and its measured ink, none carries a colour or a type size of its own, and the keyboard's focus ring and a reduced-motion preference are served with it

## 2026-09-17 - P47 Panels that earn their space

**Why:** Looking at the rebuilt pages rather than reading them: the panel a person actually reads - the run's own detail - was being cut at its fifth line while the map of the architecture had the largest share of the screen, and a panel cut by the fold said nothing about there being more. The Analytics page printed rates with no denominators, so 0.0% on two runs and 0.0% on two hundred looked alike, and a green first-pass yield could be earned by a single run.

- phase added: P47 Panels that earn their space (Block J - Making it his, gate: auto)
- exit criterion: No rate on the Analytics page is rendered without the count it was computed from
- exit criterion: A tone is not applied to a rate whose denominator is under ten
- exit criterion: A panel whose content overflows shows it, and names its own count

## 2026-09-17 - C23 Panels that earn their space

**Why:** P47 changed what the analytics computation reports and how three pages lay out what they hold; the join between them is what a browser is served.

- checkpoint added: C23 after P47, covering P47
- proves: The analytics route carries the count behind every rate, and every served page carries its counts, the shadow at a cut edge, and a board that gives the run's own detail two rows of three

## 2026-09-17 - P48 The whole design, painted with one run

**Why:** Caleb asked for the thing he always wanted this to do: from a run, open the whole node system as the blueprint draws it - every node, its edges, in the dashboard's colours - with each node's border saying what happened there on that run. The Run trace panel lists the nodes a run touched, grouped and without edges, which answers what it did and not where in the system it happened.

- phase added: P48 The whole design, painted with one run (Block J - Making it his, gate: auto)
- exit criterion: Every node of the blueprint is drawn, at the position the blueprint gives it
- exit criterion: A node's border is the state the run's trace recorded for it, and a node the run never reached is drawn as never reached
- exit criterion: What a run recorded against a node is readable from the node
- exit criterion: A node the run names and the blueprint does not have is reported on the map rather than discarded

## 2026-09-17 - C24 The whole design, painted with one run

**Why:** P48 changed the blueprint export, the graph route and the Activity page so a run can be laid over the design of record; the comparison between the two is what has to hold.

- checkpoint added: C24 after P48, covering P48
- proves: The console serves every node of the blueprint at the position the blueprint gives it, the Activity page carries the map and a way into it, and a run's trace can be laid over that drawing - including the name it records that the design has no node for

## 2026-09-17 - P49 The map, made to work with

**Why:** A review of the map as a thing to work with rather than look at. It showed which nodes a run touched and not the order it touched them in, which is the first question anybody has of a run. Its 240 edges were drawn at one weight, so picking a node said nothing about what feeds it or what it feeds. There was no way to find one of 118 nodes by name. The legend was a picture of the colours rather than a way to use them. And the keyboard had 118 stops in it, none of which said what state the node it landed on was in.

- phase added: P49 The map, made to work with (Block J - Making it his, gate: auto)
- exit criterion: The order a run went through the design is on the map and in the list
- exit criterion: Picking a node shows what it is joined to, and lets a person walk to it
- exit criterion: A node can be found by name, and the states can be shown and hidden
- exit criterion: The map can be worked entirely from the keyboard, and says what is selected

## 2026-09-17 - C25 The map, made to work with

**Why:** P49 is a browser view, and what it needs from the system - events with a node and a time, edges with their ends, one script namespace - is what a checkpoint can hold.

- checkpoint added: C25 after P49, covering P49
- proves: The order a run went through the design is derivable from what the console serves, a node's neighbours come from the blueprint's own edges, and the page serves the map's controls in one script namespace

## 2026-09-17 - P50 The map, made correct

**Why:** Five reviews of the full-design map - a visual design director, an information-visualization specialist, an accessibility engineer, a frontend engineer and the two people who read it - found defects before they found preferences: edges that miss their boxes by the difference between a CSS height and a hard-coded 52, a drag threshold that measures the wrong interval and deselects on a slow pan, Escape in the find box closing the whole view, a focus-restore target the five-second poll detaches, a fetch failure painted as 'nothing ran', and a step onto run_driver blanking the canvas. Correct first, then draw.

- phase added: P50 The map, made correct (The consoles, gate: auto)
- exit criterion: The node box is exactly the height the edge maths assumes, and a test holds the two to one exported number
- exit criterion: A slow pan does not clear the selection; a fast one still does not pick a node
- exit criterion: A failed trace or events fetch is reported, and the 'Nothing ran' statement is never made from a network error
- exit criterion: Hidden states are hidden: not focusable, not clickable, not stepped onto, and their edges go with them
- exit criterion: Every node keeps the colour of what the run did there, whatever else is marked on it

## 2026-09-17 - P51 The map, drawn like a drawing

**Why:** The same five reviews, on the drawing rather than the defects. The visual director's charge was that the map is intelligently specified and barely drawn: five states built from five unrelated recipes with two coloured shadows and a raw hex; 240 edges with no direction and a dash rule keyed on an edge kind that does not exist; a legend that draws its own copy of the nodes and has already drifted from them; ten type sizes, none on the scale, in the one stylesheet the design-system test cannot see; and a stage that paints over its own gradient so there is no sheet, no ground and no frame. The information-visualization review added the measurement that makes it urgent: the view always opens at about 0.31, inside its own far-zoom mode, where a 1px state border renders at a third of a pixel and the five fills sit inside a single deltaE-7 band.

- phase added: P51 The map, drawn like a drawing (The consoles, gate: auto)
- exit criterion: The map opens above its far-zoom threshold, so the border that carries state is never drawn sub-pixel on first sight
- exit criterion: Every edge says which way it goes, and guard, loop and masked edges are distinguishable from flow
- exit criterion: A test runs the design system's own two rules - no colour of its own, no size off the scale - over the map's stylesheet, which until now it could not see
- exit criterion: The legend's swatches are generated from the same rules as the nodes, so the key cannot drift from the drawing

## 2026-09-17 - P52 The map, answering what a person asks

**Why:** The fifth review read the map as the two people who use it - a managing director with thirty seconds, and a three-month analyst in front of a halted run at seven in the evening - and found that the screen is about the design while both of them came to it about a run. It leads with '20 of 118 touched', which the MD reads as ten per cent complete against a denominator that includes every connector and port no run ever touches. It does not say the verdict, what it cost, how long it took, where it stopped, what would have come next, or what to do now - and the buttons that would do it are on the panel this overlay covers. A node this run was blocked from reaching is drawn exactly like one no run has ever used.

- phase added: P52 The map, answering what a person asks (The consoles, gate: auto)
- exit criterion: A person who has never seen the tool can say, from the first screen and without clicking, which run this is and what happened to it
- exit criterion: The nodes this run was blocked from reaching are distinguishable from the ones nothing ever uses
- exit criterion: No accent-coloured edge asserts a flow the run did not take
- exit criterion: Every string on the screen is one of the words the glossary or the analyst uses, and a test holds the list

## 2026-09-17 - P50 The map, made correct

**Why:** The blueprint has no node-height constant to export: it measures each box (NODES.forEach(n=>{n._h=n._el.offsetHeight||86})) and routes from the real edge. Copying a number into the exporter would have created a third place for the height to live. The map instead fixes the box at one height in its own stylesheet - correct, because the coordinate grid is absolute pixels and a box that breathes with the fluid root while the grid does not is the drift itself - and measures a built node before computing any edge. The stylesheet is then the single source, and a change to it moves the edges with it.

- task added: Fix the node box to one height in the map's stylesheet, and measure a built node before computing an edge, so the drawing has one source for it
- task dropped: Bind the node box to the height the edge geometry uses - export node_height from the blueprint beside node_width so one number serves both
- exit criterion added: The node box is exactly the height the edge maths draws to, measured rather than asserted, so the stylesheet and the geometry cannot disagree again
- exit criterion dropped: The node box is exactly the height the edge maths assumes, and a test holds the two to one exported number

## 2026-09-17 - C26 The map, whole

**Why:** P50, P51 and P52 are one piece of work on one view - the defects five reviews found in the full-design map, the drawing itself, and the questions a person brings to it. A checkpoint covering the three is what proves they agree with each other and with the console that serves them, rather than each passing alone.

- checkpoint added: C26 after P52, covering P50, P51, P52
- proves: The full-design map, on the assembled system: the drawing is the blueprint's own geometry at a size its marks survive, the state a run left on each part is what the console serves, and the view answers where a run stopped without contradicting the run's own page.

## 2026-09-17 - P53 Three silent wrongs

**Why:** Three reviews of the whole system - an engine defect hunt, a read of it as the analyst who has to use it, and a security audit - found the same species of defect three times over: the code silently does something other than what it says, and says nothing. A material add-back auto-accepted because materiality was tested on a signed amount. Every figure from a comparative PDF statement was the prior year, past provenance and past footing, because the reader takes the last column. And a person named in an add-back rationale crossed from one client's engagement to another's through the Precedent Store, because the masker is only ever told the client's company name and the check that should have caught it was scanning against an empty register. All three were reproduced against the real code before anything was changed.

- phase added: P53 Three silent wrongs (The consoles, gate: auto)
- exit criterion: A material add-back routes to review whether its figure is positive or negative, and a test proves it by failing without the fix
- exit criterion: A comparative statement is flagged and escalated; a single-column one and ordinary prose are not
- exit criterion: A rationale naming a person is refused into the Precedent Store, an ordinary add-back rationale is not, and neither the event nor the diagnostic quotes what was found
- exit criterion: Every client name yields at least one identifier for the masker

## 2026-09-17 - C26 The map, whole

**Why:** P53 lands in the same block and past the checkpoint that was meant to close it. The three silent wrongs it fixes are not about the map, but they are the same session's work on the same system, and a checkpoint that stopped at P52 would leave the last phase uncovered - which tests/p01 refuses, correctly.

- proves: "The full-design map, on the assembled system: the drawing is the blueprint's own geometry at a size its marks survive, the state a run left on each part is what the console serves, and the view answers where a run stopped without contradicting the run's own page." -> "The full-design map on the assembled system - the drawing is the blueprint's own geometry at a size its marks survive, the state a run left on each part is what the console serves, and the view answers where a run stopped without contradicting the run's own page - and the three silent wrongs found beside it: materiality read as magnitude, a comparative statement stopped rather than misread, and a person's name refused into the store that is read across clients."
- after: P52 -> P53

## 2026-09-17 - P50 The map, made correct

**Why:** The checks were written as `python -m pytest`, where every other phase in the plan writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase closes, or refuses, on a verdict about nothing.

- check added: python -m uv run pytest tests/p50 -q
- check dropped: python -m pytest tests/p50 -q

## 2026-09-17 - P50 The map, made correct

**Why:** The checks were written as `python -m pytest`, where every other phase in the plan writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase closes, or refuses, on a verdict about nothing.

- check added: python -m uv run pytest tests/p48 tests/p49 -q
- check dropped: python -m pytest tests/p48 tests/p49 -q

## 2026-09-17 - P50 The map, made correct

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python tools/verify.py

## 2026-09-17 - P51 The map, drawn like a drawing

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python -m pytest tests/p51 -q
- check added: python -m uv run pytest tests/p51 -q

## 2026-09-17 - P51 The map, drawn like a drawing

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python -m pytest tests/p46 tests/p48 tests/p49 tests/p50 -q
- check added: python -m uv run pytest tests/p46 tests/p48 tests/p49 tests/p50 -q

## 2026-09-17 - P51 The map, drawn like a drawing

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python tools/verify.py
- check added: python -m uv run python tools/verify.py

## 2026-09-17 - P52 The map, answering what a person asks

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python -m pytest tests/p52 -q
- check added: python -m uv run pytest tests/p52 -q

## 2026-09-17 - P52 The map, answering what a person asks

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python -m pytest tests/p48 tests/p49 tests/p50 tests/p51 -q
- check added: python -m uv run pytest tests/p48 tests/p49 tests/p50 tests/p51 -q

## 2026-09-17 - P52 The map, answering what a person asks

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python tools/verify.py
- check added: python -m uv run python tools/verify.py

## 2026-09-17 - P53 Three silent wrongs

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python -m pytest tests/p53 -q
- check added: python -m uv run pytest tests/p53 -q

## 2026-09-17 - P53 Three silent wrongs

**Why:** The checks were written as `python -m pytest`, where every other phase writes `python -m uv run pytest`. The gate only rewrites the uv form, so these ran the system interpreter, found no dependencies, and reported FAIL for four phases' worth of tests that all pass. A check in the wrong shape is worse than no check: the phase refuses, or closes, on a verdict about nothing.

- check dropped: python -m pytest tests/p12 tests/p16 tests/p17 tests/p18 tests/p19 tests/p20 -q
- check added: python -m uv run pytest tests/p12 tests/p16 tests/p17 tests/p18 tests/p19 tests/p20 -q

## 2026-09-17 - P51 The map, drawn like a drawing

**Why:** No other phase in the plan names `tools/verify.py` as a check - verify is run once over the tree, not three times inside three closes, and running the whole suite per phase is what made these closes take an hour each. The phase checks stay the tests the phase is about; verify stays the thing run at the end of a session.

- check dropped: python -m uv run python tools/verify.py

## 2026-09-17 - P52 The map, answering what a person asks

**Why:** No other phase in the plan names `tools/verify.py` as a check - verify is run once over the tree, not three times inside three closes, and running the whole suite per phase is what made these closes take an hour each. The phase checks stay the tests the phase is about; verify stays the thing run at the end of a session.

- check dropped: python -m uv run python tools/verify.py

## 2026-09-17 - P54 The interview can finish again

**Why:** The scan that keeps a client's name inside knowledge/ has never once done its job: it reported clean over an empty register until P53, and has refused every session since. Neither state is a check, and the close-out of every /improve-agent session runs it.

- phase added: P54 The interview can finish again (The interview, gate: auto)
- exit criterion: scan returns 0 on a knowledge tree with no session logs, 1 on answers with an empty register, and scans for real when both are present - each proved by running the command
- exit criterion: Every test in the phase fails when its fix is reverted
- exit criterion: status names an empty register before the first question rather than after the last

## 2026-09-17 - C27 The interview can finish again

**Why:** P54 stands alone: it is the one thing blocking the next /improve-agent session, and it is being handed back before the engine work behind it starts.

- checkpoint added: C27 after P54, covering P54
- proves: The check CLAUDE.md names as what keeps a client's name inside knowledge/ answers honestly in all three states on the repo as it stands - refusing an empty register over real answers, passing on a clone nobody has been interviewed on, and scanning for real when there is something to scan - and the protocol, the map and the session that run it all still describe the same command.

## 2026-09-17 - P55 Built, and wired to nothing

**Why:** Three things are built, registered, tested in isolation and connected to nothing in the only wiring that runs. Two of the three are reproduced rather than caught by the nearest end-to-end test, which is why each passed a full suite while doing nothing.

- phase added: P55 Built, and wired to nothing (The consoles, gate: auto)
- exit criterion: A served run assembles context from the Precedent Store, proved by a test that fails when the keyword argument is removed
- exit criterion: serve.py --check reports precedent retrieval, and reports it unjoined when the wiring drops it
- exit criterion: A release step runs end to end against a constructed ReleaseGate rather than raising AttributeError into an undiagnosed quarantine
- exit criterion: A guard failure's quarantine carries its diagnostic code and appears in the analytics failure-code breakdown

## 2026-09-17 - C28 Built, and wired to something

**Why:** P55 closes the block: the three joins it makes are separable from the loop work behind them, and each is provable on the assembled system today.

- checkpoint added: C28 after P55, covering P55
- proves: The system the command assembles reads precedent into every context it builds, carries what a release gate is built from, and records a failure under the code it arrived with - each asked of the object build() returns rather than of a double, because a double would have been wired correctly by whoever wrote it.

## 2026-09-17 - P56 The register, fillable from what was already said

**Why:** The register that keeps a client's name inside knowledge/ is empty after three sessions, and the only way to fill it is for a person to remember every name they have ever mentioned. Nobody can do that, which is why it is still empty.

- phase added: P56 The register, fillable from what was already said (The interview, gate: auto)
- exit criterion: suggest names the candidates in this repo's knowledge/ and says which file and line each came from
- exit criterion: It writes nothing: identifiers.txt is unchanged after it runs, proved by a test
- exit criterion: A term already in the register is not proposed again, and ordinary prose is not proposed at all

## 2026-09-17 - P56 The register, fillable from what was already said

**Why:** suggest found no client names in three sessions of answers - the interview has been conducted generically throughout. So the refusal is a false alarm here, and the missing piece is not a better detector but a way for a person to record that they looked and there was nothing to register, which expires the moment a new answer arrives.

- task added: A person can record that the register was reviewed and is deliberately empty, and that acknowledgement expires when a session newer than it is recorded
- task added: register adds a name from the command line, so a session does not hand-edit the file mid-conversation
- exit criterion added: An acknowledged-empty register scans clean and names who reviewed it and when; one with a session recorded after the review refuses again

## 2026-09-17 - C29 The register, fillable

**Why:** P56 closes the interview block: the register can now be filled from what was already said, and an empty one can be honest. The engine work that follows is a different block.

- checkpoint added: C29 after P56, covering P56
- proves: A name enters the register because a person put it there, and a person is given what they need to do it: what in knowledge/ has the shape of a name and where it appeared, a command that adds one, and - for a session that named nobody, which the first three did - an acknowledgement that a person signed and that expires the moment another session is logged. No path lets the check pass without somebody having looked.

## 2026-09-17 - P57 Approving a recipe on a machine that has none

**Why:** recipes/registered.yaml is gitignored on purpose and the only writer is SkillBoard.register_recipe, called from two test files and nothing else. On a clean clone no recipe loads, preflight check 10 fails, no engagement activates and no run starts - with nothing to click. It is the first thing that will stop the work-machine clone.

- phase added: P57 Approving a recipe on a machine that has none (The consoles, gate: auto)
- exit criterion: A recipe can be approved from /admin on a clean clone, the approver's name is on the governance chain, and preflight check 10 goes green as a result
- exit criterion: The route refuses anything that is not an approval, the way board.register_recipe already does
- exit criterion: Nothing writes recipes/registered.yaml except the board, proved by a test that fails if a second writer appears

## 2026-09-17 - C30 A machine that can be started

**Why:** P57 stands on its own: it is what makes a clean clone startable, and it is the last thing before the loop work, which is a larger change to the engine rather than to a surface.

- checkpoint added: C30 after P57, covering P57
- proves: A workflow can be approved from /admin by a named person with a recorded reason, through the board and into the governance chain, so a clean clone goes from nothing-will-run to something-will - and the register is still written by nothing but the board, still not committed, and still refuses a recipe edited since somebody read it.

## 2026-09-18 - P58 The documented command works, or says why

**Why:** Every command docs/USING.md tells a person to run dies with ModuleNotFoundError unless they happen to be in an activated shell. Found by running the rehearsal exactly as CLAUDE.md documents it and getting a traceback - the same class of mistake as the phase checks written in the wrong shape, one layer further out where a person meets it.

- phase added: P58 The documented command works, or says why (The consoles, gate: auto)
- exit criterion: python tools/serve.py --check from a bare interpreter prints what to run and exits non-zero, rather than a traceback
- exit criterion: Every command in docs/USING.md and CLAUDE.md is one that works from a fresh shell, proved by a test that reads them

## 2026-09-18 - C31 What a person is told to type

**Why:** P58 closes with P57: between them they are what a clone on the work machine meets - the commands that get it started, and the approval that lets it run anything.

- checkpoint added: C31 after P58, covering P58
- proves: Every command the guide and the session rules give works from a fresh shell, the one tool that must not need the environment still does not, and a tool run without it names the command to type instead of raising somebody else's ImportError five hundred lines in.

## 2026-09-18 - P07 The assertion suites

**Why:** The check ran whatever python PATH resolved to. gate.resolve() only rewrites a command beginning 'python -m uv run ', so this used the system interpreter with none of the project's dependencies and has been reporting on nothing since P07 closed. Reopened and re-closed rather than corrected in place, so the done mark rests on a verdict the project interpreter actually produced.

- check dropped: python tools/export_architecture.py --check
- check added: python -m uv run python tools/export_architecture.py --check
- status: done -> open

## 2026-09-18 - P36 Who is asking: identity on both surfaces

**Why:** Written 'python -m pytest' rather than 'python -m uv run pytest', so it ran the system interpreter with no dependencies and reported on nothing. Reopened and re-closed so the done mark rests on a real verdict.

- check dropped: python -m pytest tests/p35/test_round_two.py -q
- check added: python -m uv run pytest tests/p35/test_round_two.py -q
- status: done -> open

## 2026-09-18 - P01 Project structure and build-state system

**Why:** Two checks ran whatever python PATH resolved to rather than the project's interpreter. 'uv sync --frozen' installs into whichever environment answers, which is not necessarily the one the suite runs in; it is replaced by an import of the four packages everything else depends on, through uv, which is what that check was actually for. 'gate.py render' stays bare and is now correct by intent rather than by luck - P58 made gate.py's independence from the project environment a documented, tested property, because it is the tool that installs and checks the others and cannot be the one that needs them. Corrected in place and NOT re-closed on the new checks: P01 is the one phase that cannot be reopened, because tests/p01/test_structure.py asks open_phases()[0] where the build is, and with P01 open every package built by a later phase reads as running ahead of the plan. See LEDGER.md. The checks are right from here; P01's own done mark still rests on the old verdict, and that is recorded rather than hidden.

- check dropped: python -m uv sync --frozen
- check added: python -m uv run python -c "import fastapi, sqlalchemy, yaml, cryptography"

## 2026-09-18 - P59 The graph owns every loop, in fact

**Why:** guard_repair, tieout_repair and self_verification are declared on every shipped recipe, given integer ceilings the compiler checks, and compiled into regions on every plan - and nothing at runtime can enter one, because RepairNeeded is raised only by a test double. 'The graph owns every loop' is a non-negotiable that is currently false.

- phase added: P59 The graph owns every loop, in fact (The engine, gate: auto)
- exit criterion: A schema, provenance or tie-out rejection on a step declaring the matching region re-runs that step with the guard's failure in its context, and the second pass's context_ref differs from the first's
- exit criterion: The feedback blob is masked with the run's own identifiers before it is written
- exit criterion: RepairNeeded is raised in production code outside tests/, and a test fails if it stops being
- exit criterion: A guard failure on a step with no declared region quarantines immediately with no loop event
- exit criterion: No plan hash changes and export_architecture --check stays green with no re-export

## 2026-09-18 - P59 The graph owns every loop, in fact

**Why:** Self-verification is dropped from this phase and recorded as a finding instead. Making the runner demand it is two lines; doing it quarantines every run at tagging with 'no verification pass for line-item-tagging', because the region is declared on tagging in every shipped recipe and only ebitda-normalization has a verifier. That is the system correctly refusing to pretend a declared control ran, and it is also every run stopping. Which of the two is wrong - the declaration or the missing skill - is a person's call, not a thing to settle at the end of a night. The guard-triggered loops, which is what the phase was actually about, are unaffected.

- task added: The gap that stops self-verification is named where it cannot go quiet, rather than worked around
- task dropped: Self-verification is demanded by the runner rather than arranged by whoever wired the test

## 2026-09-18 - C32 A loop that can be entered

**Why:** P59 closes the block. The guard-triggered loops are real; the two regions that remain unreachable each need a decision rather than a fix, and both are on OPEN.md.

- checkpoint added: C32 after P59, covering P59
- proves: A schema, provenance or tie-out rejection on a step whose recipe declares the matching region re-runs that step with the guard's own verdict in its context, masked with the run's identifiers by the one object that holds them - and nothing can name a region the recipe did not declare, substitute one loop for another, or raise a ceiling. The plan hash does not move and the blueprint needs no re-export, because the code caught up to what the design already said.

## 2026-09-18 - P60 A quarantine that leaves something behind

**Why:** RunStore.hold() is the only writer of a quarantine record and is reachable only from LoopController.exhaust, so the quarantine store has never held anything - against constraints.yaml's own rule that exhaustion always produces an artifact. And on_failure, which every recipe declares on every step, is parsed, validated, carried on Step, folded into the plan hash, and read zero times by anything that executes: halt, review and quarantine all behave identically.

- phase added: P60 A quarantine that leaves something behind (The engine, gate: auto)
- exit criterion: store.quarantines() is non-empty for every run with a quarantined step, and a resumed pass over the same step key does not write a second record
- exit criterion: on_failure review opens an item, quarantine opens none, and halt ends the pass with the run closed out halted and a manifest written
- exit criterion: The executor never moves a run into a terminal state
- exit criterion: Every quarantine event carries the code its failure arrived with, including transport exhaustion

## 2026-09-18 - P60 A quarantine that leaves something behind

**Why:** Adds one public surface: the diagnostic code PROCESS.TRANSPORT_EXHAUSTED, owner system. Transport exhaustion was the one ending reaching _quarantine with no code at all - every other either carried a diagnostic or had one in hand and dropped it - so a run that failed because nothing answered was recorded as uncoded, and ops/analytics.py, which ranks the failure breakdown by that column, could not tell it from any other unlabelled ending. Added to registries/errors.py with a what_now saying what to check, and to the blueprint's ERRCODES table beside the other PROCESS codes, because a diagnostic the design does not list is one nobody reading the design can look up.

- task added: A new diagnostic code for transport exhaustion, in the registry and in the blueprint's table

## 2026-09-18 - C33 A run that ends says so

**Why:** P60 closes the engine block: the loops turn and what an ending leaves behind is real. What remains on OPEN.md needs a decision rather than a fix.

- checkpoint added: C33 after P60, covering P60
- proves: Every quarantined step leaves exactly one record whatever ending produced it, a resumed pass over the same key does not write a second, and the three failure policies every recipe declares finally mean three different things - review tells a person, quarantine does not, halt ends the run through the one door that writes a manifest, which is the driver's and never the executor's.

## 2026-09-18 - P61 What the admin surface records, and what it offers

**Why:** Found by using the approval route as a person rather than testing it: approving a recipe whose exact bytes are already approved writes a governance chain entry and no register row, because the register is write-once per digest and returns the existing entry. The chain then says one person approved what the register says another did. Found alongside the auto-accept bar, which had no value a person had chosen.

- phase added: P61 What the admin surface records, and what it offers (The consoles, gate: auto)
- exit criterion: A second approval of the same file is refused with who approved it and when, and appends nothing to the governance chain
- exit criterion: A recipe edited since approval can still be approved, and that path is unchanged
- exit criterion: The profile skeleton offers 0.90 with owner-related always reviewed, and the decision is recorded

## 2026-09-18 - C34 The setup surface, used

**Why:** P61 closes with P57: the approval a person performs, and what using it turned up.

- checkpoint added: C34 after P61, covering P61
- proves: The two records a person creates during setup agree with each other and with the chain behind them: approving bytes that are already approved says who did and writes nothing, an edited file is still a second decision, neither register is committed, and the bar the profile form offers is one somebody chose rather than a default nobody did.

## 2026-09-18 - P62 A register that cannot go stale quietly

**Why:** The test guarding BUILD/OPEN.md asserts that the register tells a session to run 'gate close P28' and 'gate checkpoint C10'. Both were discharged - P28 was signed off on 2026-09-05 and C10 has been green since - so the guard was holding the register to instructions that had expired, and correcting the register broke the test that was supposed to keep it honest.

- phase added: P62 A register that cannot go stale quietly (The consoles, gate: auto)
- exit criterion: A settled item cannot sit in the register as though it were open, and a test fails if one does
- exit criterion: The four items this build is waiting on are still named, and the test says which are live

## 2026-09-18 - C35 What a session is told, and whether it is still true

**Why:** P62 closes the block: the register and the documents a session starts from are held to being current rather than to particular sentences.

- checkpoint added: C35 after P62, covering P62
- proves: Nothing in the open register asks a session to close a phase the plan says is closed, run a checkpoint that is green, or obtain a sign-off that exists; every settled row carries the date that settled it; and the documents a session is told to read all exist and point at each other.

## 2026-09-18 - P63 An engagement view, and a way to find one client

**Why:** An analyst thinks in clients; every screen is indexed by run. Finding one engagement among ten is scrolling, and /api/runs?engagement_id= has existed unused since P23. This is the largest single thing five dashboard reviews asked for, and it is the screen the next interview session will sit in front of while walking a real project.

- phase added: P63 An engagement view, and a way to find one client (The consoles, gate: auto)
- exit criterion: A person can find one client's runs among many without scrolling the list
- exit criterion: Runs collapse by engagement with the newest on top, and a repeat client reads as one row rather than several
- exit criterion: The filter is built from data through data- attributes and the ACTIONS table, never from a handler written out of a client's text

## 2026-09-18 - P63 An engagement view, and a way to find one client

**Why:** B-026 asks the engagement line to carry a valuation date. No such field exists: the engagement profile's two as_of dates belong to size_band and fiscal_calendar, and neither is a valuation date. Putting one on the screen would mean inventing a date nothing in the system holds. The line carries what the console actually knows; the field itself is an interview question, recorded in OPEN.md.

- task added: An engagement line says where it stands: scope, run count, what is open, last activity
- task dropped: An engagement line says where it stands: valuation date, what is open, last activity

## 2026-09-18 - C36 Finding one client, and what the screen may claim

**Why:** P63 ends the consoles block: the screen an analyst finds a client on, and the question that refusing to invent a valuation date left open. The checkpoint asks whether the fold and the runs panel can disagree, whether the page claims any state a run cannot be in, and whether the register stayed current while a row was settled and a question added.

- checkpoint added: C36 after P63, covering P63
- proves: The engagement fold and the runs panel are two readings of one set of rows and cannot disagree about which runs or how many are open; every state the page names or paints is one RunState can hold; and the register still carries the question that refusing to invent a valuation date opened.

## 2026-09-18 - P64 An acknowledgement that says what it looked at

**Why:** The empty-register acknowledgement expires by date, and a session logged on the same calendar day counts as covered. That is deliberate - a person finishes a session and then records that nobody was named - but the same date also covers a session that has not happened yet when the acknowledgement is written. The register's acknowledgement is dated today and the next interview session is today, so the check CLAUDE.md names as what keeps client data inside knowledge/ would print clean over a session full of real client names. A date cannot tell the two orderings apart; what was reviewed has to be recorded, not only when.

- phase added: P64 An acknowledgement that says what it looked at (The interview, gate: auto)
- exit criterion: A session recorded after an acknowledgement on the same day does not inherit it, and scan refuses
- exit criterion: The legitimate flow still works: finishing a session and then recording that nobody was named leaves scan clean
- exit criterion: An acknowledgement with no recorded session list covers only sessions strictly before its date

## 2026-09-18 - P65 An acknowledgement is a decision, not a default

**Why:** Found by running the command rather than reading it. 'register --none' with no text records an acknowledgement worded by the code, not the person, and record_review replaces any existing acknowledgement line silently - so one careless invocation destroys a recorded decision, under someone else's name, and exits 0. An acknowledgement is the same kind of record as a methodology clearance: a person looked at something and said so. P57 already refuses to re-approve a recipe at bytes already approved, because that would record a decision that changed nothing; the same reasoning applies here and was not applied. 'mark' with an unknown topic raises a traceback instead of saying why.

- phase added: P65 An acknowledgement is a decision, not a default (The interview, gate: auto)
- exit criterion: register --none with no note refuses and records nothing
- exit criterion: An acknowledgement that is still current cannot be silently replaced, and the refusal names who made it and when
- exit criterion: An acknowledgement that has gone stale can still be renewed, because that is the legitimate act
- exit criterion: Every interview command refuses a bad argument with a sentence rather than a traceback

## 2026-09-18 - P65 An acknowledgement is a decision, not a default

**Why:** Fixing the fixture exposed the reason the accident was possible twice. The module finds knowledge/ two ways - the module attribute KNOWLEDGE, which a caller can redirect, and parameter defaults bound at definition, which silently cannot. A CLI handler that relies on the second reaches the real knowledge/ however the first is set, which is how a test in this very phase wrote to the repo's own coverage.yaml and downgraded a topic. One way to find it, named at the call.

- task added: Every CLI handler names the knowledge folder it works on, so the module attribute is the only source
- exit criterion added: No interview command reaches the real knowledge/ when the module's KNOWLEDGE has been pointed elsewhere

## 2026-09-18 - P66 Two commands, one answer about the register

**Why:** status warns that scan will refuse to close the session while scan, run the same minute, prints clean. Both are right - the acknowledgement stands now and goes stale the moment this session records an answer - but a person reading them together sees two commands disagreeing about the one check CLAUDE.md tells them to trust, at the top of the session they are about to start. The warning should say which of the two states the register is actually in.

- phase added: P66 Two commands, one answer about the register (The interview, gate: auto)
- exit criterion: With a standing acknowledgement, status says so and says what expires it, rather than warning of a refusal that is not happening
- exit criterion: With no acknowledgement and answers recorded, status still warns before the first question
- exit criterion: A test runs both commands over the same folder and fails if they disagree about whether the register is satisfied

## 2026-09-18 - P66 Two commands, one answer about the register

**Why:** C37 found a third way the same class of defect was present: scan's reporting line called relative_to(ROOT), which raises rather than falling back. It is the line that names a client's identifier having reached a file outside knowledge/ - so the one moment the check has something to say was the one moment it could raise instead of saying it. Unreachable today because everything committable_files() returns is inside the repository, which is why it survived; a landmine that has not gone off is still a landmine.

- task added: The line that reports a leaked identifier cannot raise instead of reporting it
- exit criterion added: scan names a hit in a file outside the repository rather than raising on the path
- status: done -> open

## 2026-09-18 - C37 The boundary, exercised rather than read

**Why:** P64, P65 and P66 close the interview block before the next session opens it. All three were found by running the tool rather than reading it, all three are about the one check CLAUDE.md names as what keeps a client's name inside knowledge/, and two of them destroyed real records in this repo before they were fixed. The checkpoint walks a whole session the way the protocol describes one, because what the three have in common is that the suite exercised the functions and not the commands.

- checkpoint added: C37 after P66, covering P64, P65, P66
- proves: A session walked end to end through the commands a person actually runs - status, session, answers, acknowledgement, scan - reports what the record holds at every point: the acknowledgement covers what it looked at and nothing logged after it, a standing one cannot be silently replaced, status and scan never describe the same file differently, a leaked identifier is named rather than raised on, and no command reaches the repository's own knowledge folder.

## 2026-09-18 - P67 Proved by arithmetic, or seen

**Why:** The fourth interview session answered the auto-accept bar that BUILD/OPEN.md section 2 has carried as undecided since the start, and answered it in a different shape than the build assumed: not a confidence number, but a rule about evidence. A figure may be accepted unseen when it carries its source locator and every total it feeds re-adds and the statements tie; everything else is shown, every one of them, not only what changed. That is the right shape because a confidently wrong OCR read is exactly what a probability cannot catch and a failed footing can - and most of the inbound path is about to be OCR'd scans.

- phase added: P67 Proved by arithmetic, or seen (Version one: the data it gathers, gate: auto)
- exit criterion: A figure carrying its locator and a passing arithmetic cover is accepted without a person, with no confidence stated
- exit criterion: A figure missing either one goes to review, and the reason names which is missing
- exit criterion: Materiality, an always-review category, review_required and a raised review level still send a fully covered figure to a person
- exit criterion: A skill's judgement, which is not an extracted figure, is routed exactly as it was before

## 2026-09-18 - P68 The request list, as the schedule documents arrive against

**Why:** The fourth session showed a real due diligence request list and it is two things at once: what the client is asked for, and the tracker of what has arrived. Its seven section groupings are stable across engagements; the items inside them vary and stay similar year to year for a repeat client. And each section is a folder in Box and in ShareFile, so a document's section is known from where it sits rather than from classifying it. B-009's coverage report does not need inventing - it exists on paper, with Provided and Not Applicable columns already on it.

- phase added: P68 The request list, as the schedule documents arrive against (Version one: the data it gathers, gate: auto)
- exit criterion: The section of an arriving file is read from its path, and a path naming no section says so rather than guessing
- exit criterion: A request item reference is parsed from a filename or a folder, and a malformed one is refused rather than half-read
- exit criterion: A coverage report over a request list and a set of arrived files names what is still outstanding
- exit criterion: Nothing here classifies a document type: section and type are separate axes and both are kept

## 2026-09-18 - P69 Last year's model, rolled forward

**Why:** 75% of engagements are repeat clients, and for those everything starts from last year's version of itself - the model, the WS grouping, the Input tab, the request list. That is one mechanism applied four times rather than four features, and it is the largest single saving available. Its Excel half needs the firm's real template, which is not in hand; its arithmetic half does not, and is exact: a ten-column window that drops its oldest year, two dates rolled forward a year, and a prior year's line items carried as this year's schema.

- phase added: P69 Last year's model, rolled forward (Version one: the data it gathers, gate: auto)
- exit criterion: Rolling a full ten-year window drops the oldest year and keeps the width at ten
- exit criterion: A window with fewer than ten years filled grows to the width and only then starts dropping
- exit criterion: Rolling 29 February forward a year lands on a real date rather than raising
- exit criterion: A prior line item with no match this year, and a new row matching no prior line item, are both reported and neither is resolved

## 2026-09-18 - C38 What version one gathers, and what it refuses to decide

**Why:** P67, P68 and P69 are what the fourth interview session justified building without the firm's real model in hand. The rest of its backlog - the input-help workbook, the OCR adapter, the Excel half of the roll-forward - needs the template's named ranges or an OCR engine confirmed on the work machine, and guessing at either would be expensive to reverse. The checkpoint asks the three built pieces the same question: does each still refuse what is not its to decide.

- checkpoint added: C38 after P69, covering P67, P68, P69
- proves: A repeat year rolls through all three pieces together - a ten-wide window dropping its oldest year, two dates moved on, last year's line items carried as this year's schema - and only what no arithmetic covers reaches a person; a request section never stands in for an item; a line-item mismatch is handed over rather than resolved; the sections are not a second document-type vocabulary; a skill's judgement is still routed on its confidence; and the fact that nothing yet sets the acceptance rule's evidence is recorded rather than quiet.

## 2026-09-18 - P62 A register that cannot go stale quietly

**Why:** C38 caught the guard being narrower than the register it guards. A settled row must carry a word asserting it is settled and a date, so that 'done' is checkable rather than asserted - and the word list was Done, Signed, done. That was written when only build rows were struck through. Section 2 holds decisions that belong to a person, and the register's own established vocabulary settles those with 'Answered' - it reads 'Answered, 2026-09-05' for the Power Automate decision and '(Answered 2026-09-16 ...)' for the pilot type. The first settled decision row therefore failed a guard that had never seen one. Widening the list to include Answered keeps both halves of the rule - an explicit settlement word, and a date - and stops the register having to say 'Done' about a question.

- task added: A decision settled with the register's own word for settling a decision is accepted
- exit criterion added: A struck-through row settled with Answered and a date passes, and one with neither word still fails
- status: done -> open

## 2026-09-18 - P56 The register, fillable from what was already said

**Why:** The first interview session to name real clients found the entity heuristic firing inside a longer phrase. Its lookahead is (?!\w), which a space satisfies, so 'Capital' matched in the middle of the firm template's 'Applicable Capital Gains' and the suggester proposed 'Applicable Capital' as a company. A company suffix terminates a name - that is what makes it a suffix - so it must not be followed by another capitalised word. Greedy matching means a genuine multi-suffix name like 'Northgate Dental Partners Inc' still matches at its full length. Found by tests/checkpoints/c29, which exists to notice exactly this and whose docstring says a failure means a real engagement has been discussed.

- task added: A company suffix only ends a name when nothing capitalised follows it
- exit criterion added: A suffix word inside a longer capitalised phrase is not proposed as a company, and a real name ending in one still is
- status: done -> open

## 2026-09-18 - P70 The gate can always say why

**Why:** gate.py crashed with a UnicodeEncodeError while printing a failing check's output. The tool that is the only thing permitted to mark a phase done, reporting why a phase did not pass, died in the middle of saying so - and what a person saw instead was a traceback from inside gate.py, which reads as the gate being broken rather than the check having failed. It ran at exactly the worst moment: nothing is written when a check fails, so the refusal was correct, and the reason for it was lost. The output is decoded with errors=replace already, so a replacement character is a normal thing to be holding; what is missing is that printing it must not be able to fail.

- phase added: P70 The gate can always say why (The consoles, gate: auto)
- exit criterion: A check whose output contains a character the console cannot encode is still reported, and the gate still refuses
- exit criterion: The replacement is visible in the line rather than the line being lost

## 2026-09-18 - C39 The gate reports a failure rather than becoming one

**Why:** P70 closes the consoles block with the tool the block is checked by. A checkpoint here is not ceremony: gate close is the only thing permitted to mark a phase done, and the crash it fixes happened at the exact moment a check had failed - so the path from a failing check to a person reading why it failed is worth exercising end to end rather than one function at a time.

- checkpoint added: C39 after P70, covering P70
- proves: A real check that fails with output the console cannot encode is still reported, as a failure, with its text intact and the unencodable character replaced; the gate runs as a process under that console encoding without a traceback; a passing check still reads as passing; and no phase sits past the last checkpoint.

## 2026-09-18 - P71 Nothing is built and wired to nothing

**Why:** P55 found three things built and wired to nothing - precedent retrieval handed to every collaborator but the context builder, a release gate read off a field that never existed, RepairNeeded raised only by a test double - and P60 found on_failure parsed, validated, hashed and read by nothing. Each was found by a person reading carefully, which is not a method. A scan for public functions nothing references finds the same shape mechanically, and finds two today: governance.conformance.read_draft, which duplicates the line drop.py already runs inline, and evals.metrics.provenance_of, whose docstring says 'Exposed for the harness' while being the only mention of ProvenanceGate in evals - so the eval harness has never measured a provenance failure, and a candidate skill could promote while faulting one.

- phase added: P71 Nothing is built and wired to nothing (The engine, gate: auto)
- exit criterion: A public function referenced nowhere fails the check, and adding one to the allowlist without a reason still fails
- exit criterion: The scan is quiet on the tree as it stands, so a failure means something new
- exit criterion: The eval harness not measuring provenance failures is written down rather than implied by a function nobody calls

## 2026-09-18 - C40 An unwired seam is a decision, and the decision is on the record

**Why:** P71 makes a recurring defect findable by the suite instead of by careful reading. The checkpoint asks the part the unit tests cannot: whether the code and the written record still agree about what is unwired and why. A scan with an allowlist is only as honest as the reasons in it, and a reason living solely in a test file is one nobody reading the backlog will see.

- checkpoint added: C40 after P71, covering P71
- proves: The scan is quiet on the tree as it stands, so a failure means something new; every excused seam names a backlog item that exists and does not claim to be built; the two found today are resolved the two different ways they warranted - one deleted because there was nothing to record, one kept because there was; and the earlier findings of the same shape, P55's precedent wiring and P60's on_failure, are still wired.

## 2026-09-18 - P72 A retry that can happen

**Why:** Found by extending P71's scan from functions to exception classes - the shape P55 found by hand, where RepairNeeded was raised in exactly one place and that place was a test double. TransportFailure is the same: the executor documents raising it, catches it, emits step.transport_failed on it and ends a run with PROCESS.TRANSPORT_EXHAUSTED when the attempts run out - and nothing in production has ever raised it. The Anthropic adapter translates NotFoundError and BadRequestError and re-raises everything else unchanged, so a connection error, a timeout, a 429 or a 500 falls into the executor's general handler and quarantines the step on the first try. Every recipe declares retries against a mechanism nothing can enter. The fake and scripted adapters have no network, which is why no rehearsal could ever have shown it.

- phase added: P72 A retry that can happen (The engine, gate: auto)
- exit criterion: A connection error, a timeout, a rate limit and a server error each arrive at the executor as TransportFailure
- exit criterion: A bad request, an unknown model and a missing credential are unchanged, and are not retried
- exit criterion: The executor retries a transport failure, emits step.transport_failed, and ends with PROCESS.TRANSPORT_EXHAUSTED when the attempts are used up

## 2026-09-18 - C41 The retry path, joined at both ends

**Why:** P72 joined a seam that had two correct ends and nothing crossing it. The checkpoint keeps the crossing: an exception class raised only by tests is the shape that produced this defect and produced P55's, and it is cheap to ask for directly.

- checkpoint added: C41 after P72, covering P72
- proves: The class the adapter raises is the class the executor catches and it belongs to the port so both can see it; something in production raises it, checked the way the gap was found; the executor's retry loop, its event and its exhaustion code are all still there; transient and permanent remain different questions; and the fact that no rehearsal could have caught this - the fake and scripted adapters have no network - is recorded where somebody trusting a clean rehearsal will meet it.

## 2026-09-18 - P73 An exception nobody raises

**Why:** P71 taught the suite to notice a public function nothing calls, and the same afternoon a hand-run variant of it on exception classes found TransportFailure - declared, documented, caught, given an event and a diagnostic code, wired into every recipe's retries, and raised by nothing outside a test. That is twice this shape has cost real work: P55 found RepairNeeded the same way, by hand. The variant that found it is four lines different from the one now in the suite, and leaving it out means the next one is found by hand again, if at all.

- phase added: P73 An exception nobody raises (The engine, gate: auto)
- exit criterion: An exception class constructed only by tests fails the check and is named
- exit criterion: The three reached through a factory or a variable - BudgetExceeded, NotAuthenticated, RepairNeeded - are not reported
- exit criterion: The scan is quiet on the tree as it stands, so a failure means something new

## 2026-09-18 - C42 Two scans for one defect, and the shape they share

**Why:** P71 and P73 look for the same defect from two directions - something built, correct and unreachable - and the build has paid for it five times between P55, P60 and P72, every one found by a person reading. The checkpoint keeps the pair honest, because the place a check of this kind dies is its allowlist.

- checkpoint added: C42 after P73, covering P73
- proves: Both scans are quiet on the tree, so a failure means something new; neither has stopped finding anything to look at; every excuse in either carries a reason; the two never excuse the same thing, which would let a defect hide behind whichever was read first; and the findings that paid for the scans - P55's precedent wiring, P60's on_failure, P72's retry - are all still fixed.

## 2026-09-18 - P74 The scanned page, read locally

**Why:** The analyst confirmed a local OCR engine can be installed on the work machine, which was the one thing B-035 waited on. Any PDF the clients send cannot be copied from and they send a lot of them, so most of the inbound path needs OCR before anything downstream can touch it - and keying those by hand is the one to three hours a repeat engagement costs. intake/readers/documents.py already reports a scanned page rather than reading it, by design, and says the OCR path is a later adapter. This is that adapter, and the reason it must be local rather than a vision model is the masking order: masking needs text, text from a scan needs OCR, and OCR by a model would put unmasked client documents in front of one before masking could happen.

- phase added: P74 The scanned page, read locally (Version one: the data it gathers, gate: auto)
- exit criterion: A scanned page read through the port produces lines, and the table recovery finds its rows with the locators it would have had from a text layer
- exit criterion: An OCR-derived line is distinguishable from one lifted out of a text layer
- exit criterion: Nothing under ports/ocr imports ports/llm, and the import walk fails if it ever does
- exit criterion: Absence is not a pass: with no OCR adapter configured a scanned page stays reported, exactly as before

## 2026-09-18 - P74 The scanned page, read locally

**Why:** The conformance suite refused the eighth port, correctly, on three counts: no protocol registered for it, the port set no longer matching the one the suite names, and a moved public surface. Two of those are the work of adding a port and are done here. The third is a question about the blueprint, and it is worth answering rather than waving through: the blueprint draws five port nodes - storage, delivery, secrets, queue, llm - and the code has had seven since P25 and P36, because compute and identity are deployment choices behind existing nodes rather than new boxes on the map. OCR is the same shape. The Document Reader is the node; which engine reads a scan is a choice behind it, exactly as which folder receives a workbook is a choice behind the delivery node. So no node is added, and the reason is recorded here rather than inferred later from its absence.

- task added: The conformance suite knows the port, so its adapters are checked like every other
- exit criterion added: The OCR adapters are checked against the protocol by the same conformance suite as the other seven ports

## 2026-09-18 - C43 The scan is read here, and read before anything masks it

**Why:** P74 puts a new step at the very front of the privacy ordering - image, then text, then mask, then model - and the checkpoint asks the thing that is invisible from inside the phase: whether that ordering still holds. The danger was never that OCR reads a page badly; it is that OCR becomes a model call and the unmasked document reaches a model before masking exists to stop it, which nothing downstream can recover from.

- checkpoint added: C43 after P74, covering P74
- proves: Nothing on the OCR path can reach a model - not the port, not the adapters, not the document reader that calls them - and privacy/ is still deterministic Python; the eighth port is chosen by configuration and refuses an unknown name like the other seven; a machine with no engine reads everything it always could and still reports a scan rather than reading it as an empty page; and the adapter the analyst confirmed he can install is registered and buildable without it, so a clone, a container and the work laptop are the same code with different configuration.

## 2026-09-18 - P74 The scanned page, read locally

**Why:** The rehearsals are clean and serve.py --check says nothing about OCR, which makes the readiness report quietly wrong about the thing that matters most on the work machine. CLAUDE.md calls readiness() the honest answer to 'does this work yet', and it derives what is joined by asking the code rather than by being updated. With AA_OCR_ADAPTER=none - the default, and what a fresh work machine has until somebody sets it - every scanned PDF reads as nothing, which is most of the inbound path for this firm, and the one screen built to say what is wired does not mention it.

- task added: The readiness report says whether a scanned page can be read here, and what it means when it cannot
- exit criterion added: serve.py --check names the OCR seam, green when an engine is configured and honest about what is lost when it is not
- status: done -> open

## 2026-09-19 - P75 An OCR engine that installs without an administrator

**Why:** Testing P74 against a real SEC filing turned up a better answer to the question P74 assumed. Tesseract needs an executable installed on PATH, which on a managed work laptop is a request to somebody. rapidocr-onnxruntime is a wheel with its models bundled - pip installs it, no admin rights, no system binary - and on the three financial statement pages of a real annual report it read every figure in every column correctly at about 0.99 confidence. A choice that needs no administrator is a materially different choice on the machine this has to run on, and it costs one adapter file beside the one already there.

- phase added: P75 An OCR engine that installs without an administrator (Version one: the data it gathers, gate: auto)
- exit criterion: The adapter satisfies the port and is built like the others, on a machine without its dependencies installed
- exit criterion: Nothing on this path reaches a model either, checked the same way
- exit criterion: With the packages absent it raises OCRUnavailable naming what to install, rather than failing as an import error

## 2026-09-19 - P76 A real filing, kept as the document that finds things

**Why:** Every fixture in this repo is synthetic, and that is why the reader had never met a real financial statement until a test against a public SEC filing found it reading the wrong column of a comparative balance sheet - taking the prior year and swallowing the current one into the label. The behaviour was predicted in B-030 and had never been demonstrated. A public filing is the document that finds these: real typography, real comparative columns, real image-only pages, and no client data of any kind. CLAUDE.md says fixtures are masked or synthetic always, which was written when those were the only two ways to have no client data in a file. The rule's purpose is that no client data is in the repository; a document the SEC publishes satisfies it, and the rule is widened here deliberately rather than by quietly adding a third kind.

- phase added: P76 A real filing, kept as the document that finds things (Version one: the data it gathers, gate: auto)
- exit criterion: The reader reads the real filing, and what it gets wrong on a comparative statement is pinned rather than discovered again
- exit criterion: The escalation that stops a run on that document fires, checked on the real pages
- exit criterion: The fixtures rule permits a public document and says what makes one public, everywhere the rule appears
- exit criterion: The OCR benchmark runs when an engine is present and reports that it did not when one is absent

## 2026-09-19 - C44 Two engines, one real document, and a rule widened on purpose

**Why:** P75 and P76 came out of putting the build in front of a document nobody here wrote. The checkpoint holds the two together: every engine local and none of them a fallback for another, and the real filing still finding what a synthetic one could not.

- checkpoint added: C44 after P76, covering P75, P76
- proves: Every registered OCR engine is local, reaches no model and no network, and can be built on a machine that has installed none of them; none of them silently falls back to another, so a scan is never read by an engine nobody chose; the real filing is still read and the comparative-column defect it found is pinned along with the escalation that is the only thing stopping a run on it; and widening the fixtures rule to allow a public document did not loosen what it always forbade - no client data, a named public source, and the identifier register checking the fixture like anything else.

## 2026-09-19 - P77 The first thing a session reads, made true again

**Why:** CLAUDE.md is the first thing every session reads, and four things in it are now out of date in ways that would mislead one. It says the project is DDR extraction, normalization and model building - and the fourth interview session redefined version 1 as gathering and organising data into a workbook the analyst types from, explicitly not running the model. It describes the identifier register as empty with an acknowledgement standing in, which was true of the first three sessions and is not true now that ten names are in it. It says nothing about the OCR port, which is the one setting that decides whether most of this firm's documents can be read at all on the machine it is about to be moved to. And it does not carry the acceptance rule the analyst gave - proved by arithmetic or seen - which is now the rule the confidence router applies.

- phase added: P77 The first thing a session reads, made true again (The consoles, gate: auto)
- exit criterion: Nothing in CLAUDE.md describes version 1 as building the model
- exit criterion: What it says about the register matches what the register holds and what the command does
- exit criterion: Every command and setting it names exists, checked rather than read
- exit criterion: The guards that already hold it - the gate prefix, the protocol's words, the blueprint's numbers - still pass

## 2026-09-19 - C45 The documents a person arrives at, agreeing with each other

**Why:** P77 rewrote the document every session starts from, and the risk of rewriting one of a set is that it stops agreeing with the others. The work machine is next, which makes HANDOFF.md the document that will meet somebody with no context and no session history - so the four are asked together rather than one at a time.

- checkpoint added: C45 after P77, covering P77
- proves: CLAUDE.md, the interview protocol, the using guide, the handoff packet and .env.example still say the same thing about how to run it, about the setting that decides whether a scanned page can be read, and about what version 1 is for; every adapter they name is one the ports actually register; the shared vocabulary the protocol guard stands on survived the rewrite; and every document a session is sent to read still exists.

## 2026-09-19 - P78 The packet that meets somebody at work

**Why:** The work machine is next, and HANDOFF.md is what meets somebody there with no session history. Its headline claim is that .env changes and nothing else - which was true until P74, and is not: an OCR engine is software to install, and without it every PDF this firm's clients send reads as nothing. That failure looks like nothing happening, which is the worst kind to meet on a first evening. Its list of what is still owed is the P28-era list and does not carry what the fourth interview session established: the real model that the input-help workbook has to match, the per-engagement request items, and the fact that OCR accuracy on a genuine scan is still unmeasured.

- phase added: P78 The packet that meets somebody at work (The consoles, gate: auto)
- exit criterion: No document claims that only .env changes at handoff
- exit criterion: The getting-started path names the OCR engine, and what is lost by skipping it
- exit criterion: What is still owed names the real model, the request items and the unmeasured accuracy

## 2026-09-19 - C46 The first hour on a machine that has never seen this

**Why:** P77 and P78 exist for one moment: somebody at the work machine with a clone, no session history and an evening. The checkpoint asks them together because the failure they guard against is a quiet one - skipping the OCR engine produces no error, only documents going in and nothing coming out - and because two documents describing the same product differently is the drift that survives longest, each reading fine alone.

- checkpoint added: C46 after P78, covering P78
- proves: The documents that tell somebody how to start agree with each other; the OCR step is the same wherever it is told and every adapter named is one the ports accept; the quiet failure of skipping the engine is described where somebody will look; what is owed is one list rather than two; every pytest flag a document offers is one the suite defines; and the rules and the packet describe the same version 1.

## 2026-09-19 - P78 The packet that meets somebody at work

**Why:** The first correction overshot and C10 caught it. Replacing the portability claim - .env changes and nothing else - with 'settings change and software gets installed' weakened a load-bearing sentence: the packet says that anything else needing to change to make the suite pass is a defect in the portability claim rather than a step to add quietly, and blurring it invites exactly those steps. The suite does pass with no OCR engine, so the claim is true. What needed saying is that it is a claim about the build, and that reading this firm's documents needs one operational dependency beyond it - the way the production store needs Postgres.

- task added: The portability claim is kept and scoped rather than weakened
- exit criterion added: The packet still says .env changes and nothing else, and says what that claim is about

## 2026-09-19 - P79 Where last year's model is

**Why:** Reviewing the setup surface as a beginner would meet it found the field the analyst asked for by name and that nobody built. Asked in the fourth interview how the system should get hold of last year's model for a repeat client, he said: 'In the set up, I would point it to the right box file location.' There is no such field on the engagement, in the profile, or anywhere else - and 75% of engagements are repeat clients whose whole path begins by reading last year's workbook. Everything in B-036 waits behind a path nobody can type in.

- phase added: P79 Where last year's model is (Version one: the data it gathers, gate: auto)
- exit criterion: A repeat engagement can be pointed at last year's workbook and the setting survives a reload
- exit criterion: A path that is not there is refused while the person is still looking at it, naming what was not found
- exit criterion: A new-client engagement is neither asked for one nor faulted for having none

## 2026-09-19 - P79 Where last year's model is

**Why:** The public surface moved by exactly two entries and both are the new configuration contract: config_document@1.3.0 and its schema hash. A version was added rather than 1.2.0 edited, which is the rule the registry states in its own note - a document already written is still a document that has to be readable - so 1.1.0 and 1.2.0 stay listed and stay loadable, and a configuration naming no prior model stays the version it was. The snapshot is accepted here with that reason rather than silently.

- exit criterion added: Older configuration versions stay listed and readable, and a document naming no prior model is not upgraded

## 2026-09-19 - C47 Setting up a repeat client, with everything that needs saying

**Why:** P79 added a per-engagement setting and with it a configuration contract version. The checkpoint guards the half that is easy to get wrong later: versioned contracts are only worth their cost if the old versions keep working, and the temptation when adding a field is to migrate every document to the newest because it is tidier. A first-year client's configuration should never acquire a field about last year.

- checkpoint added: C47 after P79, covering P79
- proves: The newest configuration version is the one a write produces and every supported version still loads; no version was edited in place, so 1.1.0 knows nothing of a recipe and 1.2.0 nothing of a prior model; an engagement naming no prior model is not upgraded because another one was; a repeat engagement is told on the roster that it has not been pointed at last year's workbook, and stops being told once it has; and the page is handed which engagements are repeat rather than splitting a scope path itself.

## 2026-09-19 - P80 Setup, in the analyst's words

**Why:** The setup review found the rest of what stops a beginner. The checklist promises six steps in order, and the hardest job is not one of them: step six says preflight has to pass, and preflight refuses until an engagement profile of twelve required fields is complete - a NAICS code, a size band with an as-of date, an owner compensation baseline with amount, currency, basis, source and as-of. Five easy ticks, then a wall nobody was warned about. Whether a client is repeat or new - the flag three quarters of the work turns on - is the last segment of a control labelled Practice group, written as non-repeat. The word model means the Excel template in three places, so somebody looking for which AI model is used finds three controls named model and none of them is it. And archive has an API route and no button, so an engagement can be made and paused but never retired.

- phase added: P80 Setup, in the analyst's words (The consoles, gate: auto)
- exit criterion: The checklist names the profile as a step, before the step that refuses without it
- exit criterion: A person choosing repeat or new sees those words, and the scope path follows from the choice
- exit criterion: Every control that says model says which kind, and the AI model in use is visible somewhere
- exit criterion: Archive is reachable from the roster and asks before it acts

## 2026-09-19 - C48 The setup a beginner can finish

**Why:** P80 renamed and resequenced the Setup surface around the analyst's vocabulary rather than the appraiser's, and changed the shape of the scope path a person submits. Nothing behind it moved, which is exactly when a console and the code under it start to disagree quietly - so it is checkpointed against the whole build rather than trusted to its own tests.

- checkpoint added: C48 after P80, covering P80
- proves: An engagement can be taken from an empty environment to an active run through the page alone, in the words the person doing the work uses, with the profile met as a step rather than a refusal.

## 2026-09-19 - P81 The setup surface, composed rather than assembled

**Why:** P80 fixed what the setup surface says. This is how it looks while saying it. Read as a design rather than as a feature, the page has one voice repeated seven times: seven panels of equal weight, every row the same rhythm, no figure anywhere, and the checklist - the whole reason a first-time reader is on this screen - framed identically to a reference table nobody needs twice. The stylesheet it is built on is careful, and the page does not spend what the stylesheet gives it.

- phase added: P81 The setup surface, composed rather than assembled (The consoles, gate: auto)
- exit criterion: The steps read as one sequence: the marks are joined, the current one is the subject, and a finished step costs one line
- exit criterion: A finished checklist stops taking the space the panels need
- exit criterion: No control on the page is wired twice over, and no length on it was chosen by eye
- exit criterion: Nothing the page could do before, it cannot do now

## 2026-09-19 - C49 One design language, still one

**Why:** P81 changed a stylesheet every page in the tool is built from - the steps, the buttons, the dialogs and four new components - while only the setup page was reviewed. A change to shared CSS is the definition of something that passes its own tests and breaks somewhere nobody looked.

- checkpoint added: C49 after P81, covering P81
- proves: The setup surface reads as composed, and the three pages that were not reviewed are unchanged by a stylesheet that was.

## 2026-09-20 - P82 Nothing a run cannot reach is called built

**Why:** P71 built a scan for this build's most repeated defect - something built and wired to nothing - and the scan counts a mention in a test as wiring. So a module whose only caller is its own test file passes it, which is the defect exactly. Eleven modules and about two thousand lines are in that state today, including two of the three things the fourth interview session asked for and the unmask integrity check the blueprint asserts gates every deliverable. The backlog records four of them as 'built'.

- phase added: P82 Nothing a run cannot reach is called built (The consoles, gate: auto)
- exit criterion: A module whose only caller is its own test is reported, and P68 and P69 are among what it reports
- exit criterion: No port adapter and no command-line tool is on the allowlist
- exit criterion: An allowlist entry citing a backlog item that does not exist, or one already closed, fails
- exit criterion: Every backlog item claiming built names something a run can reach

## 2026-09-20 - C50 The check that can be believed

**Why:** P82 changed what counts as evidence that something is built, and made a scan that had reported nothing into one that gates the build. A check with a false positive blocks a phase wrongly and a check with a false negative is decoration, so the mechanism itself wants proving against the tree it now judges.

- checkpoint added: C50 after P82, covering P82
- proves: The reachability scan's verdict matches what actually happens: a module it calls reachable really is reached, and one it excuses is noticed the moment production touches it.

## 2026-09-20 - P83 A context that says when it will not fit

**Why:** Every document this firm receives is a multi-page scan, and nothing measures the assembled context before it is sent. Over the model's input limit the SDK raises BadRequestError, which ports/llm/anthropic_messages.py maps to SCOPE.MODEL_PIN_UNAVAILABLE - so a sixty-page scan reports itself as 'claude-opus-5 is unavailable' and sends whoever reads it to the model registry instead of to the document. Found 2026-09-20 comparing this build against the harness-engineering literature (BUILD/proposals/harness-research.md).

- phase added: P83 A context that says when it will not fit (The consoles, gate: auto)
- exit criterion: An oversized context is refused before the call, naming the largest section and its size
- exit criterion: The diagnostic tells a person which document to look at, not a number in bytes alone
- exit criterion: A provider 400 about length carries a length diagnostic, and a real missing model still carries the model one
- exit criterion: Nothing that fits today is refused

## 2026-09-20 - P84 The stable prefix, cached

**Why:** The cost meter prices cache reads at a tenth of input and cache writes at 1.25x, Usage carries cache_read_input_tokens and cache_creation_input_tokens, and the run manifest reports both - and nothing has ever set cache_control, so every one of those fields has been zero on every call this build has made. The accounting for caching was built and the caching was not. Meanwhile the system prompt the dispatcher sends is the skill body plus its references plus a constant rule: byte-identical for every call of that skill in that scope, re-sent and re-charged every time. Observation 2 of the harness study (BUILD/proposals/harness-research.md); Claude Code splits its own prompt at a hashed cache boundary for exactly this.

- phase added: P84 The stable prefix, cached (The consoles, gate: auto)
- exit criterion: The system prompt is sent as a cacheable block and the payload is not
- exit criterion: Cache usage reaches the cost meter and the manifest, which already price it
- exit criterion: What is cacheable is stable by construction: two calls of one skill in one scope share a prefix byte for byte
- exit criterion: Nothing about the content sent to the model changes - only the marker on it

## 2026-09-20 - C51 The door still opens the same way

**Why:** P83 and P84 both changed what happens at the model door - one refusing a call before it is made, the other changing the shape of what is sent - and that door is the one boundary in this build where a mistake reaches Anthropic rather than staying in the repo. Caleb flagged the outbound path specifically when approving the plan.

- checkpoint added: C51 after P84, covering P83, P84
- proves: A call that fits is sent exactly as it was, a call that does not is refused where a person can act on it, and the caching marker changes the bill without changing the question.

## 2026-09-20 - P83 A context that says when it will not fit

**Why:** Three public surfaces were added and are accepted deliberately: constraints.ceilings.per_context, the ceilings note that says what it measures and why it sits below the provider's own limit, and diagnostics.codes.INTAKE.CONTEXT_TOO_LARGE owned by client-data. All three are this phase's point rather than a side effect. The code's family was CLIENT first, which the blueprint does not name - caught by checkpoint C51 rather than by this phase, and the method error behind it is in LEDGER.md.

- task added: The surface snapshot and the blueprint's ERRCODES table both name the new code

## 2026-09-20 - P85 A comparative statement, read as two columns

**Why:** Every audited statement is comparative and none of them reaches a model. timing_normalization stops any file the period detector flagged ambiguous on columns, and the real SEC filing in fixtures/public trips it with three figures a row. The refusal is right - the reader anchors on the last figure, so the current year is swallowed into the label and every figure silently becomes the prior year's, past provenance because the number really is at that locator and past footing because consistently prior-year totals still re-add - but stopping is not reading. Recorded as B-030 since 2026-09-17 and demonstrated on a real filing in P76. It also makes the approved P85 moot: layout-preserving markup is downstream of a document that never arrives.

- phase added: P85 A comparative statement, read as two columns (The consoles, gate: auto)
- exit criterion: A comparative statement reaches a model, with each column under its own locator and period
- exit criterion: The current year is no longer absorbed into the label
- exit criterion: A document whose rows disagree about their figure count still stops, and says why
- exit criterion: Provenance, tie-out and the numeric lock resolve against the new locators unchanged
- exit criterion: The real filing in fixtures/public is read as columns, measured rather than asserted

## 2026-09-20 - C52 Two columns, and three guards that did not move

**Why:** P85 changed the shape of what the Source Parse Store holds and the grammar of the locators that address it, and three guards resolve against exactly that - Provenance asks whether a cited locator exists and matches, Tie-Out asks for the rows behind a stated total, and the Numeric Lock compares a released figure to the value first read. The whole design was chosen so those three would not have to change; a checkpoint is how that claim is tested rather than asserted.

- checkpoint added: C52 after P85, covering P85
- proves: A comparative statement is read as columns, written under locators the guards already understand, and footed against its own column rather than a mixture of years.

## 2026-09-20 - P86 Three kinds of wrong

**Why:** The evals say how often a skill agrees with the gold set and never which kind of wrong it is when it disagrees. LAVA (arXiv 2608.16763) separates three that need different repairs: fabricated evidence, arithmetic error despite faithful extraction, and the edge cases nothing settles - and reports numerical infidelity near zero by having the model produce a formula and a deterministic engine execute it, which is what P67's acceptance rule already asks for here. The three map onto guards this build already has. Meanwhile provenance is measured on line-item-tagging by a hand-rolled check on whether a description changed, and on ebitda-normalization not at all: evals.metrics.provenance_of runs the real gate and nothing calls it, which is B-041 and the one entry on P82's allowlist that is a defect rather than a decision.

- phase added: P86 Three kinds of wrong (The consoles, gate: auto)
- exit criterion: provenance_of is called by the harness and B-041 is closed
- exit criterion: A skill whose figures cite a locator that does not resolve is reported as fabricated evidence, not as a lower agreement rate
- exit criterion: A skill whose arithmetic does not re-add is reported separately from one whose evidence is wrong
- exit criterion: No gate threshold is invented: a number that belongs to the practice is reported and named as owed

## 2026-09-20 - C53 What a scorecard is allowed to be silent about

**Why:** P86 added two gates to a shipped skill and emptied P71's allowlist. Both are changes to what stops a skill registering: a gate that silently reports itself as owed passes a skill without checking anything, and an allowlist that has quietly refilled is a scan that excuses the thing it was built to find. Neither is visible from the phase's own tests.

- checkpoint added: C53 after P86, covering P86
- proves: A skill promotes only on gates that were really measured, the two new ones catch the faults they name, and nothing is excused from the unwired scan any more.

## 2026-09-20 - P86 Three kinds of wrong

**Why:** Two public surfaces added, both this phase's point: the fabricated_evidence and numeric_infidelity gates on ebitda-normalization. A gate is a public surface because it decides whether a skill may register, so adding one is a governance change and not a refactor - which is why the snapshot asks. Accepted deliberately. sent_to_a_person_rate is not among them on purpose: it is reported on the scorecard and gates nothing, because what it is allowed to be belongs to the pilot and is owed in OPEN.md.

- task added: The two new gates are recorded in the surface snapshot as the governance change they are

## 2026-09-21 - P87 Box, on the side documents are read from

**Why:** The fifth interview session put Box on the read side: the client uploads to ShareFile, files are moved to Box, and Box is where the tool reads. The build assumed the reverse - storage/sharefile as the read side, delivery/box as the write side - so there is no Box storage adapter and nothing can sweep a Box folder. Reading his own box.sharefile.automation harness also shows the delivery adapter names the wrong credential.

- phase added: P87 Box, on the side documents are read from (Version one: the buttons he presses, gate: auto)
- exit criterion: AA_STORAGE_ADAPTER=box builds a real adapter and passes the port conformance suite
- exit criterion: list returns files in path order and folders are not files
- exit criterion: stat computes a sha256 rather than trusting a hash the service offers
- exit criterion: The Box credentials named in the code are the ones that work: BOX_USER_ID with box_subject_type=user, not an enterprise id
- exit criterion: A credential the service refuses diagnoses differently from one the environment never set
- exit criterion: No test in this phase can be read as evidence that a real Box tenant answered

## 2026-09-21 - P87 Box, on the side documents are read from

**Why:** The surface snapshot caught two changes, both intended, and the reason belongs on the record rather than in a snapshot update nobody can read. CONFIG.CREDENTIAL_REFUSED is new because a credential the service rejected is a different repair from one the environment never set - one says the secret is wrong, revoked, or the app lacks a permission, the other says add it to .env, and a single code for both sends somebody to the wrong file. ports.storage gains box because Box is on the read side and is a real adapter rather than a port contract, so the conformance suite runs over it.

- exit criterion added: The surface snapshot records exactly two changes - the CREDENTIAL_REFUSED diagnosis and box on the storage port - and no others

## 2026-09-21 - P88 A connection test that says which part failed

**Why:** A dashboard button he presses. The credentials, the app permission and the folder id are three different settings on two different screens, and 'connection failed' does not say which one to open. The adapter already tells them apart in its diagnoses; nothing yet asks it to, in order, on purpose.

- phase added: P88 A connection test that says which part failed (Version one: the buttons he presses, gate: auto)
- exit criterion: Each of the four steps reports its own result, and the ones after a failure say they were not reached
- exit criterion: The credentials step never reads a credential's value
- exit criterion: A wrong folder id and a refused token produce different reports
- exit criterion: An empty Box folder reports as connected
- exit criterion: Nothing the test read is written anywhere

## 2026-09-21 - P89 ShareFile, and the login a person does once

**Why:** ShareFile cannot be authenticated from cold. His own box.sharefile.automation harness records why: an account with MFA enabled cannot use a password grant, so three environment variables are not a credential set - a person signs in once and everything after lives on a refresh token that rotates. The adapter in the tree assumes otherwise and refuses, which is honest but is not the thing.

- phase added: P89 ShareFile, and the login a person does once (Version one: the buttons he presses, gate: auto)
- exit criterion: A refresh token never appears in the repo, in a log, or in a repr
- exit criterion: A callback carrying a state nobody issued is refused, and a state is good once
- exit criterion: A rotated refresh token replaces the stored one rather than being dropped
- exit criterion: Never-signed-in and expired produce different reports, and neither reads as a fault a retry would fix
- exit criterion: No test in this phase can be read as evidence that real ShareFile answered

## 2026-09-21 - P89 ShareFile, and the login a person does once

**Why:** ShareFile stops being a port contract because it now has an implementation. It was registered as a contract so that selecting it would be a readable refusal rather than a silent fallback, and that was right while nothing could authenticate; P89 wrote the authorization-code flow, so the refusal it existed to give is now a working adapter. The storage port therefore has no contracts left. Delivery's Box adapter stays a contract: nothing writes a deliverable to Box yet, and pretending otherwise would be the failure the arrangement exists to prevent.

- exit criterion added: ports.contracts('storage') is empty, and delivery's box adapter is still a contract because nothing writes a deliverable there yet

## 2026-09-21 - P90 The relay, which may be pressed twice

**Why:** The Update button. Power Automate is the thing that moves files from ShareFile to Box automatically and it stays outside the boundary; this is the backup he presses when it has not run. Both copiers will sometimes act on the same files, so the failure worth designing against is not a copy that did not happen - he would see that - but two copiers fighting.

- phase added: P90 The relay, which may be pressed twice (Version one: the buttons he presses, gate: auto)
- exit criterion: Pressing it twice copies once, and the second press says so
- exit criterion: Nothing is ever deleted from ShareFile
- exit criterion: The same bytes already in Box are skipped; different bytes under the same name are reported as a re-send
- exit criterion: A failure on one file does not stop the others, and every outcome is named
- exit criterion: No path exists from a graph step or a run to the relay

## 2026-09-21 - P91 A report is a document with named places in it

**Why:** The report is set up by copying last year's and getting the right appendix information in. Nothing in the tree knows what a report is, and the binding rule that governs the model - bind by named range, never by cell address - has a Word equivalent nobody has written: bind by bookmark or heading, never by paragraph index. A report somebody added a sentence to would otherwise get Appendix F written into Appendix E.

- phase added: P91 A report is a document with named places in it (Version one: the buttons he presses, gate: auto)
- exit criterion: An appendix binds by bookmark or heading name, and a paragraph index cannot be used as an anchor
- exit criterion: An anchor that is not in the document is a refusal naming it, never a best guess
- exit criterion: Content that carries a style the destination does not define arrives with that style defined
- exit criterion: A numbered list and an image survive the move
- exit criterion: Anything that could not be carried is named in the result

## 2026-09-21 - P91 A report is a document with named places in it

**Why:** Building report/ exposed a hole in the two reachability scans, and closing it found four pre-existing defects. Both scans took a hand-written list of shipped packages, and neither listed report/ - so a whole new package was invisible to the checks that exist to catch exactly that. Worse, the P82 scan counted a package's own __init__.py as evidence that its submodules were reached, so a package imported by nobody vouched for itself. Both lists are now derived from the tree, and reachability is a fixpoint: an __init__'s imports count only once the package itself is reached. That immediately found orchestrate (the whole package, imported by no production module), deliver.workpaper and governance.chain - recorded as B-058, B-059 and B-060 rather than wired, because where each belongs is a decision and not one to take while tidying a scan.

- exit criterion added: The two reachability scans derive their package list from the tree, and a package cannot vouch for its own submodules

## 2026-09-21 - P92 A button for each appendix that changes

**Why:** The buttons he presses when an appendix's data is ready. Three, not six: G, H and I stay the same as prior years and arrive in the copy of last year's report, so nothing here touches them - which is also why nothing in this system can write the certification. Each source arrives as a Word document he points the button at.

- phase added: P92 A button for each appendix that changes (Version one: the buttons he presses, gate: auto)
- exit criterion: Updating one appendix leaves the others byte-identical
- exit criterion: The report it read is not modified; the result is a new file
- exit criterion: A preview reports the same change the write makes, and writes nothing
- exit criterion: There is no path from any button to appendix G, H or I
- exit criterion: report/ is reached by something a person can press, and its allowlist entries are gone

## 2026-09-21 - P93 It really connected

**Why:** Nothing in P87 to P92 has reached a real Box tenant, a real ShareFile account or a real Chartwell report. Every test in those phases runs against a replayed transport or a generated document, which proves the code's use of an API and the shape of a document - and is not evidence that a credential, an app permission, a folder id or a heading is right at work. A phase that closed on that while implying otherwise would be this build's signature defect with a network adapter attached, so the evidence is owed, and it is owed from a person.

- phase added: P93 It really connected (Version one: the buttons he presses, gate: human)
- exit criterion: A person has confirmed, on the machine with the credentials, that each of the three connections really works
- exit criterion: One real appendix has been updated in a real report and the result opened in Word without layout damage
- exit criterion: The appendix registry matches the real report's headings, or has been corrected to

## 2026-09-21 - C54 What a button is allowed to claim

**Why:** The plumbing half of the block is finished and wants checking together: three network surfaces went onto the dashboard in four phases, and what they are allowed to claim is a property of all four rather than of any one. A checkpoint covers at most four phases, so the report half gets its own.

- checkpoint added: C54 after P90, covering P87, P88, P89, P90
- proves: Nothing in the block has reached a real service, the code says so where a person looks, the relay is not a run and cannot become one, delivery still has two inbound edges, and no credential reaches a repr, a report or a page.

## 2026-09-21 - C55 What the report cannot be made to say

**Why:** The report half of the block, plus the phase that proves any of it against the real thing. C54 covered the plumbing; this covers finding a named place in a report, moving Word content into it, the three buttons, and the signoff that is owed from a person.

- checkpoint added: C55 after P93, covering P91, P92, P93
- proves: Binding is by name in every module, an update is one appendix and leaves the rest byte-identical, a document that has been through the whole flow still opens, and no path exists from any button to the certification.

## 2026-09-21 - P94 A request list when nobody wrote one

**Why:** He will be testing with a pile of documents a client would send and no request list at all, which is also the state of every new engagement before somebody writes one. P68 built the sections, the references, the coverage and the three statuses, and deliberately left the items out - the reasoning was that the only real list in hand belongs to a client. That was right about that list and it left the machinery with no way to start: nothing in the tree can produce a request list, so nothing can track one.

- phase added: P94 A request list when nobody wrote one (Version one: the data it gathers, gate: auto)
- exit criterion: An engagement with no request list gets one, and the report says it is a starting point
- exit criterion: The default list owes nothing to any client's: every item is generic to valuation work
- exit criterion: Essential items are marked, and the historicals are among them
- exit criterion: A registered real list takes precedence over the default, and nothing silently mixes the two

## 2026-09-21 - P93 What is owed before any of this is believed

**Why:** P93 was made a blocking human gate and that was wrong. Phases close in order, so a signoff that can only happen on another machine halts every unrelated phase behind it - P94 was finished, tested and unclosable. The repo already has the right instrument: CLAUDE.md says BUILD/OPEN.md is for 'evidence only the work machine can produce', and the four steps are written there. The other human gates in this plan (P18, P20, P26, P28) are sign-offs on work that had just been done and could be checked in the same sitting, which is a different thing. So this phase becomes what it can honestly be here: the one that makes sure the owed evidence is recorded and that nothing in the block claims to have connected. The connection itself stays owed, in the place the build already keeps what is owed, and a human-gated phase records it when he is at his desk with the credentials.

- title: 'It really connected' -> 'What is owed before any of this is believed'
- exit criterion added: BUILD/OPEN.md carries the four things a person has to do, and what each needs configured first
- exit criterion added: Closing this phase does not read as the connection having been made
- gate: human -> auto

## 2026-09-21 - P95 The tracker reads the folder and updates itself

**Why:** He will point this at a folder of documents a client sent and expect the tracker to be right. P94 gave a new engagement a list; nothing yet reads a folder against it, and nothing writes the result anywhere he could open. The 2026-09-18 session settled that the request workbook is also the tracker - each item carrying In Model?, notes, Provided and Not Applicable - so the thing to produce is that workbook, which doubles as the list itself for an engagement that has none.

- phase added: P95 The tracker reads the folder and updates itself (Version one: the data it gathers, gate: auto)
- exit criterion: A folder of ordinary filenames produces a tracker with the right items marked provided
- exit criterion: A second run over the same folder changes nothing a person wrote
- exit criterion: A file that matched no item is reported rather than dropped
- exit criterion: An inferred match is visible in the workbook, not only in the code

## 2026-09-21 - P95 The tracker reads the folder and updates itself

**Why:** The dashboard button belongs in this phase rather than a later one. He described the whole thing as a button - 'I can point it to on the dashboard' - and without it the tracker is a module nothing reaches, which is this build's most repeated defect and is already flagged by the P82 scan. Splitting the button out would mean closing a phase that shipped a package nobody can run.

- task added: A button on /admin: point it at a folder and a tracker, and press it
- exit criterion added: The tracker is reached by something a person can press, and is not on the unreachable list

## 2026-09-21 - C56 A list nobody wrote, tracked against a folder nobody labelled

**Why:** The pair that makes a folder of client documents trackable: a list for an engagement that has none, and the tracker that reads the folder against it. They want checking as a sequence rather than separately - a client sending nothing, then some of it, then a corrected version, with a person writing in the workbook in between - because that is the order the two halves can disagree in.

- checkpoint added: C56 after P95, covering P94, P95
- proves: A new engagement gets a list and a tracker without anybody writing one, a guess stays labelled a guess from the file to the screen, a refresh never costs a person work, and neither half has become a run.

## 2026-09-21 - P96 The documents a valuation engagement really receives

**Why:** The first real client folder arrived on 2026-09-21 and the tracker matched 3 of its 13 files. Three causes, all in the reading rather than the tracking: the classifier's document classes are the ESOP set and this is a non-ESOP valuation engagement; the client's own folder names are discarded before anything looks at them; and a confidence is read off an attribute that does not exist, so every confidence ever reported has been 0.0.

- phase added: P96 The documents a valuation engagement really receives (Reading what a client actually sends, gate: auto)
- exit criterion: Every confidence the tracker reports is the classifier's own, and a test fails if it is read off a missing attribute again
- exit criterion: A file's folder is evidence, and a folder name alone can classify
- exit criterion: The thirteen files of the real client folder classify as recorded in tests, with no invented match
- exit criterion: No file classifies as something it is not: the false-positive cases are named and held

## 2026-09-21 - P96 The documents a valuation engagement really receives

**Why:** The two checks were written with a bare 'python -m pytest', which runs the system interpreter rather than the project venv and dies on a missing sqlalchemy. Every other phase in the plan uses 'python -m uv run pytest'. The second check also now names p17 and p38, because the classifier's closed set and the forecast rule are the two things P96 was most able to break.

- check dropped: python -m pytest tests/p96 -q
- check dropped: python -m pytest tests/p95 tests/checkpoints/c56 -q
- check added: python -m uv run pytest tests/p96 -q
- check added: python -m uv run pytest tests/p17 tests/p38 tests/p94 tests/p95 tests/checkpoints/c56 -q

## 2026-09-21 - C57 What a folder of real documents is allowed to be read as

**Why:** P96 stands alone in its block: it is the first phase driven by a real client folder rather than by files this build generated for itself, and what it changed - the classifier's vocabulary, its matching, and both places that build an Evidence - is reached by the tracker and by every run. A checkpoint is owed because those two paths were changed separately and have been wrong separately before.

- checkpoint added: C57 after P96, covering P96
- proves: That the reading a button does and the reading a run does agree about the same folder, that the vocabulary the classifier produces is the one the registry declares and the request list asks for, and that widening what can be recognised did not widen what can be recognised wrongly.

## 2026-09-22 - P97 A name a scanner ran into the next word

**Why:** B-061. The first real client folder's scanned PDFs read at 0.97 confidence and came back with words run together - BOARDMEETINGMINUTES. privacy/mask.py locates a declared identifier with re.escape and the payload scan with a lowercased 'in', so a name OCR has joined to its neighbour is masked by neither. The two agree by construction, which is the design, and what they currently agree on is the blind spot.

- phase added: P97 A name a scanner ran into the next word (Reading what a client actually sends, gate: auto)
- exit criterion: A declared identifier is masked whether or not the page kept the spaces inside it
- exit criterion: The scan catches the same identifier the masker would have missed, and a test proves it against a stubbed masker that does nothing
- exit criterion: Masking still never touches a figure, a period label or an account number it should leave alone
- exit criterion: The masker and the scan derive their matching from one function, and a test fails if either grows its own

## 2026-09-22 - P98 A fiscal year the file states seven times

**Why:** B-062. Two gaps found on the first real client folder's workbooks, both on version 1's own path. The balance sheet's seven sheets are named 2019-12-31 through 2023-12-31 plus two February interims; the detector read all seven period ends and then reported the fiscal year end as 'not stated', because its derivation requires every end to fall in one month and two of these do not. And the projections tab's periods are bare year columns - 2021, 2022, 2023, 2024 Feb YTD, 2024 (P) - where it reported no period cue at all, which understates what the page plainly says.

- phase added: P98 A fiscal year the file states seven times (Reading what a client actually sends, gate: auto)
- exit criterion: A workbook whose sheets are five December year ends and two February interims reports a December fiscal year end, with its evidence
- exit criterion: A two-year file, or one with no dominant month end, still reports the fiscal year end as not stated
- exit criterion: A forecast tab headed with bare years reports the years it covers and says plainly that dating them needs the engagement's year end
- exit criterion: Two columns headed with the same year are reported as needing to be told apart, not silently merged

## 2026-09-22 - P98 A fiscal year the file states seven times

**Why:** The second exit criterion as written contradicted behaviour that predates the phase and is defensible: two annual period ends a year apart in the same month already derive a fiscal year end, and a 52/53-week calendar ends near a month end rather than on one, so requiring a month end everywhere would refuse a real calendar. The new derivation is the stricter one because it runs on the harder case - year ends mixed with interim stubs - and that is what the criterion should have said.

- exit criterion added: A mixed set of year ends and interim stubs still reports the fiscal year end as not stated when too few years recur, when two months are equally dominant, or when the candidate ends are not month ends
- exit criterion dropped: A two-year file, or one with no dominant month end, still reports the fiscal year end as not stated

## 2026-09-22 - C58 What is read loosely, and what is still refused

**Why:** P97 and P98 both act on what a real client folder turned out to contain, and both changed a rule about reading rather than a piece of wiring. They also both loosened something: P97 widened what counts as finding a name, P98 widened what counts as knowing a period. A checkpoint is owed because loosening two readers in one block is exactly the shape that lets a wrong answer through while every phase test passes.

- checkpoint added: C58 after P98, covering P97, P98
- proves: That widening the match on a name and the derivation of a period did not widen what either will assert without evidence: a masked payload still carries its figures and period labels intact, a fiscal year end still arrives with the dates it was read off, and a projected column is still not a historical one.

## 2026-09-22 - P99 The totals that re-add, and the rows they cover

**Why:** The real client's financial statements turned out to prove the thing B-040 has been waiting for. Every one of the 280 subtotals across their fourteen sheets re-adds exactly from the rows above it, and 1,910 of the 2,198 parsed rows sit under one. review/router.py already routes an extracted figure to a person unless something re-added a total it feeds - the rule is built, tested and correct, and nothing has ever produced its evidence. The statements in the folder show the producer is a deterministic walk over rows this build already parses.

- phase added: P99 The totals that re-add, and the rows they cover (Reading what a client actually sends, gate: auto)
- exit criterion: Every subtotal in the real client's statements is found with the rows it re-adds from, and the count of covered rows is asserted
- exit criterion: A statement with a total that does not re-add reports that total as uncovered and says by how much
- exit criterion: Nothing here reaches a model, an OCR engine or the network
- exit criterion: The result reaches a person through the read record rather than sitting on a dataclass nobody looks at

## 2026-09-22 - C59 What arithmetic is allowed to stand in for

**Why:** P99 stands alone in its block. It produces evidence that an existing, tested acceptance rule reads and that nothing has ever set, and it does so on the path every run takes - so the ways it can be wrong are not about footing arithmetic but about what else moved when the read report grew a new field and the intake event grew a new sentence.

- checkpoint added: C59 after P99, covering P99
- proves: That a total re-adding is recorded as evidence about the rows under it and nothing else: the acceptance rule still refuses an extracted figure that no arithmetic covers, a statement that does not foot still says so by name and amount, and reading a folder still costs no model, no engine and no network.

## 2026-09-22 - P100 The hundredth phase, and the comparison that broke on it

**Why:** C59 went red on tests/p01 the moment the plan reached a hundred phases. Three places in tools/gate.py compare phase ids as strings, and 'P100' < 'P99'. The plan crossed that boundary this session, so the gate's own safety nets - which phases a checkpoint covers, whether phases are closing in order, and which phases sit past the last checkpoint - started giving wrong answers silently.

- phase added: P100 The hundredth phase, and the comparison that broke on it (Reading what a client actually sends, gate: auto)
- exit criterion: Every comparison of two phase or checkpoint ids in the gate orders them by number
- exit criterion: A plan of a hundred and more phases reports coverage, ordering and what is owed correctly
- exit criterion: tests/p01 passes at three digits, and a test fails if a string comparison comes back

## 2026-09-22 - C60 The gate's own arithmetic

**Why:** P100 stands alone because it is a change to the gate itself rather than to anything the gate builds. The gate is the only thing permitted to mark a phase done, so its own ordering is the one place a defect can let every other defect through - and this one had already let one through, opening P100 over a red C59 without a word.

- checkpoint added: C60 after P100, covering P100
- proves: That the gate orders phases and checkpoints by number wherever it compares two, that its four safety nets - coverage, closing in order, what is owed, and a red checkpoint blocking the next phase - all still fire at three digits, and that the tests which check the gate do not carry the same assumption.

## 2026-09-22 - P101 Version 1's own recipe, ending at a workbook nobody has to trust

**Why:** B-047 and B-048. The analyst wants to set an engagement up at the dashboard, point it at a client folder and a request list, and get a workbook out. Auditing that against the build found no path: all three shipped recipes end at qc-tieout, which CLAUDE.md puts outside version 1, and qc-tieout is a skeleton with no procedure - as is ddr-tagging, which full-ddr-intake also needs. Only four skills are live. And the two recipes that reach release write into the firm's real model template, which version 1 must never touch.

- phase added: P101 Version 1's own recipe, ending at a workbook nobody has to trust (A run that finishes, gate: auto)
- exit criterion: A released run on the focus scope reaches its release step and writes a workbook
- exit criterion: Every skill the recipe names has a procedure, and a test fails if a skeleton is added to it
- exit criterion: The workbook it writes is not the firm's model template, and says so on its face
- exit criterion: An input nothing in version 1 can produce is reported unmapped with its name, not silently skipped

## 2026-09-22 - P101 Version 1's own recipe, ending at a workbook nobody has to trust

**Why:** The first exit criterion said a run reaches its release step and writes a workbook. Driving one showed that is the wrong ending to ask for: model-load declares unmapped_inputs_require_review, so a run that cannot place every input stops on a person by the skill's own declaration - which is the designed behaviour and not a shortfall. The run reaches an ending on its own, which no run in this build had done before; release comes after somebody answers the queue, and this phase does not verify that half.

- exit criterion added: A released run on the focus scope gets through every step that has a procedure and ends on its own - waiting on a person for the inputs it could not place, rather than stopping at a step nobody built
- exit criterion dropped: A released run on the focus scope reaches its release step and writes a workbook

## 2026-09-22 - P102 Asking the model whether it is there

**Why:** The analyst wants to enter a key, choose a model and a spend limit, and press go from the dashboard. The spend limit and the folder and destination are already there. What is not is any way to find out whether the key works: the page says 'live' or 'no spend' from the adapter name alone, so the first evidence that a key is wrong is a run that quarantines after paying for the steps before it. P88 built exactly this for Box and ShareFile - four questions asked in order, each answered separately - and the model door has never had one.

- phase added: P102 Asking the model whether it is there (A run that finishes, gate: auto)
- exit criterion: Pressing the button on a machine with no key says the key is missing, and names it, without making a call
- exit criterion: Pressing it with a working key reports the model that answered and what the test cost
- exit criterion: A refusal from the API is reported as the step that failed, with the provider's own reason, and the steps after it as not reached
- exit criterion: The probe cannot be reached by a run, and spends nothing unless a person pressed it

## 2026-09-22 - C61 What a person can set up without being told how

**Why:** P101 and P102 are the two halves of one question: can a person set this up and press go. P101 gave version 1 a path a run can finish; P102 gave the model door the same test button Box and ShareFile have had since P88. They meet at the dashboard, which is the only place either is reached from, and at the spend: the one adds the step that costs money and the other is the only test that spends it.

- checkpoint added: C61 after P102, covering P101, P102
- proves: That the setup a person does at /admin produces a run that ends somewhere, that the ending names what it could not fill rather than leaving blanks, and that nothing on the path spends money unless a person pressed something - including the connection test that does.

## 2026-09-22 - P103 The files a run never sees

**Why:** Running the real client folder end to end showed ten of its thirteen files never enter a run. The binder decides a document type from filename tokens in document_type_conventions - a hand-maintained list carrying three types - and holds anything no token claims. P96 taught the classifier to recognise all thirteen, and the binder has never asked it: the classifier serves the DD tracker and the in-run read, both of which happen after a file is already in. So the analyst's stated goal - put all the data into a structured output - fails at the first step, with ten documents held and nothing wrong with any of them.

- phase added: P103 The files a run never sees (A run that finishes, gate: auto)
- exit criterion: The thirteen files of the real client folder all enter a run, and the record says which were inferred
- exit criterion: A file neither the conventions nor a confident classification claims is still held
- exit criterion: A filename a convention claims keeps that type even when the classifier would say otherwise
- exit criterion: Nothing binds a document type the registry has not declared

## 2026-09-22 - P104 Which documents a skill is even asked about

**Why:** P103 let twelve of the real client's thirteen files into a run, and the run then stalled: timing-normalization is handed every source, so it was asked to find periods in board minutes, an org chart and a competitor list. It escalated each as ambiguous, a person answered, the step re-ran and escalated again - thirty passes, thirty review items, no progress. Before P103 only three files entered and all three were financial, so nothing found it. A board minute having no periods is not an ambiguity for somebody to resolve; it is a document of a kind that carries none.

- phase added: P104 Which documents a skill is even asked about (A run that finishes, gate: auto)
- exit criterion: The real client folder's twelve bound files reach a run and only the financial ones reach timing
- exit criterion: A document type added without declaring whether it carries periods is refused by the registry
- exit criterion: A board minute in the folder no longer produces a review item nobody can answer

## 2026-09-22 - P105 Thousands on the page, cents in the cell

**Why:** The analyst gave the firm's own convention on 2026-09-22: the statements always go into the model in thousands, and they almost never arrive that way - a client sends units. And the rounding rule that goes with it: do not round before writing, keep every decimal in the cell and let Excel round to whole dollars for the eye. The input-help workbook declared scale 1 and no number format, so it would have been written in units and displayed to the cent.

- phase added: P105 Thousands on the page, cents in the cell (A run that finishes, gate: auto)
- exit criterion: The workbook declares scale 1000 and its value cells display no decimals
- exit criterion: A value written with decimals is stored with them, and a test fails if rounding creeps in before the cell
- exit criterion: The writer still refuses a figure whose scale does not match the template's, naming both

## 2026-09-22 - P106 The scale a person states

**Why:** The analyst's rule, given on 2026-09-22: the client may send financials in any form and the firm always puts them into thousands. P105 made the deliverable declare thousands; what it could not do is settle what arrived. A source whose scale is unstated stops timing-normalization, a person answers the review item, the step re-runs and asks again - because escalate() reads the source's own scale, which no decision changes. Thirty passes, thirty items, no progress. The same file already solves this for currency: the readers leave it unsettled rather than guess, the engagement profile is where a person declared it, and a source with no cue takes the profile's on the record.

- phase added: P106 The scale a person states (A run that finishes, gate: auto)
- exit criterion: A run whose statements state no scale proceeds once the profile declares one, and the record says where it came from
- exit criterion: A source carrying its own scale cue is untouched by the declaration
- exit criterion: No declaration means the run still stops, and the reason still names the file

## 2026-09-22 - C62 A document from the folder to the cell

**Why:** Four phases from one question - can the analyst point this at a folder and get a structured output - and each was found by the one before it failing on the real thing. P103 let the files in and made P104's livelock reachable; P105 fixed the deliverable's scale and left P106's question unanswerable until the profile could answer it. That chain is exactly what a checkpoint is for: each phase is green alone and the thing worth asking is whether the four agree about a document's journey from a folder to a cell.

- checkpoint added: C62 after P106, covering P103, P104, P105, P106
- proves: That a file the firm did not name a token for still enters a run and is recorded as inferred, that a skill is only asked about documents of a kind it can read, that what arrives at whatever scale is settled by a person and never defaulted, and that the deliverable is in thousands with its decimals intact.

## 2026-09-22 - P106 The scale a person states

**Why:** The profile field was added to engagement_profile.schema.json in place, at version 1.0.0. tools/surfaces.py caught it by the schema's hash - 'a contract edited in place' is the first of the accidents that snapshot exists to find, and the registry's own header says adding or changing a contract bumps the version and leaves the old one listed. 1.0.0 is restored untouched and the field lives at engagement_profile@1.1.0.

- task added: The new profile field lives at a new contract version, and 1.0.0 stays exactly as it was

## 2026-09-22 - P107 Ready to run has to mean it

**Why:** The Setup page's checklist promises that each step is checked against the live configuration, so it 'cannot tell you something is done when it is not'. It keeps that promise for the seven things that live in the configuration document and has no idea about the two that do not: the mask vault's key and the model adapter both come from .env. So the page says 'Ready to run - every step is done' on a machine where the worker pool will not start because nothing can be masked, and on one where every skill is answered by a fixture and no work is done at all. Both states were reached today while setting a real engagement up.

- phase added: P107 Ready to run has to mean it (A run that finishes, gate: auto)
- exit criterion: A machine with no vault key is told so by the checklist, before it activates an engagement
- exit criterion: A machine answering from fixtures is told that no work will be done, and how to change it
- exit criterion: A key that is present and malformed reads as missing rather than as done
- exit criterion: With both satisfied and every other step done, the page says ready and means it

## 2026-09-22 - P108 The one multiplication, and where it is allowed to happen

**Why:** P105 made the deliverable declare thousands and P106 made what arrived settleable, and between them sits the arithmetic nobody does: a figure read at the scale the client sent cannot be written into a template that declares another, because deliver/builder.py refuses a mismatch. That refusal is right and the reason is stronger than it looks - the Numeric Integrity Lock brackets the write and is only meaningful because the builder is arithmetic-free. So the restatement cannot go there, and until it goes somewhere the analyst's own rule - always thousands, whatever the client sends - has nowhere to happen.

- phase added: P108 The one multiplication, and where it is allowed to happen (A run that finishes, gate: auto)
- exit criterion: A figure at the scale the client sent reaches a thousands template with its value restated and the restatement on the record
- exit criterion: A figure already at the template's scale is untouched and nothing is recorded about it
- exit criterion: The writer still refuses a mismatch, because nothing downstream may rely on it restating
- exit criterion: The Numeric Integrity Lock still brackets a write it can prove faithful

## 2026-09-22 - P108 The one multiplication, and where it is allowed to happen

**Why:** A real folder carries roughly thirty lines over three years, so one event per restatement is ninety events in a run that did one thing. That buries the log it is meant to make readable, and the question a person actually asks is 'were they all moved by the same factor, and which ones were not' - which one event answers and ninety do not. So: one event, and its payload names every figure with both scales and its value before and after.

- task added: One event carries every restatement, naming each figure, both scales and the value before and after

## 2026-09-22 - P108 The one multiplication, and where it is allowed to happen

**Why:** The per-figure task is replaced by the one-event task added above; leaving both would read as a requirement for ninety events and one.

- task dropped: Each restatement is an event naming the figure, both scales and the factor

## 2026-09-22 - P109 The version nothing pointed at

**Why:** P106 built the scale settlement on a profile field, created engagement_profile@1.1.0 to declare it, registered it, and pointed nothing at it. intake/config.py still validates every profile against @1.0.0, whose additionalProperties is false, so the one field the settlement reads is the one field a person is refused for sending. The first real-folder run found it in four seconds: the profile POST came back 422 SKILL.SCHEMA_INVALID and the engagement would not activate. This is the build's most repeated defect - something built and wired to nothing - and it got past two reachability scans because it is a version string in YAML rather than a function nobody calls.

- phase added: P109 The version nothing pointed at (A run that finishes, gate: auto)
- exit criterion: The real client folder gets past the profile and activates
- exit criterion: A profile written before this phase still validates and still runs
- exit criterion: The scan is red if PROFILE_CONTRACT is put back to 1.0.0

## 2026-09-22 - P109 The version nothing pointed at

**Why:** engagement_profile@1.1.0's schema_version const still said @1.0.0 - the version bump was half done, so declaring the new version failed the new version's own check. Fixed in place rather than by cutting a @1.2.0, and that is allowed here only because @1.1.0 had never been committed and had never validated a single document. A version anything cites is fixed by cutting the next one. The surface snapshot caught the edit, which is what it is for; this is the decision it was asking for.

- exit criterion added: A schema's $id and its schema_version const name the same version, in every contract, checked

## 2026-09-22 - P110 Asking a question the profile already answers

**Why:** The timing payload is {files: [...]} and nothing else. The model is handed twelve documents, asked to type and date every period it finds, and never told when this company's fiscal year ends - although the engagement profile records exactly that, in fiscal_calendar.year_end_month and year_end_day, and a person filled it in at setup. Then a guard refuses the answer for saying FY2023 two ways. The guard is right; the question was unanswerable. The first real client folder quarantines there, and so would a real model, because a June year end and a bare 2023 on another page cannot be reconciled by anybody who has not been told which one this company uses.

- phase added: P110 Asking a question the profile already answers (A run that finishes, gate: auto)
- exit criterion: A run over the real client folder gets past timing
- exit criterion: The payload names the year end, and a test fails if the profile stops reaching it
- exit criterion: Two genuinely different ends for one label are still refused

## 2026-09-22 - P111 What a step declares, and what its handler asks for

**Why:** The release step declares needs: [model] and its handler asks for the output of timing as well - the writer resolves every figure_ref in the mapping against a catalogue built from timing's output, so a release handed a mapping alone has nothing to look the figures up in. It failed five steps into the first real client folder with 'release needs the output of timing, which this run does not have'. Nothing had caught it because needs is a recipe's declaration and the ask is a handler's code, and no test compares the two - and because the three older recipes all end at qc-tieout, which has no procedure, so no run in this build's history had ever reached a release step.

- phase added: P111 What a step declares, and what its handler asks for (A run that finishes, gate: auto)
- exit criterion: A run over the real client folder reaches the writer
- exit criterion: Dropping timing from the release step's needs fails a test rather than a run
- exit criterion: The scan reads the code rather than a table somebody has to remember to update

## 2026-09-22 - P112 The waiver the message promised

**Why:** The writer refuses to write anything while any required input has no source, and raises a review item saying 'nothing is written until a person supplies or waives them'. There is no way to waive. A person accepts the item, the step re-runs, recomputes the same list and asks again - the same livelock P104 fixed for timing, in the one step that produces the deliverable. On the first real client folder it blocked on eighteen inputs and blocked again on the identical eighteen after the item was answered. Every run where the mapping is not total ends with no workbook at all, and a mapping over a real client's folder is rarely total.

- phase added: P112 The waiver the message promised (A run that finishes, gate: auto)
- exit criterion: A run whose mapping is partial reaches a workbook instead of asking the same question twice
- exit criterion: An unanswered list still blocks, and an answered one does not silently cover a list that changed
- exit criterion: The Numeric Integrity Lock still brackets the write, marker cells included

## 2026-09-22 - P113 The front page, and what it now has to say

**Why:** The workbook's front page tells the analyst two things that stopped being true. It says a figure version 1 could not find is left blank - P112 now writes 'not found' into its own cell, and blank versus text is exactly the distinction that page exists to draw. And it says figures are 'stored to the cent', when P108 stores every decimal the restatement produced: the real folder's first workbook has 37.83500041 in a cell the page claims holds two decimals. The front page is the first thing anybody reads and the only thing standing between this file and being treated as the model. A page that describes a workbook that no longer exists is worse than no page.

- phase added: P113 The front page, and what it now has to say (A run that finishes, gate: auto)
- exit criterion: The delivered workbook's front page matches what the writer does
- exit criterion: Changing the marker or the format without changing the page fails a test

## 2026-09-22 - P113 The front page, and what it now has to say

**Why:** tests/p105 asserted the literal words 'stored to the cent' on the front page. That was P105's own sentence and P108 made it false three phases later - the cell holds every decimal the restatement produced, not two. The test was holding a wrong claim in place, which is the failure mode this build calls a test that checks nothing in reverse: an assertion precise about the wording and wrong about the fact. Rewritten to assert what P105 was actually for - that the scale is stated where somebody reads it - plus the precision promise in whatever words the page uses.

- exit criterion added: The P105 assertion holds the claim rather than the sentence, and still fails if the page stops naming the scale

## 2026-09-22 - C63 The first real folder, part one: setup, scale and the questions

**Why:** P107 to P110 are the four things that stood between a real client folder and a run that got anywhere: a checklist that called a machine ready when it could not mask or ask, the multiplication nobody did, a contract version nothing pointed at, and a question the profile already answered. Each was found by pointing the system at thirteen real files and reading what came back.

- checkpoint added: C63 after P110, covering P107, P108, P109, P110
- proves: A machine says honestly whether it could do any work; a figure read at the client's scale is restated to the template's, once, recorded, outside the writer; the field that declares the arrival scale can actually be set; and the skill that dates periods is told when the year ends.

## 2026-09-22 - C64 The first real folder, part two: the deliverable

**Why:** P111 to P113 are what was left once a run could reach the writer: a step that asked for something nobody handed it, a refusal that promised a waiver nothing could give, and a front page describing a workbook that had stopped existing. The last of the three was found by opening the file the first real folder produced and reading it.

- checkpoint added: C64 after P113, covering P111, P112, P113
- proves: A run over thirteen real client documents reaches a written workbook: every step is handed what its handler asks for, a person can say write it without these and be answered, and the page they read first says what is actually in the file.

## 2026-09-22 - P111 What a step declares, and what its handler asks for

**Why:** Three recipe plan hashes moved, because three release steps are now handed the figures as well as the mapping. The plan hash is what a run records itself under, so this is a real surface change and the snapshot is right to ask: valuation-input-prep because its release step failed on the first real client folder, monthly-refresh and mature-company-valuation because the same scan found them broken the same way. full-ddr-intake is unchanged and still cannot release, which is B-067.

- exit criterion added: The three changed plan hashes are recorded rather than accepted silently

## 2026-09-22 - P114 Files one level above where anybody is looking

**Why:** Setting the first real folder up, I registered the engagement's folder as 'Test Client' under a pattern watch at depth 2. The sweep looks at <root>/<a>/<b>, so every file sat one level above where it looks: the planner skipped them, no target was produced, no arrival was recorded, nothing was reported unclaimed - and preflight said 'every swept folder maps to an engagement', which is true and useless when nothing is swept. A green Setup page, thirteen client files on disk, and silence, for as long as anyone cares to wait. It took reading the planner's source to find. This is the step the analyst's own test begins with - point it at the folder where the docs live - and it is the one place the system watches somebody make a mistake and says nothing.

- phase added: P114 Files one level above where anybody is looking (A run that finishes, gate: auto)
- exit criterion: Registering a one-level folder under a depth-two watch fails, naming the shape expected
- exit criterion: Files dropped a level too high are reported by preflight with their count and location
- exit criterion: A correctly filed folder is unaffected and produces no warning

## 2026-09-22 - P114 Files one level above where anybody is looking

**Why:** The second check should run tests/p16 (the planner) and tests/p24 (preflight), which are the two places this changes. tests/p15 is the review queue and has nothing to do with it - it was named from a guess at the numbering.

- check dropped: python -m uv run pytest tests/p15 tests/p16 -q
- check added: python -m uv run pytest tests/p16 tests/p24 -q

## 2026-09-22 - P115 The column that was promised and never written

**Why:** The delivered workbook has a Source column with a header and forty-four empty cells, and the page in front of it says 'The Source column says which file and which row, so any one of them can be checked in a click rather than taken on trust.' Nothing has ever written it. I found it by opening the file the first real client folder produced. Every figure envelope already carries its source_id and its locator - the whole provenance chain exists and stops one cell short of the person who needs it. The blueprint's rule is that a figure is proved by arithmetic or it is seen, and this column is the seeing.

- phase added: P115 The column that was promised and never written (A run that finishes, gate: auto)
- exit criterion: A run over the real client folder produces a workbook whose Source column is filled
- exit criterion: The mapping cannot write a source cell, and a test proves the refusal
- exit criterion: A source cell that does not read back as written stops the release

## 2026-09-22 - C65 What the first real folder taught about setting it up and reading the output

**Why:** Both of these came from doing the analyst's own test rather than from reading the code. P114 is the folder I filed one level too shallow, which produced a green Setup page and silence. P115 is the column I found by opening the workbook the run produced - promised on its front page, never written, and the one thing that turns a figure from something to re-check into something to click through to.

- checkpoint added: C65 after P115, covering P114, P115
- proves: A folder the sweep can never reach is refused where it is typed and reported where the files are; and every figure in the delivered workbook says which document and which row it came from, read back after the write.

## 2026-09-22 - P116 The four keys the API does not take

**Why:** Every live model call this build would make carries metadata={run_id, context_ref, step_id, skill}. The Messages API's metadata object accepts one key, user_id, and rejects anything else with a 400 - confirmed against the installed SDK's own MetadataParam, which declares user_id and nothing else. So on a machine with a real key, the first call fails, and it fails as MODEL_PIN_UNAVAILABLE reading 'claude-sonnet-5: ...', which sends whoever reads it to the model registry to debug a model that was never missing. This module already learned that exact lesson once - the comment above _TOO_LONG says a scan nobody could shrink reported itself as 'claude-opus-5 is unavailable' - and the lesson was applied to one phrase rather than to the shape of the problem. Nothing caught it because every test answers from a fixture or a stand-in, and no request this build sends has ever reached the API.

- phase added: P116 The four keys the API does not take (A run that finishes, gate: auto)
- exit criterion: The request built for a real call carries only fields the installed SDK declares
- exit criterion: A refusal about an unknown parameter names the parameter and does not say the model is unavailable
- exit criterion: The fake and scripted adapters still route by skill

## 2026-09-22 - P117 A workflow a run can finish, and a machine that has one

**Why:** The watch form pre-selects mature-company-valuation whenever it is in the list, and every engagement under that watch inherits it. That recipe names gpc-scrub, cost-of-capital, dcf-build and qc-tieout; four procedures exist, none of them those, and tests/p101 asserts the recipe still cannot finish. So the default path is: setup goes green, files land, the run pays a real API for timing, tagging and EBITDA, and then quarantines at a skill nobody wrote. Money spent, no workbook, and the dropdown said nothing - its labels only distinguish approved from not approved, never built from not built. Two smaller ones sit beside it: approving a workflow is required before an engagement can activate and is on no checklist, so the refusal arrives at the last step; and templates/*.xlsx is gitignored while nothing on the start path builds them, so a clean machine has no workbook to deliver into and the remedy text tells a non-developer to bind a fallthrough at a higher layer.

- phase added: P117 A workflow a run can finish, and a machine that has one (A run that finishes, gate: auto)
- exit criterion: A first-time user cannot select a workflow that will stop, without being told it will
- exit criterion: A clean machine reaches an activatable engagement without anybody running a build script by hand
- exit criterion: The checklist's steps are the steps, and the count still follows the list

## 2026-09-22 - P118 The key it never checked and the limit it mislabelled

**Why:** Two claims the Setup page makes about the two things that cost money. First: the AI-model step reads done from the adapter's name alone - reaches_a_model is 'adapter not in (fake, scripted)' - so a machine with AA_LLM_ADAPTER=anthropic_messages and a missing, revoked or wrong-account key shows 'Ready to run: a run would mask, ask a model and write a workbook'. P107 was written precisely to stop that sentence being said on a machine that could not, and it checked the vault by opening it and the model by reading a string. Second: the spend limit is labelled 'Spend limit per run (USD)' with the hint 'This is per run, not per month', and harness/budget.py compares it against the engagement's cumulative spend across every run it has ever had. Set fifty dollars as a generous per-run allowance and the third run halts at a ceiling nobody set. It fails in the safe direction for money and it is a control whose label lies about what it does, which by this repo's own rule is a finding rather than a preference.

- phase added: P118 The key it never checked and the limit it mislabelled (A run that finishes, gate: auto)
- exit criterion: A machine with the adapter set and no key does not read Ready to run
- exit criterion: The label and the code agree about what the number caps
- exit criterion: A person is told what a run may cost when they have set no limit at all

## 2026-09-22 - P119 The period a figure carries and the period the cell asks for

**Why:** ModelLoad.apply refuses a named range the template does not declare, a figure_ref not in the catalogue, and a double binding. It never compares the period the template input asks for with the period the figure carries - and both are sitting in the payload it was handed. The only guard downstream is the Numeric Integrity Lock, which is a multiset: bind FY3's revenue to Revenue_FY1 and transpose two years and the lock's difference is empty, every total re-adds, provenance passes, and the workbook is wrong in a way nothing in this build can see. Every other invariant here is a guard a model cannot relax; the one cross-check that is free was left to the model's judgement. The line cannot be checked the same way - the template says 'Cost of sales' and the client's own label is 'Costs of Goods Sold', and matching those is the work the skill exists to do - so this phase does the half that is provable and records the half that is not.

- phase added: P119 The period a figure carries and the period the cell asks for (A run that finishes, gate: auto)
- exit criterion: Transposing two fiscal years in a proposal is refused rather than written
- exit criterion: The refusal names the input, the period it wanted and the period it was offered
- exit criterion: Nothing about the line is silently asserted

## 2026-09-22 - P120 Guards that were checked by looking for a word

**Why:** An audit of this suite found seven tests standing a substring in for a property, four of them the only enforcement of a named non-negotiable. The worst is tests/p45: it asserts 'proxy_headers=False' appears in tools/serve.py, and the phrase occurs twice - once as the keyword argument and once in the comment explaining it - so deleting the argument leaves the test green and uvicorn goes back to trusting X-Forwarded-For, which on a loopback bind is every peer, which makes the one input the identity check has rewritable by the request itself. It was defeated by a good comment, and 'keep the substring unique' is not a rule anybody can follow. The same shape guards OCR-is-local ('urllib.request' not in source, defeated by 'from urllib import request'), guards-are-not-configurable ('intake.config' not in source, defeated by 'from intake import config'), and the secrets port. Beside them sits a one-line hole the substring tests had nothing to do with: ui/who.py explicitly allows Origin: null, which a sandboxed iframe on any website sends, and several write routes take no body at all, so a page the analyst has open can pause every engagement.

- phase added: P120 Guards that were checked by looking for a word (A run that finishes, gate: auto)
- exit criterion: Deleting proxy_headers=False fails a test even with the comment left in place
- exit criterion: from intake import config and from urllib import request are both caught
- exit criterion: A rejected review item does not waive an unmapped input, asserted by calling it
- exit criterion: A cross-origin request with Origin: null cannot reach a write route

## 2026-09-22 - C66 What five reviewers found: the first run, and what it costs

**Why:** Three phases from pointing five reviewers at the build. Two of them would have stopped the analyst's own test tomorrow before it produced anything: every live model call carried four keys the Messages API rejects, so the first call 400s and reports itself as a missing model; and the dashboard pre-selected a workflow whose own test asserts it cannot finish, so the default path pays for three steps and quarantines at a skill nobody wrote. The third is what the screen claims about the two things that cost money - a key it never checked and a spend limit whose label contradicted the code enforcing it.

- checkpoint added: C66 after P118, covering P116, P117, P118
- proves: A request the provider accepts and a refusal that names the field rather than the model; a workflow a run can finish, offered by a form that says which ones cannot; and a Ready-to-run that means a key is present and a spend limit that says what it limits.

## 2026-09-22 - C67 Guards that were not guarding

**Why:** Two phases about guards that were not guarding. P119: a figure could be bound to the cell of another year and every check after it passed, because the Numeric Integrity Lock is a multiset - two transposed years leave its difference empty and every total still re-adds. P120: seven tests stood a substring in for the property they guarded, four of them the only enforcement of a named non-negotiable, and the worst was defeated by the comment explaining the line it was checking.

- checkpoint added: C67 after P120, covering P119, P120
- proves: A figure has to come from the year its cell asks for; and the guards over the peer address, the configuration boundary, local OCR, the secrets port and the waiver gate are each checked by what they do rather than by a word near them.

## 2026-09-22 - P116 The four keys the API does not take

**Why:** A new diagnostic code, SCOPE.PROVIDER_REFUSED_A_FIELD, owned by system. It is the point of the phase rather than a side effect: a 400 about the shape of the request is this build's mistake and says nothing about the model, and reporting it as MODEL_PIN_UNAVAILABLE sent whoever read it to the model registry to debug a model that was never missing. The remedy tells them not to change the pin.

- exit criterion added: The new code is on the diagnostics surface, deliberately

## 2026-09-23 - P121 Which year is FY1

**Why:** P119 refused a binding whose figure is not from the period its cell asks for, and immediately exposed why nothing had been able to check it: RunFacts.period_slots is declared, read by build_inputs, and populated by nothing. Only evals sets it. So on a real run the catalogue's periods are the client's own labels - FY2023, FY2024 - and the template asks for FY1, FY2, FY3, with no statement anywhere of which year is which. The model was left to guess, the scripted stand-in guessed by sorting, and the two guesses agreeing was the only thing holding it together. With P119 in place and the slots unpopulated, every binding on a real run is refused, so this is not an improvement on the situation - it is the other half of the same phase. Which years fill the slots is also a judgement (B-073 - three slots against five years of client data) and the rule has to be stated rather than inferred: the convention is already written down twice, in evals SLOTS and in the stand-in's sort, and it is that FY1 is the earliest of the slots and the newest year takes the last.

- phase added: P121 Which year is FY1 (A run that finishes, gate: auto)
- exit criterion: A real run binds figures to cells instead of being refused by the period check
- exit criterion: The mapping from the client's years to FY1..FYn is on the record by name
- exit criterion: The rule is written once and the two places that already assumed it agree with it

## 2026-09-23 - P121 Which year is FY1

**Why:** The mapping is stated in the model-load payload rather than emitted as an event. There is no bus at the layer that builds a skill's inputs - the runner has none and the dispatcher's is one level further in - and putting it in the payload is better than working around that: the payload is stored in the context store, so it is on the record either way, and it is in front of the model, which is the party that was being asked to guess. It is the same move P110 made with the fiscal calendar, for the same reason.

- task added: Which year became which slot is stated in the payload the model is given, and recorded with it
- task dropped: Which year became which slot is an event on the run

## 2026-09-23 - C68 Which year is FY1

**Why:** P119's period check had no way to pass until this, because the slot mapping the whole catalogue is keyed on was declared, read, and set by nothing. The two halves are one change: refusing a figure from the wrong year is only possible once something says which year each cell is.

- checkpoint added: C68 after P121, covering P121
- proves: Every run derives the client's years onto the template's slots by one stated rule, says in the payload which year each slot is, and binds figures to cells instead of being refused by the check that was added to protect them.

## 2026-09-24 - P122 A call the plan can bound, and no loop the graph does not own

**Why:** Two things the plan declares and nothing enforces, both of which decide what happens when a call is slow. Every step carries timeout_s - graph/execute.py computes it as min(step's, the firm ceiling) and puts it on the Attempt - and nothing between there and the provider reads it: the adapter passes no timeout, so the SDK falls back to a bound it computes from max_tokens. And the SDK is constructed with its default max_retries of 2, which sits inside a step the executor will itself retry, so one step can make six HTTP attempts and the run's own retry count says one. Worst case on a slow night is an hour on a single step with nothing in the event stream to say so. The second half is a blueprint non-negotiable rather than a preference: the graph owns every loop, declared with an integer maximum the compiler checks, and a retry the transport performs is a loop nothing counts.

- phase added: P122 A call the plan can bound, and no loop the graph does not own (A run that finishes, gate: auto)
- exit criterion: A step that declares 300 seconds cannot spend longer than that in one call
- exit criterion: One step makes at most as many provider calls as the plan says it may
- exit criterion: A timeout is distinguishable from a refusal, in the event and in the code

## 2026-09-24 - P123 Watching a run happen

**Why:** Tonight is the first run with a real key, and there is no way to watch one happen. Everything the build records is there - step.started and step.completed, model.called and model.answered with a price on it, the stall detector's alerts, the review queue - and all of it is behind a browser page a person has to keep refreshing, or behind an API a person has to know the shape of. What somebody actually needs while a run is going is one command that says which step is running, how long it has been running, what has been spent, and whether anything has gone quiet. Without it the honest answer to 'is it working or is it stuck' is to open the console and squint at a trace.

- phase added: P123 Watching a run happen (A run that finishes, gate: auto)
- exit criterion: A run in progress can be watched from one command with no browser
- exit criterion: A step running longer than its step declared is called out by name
- exit criterion: Nothing it does writes to the store

## 2026-09-24 - C69 Bounding a real call, and being able to watch one

**Why:** Both phases are about the first run with a real key. P122 is the bound: every step declared a timeout, the executor computed it, and nothing between there and the provider read it - while the SDK retried twice inside a step the executor would retry again, which is a loop the graph does not own. P123 is the seeing: everything a person wants while a run is going was recorded and only reachable through a browser.

- checkpoint added: C69 after P123, covering P122, P123
- proves: A slow provider produces a bounded, visible failure rather than an unbounded silence, and a run in progress can be watched from one command that changes nothing.

## 2026-09-25 - P124 A payload with the padding taken out

**Why:** A harness study (SoL-Pi, arXiv 2609.20519) puts a number on something this build has been paying without measuring: the model-load context is 305 KB against a 400 KB ceiling, and more than half of it is structural repetition carrying no information. The paper's third mechanism is 'keep access, drop repetition'; the cheapest form of that here is the serializer, which has been pretty-printing a machine-read payload since the first procedure was written.

- phase added: P124 A payload with the padding taken out (the run, gate: auto)
- exit criterion: Every procedure payload round-trips: json.loads(compact) equals json.loads(indented)
- exit criterion: A catalogue of about 1100 rows serializes at least 10% smaller than it did
- exit criterion: No payload is pretty-printed for a reader that does not exist

## 2026-09-25 - P124 A payload with the padding taken out

**Why:** The checks were written without the venv runner, so the gate ran a bare pytest that cannot import jsonschema or cryptography. Every other phase spells it 'python -m uv run pytest'.

- check dropped: pytest tests/p124 -q
- check dropped: pytest tests/p121 tests/p110 tests/p19 -q
- check added: python -m uv run pytest tests/p124 -q
- check added: python -m uv run pytest tests/p121 tests/p110 tests/p19 tests/p71 tests/p73 -q

## 2026-09-25 - C70 The same payload, spelled smaller

**Why:** P124 sits past C69 and the gate's own invariant is that the last checkpoint covers the last phase. The payload change touches every procedure at once, which is exactly the shape a checkpoint exists to catch: each phase's tests pass on its own module, and what they cannot see is a run where all four send a differently-spelled payload through the same assembler, guards and stand-in.

- checkpoint added: C70 after P124, covering P124
- proves: That compacting every procedure's payload changed nothing a run depends on: the assembled context still passes the guards, the scripted analyst still reads every payload, the review loop still resumes, and the workbook still comes out - while the context that was nearest the ceiling is measurably further from it.

## 2026-10-01 - P125 The formulas a workbook gets wrong

**Why:** The analyst asked for three reads a reviewer makes before a deliverable leaves - does the valuation make sense, does the prose sound like a person wrote it, and is there a silly mistake in the file. The third is the one this build can prove things about, because a formula is arithmetic: a total whose range stops a row short of its block opens cleanly, prints a plausible number and is wrong by one line, and deliver/qc.py asks only whether a workbook is broken in the ways Excel admits to. This phase is the workbook half.

- phase added: P125 The formulas a workbook gets wrong (The reviewer's reads, gate: auto)
- exit criterion: Each of the eight checks fires on a workbook built to contain its defect, and none fires on a workbook built to be correct
- exit criterion: A workbook with a wrong formula is still released; the findings are a record, never a refusal
- exit criterion: The footing check names how many totals it could not evaluate, so silence is never read as a pass
- exit criterion: The audit is reachable three ways - a released run, the console, the command line - and a test holds each

## 2026-10-01 - P126 The tells, the slips, and the two spellings of one thing

**Why:** The second of the analyst's three reads: the prose. A restricted-use report is the one thing a valuation engagement sends a client in words, and the analyst named three things to look for in it - does it sound like AI slop, are there em dashes, and is there a silly mistake like a missing comma. The hard half was not finding things: the first version of this module, over this repository's own four longest documents, reported about a hundred and fifty findings of which almost none were about the writing.

- phase added: P126 The tells, the slips, and the two spellings of one thing (The reviewer's reads, gate: auto)
- exit criterion: Every check fires on prose written to contain its defect, and the module describes each one
- exit criterion: A Markdown document built out of code fences, tables, CLI flags, file paths and fiscal years produces no slips at all
- exit criterion: A well-written paragraph produces nothing, and the defined-term check is silent on an ordinary word that sometimes starts a line
- exit criterion: --fix makes four substitutions, leaves a fenced block and a table byte-identical, refuses a .docx, and refuses to write without being told where
- exit criterion: A tell alone is a zero exit and a slip is not, so nobody's commit fails over an em dash

## 2026-10-02 - P127 The questions a reviewer asks of the numbers

**Why:** The third of the analyst's three reads: the figures. It is a different kind of check from the other two - the formula audit and the prose checks each make a statement about an artifact, provable from the artifact, and nothing about whether a margin is plausible is provable from a spreadsheet. So every finding is a question for a person, there are no default tolerances, and a test holds the module's own output to saying nothing that concludes.

- phase added: P127 The questions a reviewer asks of the numbers (The reviewer's reads, gate: auto)
- exit criterion: Each family of question fires on a table built to contain its gap, and a table with nothing worth asking about produces no question at all
- exit criterion: Every tolerance is the caller's: a unit with none is could_not_evaluate naming the unit, and zero is refused
- exit criterion: Nothing in the output concludes anything - held by a test reading the module's own text for the words a verdict would use
- exit criterion: Every finding is a result the qc-tieout contract allows, read out of the schema rather than repeated
- exit criterion: The ratios cover every operating expense and current-section category the taxonomy declares

## 2026-10-02 - P128 A command, not a page - and nine lines that would have failed on a clone

**Why:** The analyst wants a second way in: a command, not a page - point it at the right folders at lunchtime, come back and review. Three subcommands, each doing something the dashboard does not, and the slash commands that wrap them. Writing the guard for those slash commands found nine documented invocations that would have failed on a fresh clone, in the file the next interview session reads first, and the check that exists to stop that had been reading fenced blocks only.

- phase added: P128 A command, not a page - and nine lines that would have failed on a clone (The reviewer's reads, gate: auto)
- exit criterion: One command over a folder of mixed files reads each with the right check, renders through that check's own reporter, and one unreadable file does not take the folder with it
- exit criterion: stage goes through the only writer, records who and why, and takes the name rather than the path it came from
- exit criterion: ops/ imports no tool module: the console reaches the formula audit through deliver/, and tests/p10 is green
- exit criterion: Every command named in a slash command or a document exists, parses, and carries the environment unless it provably needs none
- exit criterion: A tool that needs the environment says what to type when it does not have it

## 2026-10-02 - C71 The three reads, agreeing with each other

**Why:** The four phases of the reviewer's reads each pass alone, and what none of their own suites can see is whether they still say the same thing as each other: one workbook is audited in three places, three modules were each written to have no default tolerance, and 'nothing concludes' is a property of what a person reads rather than of any one module's output.

- checkpoint added: C71 after P128, covering P125, P126, P127, P128
- proves: A workbook delivered by a run is audited identically by the release record, the console route and the command line; no read has acquired a default tolerance; and the combined output of all three concludes nothing about a valuation.

## 2026-10-02 - P129 Reading the firm's model, and refusing to say what its names mean

**Why:** B-008 and B-036 have both been blocked on the firm's model arriving, and what they are blocked on it for is four hundred lines of YAML: the named ranges, and what each one means. CLAUDE.md said the named ranges are not knowable from a photograph, which is true and had been read as not knowable at all. They are knowable from the file, and the half that must not be knowable from the file is what each name means - so that half is marked and refused rather than guessed.

- phase added: P129 Reading the firm's model, and refusing to say what its names mean (The reviewer's reads, gate: auto)
- exit criterion: The inventory resolves every defined name - global and sheet-local - to a sheet, a cell and whether it is empty, a number, a formula or a block
- exit criterion: A draft a person has read loads into TemplateInputs, and one they have not does not
- exit criterion: A name pointing at a missing sheet, two destinations or a whole column is reported rather than dropped
- exit criterion: The whole path works against a workbook this tool was not written against, and every name it proposes is a name that workbook really has
- exit criterion: It never writes into the workbook, and never over a draft somebody has been through

## 2026-10-02 - P130 Three questions the interview was not asking

**Why:** The analyst described two things this build has no question for: the workflows already built in Claude Code on the work machine, which hold context about the master model and about writing the reports, and the restricted-use report and deck themselves. Both are knowledge somebody has already written down, and the interview map was the only route in and was not asking. The excel-models topic was also asking for four hundred rows of transcription that tools/read_template.py now reads off the file.

- phase added: P130 Three questions the interview was not asking (The reviewer's reads, gate: auto)
- exit criterion: The map loads, every topic has angles, a done_when and feeds, and the ids are unique
- exit criterion: The two new topics read as open in interview status, so the next session is offered them
- exit criterion: The map is still generic: interview.py scan prints clean over the repository

## 2026-10-02 - P130 Three questions the interview was not asking

**Why:** The phase closed with its checks pointing only at the suites that already existed, which is how a data change comes to be covered by tests that would have passed over it. tests/p130 holds what the phase actually claims: that each topic asks for what the module it feeds is waiting on.

- check added: python -m uv run pytest tests/p130 -q

## 2026-10-02 - C72 The handoff, read end to end

**Why:** P129 reads the firm's model and drafts the binding it needs; P130 makes the interview ask for the part the file cannot state. Separately each is small and well tested. Together they are supposed to be a route - a command on the work machine, a question for the rest, a schema that loads here - and whether that route joins up is exactly what neither suite can see.

- checkpoint added: C72 after P130, covering P129, P130
- proves: The interview asks for what read_template.py produces, what it produces loads where the question says it goes under the filename the registry wants, and the route that invites work-machine files here still passes the outbound scan.

## 2026-10-02 - P128 A command, not a page - and nine lines that would have failed on a clone

**Why:** A fourth subcommand and a fifth slash command. The analyst's lunchtime question is whether there is anything to do yet, and that is what the client still owes - which had a button on the Setup page and no way to ask from a terminal. Adding it also forced the phase's own stated principle to be corrected: 'each subcommand does something the dashboard does not' was not quite true of any of them. The real line is that a command may be a second surface on a capability and may not be a second answer.

- task added: aa owed: what the client still owes, through the same dd_tracker the Setup page calls, writing nothing unless asked
- task added: a /owed slash command that drafts a chase note from the essential items and sends nothing
- exit criterion added: A command may be a second surface on a capability and never a second answer - stated in the module and held by the subcommand census

## 2026-10-02 - P128 A command, not a page - and nine lines that would have failed on a clone

**Why:** The fourth subcommand found B-081. aa owed --write was the first caller ever to use the tracker's default path, and the first run of its test wrote a client-named directory tree into the git working copy - which is what B-081 described and said no test covered, because every test passed an explicit path and the default was the only shape the page used. Fixed with the test that found it.

- task added: fix B-081: join the tracker path to the storage root, and refuse where storage is not a folder
- exit criterion added: The tracker lands beside the documents, and what a person wrote in it survives a refresh - both failing when the join is taken out

## 2026-10-02 - P128 A command, not a page - and nine lines that would have failed on a clone

**Why:** The needs() additions broke two of the six tools they were added to, and the test written to cover that was green on the break. Both are recorded in B-089 because the shape is the lesson: a check on the text of an invocation is not a check that it runs, and a subprocess whose launcher fails produces an error message that matches neither of the things being looked for.

- task added: fix the two tools the needs() addition broke, which put tools/ on the path rather than the repo
- exit criterion added: Every documented tool starts: run with the interpreter running the suite, asserting the return code rather than searching the output for words

## 2026-10-02 - P131 The prose checks, where the prose actually moves

**Why:** P126 built the prose checks and reached them from the command line, which means somebody has to remember. The analyst asked for checks that run when the thing is actually running, and there is exactly one place in this build where prose enters a client deliverable: the moment an appendix's content is transplanted into the report. The preview is where somebody is already looking.

- phase added: P131 The prose checks, where the prose actually moves (The reviewer's reads, gate: auto)
- exit criterion: A preview names the em dashes, the register phrases and the mechanical slips in the content arriving, and an update says the same thing as its preview
- exit criterion: The appendix moves whatever the words are; nothing here can refuse one
- exit criterion: A source with nothing wrong with it produces no findings at all
- exit criterion: A source the prose checks cannot read is reported with its reason, and the appendix still moves
- exit criterion: Nothing here reaches Appendix H, asked of the registry rather than of a docstring

## 2026-10-02 - C73 One check, two surfaces, one answer

**Why:** P131 gave the prose checks a second surface, and a check with two surfaces is a check that can come to say two things. That is the property C71 holds for the formula audit across its three, and it is worth holding for this one before it acquires a third.

- checkpoint added: C73 after P131, covering P131
- proves: The appendix preview and the command line read the same words and report the same findings; neither changes the document; the appendix moves whatever the words say; and the house style the checks are held to is still an open question on the interview map rather than a quietly settled one.

## 2026-10-02 - P126 The tells, the slips, and the two spellings of one thing

**Why:** A false positive found by pointing the checks at BUILD/OPEN.md: a bare file extension written in prose - 'whether a source .docx is the appendix whole' - reads as a space before a full stop. The extension list was already there for the missing-space check and now covers this one too. Calibration against documents that are fine is the half of this phase that took the work, and it does not stop when the phase closes.

- task added: a bare file extension in prose is not a space before a full stop
- exit criterion added: A bare file extension written in prose produces no slip, and the check still fires on a real space before a comma

## 2026-10-02 - P132 The dashboard answers what do I do now

**Why:** Run the console against a store of eighteen real runs and read the screen rather than the source. Four things were visible in one look: an engagement with one run printed the client, the scope and the time twice, and every engagement had one run; the two counts in the chrome read as disjoint buckets and were not, one counting runs and one counting questions that sat on those runs; the counts were facts rather than controls, when the next thing somebody wants after reading a number is the things it counted; and the dark button on a quarantined run was Resume, directly under a sentence saying retrying will not fix it.

- phase added: P132 The dashboard answers what do I do now (The reviewer's reads, gate: auto)
- exit criterion: A single-run engagement renders one row carrying the client, the engagement, the scope and the run id; a multi-run engagement still folds
- exit criterion: The two chrome counts say what they count, and the old wording cannot come back unnoticed
- exit criterion: Narrowing to what needs a person is a redraw of what the browser holds, composes with the find box, and leaves newest-first alone
- exit criterion: Resume is not the primary action under a sentence saying retrying will not fix it, and the sentence is asserted with it

## 2026-10-02 - P133 Where runs stop was not a funnel

**Why:** The Analytics funnel reported seventeen runs through the guards and none that ran a skill, on the same eighteen runs. Each stage counted every run matching its own predicate with no reference to whether that run got through the stages before it, and the max(0, ...) on the drop clamped the impossible negative - so the panel hid its own contradiction rather than showing it. A second label named one thing and measured another: Skills dispatched counted skill.completed, so a run whose skill was dispatched and then quarantined read as one that never started.

- phase added: P133 Where runs stop was not a funnel (The reviewer's reads, gate: auto)
- exit criterion: No stage reports more than the stage before it, held against the run shape that broke it - intake and a passing guard and no skill
- exit criterion: That run is counted where it actually stopped rather than only excluded from later stages
- exit criterion: A run that really passed everything is still in every stage
- exit criterion: The drops are plain subtractions and sum to the runs that fell out

## 2026-10-02 - P134 The source a reviewer was told to read

**Why:** Opened a real review item on the console. The modal asked what a document was, said why it had come to a person, and then told the reviewer to read a source it did not show - because the excerpt block is conditional on there being one and that sentence was not. And the excerpt existed the whole time: the classifier records the twelve headers it looked at under 'headers', and the review surface reads an excerpt from 'source_excerpt'. Two names for one thing, in the one place where a person is being asked to disagree with the system and cannot see what the system saw.

- phase added: P134 The source a reviewer was told to read (The reviewer's reads, gate: auto)
- exit criterion: A workbook classified 'other' reaches a reviewer carrying the headers it was judged on and the file they came from, end to end through the real reader and the real surface
- exit criterion: The modal only tells somebody to read the source when there is one, and says where to look when there is not
- exit criterion: The reveal discipline is unchanged: Accept and Correct still wait on the proposal being shown

## 2026-10-02 - C74 The screen says one thing, and it is true

**Why:** Three phases found the same way - running the console against eighteen real runs and reading the screen. Each is small alone; what none of their own suites can see is whether they left the three surfaces using one vocabulary, making one claim about order, and keeping one rule about what a person is shown before they decide.

- checkpoint added: C74 after P134, covering P132, P133, P134
- proves: The chrome, the engagement header and the filter use one phrase for a run that wants a person and the Help page defines it; the funnel's sentence and its numbers make the same claim and neither can move alone; and three phases of additions to the review modal left the reveal gate exactly where it was.

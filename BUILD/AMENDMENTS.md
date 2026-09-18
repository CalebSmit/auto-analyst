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

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

# The blueprint, node by node

*An audit record, 2026-10-05 to 2026-10-06, of all 118 nodes in `docs/architecture.html`
(exported to `graph/architecture.json`), made for the morning this repository is cloned onto
the work laptop. The question for each node is the owner's: is it serving a purpose, and is
it working. Verdicts are one of* **v1 working** *(built, reached by a real run, exercised
by a behavioural test),* **v1 gap** *(version 1 needs it and it is not wired or not
working),* **parked** *(built for later, recorded as such),* **parked, unrecorded**
*(built for later, and no document said so until this one),* **not built** *, and*
**superseded** *. Eighty-one nodes were audited by running their tests and tracing their
call sites; the thirty-seven in `orch`, `skill`, `tool` and `out` were audited from the code
and the closed phases after that audit was cut off twice (B-156), and are marked* (code
reading) *. Version 1 is `recipes/valuation-input-prep.yaml`: gather, read, normalize to the
input-help workbook, a person reviewing what arithmetic does not cover.*

*This file is hand-maintained, like `OPEN.md`. The backlog ids in the right-hand column are
where each gap is tracked; a node with none has nothing owed.*

## entry

| node | verdict | what is actually there |
|---|---|---|
| engagement | v1 working | `intake/roster.py RosterEntry` + profile `engagement_profile@1.1.0`; Setup page, launch, driver. Three required profile fields read by nothing (B-078). |
| analyst_chat | not built | No module, route or test; blueprint says `now`. Nothing to see. B-155. |
| job_recipes | v1 working | `graph/recipes.py`; four recipes; `registered.yaml` is gitignored so a fresh clone approves one on Setup first. |
| project_roster | v1 working | `intake/roster.py ProjectRoster`; the sweep reads nothing else. |

## source

| node | verdict | what is actually there |
|---|---|---|
| sweep_planner | v1 working | `intake/sweep.py` every 60 s from `serve.py`; unclaimed folders reported, never guessed. |
| sharefile | parked | `ports/storage/sharefile.py`, proved against a fake only (B-056, OPEN). Not on v1's path. |
| local_intake | v1 working | `intake/local.py` over `ports/storage/local_folder.py`; `AA_INBOX_ROOT=./inbox`. |
| email_watcher | not built | No mailbox code; `.eml` is read as a document (P158). B-155. |
| engagement_bind | v1 working | `intake/bind.py`; one engagement by path, one document type by name, else held. |
| storage_port | v1 working | `ports/storage/` Protocol; adapters local_folder, box, sharefile. |
| intake_window | v1 working | `intake/window.py`; quiet 30 min, max wait 24 h, a gap recorded rather than a delta sent. |
| engagement_lock | v1 working, one dead edge | `intake/lock.py`; `overdue()` has no production caller - the step-level stall scan covers it (B-154). Timeout hard-coded 6 h (B-078). |

## intake

| node | verdict | what is actually there |
|---|---|---|
| file_fingerprint | v1 working | `intake/fingerprint.py`; sha256 source id, version by bytes. |
| doc_reader | v1 working | `intake/readers/documents.py` + `layout.py` + OCR port. P151-P166: band reader, scans, misreads, cash roll-forward, column dating, signs, the files a client sends. 194 of 199 figures right against the filer's XBRL (P161). |
| workbook_reader | v1 working, half | `intake/readers/workbook.py` structural selector is live; `ModelSheetSelector` is built, tested and passed by nothing (B-155). |
| doc_classifier | v1 working, half | `intake/readers/classify.py`, deterministic; the model residue the docstring promises is not in the dispatcher (B-155). |
| period_detector | v1 working, half | `intake/readers/periods.py`, deterministic; same promise, same gap. Columns dated from the page since P163. |
| source_parse | v1 working | `ops/source_parse.py`; one resolver for both locator shapes; guards read through it. |

## data

| node | verdict | what is actually there |
|---|---|---|
| scope_registry | v1 working | `scope/scopes.yaml` + `registries/scopes.py` + `graph/resolve.py`; every run resolves. `--check` prints a corporate-finance template gap on a non-ESOP install (noise). |
| foundations | v1 working | `foundations/` ten files, `registries/methodology.py` clearance by digest, attached by the Context Builder. Nothing cleared on a fresh clone, by design. Six of the ten are P167's knowledge rules. |
| coa_taxonomy | v1 working as a placeholder | `taxonomy/coa-taxonomy@1.0.0.yaml` is not the firm's (OPEN); for a repeat client the prior workbook is meant to be the chart of accounts and that mechanism is not this node (B-049/B-145). |
| precedent_store | v1 working | `precedent/store.py`; human-decision-only writeback in four layers, verified. Empty on a fresh laptop. |
| index_gate | not built | Only a constraint cap and a notice string; no `index_lookup` tool registered. Both declared users superseded (P167). B-155. |
| coc_data | not built | No dataset, loader or vintage. Superseded with `cost-of-capital` (P167): the inputs are gathered, not looked up. |
| multiples_data | not built | Same; superseded with `gpc-scrub` (P167): the set comes from a Capital IQ export a person pulled. |

## orch *(code reading)*

| node | verdict | what is actually there |
|---|---|---|
| skill_tree | v1 working | `registries/skills.py SkillTree`; frontmatter for every skill, the body for one. |
| scope_resolver | v1 working | `graph/resolve.py`; walks the five layers once per run. |
| skill_index | v1 working | `registries/skills.py SkillIndex`. |
| orchestrator | parked | `orchestrate/orchestrator.py`; the whole package is reached by nothing (B-058, allowlisted). |
| run_plan | v1 working | `orchestrate/plan.py` validates `run_plan@1.0.0`; recipes are the live source of plans. |
| dispatcher | v1 working | `harness/dispatch.py`; context, masking, the door, every guard, in that order. |
| context_builder | v1 working | `harness/context.py`; skill body, references, methodology, precedents, profile, payload; content-hashed. |
| triage | parked | `orchestrate/triage.py`; same package (B-058). |
| graph_compiler | v1 working | `graph/compile.py`; every loop declared with an integer ceiling. |
| step_executor | v1 working | `graph/execute.py`; ledger, attempts, idempotent resume - what P168 leans on. |
| loop_controller | v1 working | `harness/loops.py`; exhaustion quarantines. |

## skill *(code reading; statuses from the tree)*

| node | verdict | what is actually there |
|---|---|---|
| sk_ddr | parked | `ddr-tagging` skeleton; named by `full-ddr-intake`, which therefore cannot run (B-143). |
| sk_timing | v1 working | `timing-normalization` draft, procedure `tools/normalize.py`; the unit rule (P162) and the one multiplication (P165). |
| sk_lineitem | v1 working | `line-item-tagging` draft, procedure in `harness/procedures/`. Output reaches model-load by no path (B-072). |
| sk_ebitda | working, outside v1 | `ebitda-normalization` draft, procedure, five categories; not in version 1's recipe. |
| sk_dcf | superseded | `dcf-build`: the firm's model does the DCFs (P167). Knowledge in `knowledge/methodology/`. |
| sk_gpc | superseded | `gpc-scrub`: comps are screened by a person in Capital IQ (P167). |
| sk_coc | superseded | `cost-of-capital`: inputs to the model, gathered and labelled (P167). |
| sk_model | v1 working | `model-load` draft, procedure; refuses a wrong period and, since P165, a figure that is not money. |
| sk_qc | parked | `qc-tieout` skeleton; out of v1 by design (B-004). |
| skill_contract | v1 working | `contracts/skills/*.schema.json`, checked on every proposal and output by `guards/schema.py`. |

## tool *(code reading)*

| node | verdict | what is actually there |
|---|---|---|
| guarded_runtime | v1 working | `harness/runtime.py`; `bound()` is the only way a procedure gets a tool; the policy gate inside every closure. |
| diagnostics | v1 working | `registries/errors.py`; every refusal carries a code, an owner and a *what now*. |
| constraint_registry | v1 working | `registries/constraints.py`; `require_version` is never asked on resume (B-139). |
| t_timing | v1 working | `tools/normalize.py` registered as `timing_normalizer`. |
| t_recompute | v1 working | `tools/recompute.py`; `annualize` and `restate_scale` are dispatched by tie-out and written by nothing, and `annualize` is wrong (B-143). |
| t_template | v1 working | `template_schema_lookup` from the template registry. |
| contract_registry | v1 working | `registries/contracts.py`; 34 schemas; `workpaper@1.0.0` validated only by tests (B-143). |
| t_registry | v1 working | the five tools `serve.py` registers; `index_lookup` is not one of them. |

## out *(code reading)*

| node | verdict | what is actually there |
|---|---|---|
| model_builder | v1 working | `deliver/builder.py`; arithmetic-free, bracketed by the numeric lock; refuses a non-currency figure first (P165). |
| ddr_pack | parked | the DDR deliverable waits on `ddr-tagging`. |
| workpaper | parked | `deliver/workpaper.py`; allowlisted-unreachable (B-059), prints a count as a count since P165. |
| idempotency_ledger | v1 working | `deliver/release.py` release ledger; a repeat is `release.replayed`. |
| delivery_port | v1 working | `ports/delivery/`; local_folder live, `box` a contract (B-143 names an enum mismatch). |
| box_mcp | parked | declared in the contract enum, no adapter by that name (B-143). |
| box_ccg | parked | same. |
| local_out | v1 working | `ports/delivery/local_folder.py`; the outbox. |

## guard

| node | verdict | what is actually there |
|---|---|---|
| untrusted_boundary | v1 working | `guards/untrusted.py` on every file read and every context; a hit halts the run with the pattern and offset. |
| payload_scan | v1 working | `privacy/payload_scan.py` at the model door; the only path to a model. |
| budget_governor | v1 working | `harness/budget.py` before and after every call; the door passes a literal estimate and the per-step cap is read by nothing (B-079). |
| policy_gate | v1 working, 3 of 4 | `harness/policy.py`; the budget predicate cannot fire - no caller passes a cost (B-153). |
| schema_gate | v1 working | `guards/schema.py` on proposal and output, with the repair loop. |
| provenance_gate | v1 working | `guards/provenance.py`; every figure's locator resolved against the parse store. |
| tieout_gate | v1 working | `guards/tieout.py`; fail-open branch for a missing derivation the contract forbids (B-143). |
| reconcile | parked | `guards/reconcile.py`; one tagging skill, nothing to reconcile (B-044). |
| confidence_router | v1 working | `review/router.py`; every one of 87 items on the real run went to a person. `arithmetic_cover` set by nothing yet (B-040); `review_floors` never produced (B-143). |
| unmask_verify | parked | `privacy/verify.py`; not on v1's path - the workbook is written from parse-store figures, never model text (B-043/B-077). |
| numeric_lock | v1 working | `guards/numeric_lock.py` brackets the write. |
| quarantine | v1 working as a record | `store.hold()` on every quarantine since P60; `quarantines()` read by nothing, so the context a person would need is invisible (B-153). B-032 is done. |
| deliverable_qc | v1 working | `deliver/qc.py` on every release; the formula audit's nine checks. |
| release_gate | v1 working | `deliver/release.py`; one file in the outbox, a repeat replayed. |

## privacy

| node | verdict | what is actually there |
|---|---|---|
| mask_engine | v1 working | `privacy/mask.py`; people are never declared to it (B-031, OPEN). |
| mask_vault | v1 working | `privacy/vault.py`; the pool will not start without `AA_VAULT_KEY`. |
| unmask_engine | parked | `privacy/unmask.py`; not on v1's path (B-043). |

## hitl

| node | verdict | what is actually there |
|---|---|---|
| review_queue | v1 working | `review/queue.py`; SLA sweep from `serve.py`. |
| review_surface | v1 gap | `review/surface.py`; ACCEPT works end to end; a REJECTED or CORRECTED decision changes nothing on the run it was made on (B-152, decided 2026-09-18, built by no phase). |
| decision_log | v1 working | append-only by trigger; on the run page and in the manifest. |
| outcome_feedback | not built | blueprint `now: None`; nothing owed for v1. |
| precedent_writeback | v1 working | `precedent/writeback.py`; 32 "no example shape" refusals per run are by design and read as noise (B-153). |
| sample_audit | parked | OPEN §5b; needs a rate a person sets. |

## notice

| node | verdict | what is actually there |
|---|---|---|
| fixed_notice | parked, unrecorded until now | `harness/notice.py`; one of seven templates reachable, its sentence stored in an event payload the console never renders (B-153). |

## ops

| node | verdict | what is actually there |
|---|---|---|
| event_bus | v1 working | `ops/events.py`; append-only three ways. |
| run_store | v1 working | `ops/run_store.py`; one SQLite file under `runs/`, named by `--check` since P168 (B-151). |
| checkpoint_store | v1 working since P168 | the ledger + resume; a process death stranded a run until P168 (B-149). |
| ops_console | v1 working | `ops/console/`; seven routes fetched by no page (B-139). |
| run_scorecard | v1 working | `ops/scorecard.py`; `manifest_entry` unwired (B-139). |
| analytics | working, unlinked | `/analytics` reachable by typed URL only (B-154). |
| admin_console | v1 working | `admin/`; `edit_watch` unwired (B-139). |
| preflight | v1 working | `admin/preflight.py`; sixteen checks since P168, the last asking whether the model adapter answers (B-150). |
| config_audit | v1 gap, read side | written on every admin write; read by no page and no command (B-154). |
| cost_meter | v1 working | `ops/cost.py`; every call charged. |
| drift_monitor | parked | `ops/drift.py`; `reopen_from_drift` joined to nothing (B-154). |
| stall_alert | v1 working | `ops/stall.py`; four kinds, raised every sweep. |
| run_manifest | v1 working | `ops/manifest.py`; `prompt_version` and `tieout_tolerance` never recorded (B-143). |

## gov

| node | verdict | what is actually there |
|---|---|---|
| skill_drop | parked, blueprint wrong | `governance/drop.py`; reached by nothing; blueprint says `now` (B-139, B-155). |
| skill_conformance | v1 working for methodology | `find_client_data` is the clearance scan; the skill-draft half parked (B-139). |
| skill_adapt | parked, blueprint wrong | `governance/adapt.py`; nothing reaches it (B-139, B-155). |
| skill_sandbox | parked | `governance/sandbox.py`; chain only, and the chain is dead (B-060). |
| sandbox_test | parked | same. |
| eval_harness | working as a command | `python -m evals`; registration is consulted by nothing on the run path (B-154). |
| replay_harness | parked, unrecorded until now | `evals/replay.py`; tests and the dead `shadow` only (B-155). |
| skill_submit | parked | `governance/board.py submit`; chain only (B-060). |
| skill_board | v1 working for recipes | the Approve button; the skill-review half parked. |
| shadow_run | parked | `governance/shadow.py`; `now: None`. |
| skill_registry | parked | `governance/registry.py`, "the one edge back into the live system", reached by nothing (B-139). |
| governance_log | live for recipe approvals | hash-chained; `verify()` runs in no production path (B-154). |

## port

| node | verdict | what is actually there |
|---|---|---|
| secrets_port | v1 working | `ports/secrets/dotenv.py`, the only adapter; the blueprint's keyring and cloud do not exist (B-155). |
| llm_port | v1 working, default is a trap | `fake` by default; a work laptop sets `anthropic_messages` and the key, and preflight is red until it does (P168). |
| model_pin | v1 working | fails the first model step, not startup as the blueprint says (B-155). |
| queue_port | v1 working | `in_process`, memory-only - the root of B-149, handled since P168; `redis_rq` fake-tested (OPEN). |
| compute_target | v1 working | `local_process`; the container half unproved here (OPEN). |

## pref

| node | verdict | what is actually there |
|---|---|---|
| config_store | v1 working | `intake/config.py`; validates on write, logs every change. Five settable fields read by nothing (B-078). |
| checkpoint_policy | v1 working, floor half | `review/policy.py`; "raise, never lower" is half-built - `review_floors` consumed and unproducible (B-143). |

## The count

118 nodes. 68 **v1 working** (nine of them with a recorded half or edge still owed), 3 **v1
gaps** (a rejection does nothing, the config log has no reader, the read side of the
quarantine), 3 **superseded**, 8 **not built**, and the rest parked - 14 of those with a
record before this audit and 7 without one, each now in the backlog. On the one real run
recorded in this repository, every guard on version 1's path fired or passed as designed,
and 87 of 87 extracted items reached a person.

# Chartwell Automated Analyst - master build plan

*Generated from `BUILD/plan.json` by `tools/gate.py`. Do not edit by hand -
use `gate amend`, so the reason for every change is captured with the change.*

**47 of 47 phases closed.** A phase closes only when `gate close` runs its checks and they pass.

Checkpoints re-run every prior phase together plus an integration test of their own.
A red checkpoint blocks the next phase - it means the phases disagree with each other.

## Block A - Foundations (the walking skeleton)

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P01** Project structure and build-state system | auto | Every directory in the blueprint repo tree exists and carries a README | 2026-09-02 |
| [x] | **P02** Contracts and registries | auto | Every schema loads, self-validates, and carries a version in its id | 2026-09-02 |
| [x] | **P03** Ports and adapters, with one conformance suite | auto | All six ports have a Protocol and at least one adapter | 2026-09-02 |
| [x] | **C1 - The skeleton holds bytes** | integration | A fake run moves bytes storage to delivery, emits events and writes a manifest | 2026-09-02 |
| [x] | **P04** Event bus, run store, manifest | auto | A halted run still writes a complete manifest | 2026-09-02 |

## Block B - The engine

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P05** Scope resolver | auto | An overlay that lowers a HITL requirement or widens a privacy class raises | 2026-09-03 |
| [x] | **P06** Graph compiler | auto | An undeclared cycle is rejected at compile time with a locatable error | 2026-09-03 |
| [x] | **C2 - A plan compiles and hashes** | integration | A recipe compiles; identical inputs give an identical plan_hash and a changed precedent snapshot changes it; and the store conformance suite passes against a real Postgres server as well as SQLite | 2026-09-03 |
| [x] | **P07** The assertion suites | auto | All 25 invariants are executable and pass against the current architecture | 2026-09-03 |
| [x] | **P08** Step executor, idempotency, resume | auto | Killing a run mid-flight and resuming re-executes zero completed steps | 2026-09-03 |
| [x] | **P09** Context builder | auto | context_ref reproduces the exact bytes a model was shown | 2026-09-03 |
| [x] | **C3 - A run survives being killed** | integration | Kill mid-flight, resume, zero completed steps re-execute, and plan assertions gate the resume | 2026-09-03 |

## Block C - The harness around one step

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P10** Policy gate, constraints, guarded runtime | auto | A tool not in the caller's allowlist is denied and the denial is in the event stream | 2026-09-03 |
| [x] | **P11** LLM port, model pin, budget governor | auto | A call attempting more than one model turn raises before it is sent | 2026-09-03 |
| [x] | **P12** Privacy: mask, vault, unmask, verify | auto | The same account masks to the same token across runs weeks apart - period alignment depends on this | 2026-09-03 |
| [x] | **C4 - One step through all six harness stages** | integration | A no-op skill passes context, reason, policy, act, verify and accept, with every stage emitting | 2026-09-03 |
| [x] | **P13** Guards and their adversarial fixtures | auto | A total altered by 0.4% fails tie-out - plausible on sight, outside tolerance | 2026-09-03 |
| [x] | **P14** Loop controller, quarantine, diagnostics | auto | A skill returning byte-identical output is stopped rather than retried | 2026-09-03 |
| [x] | **P15** Confidence router, review queue, decision log | auto | A policy attempting to lower a skill's review floor is rejected | 2026-09-03 |
| [x] | **C5 - Every guard fires on its own fixture** | integration | Every adversarial fixture whose guard is built fires that guard and only that guard (seven of ten after P15, the rest reported by phase), every loop is bounded by an integer the registry allows, and every failure carries code, owner and what_now | 2026-09-03 |

## Block D - First real vertical, local end to end

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P16** Intake: roster, sweep, binding, lock, window | auto | Invariant 24 proven by graph walk: no path from any intake source into the pipeline for an off-roster engagement | 2026-09-03 |
| [x] | **P17** Readers and the Source Parse Store | auto | Every extracted figure resolves by (source_id, locator) through one interface, whatever kind of file it came from | 2026-09-03 |
| [x] | **P18** First real skill: timing normalization | human | 100% arithmetic agreement with the deterministic tool | 2026-09-03 |
| [x] | **C6 - The walking vertical** | integration | Watched folder to masked payload to one real skill to guards to review to local output, on one real engagement | 2026-09-03 |

## Block E - Real skills and their surfaces

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P19** Line-item tagging and the precedent store | human | At least 95% top-1 agreement with the analyst gold set over a 400-item fixture | 2026-09-03 |
| [x] | **P20** EBITDA normalization | human | 100% of proposed add-backs tie via recompute | 2026-09-03 |
| [x] | **P21** Model builder, template registry, release | auto | A binding to a cell address is rejected at registration | 2026-09-03 |
| [x] | **C7 - A deliverable an analyst would accept** | integration | Three real skills on real files produce an .xlsx that opens clean, with every figure sourced and recomputed | 2026-09-03 |

## Block F - Assurance and operations

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P22** Eval and replay harnesses | auto | Every shipped skill has fixtures and a named numeric gate | 2026-09-03 |
| [x] | **P23** Ops console, scorecard, drift, stalls | auto | Every run gets a scorecard with a computed verdict | 2026-09-03 |
| [x] | **P24** Admin console, preflight, config audit | auto | A failing preflight check blocks activation of that engagement rather than failing later in a run | 2026-09-04 |
| [x] | **C8 - Observable and self-service** | integration | A run is fully observable from its event stream alone, and a new engagement is set up without touching code | 2026-09-04 |

## Block G - Scale, judgment and handoff

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P25** Worker pool and the queue port | auto | Several engagements process concurrently while one engagement still serialises | 2026-09-04 |
| [x] | **P26** Orchestrator agent and triage | human | A proposed plan that violates any plan assertion is rejected and the recipe is used instead | 2026-09-04 |
| [x] | **P27** The governance chain | auto | No path from the drop folder to the tree skips fixtures, review or a shadow run - remove any one gate and the path breaks | 2026-09-04 |
| [x] | **C9 - Many engagements, governed change** | integration | A nightly sweep over several engagements completes, and a skill ships through the full governance chain | 2026-09-04 |
| [x] | **P28** Docker, portability, handoff packet | human | No managed-service primitive is depended on anywhere in the codebase | 2026-09-05 |
| [x] | **C10 - v1 - portable and handed off** | integration | Everything above, green, inside a container, from a clean clone plus .env | 2026-09-05 |

## Block H - Practice groups and their workflows

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P29** Scope choices in the admin surface | auto | The admin surface offers every declared practice, segment and disposition, and marks the undefined ones | 2026-09-05 |
| [x] | **P30** Registered methodology: cleared once, checked every run | auto | A methodology file carrying something shaped like client data cannot be cleared | 2026-09-06 |
| [x] | **P31** Methodology per practice group | auto | A valuation run carries the firm and valuation methodology and not consulting's | 2026-09-06 |
| [x] | **C11 - A group's methodology, and nobody else's** | integration | An engagement is set up by choosing its practice group, and carries that group's cleared methodology and no other group's | 2026-09-06 |
| [x] | **P32** The recipe belongs to the engagement | auto | Two engagements under one watch run different recipes | 2026-09-07 |
| [x] | **P33** Registered recipes | auto | An unregistered recipe cannot run on client work | 2026-09-07 |
| [x] | **C12 - A group's workflow, and only approved ones** | integration | An engagement runs its own group's workflow, and a workflow nobody approved does not run at all | 2026-09-07 |

## Block I - The system runs

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P34** The run executes: the executor meets the dispatcher | auto | A skill step of a compiled plan executes through the SkillDispatcher, carrying the run's scope, engagement profile and identifiers | 2026-09-07 |
| [x] | **P35** A released run is driven to an ending | auto | A run released by intake is picked up and driven to a delivered or halted ending, on a real store, with no test double in the path | 2026-09-07 |
| [x] | **P36** Who is asking: identity on both surfaces | auto | Neither surface serves anything outside a loopback bind without an authenticated identity | 2026-09-07 |
| [x] | **C13 - The system runs** | integration | A file landing in a watched folder becomes a deliverable in the outbox, with nothing in the path that exists only in a test | 2026-09-07 |

## Block J - Making it his

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P37** The division focus, and the interview that fills it | auto | A focus that names an undeclared or parked segment fails the registry load | 2026-09-16 |
| [x] | **C14 - Making it his** | integration | The focus division is offered first and can be scoped into, the interview describes it in the resolver's terms, and what the interview learns cannot reach a committed file | 2026-09-16 |
| [x] | **P38** What the research changed | auto | The three model checks pass on statements that tie, fail with both numbers on ones that do not, and never pass on missing evidence | 2026-09-16 |
| [x] | **C15 - What the research changed** | integration | On a system started the way a person starts it, a client forecast cannot pass for historical statements by name, by contents or at the historical table, and the model checks can place every category the tagging skill writes | 2026-09-16 |
| [x] | **P39** A citation is checked where it points | auto | A figure read off the page with a number its cited rows do not carry fails the Provenance Check, naming both | 2026-09-17 |
| [x] | **C16 - A citation is checked where it points** | integration | The system a person starts calls every output guard the blueprint runs on a skill step, and every adversarial fixture fires its own guard | 2026-09-17 |
| [x] | **P40** What the second interview changed | auto | An add-back proposed as one-time that appears in more than two periods, or in the earliest period, is reviewed by a person | 2026-09-17 |
| [x] | **C17 - What the second interview changed** | integration | The analyst's one-time rule holds on a real EBITDA schedule, and the table that schedule read gives forecast driver baselines with their sources | 2026-09-17 |
| [x] | **P41** What the third interview changed | auto | A disagreement the analyst's rules settle has a figure from the right source that ties and cites it, and is still listed in the alignment report | 2026-09-17 |
| [x] | **C18 - What the third interview changed** | integration | An audit opinion read from a PDF is on the record, disagreeing statements are settled by the analyst's rules only where they apply without doubt, and the pilot's cost of capital waits for the comps | 2026-09-17 |
| [x] | **P42** The consoles, easier to use | auto | No page uses a browser pop-up, declares a name twice, or ships a script that does not parse | 2026-09-17 |
| [x] | **C19 - The consoles, easier to use** | integration | Runs and review items name the client the roster knows, every served page is one clean script namespace that asks nothing through a pop-up, and the review panel's round trip works through the real routes | 2026-09-17 |
| [x] | **P43** Easy to start and use | auto | A file added from the page lands only in its engagement's folder, by name, on local storage, for an engagement that is not archived, and the change is recorded with its digest | 2026-09-17 |
| [x] | **C20 - Easy to start and use** | integration | A setting written only in .env reaches the composed server, a person sets up a watch and destination and adds a client's file from the page into the folder the sweep reads, recorded against them, and Help is served beside every console | 2026-09-17 |
| [x] | **P44** The dashboards tell the truth | auto | Every verdict the scorecard can emit maps to a tone, and a passing run is not painted as needing attention | 2026-09-17 |
| [x] | **P45** Safe to leave open | auto | No page builds a script handler out of data, and esc() escapes every character that could close one | 2026-09-17 |
| [x] | **C21 - The dashboards, reviewed** | integration | A request under another name is refused before a route runs, reading the console writes nothing, a run's decisions are readable with the reveal beside each, an item on a replaced run is asked of nobody, and every served page says when it cannot reach the server | 2026-09-17 |
| [x] | **P46** The design language, set properly | auto | Every ink token meets its stated contrast against the surface it is read on, computed rather than asserted | 2026-09-17 |
| [x] | **C22 - The design language** | integration | Every served page carries the one stylesheet and its measured ink, none carries a colour or a type size of its own, and the keyboard's focus ring and a reduced-motion preference are served with it | 2026-09-17 |
| [x] | **P47** Panels that earn their space | auto | No rate on the Analytics page is rendered without the count it was computed from | 2026-09-17 |
| [x] | **C23 - Panels that earn their space** | integration | The analytics route carries the count behind every rate, and every served page carries its counts, the shadow at a cut edge, and a board that gives the run's own detail two rows of three | 2026-09-17 |


# Chartwell Automated Analyst - master build plan

*Generated from `BUILD/plan.json` by `tools/gate.py`. Do not edit by hand -
use `gate amend`, so the reason for every change is captured with the change.*

**71 of 71 phases closed.** A phase closes only when `gate close` runs its checks and they pass.

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
| [x] | **P07** The assertion suites | auto | All 25 invariants are executable and pass against the current architecture | 2026-09-18 |
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
| [x] | **P36** Who is asking: identity on both surfaces | auto | Neither surface serves anything outside a loopback bind without an authenticated identity | 2026-09-18 |
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
| [x] | **P48** The whole design, painted with one run | auto | Every node of the blueprint is drawn, at the position the blueprint gives it | 2026-09-17 |
| [x] | **C24 - The whole design, painted with one run** | integration | The console serves every node of the blueprint at the position the blueprint gives it, the Activity page carries the map and a way into it, and a run's trace can be laid over that drawing - including the name it records that the design has no node for | 2026-09-17 |
| [x] | **P49** The map, made to work with | auto | The order a run went through the design is on the map and in the list | 2026-09-17 |
| [x] | **C25 - The map, made to work with** | integration | The order a run went through the design is derivable from what the console serves, a node's neighbours come from the blueprint's own edges, and the page serves the map's controls in one script namespace | 2026-09-17 |

## The consoles

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P50** The map, made correct | auto | A slow pan does not clear the selection; a fast one still does not pick a node | 2026-09-17 |
| [x] | **P51** The map, drawn like a drawing | auto | The map opens above its far-zoom threshold, so the border that carries state is never drawn sub-pixel on first sight | 2026-09-17 |
| [x] | **P52** The map, answering what a person asks | auto | A person who has never seen the tool can say, from the first screen and without clicking, which run this is and what happened to it | 2026-09-17 |
| [x] | **P53** Three silent wrongs | auto | A material add-back routes to review whether its figure is positive or negative, and a test proves it by failing without the fix | 2026-09-17 |
| [x] | **C26 - The map, whole** | integration | The full-design map on the assembled system - the drawing is the blueprint's own geometry at a size its marks survive, the state a run left on each part is what the console serves, and the view answers where a run stopped without contradicting the run's own page - and the three silent wrongs found beside it: materiality read as magnitude, a comparative statement stopped rather than misread, and a person's name refused into the store that is read across clients. | 2026-09-17 |
| [x] | **P55** Built, and wired to nothing | auto | A served run assembles context from the Precedent Store, proved by a test that fails when the keyword argument is removed | 2026-09-17 |
| [x] | **C28 - Built, and wired to something** | integration | The system the command assembles reads precedent into every context it builds, carries what a release gate is built from, and records a failure under the code it arrived with - each asked of the object build() returns rather than of a double, because a double would have been wired correctly by whoever wrote it. | 2026-09-17 |
| [x] | **P57** Approving a recipe on a machine that has none | auto | A recipe can be approved from /admin on a clean clone, the approver's name is on the governance chain, and preflight check 10 goes green as a result | 2026-09-17 |
| [x] | **C30 - A machine that can be started** | integration | A workflow can be approved from /admin by a named person with a recorded reason, through the board and into the governance chain, so a clean clone goes from nothing-will-run to something-will - and the register is still written by nothing but the board, still not committed, and still refuses a recipe edited since somebody read it. | 2026-09-18 |
| [x] | **P58** The documented command works, or says why | auto | python tools/serve.py --check from a bare interpreter prints what to run and exits non-zero, rather than a traceback | 2026-09-18 |
| [x] | **C31 - What a person is told to type** | integration | Every command the guide and the session rules give works from a fresh shell, the one tool that must not need the environment still does not, and a tool run without it names the command to type instead of raising somebody else's ImportError five hundred lines in. | 2026-09-18 |
| [x] | **P61** What the admin surface records, and what it offers | auto | A second approval of the same file is refused with who approved it and when, and appends nothing to the governance chain | 2026-09-18 |
| [x] | **C34 - The setup surface, used** | integration | The two records a person creates during setup agree with each other and with the chain behind them: approving bytes that are already approved says who did and writes nothing, an edited file is still a second decision, neither register is committed, and the bar the profile form offers is one somebody chose rather than a default nobody did. | 2026-09-18 |
| [x] | **P62** A register that cannot go stale quietly | auto | A settled item cannot sit in the register as though it were open, and a test fails if one does | 2026-09-18 |
| [x] | **C35 - What a session is told, and whether it is still true** | integration | Nothing in the open register asks a session to close a phase the plan says is closed, run a checkpoint that is green, or obtain a sign-off that exists; every settled row carries the date that settled it; and the documents a session is told to read all exist and point at each other. | 2026-09-18 |
| [x] | **P63** An engagement view, and a way to find one client | auto | A person can find one client's runs among many without scrolling the list | 2026-09-18 |
| [x] | **C36 - Finding one client, and what the screen may claim** | integration | The engagement fold and the runs panel are two readings of one set of rows and cannot disagree about which runs or how many are open; every state the page names or paints is one RunState can hold; and the register still carries the question that refusing to invent a valuation date opened. | 2026-09-18 |
| [x] | **P70** The gate can always say why | auto | A check whose output contains a character the console cannot encode is still reported, and the gate still refuses | 2026-09-18 |
| [x] | **C39 - The gate reports a failure rather than becoming one** | integration | A real check that fails with output the console cannot encode is still reported, as a failure, with its text intact and the unencodable character replaced; the gate runs as a process under that console encoding without a traceback; a passing check still reads as passing; and no phase sits past the last checkpoint. | 2026-09-18 |

## The interview

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P54** The interview can finish again | auto | scan returns 0 on a knowledge tree with no session logs, 1 on answers with an empty register, and scans for real when both are present - each proved by running the command | 2026-09-17 |
| [x] | **C27 - The interview can finish again** | integration | The check CLAUDE.md names as what keeps a client's name inside knowledge/ answers honestly in all three states on the repo as it stands - refusing an empty register over real answers, passing on a clone nobody has been interviewed on, and scanning for real when there is something to scan - and the protocol, the map and the session that run it all still describe the same command. | 2026-09-17 |
| [x] | **P56** The register, fillable from what was already said | auto | suggest names the candidates in this repo's knowledge/ and says which file and line each came from | 2026-09-18 |
| [x] | **C29 - The register, fillable** | integration | A name enters the register because a person put it there, and a person is given what they need to do it: what in knowledge/ has the shape of a name and where it appeared, a command that adds one, and - for a session that named nobody, which the first three did - an acknowledgement that a person signed and that expires the moment another session is logged. No path lets the check pass without somebody having looked. | 2026-09-17 |
| [x] | **P64** An acknowledgement that says what it looked at | auto | A session recorded after an acknowledgement on the same day does not inherit it, and scan refuses | 2026-09-18 |
| [x] | **P65** An acknowledgement is a decision, not a default | auto | register --none with no note refuses and records nothing | 2026-09-18 |
| [x] | **P66** Two commands, one answer about the register | auto | With a standing acknowledgement, status says so and says what expires it, rather than warning of a refusal that is not happening | 2026-09-18 |
| [x] | **C37 - The boundary, exercised rather than read** | integration | A session walked end to end through the commands a person actually runs - status, session, answers, acknowledgement, scan - reports what the record holds at every point: the acknowledgement covers what it looked at and nothing logged after it, a standing one cannot be silently replaced, status and scan never describe the same file differently, a leaked identifier is named rather than raised on, and no command reaches the repository's own knowledge folder. | 2026-09-18 |

## The engine

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P59** The graph owns every loop, in fact | auto | A schema, provenance or tie-out rejection on a step declaring the matching region re-runs that step with the guard's failure in its context, and the second pass's context_ref differs from the first's | 2026-09-18 |
| [x] | **C32 - A loop that can be entered** | integration | A schema, provenance or tie-out rejection on a step whose recipe declares the matching region re-runs that step with the guard's own verdict in its context, masked with the run's identifiers by the one object that holds them - and nothing can name a region the recipe did not declare, substitute one loop for another, or raise a ceiling. The plan hash does not move and the blueprint needs no re-export, because the code caught up to what the design already said. | 2026-09-18 |
| [x] | **P60** A quarantine that leaves something behind | auto | store.quarantines() is non-empty for every run with a quarantined step, and a resumed pass over the same step key does not write a second record | 2026-09-18 |
| [x] | **C33 - A run that ends says so** | integration | Every quarantined step leaves exactly one record whatever ending produced it, a resumed pass over the same key does not write a second, and the three failure policies every recipe declares finally mean three different things - review tells a person, quarantine does not, halt ends the run through the one door that writes a manifest, which is the driver's and never the executor's. | 2026-09-18 |
| [x] | **P71** Nothing is built and wired to nothing | auto | A public function referenced nowhere fails the check, and adding one to the allowlist without a reason still fails | 2026-09-18 |
| [x] | **C40 - An unwired seam is a decision, and the decision is on the record** | integration | The scan is quiet on the tree as it stands, so a failure means something new; every excused seam names a backlog item that exists and does not claim to be built; the two found today are resolved the two different ways they warranted - one deleted because there was nothing to record, one kept because there was; and the earlier findings of the same shape, P55's precedent wiring and P60's on_failure, are still wired. | 2026-09-18 |

## Version one: the data it gathers

| | Phase | Gate | Closes when | Status |
|---|---|---|---|---|
| [x] | **P67** Proved by arithmetic, or seen | auto | A figure carrying its locator and a passing arithmetic cover is accepted without a person, with no confidence stated | 2026-09-18 |
| [x] | **P68** The request list, as the schedule documents arrive against | auto | The section of an arriving file is read from its path, and a path naming no section says so rather than guessing | 2026-09-18 |
| [x] | **P69** Last year's model, rolled forward | auto | Rolling a full ten-year window drops the oldest year and keeps the width at ten | 2026-09-18 |
| [x] | **C38 - What version one gathers, and what it refuses to decide** | integration | A repeat year rolls through all three pieces together - a ten-wide window dropping its oldest year, two dates moved on, last year's line items carried as this year's schema - and only what no arithmetic covers reaches a person; a request section never stands in for an item; a line-item mismatch is handed over rather than resolved; the sections are not a second document-type vocabulary; a skill's judgement is still routed on its confidence; and the fact that nothing yet sets the acceptance rule's evidence is recorded rather than quiet. | 2026-09-18 |


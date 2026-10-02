# Build backlog

Changes the interview has proposed. Each: `## B-NNN title`, then `status:` one of
proposed, approved, declined, built; what it changes, the files, and the answers
behind it.

## B-001 Correct the interview map for this division
status: built
Pre-revenue was listed as an edge case; it is ~25% of the work. Added topics: forecast,
debt tab and model checks, internal value review, pre-revenue, purchase price allocation.
Files: interview/topics.yaml. Evidence: Q4, Q5, Q8, Q3. Size: small.

## B-002 Draft pilot recipe: mature company valuation
status: built
The analyst's order with the skills that exist: historicals (timing, tagging), EBITDA
normalization (unconfirmed), GPC, cost of capital, DCF, model load, model checks. Historical
financials are the only required document. Not registered - a person registers it at /admin.
Files: recipes/mature-company-valuation.yaml. Evidence: Q6, Q7, Q9, Q10. Size: small.

## B-003 Draft non-ESOP methodology
status: built
The three core methods, historicals first, client-sourced figures marked, both forecast
paths, the three model checks, the review chain. Needs clearing at /admin before any run
attaches it. Files: foundations/valuation/non-esop/_segment/how-we-work.md.
Evidence: Q1, Q3, Q5, Q8, Q9, Q10. Size: small.

## B-004 Mechanical half for qc-tieout: the three model checks
status: proposed (engine built 2026-09-16, P38)
The deterministic engine exists: tools/statement_checks.py - net income ties, balance sheet
balances, cash agrees, movement flags; failures keep both numbers; absence is never a pass;
output fits the qc-tieout contract. What remains: the procedure that feeds it the tagged
table and the stated totals, naming it in constraints.yaml and qc-tieout's tools (governance
chain), and fixtures. Evidence: Q8; research (askOdin, Finsider). Size: medium.

## B-005 A guideline M&A transactions skill
status: proposed
2026-09-17-2 Q11: the transaction multiples are the first thing the MD looks at in the internal value review - this is the highest-priority missing skill.
Run on nearly every engagement; no skill exists. Through the governance chain.
Evidence: Q5, Q7. Size: large. Needs: data sources and selection criteria (next session Q6).

## B-006 A forecast skill
status: proposed
2026-09-17-1 Q4-Q5: two paths. With a client forecast, nothing is proposed - it is used unchanged, and interest expense comes from the debt tab. Without one, the skill proposes drivers only (revenue growth % per year, COGS % of revenue, opex % of revenue with any gradual improvement), each with its reason; the template computes the lines. Every driver is an assumption a person reviews.
2026-09-17-1 Q6: baselines are computable - a tool gives each driver's last-year value and multi-year averages with their source rows; the skill proposes which baseline is normal and the step path over the forecast years, with a reason.
Second-largest time cost. Two paths: adapt the client's forecast, or build one for client
approval. Through the governance chain. Evidence: Q1, Q8, Q9, Q10. Size: large. Needs: next
session Q2-Q4.

## B-007 Debt tab extraction
status: proposed
Entering every long-term debt instrument is slow. Extract instruments into the template's
debt inputs. Evidence: Q8. Size: medium. 2026-09-17-1 Q4: the debt tab also produces the forecast's interest expense, which replaces the client's own interest expense line - so this feeds the forecast, not only the balance sheet. Needs: the source document and fields (next
session Q9), and the real template.

2026-09-17-2 Q2: the source is the long-term debt note in the audited financials (one page listing every instrument); fields per instrument include maturity date, starting amount, years remaining and interest rate. An extraction from a page the Document Reader already parses, each field citing its row. Still needs the template's full debt tab fields.
2026-09-17-2 Q3: with no debt note, three known treatments - match the client's interest expense, request the debt details, or forecast interest at zero or flat. The system notices the missing note, drafts the request, and puts the three options to a person; it picks none.
## B-008 Register the non-ESOP Excel template
status: proposed
Non-ESOP currently resolves to the firm master template. Bind the real model at
valuation/non-esop/_segment with its named ranges. Blocked on the template being available.
Evidence: Q1, Q8. Size: medium.

## B-009 "What am I missing" - document coverage per engagement
status: proposed
Research: F2's missing-file detection, Hebbia's documents-by-questions matrix. A per-engagement
report of which expected documents have arrived, drafted as a follow-up list for the client.
Needs `expected_types` on recipes (non-blocking, unlike required_types) and more document
types: fixed asset schedule, debt schedule, interim financials. The forecast type was added
first because its absence was a defect (see P38). Evidence: Q9, Q10. Size: medium.
2026-09-18 (P63): the mechanism is buildable and the **data is not**. An `expected_types`
with nothing in it is a report that says nothing - the "wired to nothing" shape P55 was
about - so this waits on one interview answer: for a mature-company valuation, which
documents do you expect to receive, and which of them is the job actually blocked on? With
that list it is a small build; without it there is nothing to report against.

## B-010 Add-back register with graded support
status: proposed
Research: vortex-tuck-in-analyst (defensible / scrutinize), askOdin (contradictions kept as
findings). Each proposed adjustment carries a support grade and its evidence. A new
ebitda-normalization contract version and a governance change. Needs next session Q1 first -
whether normalization is done on mature-company work at all. Size: medium.

## B-011 Extraction accuracy measured on a real engagement
status: proposed
Research Stage 1 benchmark, proposed in BUILD/OPEN.md section 5 question 5: 95% of clean line
items with the right locator; below 90% a person stays in the loop. Needs one hand-keyed
engagement as a masked gold case (next session Q16). Size: medium.

## B-012 Proof of cash
status: proposed
Research: Finsider, askOdin. Revenue reconciled to bank deposits. Needs a bank statement
document type and reader, and first: whether the practice does this at all (not yet asked).
Size: large.

## B-013 Show the cited number where it sits on the page
status: proposed
From the LlamaIndex due-diligence agent: the reviewer sees the source highlighted, not just a
locator. Step one needs nothing new - a text excerpt of the cited row with the value marked,
on the review page. Step two, a highlighted page image, needs positions from pypdf's text
visitor and a page renderer (a new dependency; check its licence). Evidence: the post;
Q3 (the associate and MD review the model). Size: medium.

## B-014 Search across an engagement's documents from the review page
status: proposed
From the same post: keyword and regex search over parsed pages, filtered by file. For a
person checking a figure, not for a skill (skills are one turn). Size: small to medium.

## B-015 The analyst's one-time test, and a place for management's confirmation
status: proposed (part a built 2026-09-17, P40: one_time_doubts; part b - recording management's confirmation on the schedule - still proposed)
The EBITDA procedure flags a non-recurring candidate only when it recurs in every period. The
analyst's test (2026-09-17-1 Q3): one-time means it appears in only one or two periods and not
in the years before; management then confirms. Two changes: (a) the recurrence test in
harness/procedures/ebitda_normalization.py follows the analyst's rule - a candidate present in
more than two periods, or in the earliest year, goes to review as possibly recurring; (b) a
review question for non-recurring items asks whether management confirmed it, with the answer
recorded on the decision (a contract version if it must live on the schedule). Size: small (a),
medium (b). Evidence: Q2, Q3.

## B-016 Correct the draft methodology: the client forecast is not adjusted
status: built (2026-09-17, P40)
foundations/valuation/non-esop/_segment/how-we-work.md says a client forecast is "the starting
point, adjusted for what the client says in due diligence". The analyst (2026-09-17-1 Q4): it is
the source of truth, used unchanged and tied to wherever possible; the one exception is interest
expense, built from the debt tab. The file is not yet cleared, so correcting it costs nothing.
Size: small.

## B-017 Pilot recipe dependencies, as the analyst described them
status: built (2026-09-17, P40)
recipes/mature-company-valuation.yaml has wacc needing gpc (from session 1's order) and dcf not
needing gpc. 2026-09-17-1 Q8: GPC, M&A transactions and WACC are independent and run side by
side; the DCF's exit multiple uses the comps' medians and averages. Change: wacc needs mask
only; dcf needs gpc as well (and the transactions step once a skill exists). Also refresh the
stale comment on the ebitda step (confirmed in Q1). A registered recipe's digest changes, so a
person re-registers it. Size: small.

## B-018 Read a Capital IQ export as an intake document
status: proposed
2026-09-17-1 Q9: comps and transactions come from Capital IQ, pulled by hand (no API). The
GPC skill, and a transactions skill, can only start from the export. Needs a document type in
the closed vocabulary, filename conventions and classifier cues, and a reader for the export
layout - which needs a sample export (promised). Size: medium.


## B-019 Forecast driver baselines, computed
status: part built (2026-09-17, P40) - tools/forecast_drivers.py exists and nothing reaches
it. Version 1 gathers data and does not run the model, so a forecast is not on its path.
2026-09-17-1 Q5-Q6: a firm-built forecast starts each driver from last year's percentage or an
average of the last few years. A deterministic tool, like tools/statement_checks.py: from the
tagged historicals, per period and per driver (revenue growth, COGS % of revenue, opex % of
revenue), the last-year value and the 2-, 3- and 5-year averages, each with the rows it came
from, through `recompute`. It chooses nothing: which baseline is normal and how it steps is the
skill's proposal and a person's review. The first mechanical piece of the forecast skill (B-006).
Size: small to medium.

## B-020 Pilot recipe version 3: WACC waits for the comps
status: built (2026-09-17, P41)
Corrects B-017. 2026-09-17-2 Q5: beta is the median unlevered beta of the comp set, relevered, so
the WACC is not final until the comps are. Version 2 made wacc independent of gpc - wrong
whenever CAPM is used. Change: wacc needs gpc again, the comment says why, dcf still needs both.
A new version; a person re-registers it. Size: small.

## B-021 Beta and cost of debt, the mechanical parts
status: part built (2026-09-17, P41) - tools/beta.py exists and nothing reaches it. The
firm's formula is a required argument rather than a default, and cost of capital is outside
version 1's path, so there is no caller to give it one.
2026-09-17-2 Q5: median of the comps' unlevered betas, relevered to the subject's capital
structure; pretax cost of debt from the credit rating the analyst assigns. A deterministic tool:
median unlevered beta with the companies it came from; relevered beta at a stated debt-to-equity
and tax rate (formula to confirm - Hamada is the usual one); cost of debt looked up from a rating
table (Capital IQ, 2026-09-17-2 Q6). The rating itself and the capital structure are judgment.
Size: small to medium.

## B-022 Credit rating support: ratios against rating bands
status: proposed
Requested by the analyst (2026-09-17-2 Q6): the rating is eyeballed today and the MD decides; a
comparison of interest coverage, debt to equity and similar measures would support the call. A
deterministic tool computes each ratio from the normalized historicals and the debt tab, places
it in a rating-band table, and shows where the measures agree and disagree. It recommends no
rating. Blocked on one person's decision: which band table the firm uses (a published
coverage-ratio table or its own) - that table is methodology, cleared at /admin. Size: medium.

## B-023 Repeat clients start from last year's model
status: proposed
2026-09-17-2 Q7: a repeat client's historicals are copied from last year's model and only the new
period is entered; the forecast method, the comps and the adjustment items carry forward; WACC
data is refreshed as of the new valuation date. The prior-year-rollforward skill exists as a
skeleton at valuation/_repeat with exactly this job. Missing: reading last year's delivered
workbook (by its named ranges, through the template registry) as the source for prior periods,
so timing normalization runs on the new period only, and a rollforward report of what changed.
Needs the real template. Size: large - but it removes most of the heaviest step for about half
the work.

## B-024 Audited over internal when sources disagree
status: built (2026-09-17, P41)
2026-09-17-2 Q8: when audited and internal statements disagree for a year, audited wins. Today the
timing normalizer takes no figure on a disagreement and sends it to a person - safe, but the rule
is settled for this pair. Needs: an `audited` marker on a financial statements source (the
independent auditor's report is the usual cue, with the classifier's evidence recorded), and a
source precedence in the normalizer that takes the audited figure while still listing the
disagreement in the alignment report. Any other pair of disagreeing sources still goes to a
person. Size: medium.
2026-09-17-2 Q9: also the most recently received document wins, including a restated prior-year column in a newer set of statements. Precedence has two parts - recency and audited over internal - and their order when they collide is asked in Q10. Q10: probably audited, not certain. So: recency within audited, recency within internal, audited over internal - by code, disagreement listed; an older audited against a newer internal goes to a person with audited shown as the likely answer, until an associate or MD confirms.

## B-025 Industry and market context for the internal value review
status: proposed
2026-09-17-2 Q11: the MD wants to know what is happening in the subject company's industry and
market. Nothing in the blueprint gathers it. It is sourced research - every statement citing
where it came from - not arithmetic, and it borders on the report, which is out of scope today.
Needs a scope decision (BUILD/OPEN.md section 5, question 6) and the firm's approved sources
before any design. Size: unknown.

## B-026 An engagement view, and a way to find one client
status: built (2026-09-18, P63)
2026-09-17, from five reviews of the dashboards. Everything on Activity is indexed by run; an
analyst thinks in clients, and a repeat client has several runs behind one engagement. There
is no filter, no search and no grouping: finding Northgate among ten engagements is scrolling.
Needs: a filter on the runs panel (client, engagement, scope), rows collapsed by engagement
with the newest run on top, and an engagement line - valuation date, what has arrived, what is
open, last activity. `/api/runs?engagement_id=` already exists and no page uses it. Size:
medium.
Built: the runs panel folds by engagement (newest run on top at both levels) and carries a
find box over client, engagement, scope and run id - a redraw of what the browser already
has, not a second request. `Console.engagements()` folds the same rows the panel reads, so
the two cannot disagree, and `/api/engagements` exposes it. **Not built: the valuation
date** the item asked for - no such field exists (the profile's two `as_of` dates are
`size_band`'s and `fiscal_calendar`'s), and inventing one was refused. It is now question 7
in BUILD/OPEN.md section 5, and a test fails if a date appears without one.

## B-027 Documents: what has arrived and what the client still owes
status: proposed
2026-09-17. Historicals are the gate the whole job waits on, and nothing on any screen says
what is in and what is missing - the files panel is behind a button on Setup. Needs the
expected set per engagement type (B-009's coverage report), then a panel on the engagement and
a "draft the follow-up list" button. Size: medium, after B-009.

## B-028 Say "tie-out" in the analyst's sense, or stop saying it
status: proposed
2026-09-17. The scorecard's *tie-out* is footing: every stated total re-added from the rows it
cites. The analyst's *tie-out* is net income ties, the balance sheet balances, cash flow ending
cash equals balance sheet cash. A green tie-out pill will be read as the second. Needs:
`tools/statement_checks.py` (already built) surfaced as a named **Model checks** panel, and the
scorecard criterion renamed to **Totals re-add (footing)**. Blocked on B-004 so the checks run
on a real run. Size: small.

## B-029 Precedent, where it is used
status: proposed
2026-09-17. An answer given on one client is shown to the model on another in the same practice
group. The dispatcher records `precedent_ids` on every dispatch; the review item never carries
them, so a reviewer cannot see that a confident proposal is an echo of a precedent they set
themselves. Needs: the ids on the item's detail, shown under the reveal, and a line in the
modal saying the answer becomes precedent. Blocked on nothing but a decision about retiring a
precedent that turns out to be wrong (BUILD/OPEN.md §5b). Size: medium.

## B-030 A comparative statement, read as two columns
status: built (2026-09-20, P85) - the column is in the locator rather than more values in
the row, so `Row` keeps its shape and provenance, tie-out and the numeric lock are
untouched. A table of three columns writes p12/t1/c1..c3; a single-column table keeps the
locator it always had. The escalation is narrowed from every comparative document to the
tables whose columns nobody named, and it names them. Three rules came from the real
filing rather than from reasoning: the columns are the trailing figures and a label may
contain numbers of its own, the width is what most rows in a run agree on, and a header is
used only when every token could be one and at least one names a period - the filing has a
header split over six lines whose last line reads `2024 $ %`, which would otherwise have
labelled the 2025 column 2024.
2026-09-17. P53 stops a run on a document whose rows carry more than one figure, because the
reader takes the last column and a row store with one value per row cannot hold the other.
Stopping is right and it is not the answer: every audited statement is comparative, so the
honest reading is both columns. Needs: `ops.source_parse.Row` to carry the figures it found
rather than one, the document and docx readers to capture every trailing figure with the label
as what precedes the first, those columns aligned to the period ends `intake/readers/periods.py`
already detects, and the `columns:` escalation narrowed to the case where the counts disagree.
Touches the parse store's shape and every provenance locator that points into it. Size: large.

## B-031 Person and entity identifiers on the engagement
status: proposed
2026-09-17, from the security review. The masker is only ever told the client's company name
and the distinctive words of it, so an owner, officer, related party or lender is never masked;
the vault declares a `PERSON` kind that production has never issued. P53 closed the leak route
(a precedent that reads as naming a person is refused) but did not give the masker the names.
Needs: an optional `related_names` on the engagement profile - who they are and what they are to
the client - the admin form field beside it, and `workers/driver._identifiers` declaring them as
`PERSON`/`ENTITY` beside the client. The interview question that has to come first is which of
those names an analyst actually has to hand at the point the engagement is set up. Size: medium.

## B-032 The quarantine store has never held anything
status: proposed
2026-09-17, from the engine defect hunt. `RunStore.hold()` is called from one place, inside
`LoopController.exhaust`, which is reachable only from `RepairNeeded` - raised nowhere in
production. So a quarantined step writes no quarantine record and opens no review item, against
`constraints.yaml`'s rule that exhaustion always produces an artifact. Nobody is assigned and
nothing reaches the queue. Fixing the loops (BUILD/OPEN.md §4b) fixes this with them; recorded
separately because the missing artifact is what a person would notice first. Size: with B-loops.

## B-033 Version 1 is data collection, not model building
status: proposed
2026-09-18-1: the analyst redefined the goal. "Version 1 of this is not for you to run the
actual model - just to make it really easy for me to input stuff into the model." Both shipped
recipes end in gpc, cost-of-capital, dcf-build, model-load and qc-tieout, which is running the
model. Change: a pilot recipe whose steps stop at organised data, and whose release produces
the input-help workbook. Drops gpc, cost-of-capital, dcf-build and qc-tieout from version 1's
path; B-004, B-005, B-006 and B-021 fall down the order with them. Files:
recipes/*.yaml, BUILD/OPEN.md. Evidence: Q1a, Q2. Size: medium (a recipe version, so a person
re-registers it).

## B-034 The input-help workbook, as a registered template
status: proposed
2026-09-18-1 Q2: version 1 fills an "input help" workbook matching the model's input format
and never touches the real model; integration comes once that works extremely well. This is
not a new mechanism - templates/bindings.yaml, templates/inputs/*.yaml, tools/write_template.py
and the model-load skill already write into a copy of a pinned template by named range. Change:
register a second template at valuation/non-esop/_segment with an input schema for the tabs
that matter - Input, WS, Sales Detail, IS, BS, D (CF skipped, Q3) - and retarget model-load to
it. Also gives the delivery path something real to release, which it has never had. The exact
named ranges need the real model; until then the schema is an educated guess the analyst asked
for. Evidence: Q2, Q3. Size: medium.

## B-035 Local OCR for scanned PDFs
status: built (2026-09-18, P74) - the port, both adapters and the reader; the engine is installed by a person
2026-09-18-1 Q14-Q16: PDFs are the only path with keying in it, none of them can be copied
from, and clients send a lot of them - so most of the inbound path needs OCR. intake/readers/
documents.py reports a scanned page and does not read it, by design ("the OCR path is a later
adapter"). **It must be local and deterministic**: masking needs text, text from a scan needs
OCR, and OCR by a vision model would put unmasked client documents in front of a model before
masking could happen, breaking the guarantee at its root. Local keeps the order image -> text
-> mask -> model and keeps privacy/ deterministic Python. Needs: the engine decision and
confirmation it can be installed on the work machine (Q21, unconfirmed). Evidence: Q14, Q15,
Q16. Size: large, and it is the single highest-value build in this list.
Built 2026-09-18 (P74): an eighth port, `AA_OCR_ADAPTER`, with `none` (refuses, so a scan
stays reported rather than read as empty) and `tesseract`. The port returns lines, so
`_tables_from_lines` gives an OCR'd page the same locators a text layer would, and an
OCR'd line carries `ocr=True` and its confidence. Nothing on the path may reach a model
and an import walk proves it. `serve.py --check` probes the engine by trying it. **What
remains is on the work machine**: install Tesseract, `pypdfium2` and `pytesseract`, set
`AA_OCR_ADAPTER=tesseract`, and measure accuracy against a hand-keyed engagement (B-011) -
until that is done, how good the reading is on this firm's real scans is unknown.

## B-036 The prior-year rollforward, as the main path
status: part built (2026-09-18, P69) - the arithmetic half; the Excel half needs the real template
2026-09-18-1 Q4: 75% of engagements are repeat clients. Q3-Q10 describe one mechanism applied
four times - for a repeat client, everything starts from last year's version of itself: the
model, the WS grouping, the Input tab, the request list. Promotes B-023 from "large, later" to
the centre. Change: read last year's workbook by named range (the analyst points at its Box
location during set-up, Q5); carry every Input field across and roll only Valuation Date and
Latest Fiscal Year End forward a year (Q9); carry the WS line items as the schema rather than
tagging against the firm taxonomy (Q7); shift the year columns in a fixed ten-wide block with
the oldest dropping, filling five (Q10); raise a review item on anything that does not match,
distinguishing a client change from the firm's own prior grouping (Q6). Evidence: Q3-Q10.
Size: large.

## B-037 The acceptance rule: proved by arithmetic, or seen
status: built (2026-09-18, P67) - the rule is in the router; no producer sets its fields yet
2026-09-18-1 Q18-Q20. The analyst needs the data 100% accurate and would otherwise re-check
every figure against the client documents; a figure carrying its page and row, whose totals all
re-add and whose statements tie, is enough not to. Anything no arithmetic covers is shown -
every one, not only what changed. This answers BUILD/OPEN.md section 2's open auto-accept bar,
and answers it as a rule about evidence rather than a confidence number, which is the right
shape because a confidently wrong OCR read is what a probability cannot catch and a failed
footing can. Change: the confidence router accepts on tie-out coverage plus provenance, not on
a score; everything uncovered opens a review item. Files: ops/ (router), policy. Evidence: Q18,
Q19, Q20. Size: medium.

## B-038 The due diligence request list as the coverage schedule
status: part built (2026-09-18, P68) - sections, refs and coverage exist in
intake/request_list.py and nothing reaches them. The items inside a section are written per
engagement and the only list in hand belongs to a client, so there is nothing yet to carry.
2026-09-18-1 Q11-Q12: the firm sends a DD request list in seven stable sections (A Financial
Records, B Corporate Documents, C Operational Matters, D Employment/Labor, E Properties &
Equipment, F Contracts, G Legal Matters); the items inside vary per engagement and stay similar
year to year for a repeat client. The same workbook is the tracker - In Model? / notes /
Provided / Not Applicable - and supporting data gets a tab named after the item number. **Each
section is a folder in Box and in ShareFile**, so a document's section is known from its path
rather than from classifying it. Concretises B-009 and B-027: expected_types becomes two-level
(stable sections, per-engagement items), and the coverage report is this tracker. Evidence:
Q11, Q12. Size: medium.

## B-039 A client's Excel is carried across, not extracted
status: proposed
2026-09-18-1 Q14: when the client provides Excel the analyst moves the tab into the model and
links it up - it is already cheap, and a tool that re-types it adds nothing and adds risk. The
input-help workbook should carry the client's tab across the way the analyst does by hand.
A different operation from extraction, and safer. Evidence: Q14, and session 1's yellow-fill
convention. Size: small to medium.

## B-040 Nothing sets the acceptance rule's evidence yet
status: proposed
2026-09-18, found while building P67. `review.router.Item` now carries `extracted` and
`arithmetic_cover`, and the rule that reads them is tested and correct - but no procedure
sets either field, so today every item is still routed as a judgement on its confidence. This
is the same shape as P55's "built, and wired to nothing" and it is recorded rather than left
quiet. The producer is the extraction step that does not exist yet: it needs the OCR adapter
(B-035) to have read something, and `tools/statement_checks.py` to say which figures its
passing checks actually cover. That second half is the real work - a finding says a total
re-added, and turning that into "these seven line items are covered" is a mapping nobody has
written. Until both exist the rule is correct and inert. Size: medium, and it is the step that
makes B-037 real.

## B-041 The eval harness has never measured a provenance failure
status: built (2026-09-20, P86) - `provenance_of` is called by `kinds_of_wrong`, which runs
the real Provenance Gate over the real parse store on every figure `ebitda-normalization`
emits, and `fabricated_evidence <= 0` is a gate. Provenance was measured on
`line-item-tagging` by a hand-rolled check on whether a description had changed, and on the
skill whose every figure carries a locator not at all. P71's allowlist is empty as a result,
and its decay test is what refused the stale excuse.
2026-09-18, found by P71's scan for public functions nothing references.
`evals/metrics.py::provenance_of` says "Exposed for the harness" and is the only mention of
`ProvenanceGate` anywhere in `evals/` - so nothing in the eval or promotion path counts the
figures the provenance gate would fault. `evals/gates.yaml` decides promotion from what the
harness measures, which means a candidate skill can promote while faulting provenance: the
guard still stops the run, but the evidence that a skill does it often never reaches the
board. Left unwired and recorded rather than deleted, because deleting removes the only
trace of the intent, and wiring it changes what promotion measures - a decision about the
governance chain rather than a tidy-up. Allowlisted in `tests/p71` with this reason. Size:
small to wire, plus a decision about whether the rate becomes a gate.

## B-042 Which OCR engine reads this firm's scans better
status: proposed
2026-09-19, from P75 and P76. Two local engines are registered - tesseract, which needs an
executable on PATH, and rapidocr, which is a wheel with its models bundled and needs no
administrator. On the public filing in fixtures/public/, rapidocr read 98.5% of the figures
on the balance sheet page and 100% on the two statement pages after it, at about 0.99 mean
confidence; tesseract has not been measured at all, because it is not installed here. The
benchmark exists and takes the engine from configuration (`pytest tests/p76 --ocr`), so
measuring the other one is running it with AA_OCR_ADAPTER=tesseract.
**What neither number means yet.** Those pages were born digital and rendered to images:
no skew, no scanner noise, no photocopy generation loss. A client's scan has all three, so
this is an upper bound rather than a forecast, and the real number needs a hand-keyed
engagement (B-011) or at least a genuinely scanned document. Size: small - it is a
measurement, not a build.

## B-043 The unmask half of the privacy band reaches nothing
status: proposed
2026-09-20, from P82. `privacy/unmask.py` and `privacy/verify.py` are imported by no module
outside the `privacy/` package itself - production reaches neither. The masking half is
wired in six places (harness/dispatch, orchestrate/orchestrator, orchestrate/triage,
precedent/writeback, workers/driver, tools/serve), so every run masks and no run has ever
resolved a token back.
Three things say this is wrong rather than deliberate. The blueprint asserts every
deliverable is dominated by `unmask_verify` - `assert_every_figure_cleared_provenance_and_tieout`
fails if a skill can reach a deliverable without it. `guards/__init__.py` calls the unmask
integrity check "the sixth guard". And `deliver/builder.py` opens with "Inputs are unmasked,
tied-out, locked figures only", which is an assumption nothing upstream satisfies.
It has not bitten because no run has ever reached `release` (both shipped recipes end at
qc-tieout, B-004). When one does, `DeliverableQC` - which *is* wired - fails the workbook
for carrying a residual mask token, and the guard will be right.
**Why it is not just wired.** Where the unmask belongs is a design decision: on the release
path before QC, or on each step's output as it returns from the model. The second changes
what a reviewer sees and what precedent records; the first leaves tokens in the review queue.
The blueprint draws `unmask_engine` and `unmask_verify` between the model band and the
deliverable, which points at the first, but "points at" is not the same as decided. Files:
deliver/release.py or harness/dispatch.py, privacy/verify.py. Size: small to wire, plus the
decision.

## B-044 conflict_resolution can never be entered
status: proposed
2026-09-20, moved here from BUILD/OPEN.md section 4b so the allowlist has something to point
at. `conflict_resolution` is declared on monthly-refresh over `[tagging, ebitda]` and two
things stop it: `guards/reconcile.py` is called by nothing outside its own tests, and the
region spans two steps while the executor re-runs only the head. Neither was in P59's reach -
the first is a guard nobody calls, the second is executor machinery that does not exist.
Size: medium.

## B-045 Four commands nobody is told about
status: built (2026-09-20, P82) - all four are now under "Running it" in CLAUDE.md, which
both tells a person and makes the reachability scan see them, so none is allowlisted
2026-09-20, from P82. `tools/simulate_files.py`, `tools/bootstrap_scaffold.py`,
`tools/synthesize_templates.py` and `python -m evals` are commands rather than libraries, and
each one's invocation appears only in its own docstring. CLAUDE.md names the two rehearsals
under "Running it" and not these, so a person reading the file a session starts from cannot
find them - and the reachability scan cannot tell them from dead code without being told.
`tools/simulate_files.py` is the one that matters: it drops every document case through the
real server, which is the third rehearsal beside the two that found twenty-three bugs.
Change: name them in CLAUDE.md, which both tells a person and makes the scan see them. Files:
CLAUDE.md, tests/p82. Size: small.

## B-046 Two ways to render a diagnostic
status: proposed
2026-09-20, from P82. `registries/diagnostics.py` renders a diagnostic for a person to read
and nothing calls it; the codes it renders live in `registries/errors.py`, which is imported
everywhere. So every diagnostic a person actually sees - on the review page, in a toast, in
a refusal - is formatted somewhere else, and this is a second renderer that has never run.
Either the surfaces should use it or it should go; what is not defensible is two answers to
"how is a diagnostic written for a person" with one of them untested against real use.
Files: registries/diagnostics.py, ui/, admin/page.py. Size: small.

## B-047 Version 1's own recipe, ending at a workbook
status: proposed
2026-09-21-1 Q1. Supersedes the open half of B-033. All three shipped recipes end at
qc-tieout, which CLAUDE.md puts outside version 1, so no run can finish. Version 1's recipe
stops at organised data and releases the input-help workbook. B-033 could not be built
because nothing said what a run should produce; Q1 says: a separate workbook laid out like
the model, which he copies and pastes from, never the model itself. Files: recipes/, and a
person re-registers it at /admin because the plan hash moves. Size: medium.

## B-048 The input-help workbook, structure derived per engagement
status: proposed
2026-09-21-1 Q2, Q6. Replaces B-034 as specified. B-034 proposed registering one template
with an input schema; that is right for the Input tab and wrong for the rest. The workbook
has two kinds of tab: **Input**, fixed and identical every time, and **WS / IS / BS / Sales
Detail**, whose structure is read from last year's model for a repeat client and from a
built-in default for a new one. Which tab a kind of data belongs in is also per client -
the sales breakout is usually Sales Detail and is sometimes in WS. Layout may be a best
guess now and corrected later (Q1), because it is our workbook and not the firm's model.
Files: deliver/, templates/. Size: large.

## B-049 Read the structure out of last year's model
status: proposed
2026-09-21-1 Q2, Q5, Q6. For a repeat client the prior workbook is the specification: tab
names, row order, and which tab holds what. Tabs are *usually* named the same and the data
*usually* starts in the same place - but people put material in Sales Detail and add tabs
to support the income statement, so the tool looks in the expected place, verifies what it
found, and **reports tabs it did not recognise** rather than skipping them. Consumes
`prior_model` (P79), which was built for this and reaches nothing. Files:
intake/readers/workbook.py or a new reader, tools/rollforward.py. Size: medium.

## B-050 Line matching against last year, deterministic
status: proposed
2026-09-21-1 Q7, Q9. The test he actually applies, in three parts: wording close enough,
the amount not absurd, and **the same numbers appearing in last year's client documents**
to confirm the client categorised it the same. The third is evidence rather than
similarity, which makes the whole test deterministic - no model call, no embedding, no
confidence score, and no tolerance to set, because the amount **flags rather than vetoes**
and so only decides what a person is shown. Distinct from line-item-tagging, which tags
against the firm's chart of accounts; this asks whether a line is last year's line.
Files: a new procedure + tests. Size: medium.

## B-051 Where last year's documents are
status: proposed
2026-09-21-1 Q8. B-050's third check needs last year's source documents and nothing points
at them. They sit in a Box folder that can be pointed at, the same way `prior_model` points
at last year's workbook. A second pointer on the engagement, set at /admin, checked when it
is set rather than when a run needs it. P79 built this machinery for the first pointer.
Files: admin/console.py, admin/page.py, a config_document version. Size: small.

## B-052 The subtotals, as evidence and as a diagnosis
status: proposed
2026-09-21-1 Q3, Q4. Closes B-040's producer and gives B-028 its surface. The tool computes
the subtotals and shows them; he pastes only the hardcodes. Their purpose is to be looked
at - the balance sheet balancing, net income agreeing with what the client stated - and
that is what earns belief without going back to the PDF. When one does not match, the
workbook is **still delivered** and the tool finds and flags **why**: which year breaks
when the other ties, a difference equal to a row's value pointing at a row dropped or
counted twice, a difference divisible by nine being the transposed digits OCR produces.
Files: tools/statement_checks.py, deliver/, review/router.py. Size: medium.

## B-053 The dashboard's buttons
status: partial - four of five built 2026-09-21 (P88, P90, P92)
2026-09-21-1 update. Version 1 is a thing he drives, not a thing that watches. The
surfaces, revised after the second half of the session: **Set up model**, **Test the
ShareFile/Box connection**, **Update** (pull ShareFile to Box), and **one button per
appendix** rather than a single set-up-report button - C, E, F, G, H, I - because each
appendix's source data becomes ready at its own moment. The automatic sweep already exists
and stays; this is the surface that makes it his. Files: admin/page.py, ops/console/.
Size: small per button, once the thing behind each exists.

## B-054 Update the DD request list tracker
status: built 2026-09-21 (P94, P95) - against a starting list, not the firm's own
2026-09-21-1 update. New in version 1: "it just reads what we asked for and what we
received, and updates it whenever we get info from the client", with the tracker pointed at
from the dashboard. B-038 arriving from the other end - P68 built the sections, refs and
coverage and reaches nothing, because the item lists are per engagement and the only one in
hand belonged to a client. The tracker **is** the list: the request workbook is also the
tracker, each item carrying In Model?, notes, Provided and Not Applicable (2026-09-18-1).
**A list has to be creatable, not only loadable.** P68 said the items "are loaded per
engagement rather than invented here", on the reasoning that the only real list in hand
belongs to a client. That is still true of *that* list - but it left the machinery with no
way to start. He has since said he will be testing with documents and **no request list at
all**, which is also the state of any new engagement before somebody writes one. So there
has to be a default list for the focus division: generic enough to owe nothing to a
client's, explicit that it is a starting point, and correctable.
Files: intake/request_list.py, a default list as data, a writer, admin/page.py.
Size: medium.

## B-055 A Box adapter, and a connection that can be tested
status: built 2026-09-21 (P87, P88) - not yet proved against a real tenant, which is P93
2026-09-21-1 update, from ClbSmt/box.sharefile.automation. Box authenticates with client
credentials **plus user impersonation** - `box_subject_type=user`, `box_subject_id`, and
the app needs "Generate User Access Tokens" enabled. The storage port exists and its Box
adapter is a registered contract that refuses rather than a working client. The test button
is the honest first build: it proves credentials and folder access without moving anything,
and cannot be tested here - only on the work machine. Files: ports/storage/box.py,
admin/page.py. Size: medium.

## B-056 ShareFile, and the relay that backs up Power Automate
status: built 2026-09-21 (P89, P90) - not yet proved against a real account, which is P93
**Settled: both a test and a transfer.** "There should be a test button for sharefile/box.
Then an update button, to pull things from sharefile to box... I'm going to keep working on
the power automate tool that does that automatically... But want this as a backup if that
doesn't work." This does not reverse the fourth session: Power Automate still does the
transfer and still sits outside the boundary, and a button a person presses when it has not
run is a different object from a pipeline stage.
**The hazard is two copiers, not a failed copy.** So the relay converges rather than
competing: copy and never move, skip on identical content hash, surface a re-send rather
than overwriting it, name what it did per file, and report partial failure rather than
retrying into silence. Pressing it after Power Automate already ran is a no-op that says so.
**Auth.** An MFA account cannot use a password grant, so ShareFile needs an interactive
authorization-code login once and a rotating refresh token after. The token is held through
the Secrets Port, never in knowledge/ and never committed. "Never authenticated", "token
expired" and "connected" are three different answers.
**Not through the Delivery Port** - its contract is two inbound edges, released artifacts
and the run manifest, and no reading of client folders. The relay gets its own surface.
Files: ports/storage/sharefile.py, a new relay module, admin/page.py. Size: large.

## B-057 Setting up the report, one appendix at a time
status: partial - the mechanism built 2026-09-21 (P91, P92); the real report's anchors and
each appendix's source location are still owed from the work machine
"Copying and pasting the report from last year, then only setting it up. Meaning getting
the right appendix information in." Named: C economic conditions, E major market indices,
F M&A markets, G assumptions & limiting conditions, H certification, I qualifications of
Chartwell & Staff.
**A button each, not one update-report button** - "when the industry data is ready, I will
press the industry update button... and like when the economic appendix is done and ready,
I will click that button" - because each appendix's data becomes ready at its own moment.
**Three buttons, not six.** G, H and I "can stay the same as the prior years" and arrive in
the copy of last year's report, so no code touches them - which is also why nothing in this
system can write the certification. C, E and F are what change.
**He points each one at a Word document**, so the source is a setting rather than something
the tool discovers. An appendix is an id, a source .docx and an anchor: **data, not code**,
because the real report has not been seen here and the first one will not match a guess.
**The move is Word-to-Word, not text.** Styles, numbering definitions and embedded image and
chart parts travel with the content, and whatever could not be carried is named rather than
dropped - paragraphs alone give a document that opens cleanly and is laid out wrong.
**Binding** follows the model's rule - a bookmark or heading name, never a paragraph index,
so a report somebody added a sentence to cannot get F written into E. A missing anchor is a
refusal naming it.
**Boundary.** Appendix H is the certification. The system may place it and carry its text
forward; it may never produce the conclusion it attests to, or sign it. The appraiser signs,
outside this system.
Still owed from the work machine: where each source document lives, the real report
template, and whether a source .docx is the appendix whole or contains it as a region. Answers OPEN.md section 5 question 6 in part - report **setup** is
in scope; drafting the valuation narrative is not what was asked for.
Files: a report/ package, templates/, admin/page.py. Size: large.

## B-058 The whole orchestrate package reaches nothing
status: proposed
2026-09-21, from P91 - found by sharpening the P82 scan, not by reading. `orchestrate/`
is imported by no production module at all. Every import of it in the tree is either
`orchestrate/__init__.py` importing its own submodules or a test under `tests/p26`.
P26 built the Orchestrator agent, the run planner and triage; nothing a person or a run
can do reaches any of it.
**Why the scan did not say so before.** It counted a package's own `__init__.py` as
evidence that its submodules were reached. `orchestrate/__init__.py` imports
`orchestrator`, `plan` and `triage`, so all three read as wired while the package they are
in was reached by nobody. P91 changed that to a fixpoint - an `__init__`'s imports count
only once the package itself is reached - and this is one of four things it found
immediately.
**It also contradicts a claim in B-043**, which lists `orchestrate/orchestrator` and
`orchestrate/triage` among the six places masking is wired. Two of those six are in code
no run reaches, so masking is wired in four places rather than six.
Not wired here: whether the orchestrator belongs on version 1's path is a design decision,
and version 1 is a person pressing buttons rather than an agent deciding what to do.
Size: unknown until that is decided.

## B-059 The workpaper narrative reaches nothing
status: proposed
2026-09-21, from P91. `deliver/workpaper.py` is imported only by `deliver/__init__.py`.
Production imports `deliver.registry` directly and never the package, so `WorkpaperNarrative`
is reached by no run. It writes the narrative that explains a deliverable - which matters
on the day a run reaches release, and no run has (B-004: both shipped recipes end at
qc-tieout). Version 1 ends at a workbook rather than a deliverable, so this stays recorded
rather than wired. Size: small once release is on a path.

## B-060 The governance chain reaches nothing
status: proposed
2026-09-21, from P91. `governance/chain.py` is imported only by `governance/__init__.py`.
Production reaches `governance.board`, `governance.record` and `governance.conformance`
directly - `admin/console.py` and `registries/methodology.py` - and never `GovernanceChain`
itself, which is the thing that walks a candidate skill from proposal through sandbox to
registration. So the chain exists and every step of it is invoked by hand instead.
Whether that matters depends on whether a skill is ever promoted without a person walking
it, which is a question for the practice rather than for a scan. Size: medium.

## B-061 OCR drops spaces, and the masker matches on substrings
status: proposed
2026-09-21, from the first real client folder. The two scanned PDFs in it read at about
0.97 mean confidence and every figure was legible - and the words ran together:
`BOARDMEETINGMINUTES`, `ThefollowingcontainstheBoardmcetingminutes`. Not every space, which
is worse than all of them: the loss is unpredictable, so nothing downstream can assume
either spacing.
**Why it matters beyond looking untidy.** `privacy/mask.py` locates a declared identifier
with `re.compile(re.escape(ident.value), re.IGNORECASE)` - a plain substring. A declared
name `John Smith` matches `Present: John Smith (President).` and does not match
`Present:JohnSmith(President).` Shown, not assumed:

    re.compile(re.escape('John Smith'), re.I).search('Present:JohnSmith(President).')  -> None

So a name OCR has run into its neighbour is not masked. The Outbound Payload Scan does not
catch it either: the module docstring says the masker and the scan agree "by construction",
and what they agree on here is the blind spot.
**What it is not.** Not a breach. CLAUDE.md records that masking is not a security boundary
- the firm's Claude account is sanctioned for client data - so the cost is cross-client
isolation and precedent portability: a precedent carrying an unmasked name cannot be reused
on another engagement. That is the whole reason masking exists, so the cost is the point of
the feature rather than a side effect of it.
**Two candidate fixes, and they are not alternatives.** Whitespace-insensitive matching in
the masker and the scan is the one that holds whatever the engine does, and it is the one to
build. Getting spaces out of the engine is worth trying too (rapidocr exposes a
`use_space_char`-style option in some builds) but it fixes one adapter and leaves Tesseract
and the next engine to be checked separately.
Files: privacy/mask.py, privacy/payload_scan.py, ports/ocr/rapidocr.py. Size: medium.

## B-062 A fiscal year end nobody stated, and periods that are bare years
status: proposed
2026-09-21, from the first real client folder. Two gaps in `intake/readers/periods.py`,
both found on real workbooks and both on version 1's own path.
**The fiscal year end.** The balance-sheet workbook's sheets are named `2019-12-31`
through `2023-12-31` plus two February interims. The detector found all seven period ends
correctly and then reported `fiscal_year_end: not stated`. Five period ends on 31 December
is not an assumption about the fiscal year end, it is a derivation from evidence already
in hand - the same standard as "a figure is proved by arithmetic, or it is seen". Reporting
it as unknown when the file says it seven times sends a person to type in what is already
on the screen.
**Bare year columns.** The projections tab's periods are `2021 | 2022 | 2023 | 2024 Feb YTD
| 2024 (P)` as header cells, and the detector found no periods at all. That is how most
forecast tabs are laid out, and a forecast with no periods cannot be placed in a model.
Care is owed on both: the point of this module is an explicit `ambiguous` flag rather than
an assumption, so a derived fiscal year end must carry what it was derived from, and
`2024 (P)` must stay distinguishable from `2024` - reading a projected year as a historical
one is exactly what P38 exists to prevent.
Files: intake/readers/periods.py. Size: medium.

## B-063 One document can satisfy two request items and only one is true
status: proposed
2026-09-21, from the first real client folder, and downgraded on inspection - which is why
it is recorded rather than fixed.
The tracker matches by kind, so a `financial_statements` file marks every item whose
`answered_by` names that class. On the real folder the same two workbooks marked both A.1
(five fiscal years) and A.2 (interim, current year to date and the same period last year).
That looked wrong. It is not: the workbooks' sheets are `2023-02-28`, `2024-02-29` and five
December year ends, so they genuinely answer both.
**What remains.** The tool could not have known that, and marked both by the kind alone. A
folder where the interims had not been sent would have read identically. The fix is not
better matching but a reason: an item satisfied by kind alone, where the same file also
satisfies a sibling item, is worth showing a person. The Evidence column already names the
file, so what is missing is the prompt to look rather than the information.
Size: small.

## B-064 The footing reader exists; nothing extracts a figure for it to cover
status: proposed
2026-09-22, from P99. `intake/readers/footing.py` now finds, for every total in a parsed
block, the contiguous run of rows that re-adds to it - on the first real client's
statements, 280 of 280 totals re-add and four fifths of the 2,383 parsed rows sit under
one. It reaches `ReadReport.footing`, the `intake.read` event and the run record, so a
statement that does not add up is visible the day it arrives, which is useful on its own.
**What it does not yet do is close B-040.** That backlog item is about
`review/router.py`'s acceptance rule, which reads `extracted` and `arithmetic_cover` on a
*review item* - and a review item is made from an extracted figure. Nothing extracts
figures yet; that is the version-1 spine (B-047 through B-052). So the producer's evidence
now exists and has nowhere to be carried to, which is the honest state and is why B-040
stays open rather than being ticked off here.
What is left is a mapping: when a figure is extracted from row *n* of block *b*, its
`arithmetic_cover` is every footing in `b` whose ordinals include *n*. That is a few lines
once figures exist, and writing it before they do would be a join to nothing.
Files: the figure extractor, when there is one. Size: small, and blocked.

## B-065 Two rehearsals cannot run at once
status: proposed
2026-09-22, found by running them in parallel by mistake. `tools/simulate_firm.py` uses a
fixed home at `runs/_rehearsal`, so a second copy dies on the first one's SQLite file with
`PermissionError: [WinError 32]` and its teardown leaves the directory behind. The findings
it prints in that state are artifacts - a run that never started reads as a seam that
failed - which cost a diagnosis before the cause was obvious.
Not urgent: nobody runs two deliberately. Worth a line because the failure *looks* like a
build defect, and the next person to trip it should find this instead of investigating one.
The fix is a home per process (a pid or a mkdtemp suffix), or a lock that refuses the
second run with a sentence saying why. Files: tools/simulate_firm.py. Size: small.

## B-066 Roll-call tests: six that report an addition as a defect
status: proposed
2026-09-22, from P101. Adding one recipe turned six green tests red, in six files, none of
which was about recipes:

* `tests/p06/test_recipes.py` - the exact tuple of recipe names, in a test still called
  `test_both_recipes_load` after the third arrived;
* `tests/p33/test_registered_recipes.py` - the same tuple, sorted;
* `tests/p01/test_structure.py` - `sorted(ids)` over phase ids, and `phase <= still_open[0]`
  (that pair is P100's string-ordering defect rather than this one, and it is the same
  shape: a fact about today asserted as a rule);
* `tests/regression/test_surfaces.py` - `set(recorded["recipes"]) == {...}`, in a test whose
  own docstring says its purpose is a **floor** and whose every other line is `>=`;
* `tests/regression/test_serve.py` - `model_bindings: 4`, which never checked the thing it
  cared about (that anything was seeded at all);
* `tests/checkpoints/c12` - the exact set of registered workflow names, in a test about the
  *shape* of each row.

**Why it is worth a backlog entry rather than six fixes.** Each one is a fact about the
configuration on the day it was written, asserted as though it were a rule. The failure is
not that they broke - it is what breaking teaches: every one of them trains whoever hits it
to update a number without reading why, and the sixth time that happens nobody looks. A
test that fails on growth is a test people learn to silence.

All six are now floors or properties: the things that shipped first must still be there,
the shape of each row is asserted over whatever is there, and counts are derived from the
file they are counted from. Nothing was deleted.

**Two more, found by C63 rather than by a person.** `tests/p80` asserted the literal words
*"Seven steps, in order."* and P107 added two steps and wrote *"Nine"*. `tests/p101` asserted
that the release step's `needs` was exactly `["model"]`, and P111 found the handler also asks
for `timing`. Both were green alone; neither is named in any later phase's check list, so
only a checkpoint that re-runs everything could see them disagree. That is worth knowing on
its own: **the checkpoint is the instrument for this defect class**, because a roll-call test
by definition does not fail until something else changes, and nothing else re-runs it.

Both are now relationships rather than values. `p80` counts the checklist's entries and looks
the word up; `p101` asserts that release depends on a mapping, which is the thing P101 cared
about, rather than the list that happened to express it that day.

**What is left.** No check stops a ninth being written. A lint for `== {` against a registry
listing would be noisy and would miss `sorted(...) ==`; what would actually work is a
convention - **assert the relationship, never the inventory; if a number appears in a test,
derive it from the thing it counts** - written where somebody adding a test would read it.
That belongs in the testing notes rather than in a scan, which is why this is recorded rather
than built.
Files: the six above are done. Size: small, and it is a documentation change.

## B-067 `full-ddr-intake` has a release step it can never run

Found by the P111 scan, which compares what each step is handed against what its handler
asks for. The release handler asks for the output of `model` - the mapping the writer
resolves every `figure_ref` against - and `full-ddr-intake` has no `model` step. Its graph
is intake, mask, ddr, timing, tagging, qc, release. There is no `needs` list that fixes
this, because there is nothing to name.

The other two older recipes had the same defect and could be fixed by editing a line; both
were, in P111. This one cannot be, and the reason is worth keeping: the question is not
which step to add but what this recipe's ending is supposed to be. It tags a DDR response
against a request schedule. Whether that should end by writing a workbook at all, or by
producing a tagged schedule and stopping, is a decision about what the recipe is for.

It has never bitten anyone, because the recipe ends at a `qc-tieout` that has no procedure,
so a run quarantines one step earlier. That is also why nothing found it for ninety phases.

The scan carries it as a named exception with this id attached, so it stays visible rather
than being silently tolerated.

Files: `recipes/full-ddr-intake.yaml`, and the `KNOWN` set in
`tests/p111/test_what_a_step_asks_for.py`. Size: small to edit, and the decision is the
whole of it - it is Caleb's, not the code's.

## B-069 The deliverable dates nothing

Found by a valuation review of the delivered workbook. The Input sheet carries two stamps -
`Template version` and `Run id` - and then forty-three rows labelled `Revenue (FY1)` through
`Other operating expense (FY3)`. There is no valuation date, no fiscal year end, and no
period end dates anywhere on the file.

CLAUDE.md records the analyst saying that the two Input fields which change year to year are
the **valuation date** and the **latest fiscal year end**. Neither exists on the deliverable.
Forty-three figures labelled FY1/FY2/FY3 with no years is not a working paper: a reviewer
cannot tell whether FY1 is 2019 or 2023, and neither can the analyst six months later.

Half of this is cheap and half is not. The **period ends** are known - timing normalization
settles them and P110 put the fiscal calendar in front of it - so they can be written as
stamps beside the values, the way P115 wrote the Source column. The **valuation date** is not
known: nothing asks for it (B-071), and it is the field everything else hangs off.

Files: `tools/synthesize_templates.py`, `templates/inputs/Chartwell_Input_Help_v1@1.0.yaml`,
`deliver/builder.py`. Size: small for the period ends once B-071 lands; the valuation date is
a schema change and a conversation.

## B-070 The input tab cannot be tied back to the client's own statements

Fourteen income-statement lines over three years, stopping at operating expenses. The real
client's income statement also has Interest Expense, Interest Income, Other Income, Property
Taxes, Loss on Obsolete Inventory, State Income Tax - Current, and a line called
**"Depreciation & Amortization"** where the template offers only "Depreciation".

Three consequences, in order of severity:

1. **Nothing foots.** The workbook cannot be reconciled to the client's stated net income, so
   nothing proves the read was right - which is the premise the whole build rests on ("a
   figure is proved by arithmetic, or it is seen").
2. **No EBITDA can be built from it**, because interest, taxes and amortization are absent.
3. **No entity tax status is visible**, and S-corp versus C-corp is the first thing an IRS
   reviewer asks about a private-company valuation. (This client looks like an S corp: state
   tax only, $1,000 common stock, $148K APIC.)

Separately, **no balance-sheet inputs at all**. Seven balance sheets arrived; the taxonomy
carries 21 balance-sheet categories with `excluded_from_al` and `include_in_nwc` flags and
written rules for both; the workbook has none of them. Without cash, interest-bearing debt,
AR, inventory and AP there is no net working capital and no equity bridge, and the flags an
analyst reviews are decoration.

The taxonomy already defines every missing income-statement category - `interest_expense`,
`interest_income`, `income_tax`, `amortization`, `gain_loss_on_disposal`,
`other_income_expense`, plus `contra_revenue`, `employee_benefits`, `advertising_marketing`,
`vehicle_expense`, `bad_debt`. Eleven categories with no destination in the deliverable. The
problem is the template, not the chart of accounts.

Also worth knowing: the client's largest unnamed operating line is Freight, ~4.5% of revenue,
which falls into the "Other operating expense" plug along with credit-card fees, health
insurance and the 401(k) match. On one interim stub roughly 69% of administrative expense
lands in that plug. That is not a normalized spread.

**Waits on the real `Model Template - MASTER 2026`**, whose Input tab is what this workbook is
supposed to mirror. Guessing at the shape now would be building the wrong thing carefully.
Files: `templates/inputs/`, `tools/synthesize_templates.py`. Size: medium, and it is the
decision about scope rather than the edit that is large.

## B-071 The engagement profile asks none of the questions that make a valuation defensible

`engagement_profile@1.1.0` requires practice, segment, disposition, NAICS, size band, fiscal
calendar, scale convention, arrival scale and an owner-compensation benchmark. It does not
ask for:

* **valuation date** - already held as OPEN.md section 5 Q7, and the real client folder
  answers it ("as of the Valuation Date in March 2024"), a date that is neither a fiscal year
  end nor an interim end. Everything depends on it: which periods are relevant, what LTM
  means, what the workbook is *as of*.
* **standard of value** (fair market value / fair value / investment value) and **premise**
  (going concern / liquidation)
* **purpose** (gift, estate, buy-sell, 409A, litigation), which is what drives the standard
* **level of value** (control / marketable minority / non-marketable minority)
* **subject interest and share count** - the client's stockholder list shows 400 + 100 + 500
  = 1,000 shares, tying to Common Stock $1,000
* **entity tax status** (S / C / LLC)

`interview/topics.yaml` shows the project knows all of these exist; none reached a schema.
These are the fields a repeat-client roll-forward would carry forward, and the first six
questions on any reviewer's checklist.

**This is Caleb's, not the code's.** The schema change is an hour; deciding which of these
version 1 asks for is the conversation. Files: `contracts/engagement_profile@1.2.0.schema.json`
(a new version), `admin/console.py` skeleton, `admin/page.py` labels.

## B-072 The tagging step's output reaches nothing

`recipes/valuation-input-prep.yaml` declares the `model` step `needs: [timing, tagging]`, and
`harness/inputs.py` builds model-load's inputs from `timing` and the profile only.
`catalogue_from` never takes the tagging output and `workers/driver.py` references `tagging`
nowhere.

So the taxonomy category the analyst has just reviewed and approved does not decide which
template line a figure lands on. Model-load re-decides from the raw label and is free to
disagree with the person who just answered the question.

This is rule 7 ("built and wired to nothing") in domain terms, sitting in version 1's only
runnable recipe - and it is the thing that would make P119's unchecked half checkable: if a
template input declared a taxonomy category, the tagged category of a bound figure could be
compared with it, and a figure in the wrong *line* would be refused the way a figure from the
wrong *year* now is.

Files: `harness/inputs.py`, `harness/procedures/model_load.py`,
`templates/inputs/Chartwell_Input_Help_v1@1.0.yaml`. Size: medium. Highest-value item on this
list once the real template arrives.

## B-073 Three fiscal-year slots against five years of data, and nobody chose which three

The request list asks for five fiscal years. Both client workbooks carry five December year
ends. The overview lists FY2019-FY2023. The template offers FY1/FY2/FY3 and
`workers/driver.py` hard-codes `periods=("FY1", "FY2", "FY3")`.

*Which* three of five is a judgement - and in a window containing the 2020 and 2021 PPP and
ERC years it is the judgement of the engagement. It is currently made by the shape of a
template, with no review item attached and nothing recording what was chosen or why.

Files: `workers/driver.py`, `harness/procedures/model_load.py` (`period_slots`). Size: small
to surface as a review item, and the answer belongs to a person.

## B-074 One officer-comp benchmark, two officers, three years

`owner_compensation_baseline` is a single amount with a single `as_of`.
`ebitda_normalization` sums *all* officer lines for a period and compares the total to that
one number. The client's `Employee Count` workbook says **"Officers | 2"**. A benchmark set
for one role, tested against two officers' combined pay, reads "above" every period - and the
same 2024-dated survey figure is tested against FY2021 and FY2022 compensation.

It produces a note rather than an adjustment, which saves it. It is a note that will be wrong
every time.

Related: the add-back schedule's `amount` for an officer-comp candidate is the **full**
officer compensation, not the excess over the benchmark. Nothing sums it today, and that is
exactly how a schedule gets double-counted by whoever reads it next.

Files: `contracts/engagement_profile`, `harness/procedures/ebitda_normalization.py`. Outside
version 1's recipe, so not urgent. Size: small.

## B-075 The statement hint reads sheet names, and this client names sheets by date

`line_item_tagging` derives income-statement-versus-balance-sheet from the sheet name inside
the locator. This client's workbooks name their sheets by date - `'2023-02-28'`,
`'2019-12-31'` - and the statement is in the *filename*, which the function never looks at.
So the hint that drives `excluded_from_al` and `include_in_nwc` returns `None` for every line
of the real folder.

Files: `harness/procedures/line_item_tagging.py`. Size: small - the filename is already on
`SourceFile` and already reaches the payload.

## B-076 A figure read and not placed is named, and shown to nobody

`model_load.apply` builds `unrouted_upstream_figures` - the model's own named misses plus
every catalogue ref it silently omitted - and writes it into the step output. The contract
requires it and the skill is instructed to fill it. Nothing reads it: `review_items()` raises
items for `unmapped_template_inputs` only, the builder reads `unmapped_template_inputs` only,
and no console panel, workbook cell, event payload or manifest field mentions it.

It is the exact mirror of a seam that *was* joined. An input with no figure gets a review item
and a `not found` cell (P112, P115). A figure with no input gets nothing - and version 1's
whole stated purpose is gathering data and putting it in one format, so the list of data that
was gathered and then dropped is close to the most load-bearing output of the run.

Files: `harness/procedures/model_load.py`, `ops/console/`. Size: small.

## B-077 Two stale excuses: the unmask step, and what B-043 is waiting on

`recipes/valuation-input-prep.yaml` labels the release step `Unmask, verify, write the
workbook`. `guards/__init__.py` calls the unmask integrity check "the sixth guard".
`deliver/builder.py` opens "Inputs are unmasked, tied-out, locked figures only". The driver's
`_release` does neither: it imports `deliver.builder` and `deliver.release` and never
`privacy.unmask` or `privacy.verify`, and no production module imports either.

That is parked as B-043 - but **on a premise that is now false.** B-043 and the allowlist
entry in `tests/p82` both say it has not bitten because no run has reached release. P101
shipped `valuation-input-prep`, which ends at `release`, and P111-P115 made runs reach it.
`deliver.workpaper`'s allowlist entry carries the identical stale sentence.

The allowlist's own decay test checks that the module is still unreachable and the backlog
item still open. It does not check whether the *reason* is still true, which is the thing that
went stale.

Files: `knowledge/backlog.md` (B-043, B-059), `tests/p82`, `BUILD/OPEN.md`. Size: the decision
is Caleb's (OPEN.md, "Where the unmask belongs"); recording that the premise changed is five
minutes and should happen first.

## B-078 Five configuration fields that nothing reads

Each is settable, persisted, and consumed by no production code:

* **`scale_convention`** - *required* in the profile, on the admin form with its own
  pick-list, labelled "Our working papers are kept in". Four hits in the tree, all writes.
  It sits next to `statements_arrive_in`, which does work, and P109 went to some trouble to
  explain that they are different questions. One of them does something.
* **`review_level`** (standard / elevated) - settable, monotone-enforced with an explicit
  refusal to lower it, persisted on the roster and in every config document version. What
  actually governs review is `CheckpointPolicy`, built from the profile's `checkpoint_policy`,
  which never looks at the roster. CLAUDE.md's non-negotiable is "an admin may raise a review
  requirement, never lower one" - the refusal-to-lower is implemented and the raise does
  nothing.
* **`lock_timeout_hours`** - required in all four config document versions, parsed into
  `IntakeTiming`, never passed: both `EngagementLock` construction sites take the default.
* **`versions.prompt_version`** on the run manifest - never written and never read, on the
  artefact whose whole job is reproducibility.
* **`industry_classification`** and **`size_band`** - required profile fields read only by
  `gpc-scrub` and `cost-of-capital`, both skeletons outside version 1. The reason is
  defensible; what is missing is anything *saying* so, while an analyst is made to fill both
  in before a run he can finish.

Size: each is small on its own. The value is in deciding, per field, whether to join it or to
say out loud that it is parked - an unread required field is a question asked for nothing.

## B-079 No aggregate spend ceiling, and runs launch themselves

`constraints.yaml`'s `per_run.usd_max` ($40) is the only hard money ceiling, and
`sweep_forever` polls the watched folders on a timer and submits whatever the sweep released -
no human presses a button per run. Total exposure is therefore $40 x (number of engagement
folders that receive files), with nothing that stops at a total.

The scenario is not exotic: a year of archived client folders syncs down overnight from
OneDrive or ShareFile, the sweep releases a run per engagement, each is individually within
its ceiling, and by morning there is a four-figure invoice with no ceiling crossed and no
review item opened.

P118 made the per-engagement budget honest and put it on the checklist, which is the mitigation
a person can apply today. What does not exist is a firm-wide or daily cap.

Related and smaller: `per_step.usd_max` ($6.00) is declared in `constraints.yaml` and read by
nothing - `harness/budget.py`'s `CEILINGS` covers `per_run` alone. And `harness/dispatch.py`
passes a literal `estimated_cost_usd=0.05` to the door regardless of context size, so the
pre-call check is decorative and the ceiling is enforced after the call that crossed it. The
overshoot is one call, so `$40` means "$40 plus one call".

Files: `constraints/constraints.yaml`, `harness/budget.py`, `tools/serve.py`. Size: medium,
and the number is a firm decision.

## B-080 The cross-client precedent check misses a bare two-word name

`precedent/writeback.py` masks, re-scans, and then runs `looks_like_a_person` as a second
check because the store is read across clients. `privacy/people.py` fires on an initial plus
surname, an honorific, or a role word adjacent to a name.

A rationale reading *"Legal settlement - Sarah Weller"* or *"Rent paid to Kline Holdings LLC"*
has no role word, is not the client's own name, masks to itself, clears the scan, clears the
person check, and is written into a store that filters by practice and skill but **not by
client**. The next engagement in valuation/non-ESOP gets that name in its model context.

The module documents itself as deliberately conservative and the cost of a miss is one carried
name rather than a batch. With real client folders arriving it becomes live for the first
time, and `precedent.writeback.refused` is the event to watch.

Files: `privacy/people.py`, `precedent/writeback.py`. Size: small to widen; the judgement is
where to stop, since every widening costs a real precedent that should have been kept.

## B-081 The DD tracker writes into the repo and silently loses the analyst's notes
status: built 2026-10-02, P128
Fixed, and found exactly the way the item said it would not be. The last line of this
entry was *"no test covers it: every test passes an explicit path, and the default-path
shape - the only shape the UI uses - is untested"*. `aa owed --write` was the first caller
to use the default, and the first run of its test left a `Clients/A Non-ESOP Client/2026/`
tree in the git working copy. The path is joined to `_local_root` now, the way
`engagement_files` already joined it, and where storage is not a folder on this machine it
refuses rather than returning a relative path that will land somewhere.

Two tests in `tests/p128`, and the second is the one that matters: the loud half is that
the tracker lands beside the documents, and the silent half is that something a person
typed into it survives a refresh - which the promise claimed and was keeping against the
wrong file. Both fail when the join is taken out.

The refusals are also ordered now. "This division has no request list" is about the
engagement and "there is nowhere to put a workbook" is about the machine; asked the other
way round, an engagement in a division nobody has written a list for was told about the
storage port, which is a true statement and the wrong answer.


`admin/console.py`'s `_tracker_beside(relative)` returns `Path(relative) / "DD request
list.xlsx"` where `relative` is inbox-relative, and it is never joined to the storage root.
`write_tracker` then creates the parent, so pressing **Update** silently writes
`<repo>/Clients/<client name>/<folder>/DD request list.xlsx` - a client-named directory tree
inside the git working copy - while the files themselves are under `inbox/Clients/...`.

Two consequences: the analyst never finds the file, and `read_tracker` reads the same wrong
path, so the module's stated rule - *"a re-run preserves everything a person wrote"* - fails
silently. `In Model?`, `Notes` and `Not Applicable` are never carried across.

No test covers it: every test passes an explicit path, and the default-path shape - the only
shape the UI uses - is untested.

Files: `admin/console.py` (join to `_local_root` as `engagement_files` already does),
`intake/tracker.py`. Size: small, and it is a real data-loss bug on a button a person will
press.

## B-082 Seven tests that check a word, and the shared helpers that replace them

P120 rewrote five of them and added `tests/importing.py` (walk the tree, never the text),
`tests/reading.py` (ask the code, not the comments) and `tests/counting.py` (derive a number
from the thing it counts). What is left from the audit:

* `tests/p105` asserts `"round(" not in source` for a whole-module claim; partly covered by
  the behavioural round-trip beside it, so it is a redundant grep rather than a hole.
* `tests/p19` asserts a regex against `precedent/store.py` that `if row.practice not in
  (practice,)` evades. Worth knowing about the shape it guards: `stmt = stmt.where(...)`
  returns a *new* statement, so dropping the `stmt = ` prefix on one line silently removes the
  **skill** filter while leaving every string the test looks for intact.
* `tests/p106` asserts both settlement calls appear in `_facts`, which has no behavioural test
  at all. Both return new tuples, so a refactor that discards one return value keeps both
  substrings and loses the settlement.
* `tests/p11` and `tests/p05` each assert `len(...) == 13` over the skills - the B-066 shape,
  aimed at the one thing `/improve-agent` exists to grow.
* Three exact port inventories in `tests/checkpoints/c43` and `c54`, which is the worst place
  for a roll-call: it only fails when something else changes, and the checkpoint is the one
  thing that re-runs everything.

Size: small each. The helpers exist now, so these are mechanical.

## B-083 The catalogue's repeated keys, and whether a table reads as well as rows

P124 took the whitespace out of every payload - 13% of a real-sized model-load context,
for no change to what the model is asked. The larger half of the same saving is still
there and is **not** free: on eleven hundred catalogue rows, the key names alone
(`figure_ref`, `source_output`, `description`, `period`, written out once per row) are
56 KB, and one repeated value - `"timing.normalized_historicals"` on every row - is
another 31 KB. Together that is a third of the payload carrying no information.

Sending it as a header plus rows (`{"columns": [...], "rows": [[...], ...]}`), or hoisting
the constant `source_output` to the top, would recover most of it. What stops it being a
serialization change is that **it changes the shape the model has to understand**, and
this build has exactly one way to find out whether that made the answers worse: the eval
harness, over the candidate skills, against a real key. So this waits behind a measurement
rather than being done because the arithmetic is obvious.

Worth doing when the ceiling is actually being hit. Until then P124's headroom is enough,
and the failure this would cause - a model that reads a positional row wrongly and binds a
figure to the wrong cell - is the exact failure the Numeric Integrity Lock cannot see.

Size: small to build, and the eval around it is the real cost.

## B-084 A cheap model for the bulk read, with the verifier already built

From the same harness study as P124 (SoL-Pi, arXiv 2609.20519). Its fourth mechanism is:
let a cheap model read the bulk and write a receipt of exact quoted lines; have
**deterministic code** check every quote against the archived original; on any failure,
hand the original to the frontier model. The claim is that delegation stops requiring
trust in a fluent summary once the quotes are checkable.

This build already has the verifier half, and did not build it for this reason. Model-load
proposes bindings by `figure_ref` and `apply()` refuses any ref the catalogue does not
hold, any input bound twice, any figure whose period is not the one its cell asks for.
Timing-normalization's output is held to provenance and tie-out arithmetic. In both cases
a wrong answer from a cheaper model is *caught by code*, not by reading it.

So the open question is narrow and empirical: **which steps still give the same answer on
a cheaper pin.** Model-load's judgement - deciding that "Costs of Goods Sold" is the
template's "Cost of sales" - is the one thing no deterministic check covers (the module
docstring says so) and is the last place to economise. Timing's bulk extraction is the
first, because arithmetic covers it.

Needs: the eval harness, a real key, and a scorecard run per pin. Do not guess at it -
the whole point of the mechanism is that the saving is measured against held-out quality.

Size: medium, and it is the largest recurring-cost lever this build has left.

## B-085 The three reads a reviewer makes
status: built (the workbook and the prose; the figures are B-087)
2026-10-01, from the analyst: "make checks like when it is actually running - from a
managing director standpoint, does the valuation actually make sense; from a grammar
standpoint, does this sound like AI slop, are there em dashes; and one looking for
consistency and silly mistakes, a missing comma, a formula summing one too many rows."

Three reads of what leaves the system. Two are built:

- **`tools/formula_audit.py`** (P125). Eight checks in three severities over openpyxl.
  The one the analyst named - a total whose range stops a row short of its block - is
  `total_misses_rows` and is severity `wrong`, because it is provable from the file.
  Wired three ways: every workbook a run releases (`release.audited`, recorded and never
  a refusal), a console route behind a **Check formulas** button, and the command line.
- **`tools/prose_checks.py`** (P126). Tells, slips, and the two spellings of one thing.
  Calibrated against documents with nothing wrong with them, which was most of the work.

The third - whether the numbers make sense to somebody who has seen a hundred of these -
is B-087, and it is a different kind of problem: every finding is a question for a person
rather than a statement about a file, because "this margin is implausible" depends on the
industry and the bands belong to the practice.

## B-086 The Oxford comma, which needs a parser
status: proposed
2026-10-01, from P126. A `serial_comma_both_ways` check was written, measured and taken
out. Over this project's own four longest documents it reported 23 lists with the comma
before "and" and 26 without, and nearly every match was an ordinary compound sentence:
"That is the design, and it holds" is a comma joining two clauses and has nothing to do
with a list.

Telling a list from a clause needs to know where the clause boundaries are, which needs a
parser rather than a pattern. `tests/p126::test_the_serial_comma_check_stays_out` is what
stops it coming back without one. Size: medium, and it needs a dependency this build does
not have - which is the real reason it is here rather than built.

## B-087 The questions a reviewer asks of the numbers
status: built (the engine and the command; the run-path wire waits on B-004)
2026-10-02, P127. The third of the analyst's three reads (B-085), and the one that is a
different kind of problem: `tools/reasonableness.py` asks questions and answers none,
because the answer depends on the business.

Three families. **A line that implies another** - depreciation with no fixed assets,
interest expense with no debt (the first question an MD asks, and the one the debt tab in
B-007 answers), tax in a loss year, amortisation with no intangibles, a lease liability
with no right-of-use asset, rent beside a related-party balance. **A ratio over time** -
gross and operating margin, days receivable, days inventory, days payable, the current
ratio, each compared step to step *and* first period to last, because a margin giving up
two points a year for three years trips no step tolerance and has moved six. **The shape
of the history** - a year missing from the middle, and fewer years than the engagement
asked for.

Three things about it that are deliberate and worth not undoing:

- **No defaults, anywhere.** Tolerances are keyed by the ratio's own unit (points, days,
  turns) and a unit with no tolerance is reported as a question nobody asked rather than
  left out. One number across all three units is right for one of them.
- **Nothing concludes.** `tests/p127::test_nothing_in_the_output_concludes_anything`
  reads the module's own output for the words a verdict would use.
- **The ratios are built from the pinned taxonomy**, not from a list in the module, so the
  operating margin cannot end up computed over fifteen of seventeen operating expense
  lines and look plausible while doing it.

**What is owed.** The run-path wire. It belongs where `statement_checks.py` belongs - in
the qc-tieout procedure (B-004) - and that waits on the same two decisions B-004 waits on,
plus the governance chain. Until then the command line is the honest front door, and it is
the one the analyst asked for. Size: small once B-004 exists.

## B-088 The second front door, and the Box connector's join
status: built
2026-10-02, P128. From the analyst: *"when I get home or when I go to lunch, I just want
to do a slash command in this and point it to the right folders, quickly tell it what to
do... and it just starts working and then I can come back and review."*

`tools/aa.py`, three subcommands, each doing something the dashboard does not:

- **`review`** dispatches the three reads by what a file is, so one command over a client
  folder reads the workbooks for formulas, the documents for prose and the tables for the
  questions. That is what lets one slash command be enough - the person does not have to
  know which check a file wants, and neither does the command they typed.
- **`where`** prints the folder an engagement's documents go in.
- **`stage`** puts them there through `AdminConsole.add_file`, the only writer.

`stage` is the **Box connector's join**, and the shape is the sanctioned one rather than a
convenience: a connector reads the client's folder into Claude Code, not into this
process, and anything outside the boundary talks through a surface - the line Power
Automate was held to (BUILD/OPEN.md section 6). Read from Box, save locally, stage in, and
the sweep finds it as it finds a file a person dropped there, with who and why on the
record.

Deliberately **no `aa status`**: `serve.py --check` and `watch_run.py --once` already
answer those two questions, and a third renderer of either is B-046 under a new name.

Four slash commands in `.claude/commands/`. `tests/p128` holds each to naming a tool that
exists, a subcommand that parses, a flag something takes, and the environment prefix - a
slash command is read by a model that will *try* the line.

## B-089 Nine documented commands that would have failed on a fresh clone
status: built
2026-10-02, found while writing P128's guard for the slash commands.

`tests/p58` existed to stop exactly this and had a blind spot the size of the other half
of the problem: it read **fenced blocks only**. `interview/PROTOCOL.md` opens by
instructing the reader to run every command in it through uv and then writes `python
tools/interview.py ...` seven times inline without the prefix; `CLAUDE.md` does it twice
more. `interview.py` needs PyYAML, so each was the exact `ModuleNotFoundError` P58 was
written about - in the file the next interview session reads first.

Four things, together, because any one alone leaves the hole:

1. **The invocations.** Fifteen across `CLAUDE.md`, `CHANGING.md`, `docs/USING.md` and
   `interview/PROTOCOL.md` now carry the prefix.
2. **The check.** It reads inline code as well as fenced blocks, and covers
   `CHANGING.md`, `interview/PROTOCOL.md` and every slash command.
3. **The exemption, derived.** It was `gate.py` by name. It is now a property: a tool is
   exempt when it imports nothing outside the standard library *anywhere in the file*.
   `verify.py` has that property and was being reported as an offence; `surfaces.py` and
   `serve.py` have no third-party import at module level because they defer them into
   functions, so a check reading only the top would have called both dependency-free.
4. **Six tools that said nothing.** `bootstrap_scaffold`, `reasonableness`,
   `simulate_files`, `surfaces`, `synthesize_templates` and `watch_run` all need the
   environment and all raised a traceback about somebody else's library instead of the
   line to type. Each calls `needs()` now, and a test holds every documented tool to it.

**And then the fix broke two of them, which is the part worth reading.** `from
tools._environment import needs` is right in four of the six and wrong in
`simulate_files.py` and `bootstrap_scaffold.py`: both put `tools/` on the path rather than
the repo, because both import a sibling (`simulate_firm`, `gate`). So the package `tools`
is not importable there, and both raised `ModuleNotFoundError: No module named 'tools'` on
their first line. The suite stayed green - `simulate_files` is a rehearsal the suite does
not run, `bootstrap_scaffold` is run by hand, and every check in `tests/p58` was satisfied
by the *text* of the invocation rather than by running it. The rehearsal found it, which is
what the rehearsals are for.

**The test written for that was green on the break too.** It ran each tool through
`python -m uv run`, and `uv` lives in the system interpreter rather than in the
virtualenv - so under pytest the subprocess died with `No module named uv`, which contains
neither "Traceback" nor "ModuleNotFoundError", and both assertions passed on a command
that never started. Found by breaking the tool again on purpose and watching the test pass.
It now runs each tool with the interpreter already running the suite and asserts the
**return code**: 0 is its help, 2 is it refusing arguments, and anything else - including a
launcher that could not launch - is a tool that did not start.

## B-090 Read the firm's model rather than wait to be told about it
status: built
2026-10-02, P129. B-008 ("register the non-ESOP Excel template") and the roll-forward's
Excel half (B-036) have both been blocked on the same thing: `Model Template - MASTER
2026`, and four hundred lines of YAML nobody has written. CLAUDE.md said the named ranges
"are not knowable from a photograph", which is true and was being read as "not knowable".

`tools/read_template.py` reads them off the file. The inventory - every defined name, the
sheet and cell behind it, whether that cell is empty, a number, a formula or a block - is
what the roll-forward's Excel half needs as much as the schema does. The draft schema is
in the exact shape `TemplateInputs.load` reads.

**The half that matters is the refusal.** Every `line:` is marked `REVIEW` and the draft
will not load until a person has removed them. Reading `Revenue_FY1` as the line *Revenue*
in period *FY1* is reading a naming convention - a thing a firm has, not a thing a file
states - and a schema filled in silently would bind the firm's model by inference. The
first symptom would be a figure in the wrong row of a workbook that opens perfectly.
`--scale` defaults to 1 and not to the firm's thousands convention for the same reason.

`tests/p129` generates a draft, strips the markers as a reviewer would, and loads it into
the registry: the shape is proved, the judgement is not taken. It runs that end to end
against the repository's own synthetic master template, which this tool was not written
against.

**What is still owed:** the file. And then the `line:` values, which are an hour of
somebody's reading rather than a design problem.

## B-091 Three questions the interview map was not asking
status: built
2026-10-02, P130, from the analyst: *"at work I'm building a bunch of things within Claude
Code like workflows to help me write restricted use reports through a Word document and
also restricted use PowerPoints... it has a lot of context of how to do all these things
on my work computer that hopefully this tool can integrate with. And then also it has a
lot of context of how the model, the master model works and how to fill in the inputs."*

Two new topics and one rewritten angle in `interview/topics.yaml`:

- **`work-machine-context`** (priority 1). What has already been built on the work machine,
  what each thing knows, and for each one whether it is copied here, called from here, or
  left where it is. This is the handoff: knowledge this build is missing and somebody has
  already written down. It was not a question anybody was going to be asked - `ai-tools`
  asks which tools are *approved*, which is a different thing from what has been built with
  them. The topic also asks, explicitly, which of it carries a client's name, because
  moving any of it here puts it under the outbound scan.
- **`report-and-deck`** (priority 2). `report/` can already copy last year's document and
  put this period's appendices into it by name, and nothing told it which appendices a
  restricted-use report has. `tools/prose_checks.py` can read a draft for the tells and the
  slips, and nothing told it what the firm's house style is - which dash, how amounts are
  written, which terms are capitalised because they are defined. Both are waiting on the
  same answers and neither had a question.
- **`excel-models`**, rewritten. It asked the analyst to write the template's input map,
  which is four hundred rows of transcription. It now asks them to run
  `tools/read_template.py` against a blank copy and bring back what it prints - and then to
  answer the one part the file cannot state, which is what each name means.

The map is still generic: no client, no project, no figure. `interview.py scan` prints
clean over it.

## B-092 What happens the first time a run reaches release, traced
status: proposed (the trace; the fix is B-043's decision)
2026-10-02, while wiring the formula audit into the release path (P125). B-043 records that
`privacy.unmask` and `privacy.verify` are reached by nothing in production, and says the
consequence is that "no run has ever resolved a token back". This is the rest of that
sentence, traced rather than inferred, because the audit wire made it worth knowing exactly
what would happen on the day:

1. the masker replaces the client's declared identifiers before anything reaches a model;
2. nothing unmasks them on the way out - `deliver/builder.py` opens by *claiming* its
   inputs are unmasked, and nothing makes that true;
3. so the workbook the writer produces carries mask tokens in its cells;
4. `deliver/qc.py` searches every cell and every formula for `TOKEN_PATTERN` and refuses on
   one, which is tested (`tests/p21/test_release.py` passes it `"Officer salary
   [[PERSON_1]]"` and expects "residual mask token");
5. so the **first run ever to reach release is refused by QC**, with the right diagnostic,
   and nothing partial escapes.

That is the system failing correctly, and it is the only way this could have gone that does
not end with a client's workbook full of `[[PERSON_1]]`. Worth having written down because
the symptom - "QC refuses every deliverable" - looks like a QC defect and is not one.

**No new work here.** Where the unmask belongs on the release path is the design decision
B-043 holds, and OPEN.md says it is not one to take while tidying something else. What
changed is that the consequence is now a trace with a test at the end of it rather than a
paragraph.

## B-093 The prose checks, where the prose actually moves
status: built
2026-10-02, P131. P126 built `tools/prose_checks.py` and reached it from the command line.
This joins it to the one place in this build where prose enters a client deliverable: the
moment an appendix's content is transplanted into the report.

The reason for putting it there rather than leaving it to `/review` is the analyst's own
words - *"checks like when it is actually running"*. Appendix commentary is where a draft
written with a model enters a report, the preview is where somebody is already looking, and
a check nobody has to remember is a check that runs. A preview now reads:

    Appendix C: 3 block(s) out, 8 block(s), 1 style, 1 numbering, 1 image in;
    5 thing(s) to look at in the words arriving, 2 of them mechanical  (nothing written)

Three things it does not do, each with a test in `tests/p131`:

- **it does not stop the update.** An appendix that failed to move because of an em dash
  would be this tool deciding something that is not its decision. The slips are counted
  apart from the tells for the same reason: one is provably a mistake and one is a
  judgement.
- **it does not report silence as clean.** A source that could not be read says so, with
  the reason, and the appendix still moves.
- **it does not reach Appendix H.** Asked of the registry rather than of a docstring: the
  certification is not `updated`, is not in `updatable()`, and `preview` refuses it.

What is still owed is the house style the checks are held to - which dash this firm uses,
how amounts are written, which terms are capitalised because they are defined. That is the
`report-and-deck` interview topic (B-091), and until it is answered the checks are held to
a style they inferred.

## B-094 The restricted-use deck has no path at all
status: proposed
2026-10-02. The analyst builds restricted-use **PowerPoints** at work alongside the
restricted-use reports, and `report/` is Word-only: `python-docx` is a dependency,
`python-pptx` is not, and nothing in this build has ever opened a `.pptx`.

Not built tonight, and the reason is the one that matters: `report/` works because it binds
by **name** - a bookmark or a heading, never a paragraph index - and the equivalent for a
deck is a named placeholder or a named shape. Which of those this firm's template uses is
not knowable from here, and a deck path built on a guess would bind by slide index, which
is `B44` with a different spelling.

What it needs is the second half of the `report-and-deck` topic (B-091): what is on each
slide, which slides change every year, and where the figures come from. Then it is the same
three pieces `report/` already has - find the place by name, move the content with the
things that make it render, and never edit the file that was read.
Size: medium, and it is a straight port of a pattern that works rather than a new design.

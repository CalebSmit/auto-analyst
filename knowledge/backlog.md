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

## B-095 Four things found by reading the screen rather than the source
status: built
2026-10-02, P132 to P134, sealed by C74. The console was run against a store of eighteen
real runs and looked at. Every one of these was visible in one look and none of them was
visible from the code:

- **An engagement with one run printed everything twice.** The group header carried the
  client, the scope and the time; the run row under it carried all three again plus the run
  id. All eighteen engagements had exactly one run - which is every engagement until a
  client comes back - so the fold was pure duplication. Seven engagements now fit where
  four did. The fold stays for a repeat client, which is what P63 built it for.
- **"12 need attention . 2 waiting on you" counted two different things.** Twelve *runs*
  and two *questions*, and both questions sat on runs already inside the twelve. They now
  name their units, and both are pressable: the number somebody reads is the control they
  press, because the next thing they want after reading it is the things it counted.
- **The funnel was not a funnel.** "Skills dispatched 0 of 18" followed by "Guards 17 of
  18". Each stage counted every run matching its own predicate with no reference to the
  stages before it, and `max(0, previous - count)` clamped the impossible negative - so the
  panel hid its own contradiction. It counts survivors now. The same stage was also named
  for one thing and measured another: it counts `skill.completed`, so a run whose skill was
  dispatched and then quarantined read as one that never started.
- **The review modal told you to read a source it did not show** - and the source existed.
  The classifier records the twelve headers it judged the document on under `headers`; the
  review surface reads an excerpt from `source_excerpt`. Two names for one thing, so twelve
  headers were captured for a reviewer and never reached one, on the one question that is
  only answerable by looking.

**And the primary button contradicted the sentence above it.** A quarantined run says
"stopped on itself - a step failed in a way retrying will not fix" and **Resume** was the
dark button. The Help page already said the right thing - *fix that, then Resume* - so the
button was the only surface disagreeing. It is no longer primary and both actions now say
what they do before they are pressed.

What this says about method: four defects in surfaces that are heavily tested, found by
opening them. The suite can only ask whether a page does what its code says; whether what
it says is true of what a person sees is a different question and needs eyes.

## B-096 A fresh clone could not set itself up
status: fixed (P135)
2026-10-02. Started a server against an empty store - the state the work machine begins in -
and opened `/admin`. The page was twelve grey rectangles under a red banner reading *"This
page cannot reach the server"*. Five defects, each of which alone stops a first day:

1. `SETUP` was `null` on an unconfigured machine and `checklist()` dereferenced it. Most of
   the page guarded for null; one step did not, threw, and took every panel after it with
   it. **Null was the wrong shape for "nothing is set up"**; an empty object is the right
   one, and whether a configuration exists is a separate flag because it is a separate
   question.
2. The refusal was reported as an unreachable server. `refresh()` tested `e.code`, and only
   *structured* diagnostics carry a code - so the one refusal this page exists to handle
   took the other branch. Every refusal now says `refused: true`, which is the question
   actually being asked.
3. The masking key and the model adapter were only ever returned inside `/api/admin/setup`,
   which refuses when there is no document - so steps one and two of the checklist read
   "unknown" and "?" on the one machine where they are the whole job. They need no
   configuration and are now their own route.
4. **`SETUP.recipes` is returned by no route at all.** The workflows live behind
   `/api/admin/recipes`. So on *every* machine, configured or not, step seven could not be
   ticked, its Approve button could not appear, and the checklist could not reach "Ready to
   run" however much was done - while the panel beside it said four approved. This build's
   most-named defect, in the list a person follows on their first day.
5. A step's control rendered only when that step was `next`. A fresh clone runs on the fake
   adapter, so step two can never be marked done, so it was permanently `next`, so step
   three's **Set it up** never appeared. There was no way to configure the machine from the
   page whose only purpose is configuring it.

And two sentences that were not sentences: `the firm ceiling of $undefined`, and `Next:
connect the ai model`.

Not found by reading. Found by starting a server on an empty database and looking at it.

## B-097 The board is a monitor layout
status: fixed (P136)
2026-10-02. Measured rather than guessed: with the Setup page's wrapper forced to 600px -
a 1366x768 laptop less the browser's chrome - the "Getting set up" panel reported
`clientHeight 259, scrollHeight 750`. **35% of its own content**: three steps of eleven, in
the panel a first day is spent in, with the other eleven panels no better.

The stylesheet already contained the argument, for the other dimension: *"One screen, no
scrolling, is the rule at desk width. Below it the same rule hides whatever does not fit,
with no way to reach it."* Nobody had said it about height. Below 760px the board now falls
back exactly as it does below 1100px of width, a finished step costs one line instead of
two, and the checklist holds four of the board's six rows while it has work in it. Eleven
of eleven, visible at once.

Worth saying plainly: this was invisible on the machine it was built on and is the shape of
the machine it is moving to.

## B-098 What the three reads say on real input
status: fixed (P137)
2026-10-02. Ran `aa review` over a normalisation workbook with the two mistakes the analyst
named, a page of appendix commentary written the way a model writes one, and a three-year
table with signed amounts.

**The formula audit was right.** It found the total one row short and the total that reached
up over a subtotal, named the cell, named the rule, printed the formula, and said which
checks it could not run and why. Nothing to do.

**The prose read reported a bullet list as a sentence missing its full stop.** The rule
looked only at the first line of a Markdown block, so

    Key considerations include:
    - owner compensation normalised to a market rate

is one block beginning with a sentence - the commonest shape in a report, and every one of
them a finding. The last line decides now. It also said `ends in 'k'`, which is the last
character of the sentence printed directly above it.

**The reasonableness read asked twelve questions about figures that cannot exist.** Given a
table with a cost of sales of -10,900 rather than 10,900 - what a trial balance looks like -
it reported a gross margin of 173.6 points and asked *"What changed in the business - and is
it in the forecast?"* A margin above 100 points is not a business event; profit cannot
exceed revenue. Each ratio now carries the range its own arithmetic can produce, a value
outside it is reported once with the negative rows named, and no movement is asked about.

Both failures are the same one: **a read asserting something it had not established.** The
fixtures were in the shape the checks were written against, so neither had ever been seen.
A margin has no floor - a business can lose more than it earns - so only the bound the
arithmetic actually gives is claimed.

## B-099 What three real runs say on the screen
status: fixed (P138)
2026-10-02. Ran `simulate_firm.py --scripted --keep` into a directory that survives it,
started a server on the store it left, and read the console against three runs it had
actually produced. Three things:

**"1 need a person."** The chrome and the engagement header count the same states and C74
holds them to the same *words*. Both wrote the sentence themselves, so they agreed on the
noun and neither inflected the verb - invisible until a count came out as one, which no
fixture and no screenshot had ever produced. `needAPerson(n)` owns the phrase and its verb
now, and C74's test was changed from counting the literal twice to asserting one home and
two callers, which is the property it was reaching for.

**"quarantined · in progress", tooltip "still running."** `in_progress` on a scorecard means
*no verdict yet*; the pill rendered it as the run's own motion. So a run that had stopped on
itself was labelled as running, with a tooltip insisting on it. Two vocabularies - run
states and scorecard verdicts - and the page read one in the other's terms. On a stopped run
a scorecard with no verdict now says `no verdict`.

**Two keys the map answers to and never mentions.** `+` and `-` zoom; the hint line named
five keys and not those, and "0 fits" reads as a count of something beside "/ finds", which
is the same shape and does not. A test now holds the line to the handler in both directions.

(The keys themselves all work - verified in the browser. A first probe suggested they did
not, and was wrong: a `KeyboardEvent` dispatched on `document` has `target === document`,
`document` has no `.closest`, and the handler's second line throws before any key is read.
Dispatch on an element.)

## B-100 One vocabulary, and there were four surfaces
status: fixed (P139)
2026-10-02. C74 held the chrome, the engagement header and the Help page to one set of
words. There are four surfaces. The Analytics console titled the same condition **Needs
attention** - one tab away from a chrome reading **2 need a person** - and the run detail
still said **Waiting on you**, on the panel somebody reads *after* pressing the chrome's
number. Both are phrases P132 retired; both survived because P132's guard was scoped to the
two functions it had changed.

And the Help page, which exists so a reader can look up a word they met on a screen, defined
`Waiting` and `Quarantined` but not `Needs a person` - the word printed larger than either,
and the only one in this vocabulary that is not a state. It also did not define `queued` or
`superseded`, two states a run can be in that want nothing from anybody, which is why nobody
had missed them.

**What is worth keeping is the test, not the strings.** It finds the surfaces rather than
listing them - every module that defines a `PAGE` - so the next page added to this product
is held to the same words without anybody remembering. A list of three was what let the
fourth drift.

## B-101 Sixty-eight skipped tests that say they are unwritten and are not
status: proposed
2026-10-02, noticed while writing C76. `gate seal` writes a stub beside each new checkpoint:

    @pytest.mark.skip(reason="written at the end of P139")
    def test_c76_integration():
        raise NotImplementedError

It exists so the integration test has a home before it is needed, which is right. What
nothing does is remove it once the real test is written beside it - so there are **68 of
them**, every one skipped, every one saying "This checkpoint is not written yet" about a
checkpoint that is written and green.

Why it is worth fixing rather than ignoring: this repo's whole apparatus is built on a
skipped test not being a passing one, and the session summary counts skips so that a real
one is visible. Sixty-eight permanent ones are the noise a real one hides in.

Two ways, and the choice is a small design one:

* **Delete each stub when its checkpoint's real test lands**, and add one test asserting
  that a closed checkpoint has no stub left. 68 file deletions, mechanical, and the `Proves:`
  sentence each stub carries is already in `BUILD/PLAN.md`.
* **Make `gate seal` write the real file**, so there is one file per checkpoint from the
  start and nothing to remove. Does nothing about the 68 already there.

Not done here because it is 68 deletions in a session that was about the consoles, and
because which of the two is right is a judgement about the gate rather than a defect in it.

**It grows by one per checkpoint.** C85 made it 69 (2026-10-02), and the count is updated
here rather than left at 68, because a backlog item that quietly stops being true about its
own size is the same defect it is describing. Still not fixed in that session either: it was
about reading a client's documents, and nothing about a stub affects that.

## B-102 The consoles were served with no cache headers
status: fixed (P140)
2026-10-02. Fixed a syntax error in the Setup page, restarted the server, and the page was
still the broken one. Three more restarts, same. It only came back when the URL was changed
to `/admin?v=1`.

The three consoles are Python strings built at import, so the only way a new one reaches a
person is a restart - and the responses carried **no cache headers at all**, which leaves a
browser free to reuse one without asking. It does.

On the machine this is moving to that reads as "I pulled the update and the fix is not
there", with nothing on screen to say otherwise, and the next thing somebody does is look
for a bug that was already fixed. `ui/who.py` now adds `Cache-Control: no-store` to every
`text/html` answer - in the middleware rather than on each route, because a route added
later would not know to, which is exactly how `/analytics` and `/help` would have been
missed. The API answers are untouched: the scripts ask for those afresh anyway.

## B-103 The gate ordered an id as a string, in a fourth place
status: fixed (P141)
2026-10-02. `gate amend C76 --set-after P140` ran `amend_checkpoint`, which sorted the
checkpoint list with `sort(key=lambda x: x["after"])` - on the spelling. The plan came back
with its 76 checkpoints in the order P03, P06, P09, **P100**, P102, ..., and C59-after-P99
last. `tests/p01` then said *"the last checkpoint must cover the last phase"*, which was a
true statement about a plan whose order had just been scrambled by the tool reporting it.

`number_of()` exists for exactly this. Its docstring already named three sites fixed on
2026-09-22 when the plan crossed a hundred phases - `phases_covered_by`, `cmd_close`'s
in-order check, `phases_after_last_checkpoint`. This was a fourth, and that sweep could not
have found it: **a sort key is not a comparison**, so looking for `<` finds three.

Nothing was lost. `save()` renders PLAN.md from the plan, and the order was repaired
numerically before anything was generated from it. What it cost was an hour.

`tests/p141` now holds the rule over the whole file with an `ast` walk rather than site by
site: no comparison and no sort key in `tools/gate.py` orders a phase or checkpoint id
except through `number_of`. Run against the code as it stood, it found that one offender and
nothing else.

## B-104 One diagnostic code was doing the work of five
status: fixed (P141)
2026-10-02, found by running `aa owed` against a real store. An engagement whose division
has no request list is refused correctly and then told:

    what to do: The run criteria version named is not a file under ops/criteria/ ... Pin a
    version that exists; a run scored against 'whatever is newest' cannot say what bar it
    was judged by.

`SCOPE.UNKNOWN_CRITERIA` was raised at five sites, four of which are not about criteria.
`what to do` is the half a person acts on, and borrowing a code borrows its advice for a
problem it was not written about. `/owed` is one of the slash commands.

| raised for | now |
|---|---|
| a criteria version not on disk | `SCOPE.UNKNOWN_CRITERIA` (correct, `ops/scorecard.py`) |
| a division with no request list | `SCOPE.NO_REQUEST_LIST` |
| an appendix id that does not exist | `SCOPE.UNKNOWN_APPENDIX` |
| a malformed appendix registry | `SCOPE.APPENDIX_REGISTRY_INVALID` |
| an appendix that carries forward | `SCOPE.APPENDIX_CARRIES_FORWARD` |

**Three things found by the layer above, in order.** The phase searched two files and wrote
its test over those two. C77 walked every module that raises a diagnostic and found the
fifth, in `report/setup.py` - so the phase reopened through `gate amend --reopen` rather
than letting the fix arrive uncovered, and its test now walks rather than searches. Closing
that found the four codes missing from the blueprint's `ERRCODES` table, which `tests/p14`
exists to catch because ten codes once grew in the registry over nine phases without
reaching it. Accepting *that* found the public-surface snapshot refusing them, correctly: a
code is a published contract, a caller may key on it, so adding one is a surface change and
the reason goes in `gate amend` before the snapshot takes it.

**And one correction to the fix itself, found by reading the output rather than the diff.**
The first draft of `NO_REQUEST_LIST`'s `what_now` restated the refusal almost word for word
- the "why" twice and the "what to do" nowhere. The two halves do different jobs: the
message says what happened and why another division's list is not lent; the advice says
where to write one and which scopes a file serves. `tests/p141` asserts both halves and that
neither takes the other's job.

## B-105 The board gave every panel the same share of the screen
status: fixed (P142)
2026-10-02, from a review of the dashboard's design. Measured every panel's body against the
content inside it, on all three board pages, at a desk viewport with three real runs and
three engagements:

| page | starved (content over box) | half empty (under 0.7) |
|---|---|---|
| Activity | Live activity **6.07**, Run trace **3.58** | Alerts 0.44, Waiting 0.41, Runs 0.54 |
| Setup | What is wired **4.39**, Engagements **3.16**, and three more | Methodology 0.56, report 0.69 |
| Analytics | - | What to fix first **0.13**, By skill 0.36, Outcomes 0.34 |

**Seven of twenty panels hid content behind an inner scrollbar while eight sat under seventy
per cent full, on the same screens.** `grid-template-rows:repeat(6,minmax(0,1fr))` hands each
panel an equal share of a fixed board whatever is in it, so it was wrong in both directions
at once. A reader scrolled inside twelve boxes rather than scrolling one page, and a box only
tells you it scrolls once you have found it.

Rows are `min-content` now, `html`/`body` can scroll, and `.top` is sticky so the counts that
say what needs a person stay in view - which is the half of "one screen, at a glance" that
was worth keeping. Seventeen of twenty panels now hide nothing; the three that do are marked
`stream` in the markup, with the reason beside them, because their content has no end: the
event log, the map of a hundred and eighteen nodes, the list of every seam. Stretch after the
change is two to three pixels a card, which is the border.

**It made P136 dead.** That phase added a `max-height:760px` block so a laptop got one column
and a scrolling page. Measured with the block applied and removed, the answer was identical -
the same two panels scrolled either way. It was also wrong in principle: it let *height*
decide the *column count*, and how many columns fit is a question about width. A 1366x600
laptop is a wide screen. Removed, and P136's tests now assert the cause rather than the
mechanism they were written for.

**And the furniture outranked the content.** The two largest things on the Activity console
were the words "Activity" (25px) and "Runs" (17px) - labels for things that label themselves -
while the run the detail panel was *about* sat at 11.5px, the smallest tier on the page, in
the same size as the panel's own explanatory sentence. The panel is titled with the run now.

## B-106 A link the page handed out and did not answer to
status: fixed (P143)
2026-10-02. Read off the source, both halves side by side:

    routed   #profile=   #files=
    linked   #profile=   #settings=

`#settings=` worked when clicked - the element carries `data-act` as well - and did nothing
when pasted into a message or reloaded, which is the only reason a control is a link rather
than a button. `#files=` was a destination the router knew and nothing reached. The comment
over the router says what it is for: *"so the person who owns the missing judgements can be
sent straight to them"*, which is the half that worked.

One table now, and the router reads it rather than repeating the prefixes, so a fourth
destination cannot be half-added. A test reads it in both directions.

**Two things it turned up.** `.btn` exists so an anchor can look like a button, and half the
theme's modifiers named only `button` - so the moment `files` and `settings` became anchors
they rendered as solid buttons beside the quiet ones they sit with. Paired everywhere, and
verified identical in the browser down to the padding. And two tests keyed on `selector + "{"`
to find a rule, which asks whether a component is written *alone* rather than whether it
exists; both failed the day a rule gained a second selector, and both now look for the
selector in its list.

## B-107 What cannot be checked in this browser harness
status: noted
2026-10-02. Chrome freezes CSS animations in a tab that is not foregrounded. Driving the
browser from here leaves `document.visibilityState === "hidden"`, so every animation sits at
`currentTime: 0` for ever - and `.modal` fades in with `animation:fade .18s`, which means a
modal that is correctly built, laid out and positioned reads as `opacity: 0`.

That cost a long detour chasing a deep-link "defect" that did not exist. The router matched,
called its handler and appended the modal; only the fade never advanced. **Modal appearance
cannot be verified in this environment.** What can: the DOM (is the element there, what are
its rect and computed position), the console, the network, and `getAnimations()` - and
calling `el.getAnimations().forEach(a => a.finish())` first makes opacity readable.

## B-108 Three things identified by a shape, all under the bar for one
status: fixed (P145)
2026-10-02, measured in the browser against the surface actually behind each one. WCAG holds
a non-text indicator to 3:1 rather than the 4.5:1 a word gets, and all three missed it:

| what | measured | where it matters |
|---|---|---|
| a button's and a field's border | **1.54:1** | a white button on a white panel has no other edge |
| the focus ring, on the navy chrome | **2.40:1** | the four navigation tabs - where a keyboard arrives first |
| "never got to" against "not used here" | **1.01:1** | the map's far view, which says everything with fill |

**The first is the one with consequence.** In an engagement's row six controls sit together:
five open a panel and are plain text, and the sixth - Pause, the one that changes state - is
marked out by a box. That box was the faintest thing in the row. `--line-strong` went .22 to
.51, which clears 3:1 on all four papers (3.13, 3.06, 3.02, 3.03). The look did not get
heavier, because `--line` and `--line-soft` carry the card edges and row rules and those are
separating content, which the standard exempts and which is most of why this product looks
the way it does. One decorative use of the strong one - a rule under a band label on the map
- moved to the plain hairline so it would not follow the control.

**The ring is now a token, not a colour.** `--ring` defaults to the accent and `.top`
redeclares it to `--brand-p3`, which is 5.22 and 6.24 against the two ends of the chrome's
gradient. One rule, one ring, and the ground picks the colour.

**The map was missing a rule rather than mistuned.** At far zoom the labels go and every
state that means *something happened* fills solid - passed green, running blue, failed plum.
`blocked` was left out of that list, so it kept the pale wash it wears up close and landed
1.01:1 from `notreached`. Those two mean opposite things: "the run stopped before it got
here" and "this recipe does not include this part". It fills `--warn` now. Two things fell
out of the same change: the touched node's white label was 1.56:1 on its own fill and is now
3.15 (large text, 3:1 bar), and the stopped node is visible on the drawing at all - which is
the one thing a person opens the map of a failed run to find.

**Two mistakes of my own, both the kind this repo is about.** The first test of "are these
two the same colour" used a contrast ratio, and went red on blue against gold, which measure
1.08:1 and are plainly different - a ratio answers "can you read this on that", not "are
these the same". It uses CIE76 now, bar of 10. And `far_wash` returned the token rather than
the token composited onto its ground, so `touched` - the one translucent fill - read as solid
navy at 17:1 and two tests passed without ever looking at the thing they name. Found by the
revert harness, which is what it is for.

## B-109 The run trace's fills say less than the panel claims they do
status: open (first written wrong - see below)
2026-10-02. **What I first wrote here was overstated and the measurement did not hold it
up.** The entry said the trace "tells passed from failed by hue alone". It does not: the
failed node is set at weight 600 where the others are 400, which is a non-colour cue on the
one state that matters most, and the text colours are far apart and stay apart. Simulated
over the three states, CIE76 against each other:

| pair | normal | protanopia | deuteranopia |
|---|---|---|---|
| the pale fills, passed vs failed | 6.8 | 3.3 | **0.5** |
| the pale fills, passed vs running | 3.2 | 2.6 | **1.6** |
| the text inside, passed vs failed | 48.2 | 27.5 | 16.7 |
| the text inside, passed vs running | 21.8 | 17.3 | 9.0 |

A just-noticeable difference is about 2.3. **The fills are below it for everybody** - passed
against running is 3.2 with ordinary colour vision - and they collapse to nothing under
deuteranopia. The text does all the work, and does it robustly.

So the design is sound and the finding is a smaller one: the panel's own prose presents the
fill as the signal - *"Mint passed, plum failed with its diagnostic below, a ring on
whatever is running"* - and the fill is the part that carries least. A reader told to look
for mint is being pointed at a 3.2. This is the same class of thing C79 now tests for in the
stylesheet: a sentence about the design that the design does not support. The fix is to make
the sentence true, and to decide whether a fill worth naming is worth having.

**Why it is not folded into P145.** That phase was about things measured against a floor.
This is about a claim, and the measurement that settles it is a perceptual distance under
simulated colour vision, which nothing in this repo computes yet.

## B-110 What target size, names and markup hygiene measure, so nobody measures them again
status: measured, nothing to fix
2026-10-02, swept across all three consoles while looking for the next thing to improve.
Recorded because a negative result that is not written down gets re-derived:

* **Target size (WCAG 2.5.8).** Six controls are under 24x24 - the chip at 77x19, three
  `.small` buttons at 23 tall, a checkbox at 13x13. **Every one passes the spacing
  exception**: the nearest other target's centre is 31 to 616px away, against a bar of 24.
  The first sweep said the chip failed at 15px; that was measured with the map open, and the
  map is a full-screen overlay, so the two were never clickable at once.
* **Accessible names.** Nothing unnamed. The touched-only checkbox looked unnamed to a first
  probe that only read `aria-label`; it is wrapped in its `<label>`, which is the better way.
* **Duplicate ids, dangling `aria-*`/`for` references, controls nested inside controls,
  unlabelled fields, images with no alt.** None, on any of the three.
* **Truncated text.** One element clips - a diagnostic line on the Activity console - and it
  carries a `title`. Nothing else on any page overflows its box.
* **Heading structure.** One `h1` per page, `h2` per panel, `h3` per band in the trace.

One cosmetic thing left: a panel's count is inside its heading, so `<h2>Engagements<span>3`
reads as "Engagements three" rather than "Engagements, 3".

## B-111 Six guards for one rule, all spelling it the same wrong way
status: fixed (P146)
2026-10-02. CLAUDE.md: *"Pages build no handler out of data - values reach a handler through
`data-` attributes and the `ACTIONS` table."* Six tests enforce it, in six files, and all six
are the same line: `assert "onclick=" not in page`. HTML has about seventy event-handler
attributes. Three were in use - `oninput` on the run filter, `onchange` on the trace's
touched-only box, `onchange` on the analytics period - and **every one of the six guards
passed over every one of them, for as long as they existed.**

**Why they existed is the part that matters.** The shared dispatcher listened for `click` and
`keydown`. A field fires neither. The one mechanism did not cover the one case, so three
controls went around it - not by anybody's decision, but because there was nowhere to go. A
guard that forbids a workaround without providing the road gets worked around again.

`tests/p45` records the defect those guards were written for: a client called `O'Brien`,
whose apostrophe closed the `onclick` it had been interpolated into. If that came back as
`oninput="go('" + client + "')"`, all six would have stayed green.

The dispatcher carries `change` and `input` now, from a `CLIMBS` table the listeners are
built from, and the table also says which events may *climb*: a press travels up from the
text you clicked to the row that acts, and a field's own events do not, because a search box
sits inside a row and typing in it would otherwise run the row's action per keystroke. Both
halves verified in the browser: a click inside a row still opens the run, and `input` and
`change` fired on a field inside a `data-act` row do nothing.

"An inline handler" is defined once now, in `tests/reading.py`, beside the two other readers
that exist because a substring is not a question about code - and this one needed that module
more than either: the comment explaining why there are no inline handlers contains the words
`oninput=` and `onchange=`.

## B-112 Rules that undid rules nothing sets any more
status: fixed (P146)
2026-10-02. The `max-width:1100px` block carried six declarations and three of them undid
rules P142 removed:

    html,body{overflow:auto}      nothing sets an overflow on html or body
    .wrap{overflow:visible}       nor on .wrap
    .card .body{max-height:none}  0,2,1 against .card.stream>.body at 0,3,1 - it loses

Verified in the browser by injecting all three at the top of the sheet and measuring: the
stream's cap read 377px before and 377px after, and no other card body was ever capped. The
comment over the block described the page scrolling as something the block achieves; it has
been the base behaviour at every width since P142. What the block is actually for is the
column count, which is the one question about width.

## B-113 A checkpoint does not re-run the checkpoints before it
status: open
2026-10-02, found by being bitten by it. `gate checkpoint CNN` runs `tests/pNN` for every
phase it covers, plus its own integration test. It does **not** run
`tests/checkpoints/cNN` for any earlier checkpoint. Its own summary line says *"everything
built so far still works together"*, which is broader than what it ran.

The consequence, this session: P145 changed the focus rule from `var(--accent)` to
`var(--ring)`. Seven tests asserted the old literal. Six were found and updated; the seventh
was `tests/checkpoints/c22`, and **C79 went green with it broken.** It surfaced only on a
full `pytest tests/`, two phases later.

Worth fixing, and the cost is the question: the prior-phase regression already takes about
ten minutes at 147 phases. The checkpoint integration tests are mostly pure-source reads and
should be cheap, so running all of them may be nearly free - measure before deciding. The
alternative is to leave the scope alone and make the summary line say what it actually ran,
which is the cheaper honest fix.

## B-114 The key that was a second copy of the drawing
status: fixed (P147)
2026-10-02. The Run trace draws 118 nodes and colours the ones a run touched. Above them sat
a key of five swatches written as five inline styles. Measured in the browser against the
nodes they stand for, **all five disagreed**:

| the key drew | the node is |
|---|---|
| passed: mint box, **solid** green ring | mint box, pale green ring |
| failed: a **solid plum** block `#512a44` | a pale pink box `#f7eff4` |
| running: a **solid blue** block `#4f758b` | a pale blue box `#eef3f6` |
| touched: a **solid grey** block `#696f71` | a near-white box `#f7f6f1` |
| never reached: a bordered square | **no box at all** |

The last line is the one with consequence, and the panel's own sentence says why: *"never ran
and passed are the two answers it matters most not to confuse."* The key drew both as a pale
bordered square.

**This defect was found and fixed once already, in the other key.** `map_view.py` says so:
*"its swatches are the node's own rules rather than a second copy of them, which had already
drifted."* The map's key uses the node's class. This one used `<i style="background:...">`.

The key is the nodes now - each entry a real `.node` of its state carrying its own name, so
the reader meets the same chip in the key and in the drawing because it is the same chip. The
fifth is said rather than drawn: *"and a name with no box at all is a node this run never
reached."* Drawing a box for the state whose whole appearance is not having one is how the
two answers came to look alike.

## B-115 Four sentences that count, and two that counted wrong
status: fixed (P148, and two more found by C81)
2026-10-02. Every number written in prose on the three consoles and the help page, held to
what it counts:

| where | said | counts |
|---|---|---|
| Setup, over Preflight | **Fourteen** checks | `CHECKS` has **15** |
| Help, over the colour key | **Three** colours | **4** rows |
| Setup, over the checklist | Eleven steps | 11 - right |
| Help, over the walkthrough | Six steps | 6 - right |

The first is the worst: the panel directly beneath that sentence prints the live count and
reads `15 checks · 3 warnings`, so the page disagrees with itself in one glance. A third was
in `admin/page.py`'s own module docstring, which named a count of the checklist that had been
wrong for about a hundred phases - the first paragraph anybody maintaining the file reads.

**`tests/counting.py` already existed for this.** Its rule is at the top: *derive the prose
from the list, never write the number down twice.* It was written because the count of
preflight checks came to be typed in three places and was wrong in all three the day P114
added one. It had six users and not one was a console.

The reason it did not hold is the useful part: **the table lived under `tests/`**, so a test
could check a sentence after the fact and a page could never *build* one. A rule a page
cannot reach is a rule a page will break. It is `ui/words.py` now and `tests/counting.py`
re-exports it. Verified structurally rather than asserted: adding a check makes the sentence
say *Sixteen*, adding a colour makes it say *Five* - the drift cannot be reintroduced by
adding to the list, which is a stronger result than a guard going red.

**C81 found two more by asking what the phase could not.**

* `tests/p80` kept a third copy of the table. It was written before `counting.py` existed
  and did the right thing with it - derived its count - which is exactly why nothing noticed
  the table itself was the defect, one level up.
* `docs/USING.md` says *"Three checks you can point at anything"* and printed a copyable
  command line for **one** of them. A reader of the guide CLAUDE.md says to keep true could
  not run the formula audit or the reasonableness questions at all - and the second has no
  default tolerance, so it cannot run without a `--move` flag the guide never showed. Both
  command lines added and checked against the tools' own `--help`.

## B-116 What a frontend sweep found nothing in
status: measured, nothing to fix
2026-10-02, recorded so it is not re-derived. Beyond B-110's target sizes and markup hygiene:

* **Text truncation.** One element on Activity clips, and it carries a `title`. Nothing on
  Setup overflows its box at all.
* **The run trace's state fills.** B-109 first claimed it told passed from failed by hue
  alone. It does not: `failed` is weight 600 where the others are 400, running carries a
  spinner, an untouched node has no box at all, and the text colours stay 9 to 17 apart
  under simulated deuteranopia. The pale fills carry almost nothing - 0.5 to 3.2 - but they
  are reinforcement, not the signal.
* **The help page's colour key** uses real `.pill` components rather than hand-painted
  swatches, which is the pattern P147 had to put into the trace's key.

## B-117 The cap went to what was long that day, not to what grows
status: fixed (P149)
2026-10-02, found by putting a realistic firm through the real page rather than by reading
anything. 54 runs over 18 engagements, same server, nothing changed but the number of rows:

| | before | after |
|---|---|---|
| the page | 4787px | **1134px** |
| the Runs panel | 4148px, four screens | **494px** |
| scrolling to reach the last run | 3686px down | **24px** |
| where the detail panel then is | **3570px above the window** | 91px, on screen |
| tallest panel / shortest | 8x | **2.1x** |

The fourth row is the one with consequence. A reader scrolls to a run near the bottom, clicks
it, and the panel it opens is three and a half screens behind them: once the list is long,
**the list and the thing the list is for cannot be on screen together.**

**P142 wrote the right rule and applied a different one.** The reason beside `stream` said
*a panel whose content has no end*. What actually got a cap was whatever looked long on a
screen with three runs on it - so the event log was capped and the list of every run the firm
has ever done was not. Seven panels across the three boards have a length that belongs to the
firm: Runs, Waiting on a person and Alerts; Engagements and Preflight; What to fix first and
Outcomes by week. None was capped. Two of the three that were capped are design-sized and
fixed, which is a second and perfectly good reason to cap - just not the one that was written
down.

The rule is now a question that can be asked of a panel rather than seen on a screen:
**whose length is it?** One row per step of setup, per practice group, per recipe, per seam is
as long as this build made it. One row per run, per engagement, per open question, per week of
history is as long as the firm's own work, and nothing here can know how long that is.

**It costs nothing until it is needed.** The cap is a `max-height`, so at the three runs this
machine has, every measurement is identical both ways - the Runs panel is 422px with it and
422px without. That is what made it safe to do to seven panels at once.

Two things the tests caught in my own reasoning. The first draft asserted capped-if-and-only-
if-the-firm's and went red on the map and the seam list, which are this build's and are right
to be capped - there are two reasons to cap and only one is about the firm. And `tests/p142`
required a reason in the markup beside every stream, which the seven new ones did not have;
writing them was better than weakening the test.

## B-118 What the consoles did not say to a reader who cannot see them
status: fixed (P150)
2026-10-02. Two things, both verified before being believed.

**No `main` landmark on any of the four pages.** The shell emits a `nav` inside the chrome
and every page then opened a plain `div.wrap`, so a screen reader had a navigation region to
jump to and nothing to jump *from* it to; a skip link would have had no target. Measured
across the three boards and the help page: one `nav`, seven `header`s, **zero** `main`s. The
wrapper is the `main` now - it already had the layout on it, so wrapping it in a second
element would have meant two boxes where the sheet expects one.

**A panel heading welded its title to its count.** `<h2>Runs<span class="of">3</span>` with
the span at `display:inline`, so no browser inserts anything between them: the accessible
name was `Runs3`, heard as *"Runs three"*. Same on Engagements, Waiting on a person and
Alerts. A literal space fixes it, and a test asserts the span is still inline - because if it
ever becomes a block the browser supplies its own separator and the space is doing nothing.

**Three of my four findings here were measurement artefacts.** The first sweep used
`textContent` as a proxy for an accessible name and reported the Setup progress block as
*"2 steps leftNext: Connect the AI model 9 of 11done"*. It is not: the `b` inside it computes
to `display:block`, and so does `.of.done`, and a browser inserts whitespace at a block
boundary while `textContent` does not. **Only the heading count is genuinely inline.** The
instrument has to be the thing the name is computed from, which here meant reading `display`
before believing the string.

**And two of my own tests were vacuous until the revert harness said so.** The first sweep
for a welded heading looked for a letter beside a digit in the served markup - but the count
is written in by script, so the markup only ever holds an empty span, and the sweep passed on
the welded page. It tests the *shape* now: a word, then an element opening, with nothing
between. And C83's symbol-only-control test matched a label of up to three characters, while
the markup says `&minus;` - seven. It examined none of the four buttons it was written for.
It unescapes first now and asserts it examined at least four.

## B-119 The frontend sweeps that now come back clean
status: measured, nothing to fix
2026-10-02. After P142-P150, these are measured and hold a test. Recorded so the next person
does not re-derive them: text contrast against the 4.5:1 floor, non-text contrast against
3:1, control boundaries and focus rings on every ground they land on, panel sizing at a
firm's worth of data as well as at three runs, target size against WCAG 2.5.8 including the
spacing exception, accessible names on every control, duplicate ids, dangling `aria-*` and
`for` references, controls nested inside controls, unlabelled fields, images with no alt,
text truncation, landmark and heading structure, numbers written in prose, and every colour
coming from a token so a sweep over tokens is a sweep over the product.

## B-120 A text line is not a statement row
status: fixed (P151)
2026-10-02. Measured on `fixtures/public/sec-ars-3d-systems-2025.pdf`, page 56, its
consolidated balance sheet:

| the filing says | the reader produced |
|---|---|
| Total assets **521,728** | *no row at all* |
| Total liabilities **279,177** | *no row at all* |
| Common stock **146** | **220,000** |

**The two that vanished.** An audited statement sets its grand total on a ruled row and the
PDF emits the label and the figures as separate runs - `Total assets` then
`$ 521,728 $ 608,846` - so the run of figure-carrying lines broke at the label and the row
was built by nothing. Those are the two figures a balance sheet exists to state.

**The one that was wrong is worse.** The Common stock line wraps, and its first line reads
`...authorized 220,000 shares; shares issued 145,581 and`. Taking the last figures on the
line stored the authorized share count as the common stock balance. It passed every guard:
provenance, because 220,000 really is at that locator, and footing, because the row is not a
total and nothing re-adds it. A confidently wrong figure in the equity section of a balance
sheet is the failure this build says it most cares about.

**Both are one assumption**, and no reading of the text can fix either: a row is a band of
the page and a column is a band too. Figures align on their **right** edge - left edges
scatter with the width of the number - and on page 56 the columns sit within three points of
x=482 and x=549 while the 220,000 inside that label sits at x=234.

pdfplumber and pdfminer.six, pure Python, no system dependency, no network, no model. The
line reader is kept and still runs: a PDF whose lines are each one drawn string has no column
geometry at all, and coordinates there would find columns that are coincidences. The test is
whether a run resolves into two or more columns.

**What it cost elsewhere: nothing, and it gained.** Over the whole filing, rows carrying a
value went 674 to 815 and tables whose every column is named went 21 to 27 (recorded here
as 28 until C86 asserted the count and measured 27; P155 did not move it). The table count
fell 88 to 72, because a statement no longer breaks into four tables at the rows that lost
their figures.

Four things measured rather than assumed, each of which changed the design: the row band is
overlap and not baseline distance, because a figure set against a two-line label is centred
on the pair and sits on neither; a column belongs to a table and not to a page, because page
30 carries two tables and clustering the page gave it nine columns; a bare year may not
establish a column, or the header row joins the table and no column gets a name; and a
`COLUMN_SHARE` threshold I added on page-56 evidence turned out to change **no page at all**
once the figure definition was tightened, so it is gone rather than kept as caution with a
comment that had stopped being true.

## B-121 Two of the four spreadsheet types could not be opened
status: fixed (P152)
2026-10-02. `intake/fingerprint.py` routes `.xlsx`, `.xlsm`, `.xls` and `.csv` to a reader
that calls openpyxl, which opens the first two. A trial balance sent as a CSV was refused and
what a person was told was **"TB.csv cannot be opened as a workbook (BadZipFile: File is not
a zip file)"**.

`tools/simulate_files.py` has had a CSV case since it was written and it passed every time,
because the rehearsal judged a case by whether its run reached an end - and a halted run has
ended. **A rehearsal that accepts any ending accepts the wrong one.** It now names the cases
whose files are all well formed and calls an `UNREADABLE_FILE` on one of them a finding,
which closes the hole for the other twelve cases too.

Each is converted to a workbook at the door, so nothing above changed: sheet selection,
normalisation, footing and the `'TB 2025'!B5:B8` locator a figure cites all go on reading a
real workbook. The debit and credit columns of a CSV trial balance come back as two blocks
at two ranges.

**The care is in the numbers**, because a CSV has no types. `402,000` is four hundred and two
thousand or four hundred and two depending on a convention the file may not state, and
writing the wrong one is undetectable afterwards since both are plausible figures. The
convention is decided once from the whole file on evidence that can only mean one thing, and
where the file settles nothing the cell **stays text and is named** - a file carrying both
`402,000` and `1.234` yields no figure block at all and says why.

Two of my own mistakes, both found by the revert harness rather than by me: the encoding was
reported as `utf-8-sig` for every UTF-8 file, because that codec reads a file with no byte
order mark perfectly well and the name was saying something the file did not; and two tests
were too weak to catch what they named - a title block that does not contain a comma cannot
show that the delimiter is read from the whole file, and an `.xls` with no date in it cannot
show that a date keeps its mode.


## B-122 A file that was not text became content anyway
status: fixed (P153)
2026-10-02. `read_document` ended in a branch that decoded its bytes as UTF-8 and called the
result a document. The assumption was one line long - a file that is not a PDF and not a
`.docx` is text - and it applied to everything that reached the reader. Measured:

| what was sent | what the parse store got |
|---|---|
| an RTF engagement letter | **one line** of `{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fnil Calibri;}}...` |
| a `.doc` (OLE2 compound file) | replacement characters and a dump of the bytes 0 to 255, over three lines |

Both were written to the Source Parse Store as rows a figure could cite, both were handed to
the classifier, and **both were appended to the text a model is sent**. That is worse than
refusing: it is wrong *as content*, and nothing downstream can tell a line of RTF control
words from a sentence somebody wrote.

So the question asked now is what the file *is*, from its first bytes rather than from its
name - a `.doc` saved as `.txt` is still an OLE2 compound file - and a file that is not text
is refused with what it is and what to do about it. `INTAKE.FORMAT_NOT_READ` is its own code
rather than `UNREADABLE_FILE`, because the action differs: save it as something that is
read, not ask the client to send it again.

The signature list will always be shorter than the world, so a NUL byte is the general
catch - no text file in any encoding holds one, and every binary format does.

**An RTF really is text and is now read properly.** `striprtf` leaves the font table, the
stylesheet and the generator behind and turns both kinds of escape back into characters:
`\'24` is a byte in the document's code page and `舒?` is a codepoint with an ASCII
fallback after it. A reader that handled one and not the other would leave half the
punctuation as markup, including the em dash, which this build has a prose check about.

**A `.doc` is refused on purpose.** `legacy-doc` is pure Python and would have been easy to
add. There is no real `.doc` on this machine to measure a parser against, and a half-working
parser for a binary format produces plausible *partial* text - the failure this repository is
most careful about. Routed, named, refused, with the thing to do.

Two of my own errors, both from the tooling rather than the code. A heredoc turned
`\rtf1\ansi` into `tf1nsi` and made a fixture that tested nothing - the sixth time that has
happened, so RTF fixtures are built with `chr(92)` now. And the Write tool resolved `舒`
on the way to disk, so three probe files held the character rather than the escape and I
believed `striprtf` had failed to decode an em dash. It never had: what I was looking at was
a Windows console that cannot print one.

## B-123 Three totals a person checks first were all uncovered
status: fixed (P154)
2026-10-02. `review/router.py` routes an extracted figure to a person unless a total that
re-adds covers it, and `intake/readers/footing.py` is the only thing that produces that
evidence. It knew two shapes - a total of the lines above it, and a total of the subtotals
above it - and **a real balance sheet's grand total is neither**:

    Total current assets          346,707     <- subtotal, over the five rows above
    Property and equipment, net    49,249
    ... six more
    Total assets                  521,728     <- the subtotal AND the seven loose rows

Over the lines it double-counted the subtotal and missed by exactly 346,707; over the
subtotals it needed two and had one. So `Total assets`, `Total liabilities` and the line that
totals the other side were all uncovered - and because the rows above an uncovered total stay
uncovered too, **every figure on the statement went to a person as though nothing had been
checked**.

**The two shapes are one shape seen twice.** A total sums the run of rows standing above it,
where a run that has already been totalled stands as its own total rather than as its parts.
One list, and the mix falls out of it. Measured over the whole filing: the 65 totals that
footed over lines still foot over lines, four more foot over a mix, nothing else moved, and
`Total assets` takes eight rows while `Total liabilities` takes five - which is what they are.

One rule had to be said out loud that the old reader got for free. A subtotal equal to a
later total is a figure **carried down**, not a sum of it, and the old shape refused that by
needing two subtotals. With one list it is stated directly, and it matters because calling it
a footing would cover the subtotal's own rows a second time and claim the same evidence twice.

**And footing cannot prove the two sides agree.** They are different runs of rows, and on a
real filing they are not even in the same block - the reader starts a new one at every
heading. So that is a separate check, reading the two labels the statement wrote and comparing
the two figures it printed: nothing inferred, `None` rather than `False` on a document that
states no balance sheet, and of a hundred and eight pages it speaks about one.

Two near misses in the matching, both found by reading rather than by a test. `Total
liabilities` is a *part* of the other side, so the label has to name the equity as well or
every balance sheet in the world is out by its equity. And the assets side is matched
**exactly** rather than by prefix, because a statement writes `Total assets held for sale` as
an ordinary line in the current assets - it begins with the same two words, it comes first,
and a prefix match reports the balance sheet as out by nearly all of itself. The filing this
build measures against carries that very label.

C85 then found that two of its own guards could not fail on this document - no page here
holds a `Total assets ...` line and no page states a single side - so those two live in
`tests/p154` on statements written for them, and C85's docstrings say what the filing can and
cannot see. A checkpoint that reads as though it covered more than it does is the same defect
as a test that asserts nothing.

## B-124 A scanned statement read as nothing, with every figure on it read correctly
status: fixed (P155)
2026-10-03. CLAUDE.md has said since P24 that **every PDF this firm's clients send is a
scan**, and `AA_OCR_ADAPTER` has existed to answer that since P74. Measured with the engine
configured, on page 56 of the public filing - the consolidated balance sheet - rendered to an
image and wrapped in a PDF with no text layer:

| | text layer | the same page scanned |
|---|---|---|
| lines | 61 rows | 122 fragments |
| tables | 3 | **0** |
| figures with a locator | 61 | **0** |
| footings that re-add | 10 | **0** |
| states both sides | yes | no |

**The engine was not the weak part.** Over pages 55 to 63 `rapidocr` read **295 of 296**
printed figures and invented none. All of it was thrown away. The OCR port returned text and
nothing else, and an engine returns a **cell** at a time - `Total assets`, then `521,728`,
then `608,846`, as three fragments - while the reader's line-based row builder wants one line
carrying a label and all of its figures. Nothing between the two reassembled them, so the
main inbound path for this firm extracted nothing at all.

Tesseract escaped it by grouping into lines itself, which is exactly the "second row-builder"
the port's own docstring warned against - and is why the two engines disagreed about what a
row is while nothing could tell. `rapidocr` is the one that matters: it is a wheel with its
models bundled, so it is the one a managed laptop can install without asking anybody.

**A row is a band of the page and a column is a band too**, which is what P151 built for a
text layer. Everything in `intake/readers/layout.py` below `lay_out` is geometry and knows
nothing about PDFs, so `lay_out_words` is public now and both paths come through it. A scan
and a text layer agree about what a row is for the reason they agree about anything: there is
one implementation of it.

**The unit is the adapter's job**, because only the adapter knows what it rendered at. The
tolerances are absolute points calibrated on a real page; an engine measures in pixels of
whatever it was handed. Page 56 is 594 by 774 points and was rendered to 2475 by 3226 pixels,
so unconverted boxes would be grouped at a seventh of the intended tolerance and find
nothing. Divided by the render scale the adapter chose, the figure columns land at 482.6-486.5
and 549.9-553.4 - the two columns P151 measured at x=482 and x=549. An image states no page
size at all, so there the page is scaled by what its own text measures against `TEXT_HEIGHT`
and the page says `geometry="estimated"` rather than letting a guess read as a measurement.

**Two more defects had to go, and neither was the one planned for.**

The engine returns `$` as its own fragment, and in its own detection order it came *first* -
so the label was `$ Total assets`, the exact match in `two_sides` failed, and the balance
sheet stopped stating its two sides. The rule is positional now ("a lone mark to the right of
every other label word"), after two wrong attempts that the harness caught: taking it off the
end of the *list* only ever worked on words already in reading order, and sorting the list by
position was worse, because a band spans a label that wraps over two lines and sorting by `x0`
interleaves them into nonsense. Dropping the mark wherever it appeared was wrong too -
pdfplumber splits `$0.001` into two words at this tolerance, so `Common stock, $0.001 par
value` lost its par value and the row stopped being findable. **It was hiding four real
totals on the text layer**: `is_a_total` asks whether a label *begins* with the word total, so
`$ Total property and equipment, net` was not one. Page 75 in both years and page 104's two,
all four re-adding exactly, now covered - 69 over plain lines where there were 65.

And `_is_figure` was asked of a whole word to decide whether a band belongs to a table, which
is right for a text layer and wrong for a fragment. `Common stock, $0.001 par value,
authorized 220,000 shares; shares issued 145,581 and` is not money-shaped, so that band read
as prose, the table never started over it, and the two figures printed on the row - 146 and
136 - were taken for the *names* of the next table's columns. That is the row this reader is
most careful about: before P151 read coordinates it stored **220,000**, the authorized share
count, as the common stock balance, and it passed provenance and footing both. Where a table
*is* and where its columns *are* are two questions now: the first may reach inside a word, the
second may not, because three phrases ending level would put a column wherever sentences stop.
The filing cannot show that second half - `COLUMN_NEEDS` wants three figures sharing an edge
and one phrase cannot make a column alone - so it is held by a page written for it rather than
left as a rule nobody can check.

**The result.** The same page scanned and from its text layer gives the same 3 tables, the
same 61 rows, the same figures, the same 10 footings, and `Total assets` of 521,728 against
521,728. Letter for letter the labels are identical; 4 of the 61 lose a space inside a
fragment, which is a difference in spacing rather than in the statement.

**A screenshot is a document now too.** `.png`, `.jpg`, `.tiff`, `.bmp` and `.webp` were
`kind="other"` and reached no reader at all, which is most of what arrives after a phone call.
An image is a page with no text layer - the same thing a scanned PDF page is - so it is one
page handed to the same seam, and `looks_like` had to be ordered after the image branch or
every screenshot is refused as the very thing it is. With no engine it is an empty page
reported as scanned, which is the reader's standing promise rather than a new rule.

**The engine is replayed, not run.** `rapidocr-onnxruntime` is deliberately not in
`pyproject.toml` - it would put an ONNX runtime into every clone and every container that
never reads a scan - so a test needing it would fail on a clean one. What it read off page 56,
boxes and all, is in `fixtures/public/ocr-sec-ars-3d-systems-p56.json` in the engine's own
unit, which makes the conversion proved rather than assumed. Twelve breaks, twelve reds; three
of them passed on broken code first. One was a test that could not fail - removing `.png` from
the declared table left it green because this host's `mimetypes` happens to know PNG, and does
not know `.webp`, which is the measurement showing the table is load-bearing.

## B-125 A document that would not open was a traceback about a stream
status: fixed (P156)
2026-10-03. Two branches of one function, and only one had been written to answer the
question. `intake/readers/__init__.py` catches everything the workbook reader can raise and
raises `INTAKE.UNREADABLE_FILE` naming the file - *"a zero-byte file, a text file with the
wrong extension, a workbook still being written, an encrypted one. None is a pass that
failed; each is a file that cannot be read, named, so the person replaces it."* The document
branch caught only `NotText`. Measured:

| what was sent | what came out |
|---|---|
| a truncated PDF | `PdfStreamError: Stream has ended unexpectedly` |
| a corrupt `.docx` | `BadZipFile: File is not a zip file` |
| a truncated PNG | `UnidentifiedImageError: cannot identify image file` |

None names the file. **And it was worse than a confusing message**: run through the real
server, the run was left in `running` with `worker.failed - attempt 1 raised PdfStreamError`,
holding the client's lock - which is the exact thing `_halt`'s own comment says it exists to
prevent. With the fix the same case ends `halted`, with the file named, and no findings.

Clients send these constantly: a phone photograph that stopped uploading, a PDF saved from a
browser that was still printing, a `.docx` copied off a share mid-write. P155 made the third
row possible by routing images at all.

**The two answers stay apart, because the thing to do differs.** A format this build routes
and does not read is `FORMAT_NOT_READ` and means *save it as something else*; a file that
will not open is `UNREADABLE_FILE` and means *send it again*. Collapsing them would tell half
the people the wrong thing, which is worse than a traceback - a traceback at least looks like
a problem. Both end with the file arriving again, so that phrase is not what separates them;
what separates them is what somebody does first, and only one mentions saving it.

A truncated image with **no** engine configured stays an empty page reported as a scan,
because nothing opened it and nothing can therefore find it broken. It is only a refusal on a
machine that has an engine, which is the machine doing real work.

## B-126 The rehearsal case called `pdf` had never read a PDF
status: fixed (P157)
2026-10-03. Measured by printing every `intake.read` event per case: the `pdf` case reads
three files and **all three are `.xlsx`**. Its document was called `Statements.pdf`, and a
name carrying no document-type token is *held* by the binder rather than bound - so it reached
no reader at all. Three runs on three workbooks, green since the rehearsal was written.

Two things were wrong and each hid the other. The bytes were not a PDF either: pypdf raises
`PdfReadError` on them. Nobody had met that error because nothing ever opened the file. A
fixture that cannot be opened is not a simpler fixture; it is a different test, and here it
was a test that proved the opposite of what the case was named for.

**Three times now, the same shape.** B-121 was a CSV refused while the case passed, because a
halted run has reached an ending and nothing asked whether the refusal was right. The
`half-sent` case added in P156 read as a pass until its file was renamed - it ended
`quarantined` with the fix and `quarantined` without it, and the events showed `intake.read`
had succeeded, on the workbooks beside the file the case was about. And this. Each time the
rehearsal judged a case by whether its run finished, and each time the file the case was
*about* was never looked at - which is invisible in an ending, because the other files in the
folder are fine and the run ends on them.

So `MUST_BE_READ` names the file each such case exists for and makes the case a finding when
no `intake.read` event names it, `ONE_FILE_IS_UNREADABLE` is its other half for a case whose
file is meant to be refused, and each finding says what the run *did* read rather than
sending somebody to the events by hand. The `pdf` case now carries a trial balance printed on
a real PDF, and reading it yields the three rows.

`tests/p157` holds the same claims **statically**, which is both faster and stricter: whether
a filename will bind is answerable from the name and the conventions, so the next case added
is checked before it is ever run. It also found that two cases - `partial` and
`changed-after` - existed only as string literals in the middle of the sweep, because they
need the clock; they are named in `INLINE_CASES` now, so something can list them.

## B-127 A letter standing in for a digit made a row vanish, and nothing said why
status: fixed (P158)
2026-10-03. Measured on page 56 of the public filing read by a real engine: the printed
**5,000** came back as **`5,0o0`** - a zero read as the letter o - **at 0.938 confidence**.
Too high for any score to flag, which is this build's own stated thesis about OCR.

The usual answer to a misread here is arithmetic, and it is a good one: a total that stops
adding up is what finds a figure read *wrongly*. This misread produces no figure at all, and
what happens next is why it needs its own check. Through the reader:

    Inventories l27,496   ->  label '', values []

The whole row goes, label and all. That is the safe direction - nothing wrong is stored - and
it is **silent**: the statement quietly loses a row, the total above it stops footing, and the
only thing a person is told is that some total is out by an amount nobody can account for. The
amount it is out by *is* the row that went missing.

So a token shaped like a figure but for its letters is named, with the line it sits on,
through the same report a footing reaches a person by. **It reports and never repairs**:
substituting the digit would be this code guessing at a client's figure and producing a
plausible number, carrying a real locator, that the document does not print. `reads_as` is
offered because it is the first thing anybody wants to see, and it is a **string**, never a
float, so nothing downstream can total it.

**Calibrated against text nobody misread**, over all 108 pages - 58,606 tokens - where it
reports nothing. Three decisions came out of that measurement rather than out of taste:

* the **two-digit floor** stays: without it the rule reported `1B` and `9B` on four pages,
  which are billions written the way people write them;
* **`D` for zero** went: a real confusion on a photocopy, and it reported `21D` twice -
  *"contribution under Section 10(b) and 21D of the Securities Exchange Act"* - in a filing
  belonging to a company called 3D Systems. Two findings out of three that are not findings
  is the ratio this repo takes a check out over (B-086, the Oxford comma);
* a **one-letter rule** went, and for the opposite reason. It was in on the reasoning that a
  token with two letters is a word rather than a near miss; measured, it changed **no answer
  at all** on either input, which is the state P151 removed `COLUMN_SHARE` in. It was also
  wrong about what it excluded - `1O,5O0` is two digits misread in one figure, an ordinary
  photocopy, and it was skipping that in silence. What actually keeps a word out is the digit
  floor, which the test for the one-letter rule had been passing on the whole time.

## B-128 Four formats a client sends reached nothing at all
status: fixed (P159)
2026-10-03. `.ods`, `.xlsb`, `.eml` and `.msg` were `kind="other"`, which routes nowhere. The
file was listed in the manifest and then nothing read it, nothing said why, and nobody was
told what to do - the worst of the four possible answers, because it looks like success.

**An `.ods` is read**, through the conversion seam `tabular.py` already had: a `.csv` and an
`.xls` are turned into a workbook at the door so everything above goes on reading a workbook,
including the `Sheet!A1` locator a figure cites for as long as the figure exists. `odfpy` is
pure Python and brings `defusedxml`, which is the right dependency to gain on a path that
opens a client's file - an ODS is a zip of XML and XML from outside is where entity expansion
lives.

The care is in the cells, and it is the same care the CSV path needed for the same reason. An
ODS carries a cell's **type and value** separately from the text it displays, and the type is
what to read: LibreOffice writes `1.234,5` or `1,234.5` into the display depending on the
locale the file was saved in, and parsing that back would reinvent an ambiguity whose two
answers are both plausible figures. So there is nothing to report as ambiguous here - a number
in an ODS is a number and was never text. A repeated empty cell is also expanded, because an
ODS writes a run of them as one cell with a count, and dropping the count shifts every figure
on the row to the left.

**An `.eml` is read** as the message it is, so an instruction in an email meets the same
Untrusted Content Boundary as an instruction in a letter - and **its attachments are named,
not extracted**. Extracting one would make a file out of a file, and every guarantee
downstream rests on a `source_id` that is the hash of something a person put in a folder: a
figure citing a row inside an attachment that exists only inside another document has a
locator nobody can open. Naming them is the sentence somebody can act on.

**An `.xlsb` and a `.msg` are refused by name.** Both binary, both with readers in the world,
and no real example of either on this machine to measure one against - the `.doc` decision
again, because a half-working parser for a binary format produces plausible *partial*
content. A `.msg` is also OLE2, so leaving it to `looks_like` would have called it a Word
document, which is the wrong advice entirely.

One thing had to change shape for that to be sayable. `READ` held only *document* types, so a
spreadsheet format nobody reads was indistinguishable from one that is read: an `.xlsb` passed
every check and was then handed to openpyxl, which said it **"cannot be opened as a
workbook"** - perfectly true, and the wrong thing to do about it, because nothing is wrong
with the file. `READ` covers both kinds now, and C85's routing check was asking two separate
membership questions where it needed one equality.

Two of my own near misses, both caught by the harness. The refusal first read `row.mime`,
which is right in production and `application/octet-stream` for any caller that does not fill
it in - so a perfectly readable `.ods` was refused; it goes through `mime_of(row.filename)`
now, which is the same function the fingerprinter used and therefore a stronger way to have
the same answer than a copied value. And a `.ods` added to the rehearsal's readable set
without a case behind it was caught by `tests/p157`, which is the test B-126 put there.

## B-129 A function nothing had called since P151, kept alive by a test
status: fixed (P158)
2026-10-03. `_split_figures` in `intake/readers/documents.py` turned a line into its label
and its figures. P151 moved that work into `_tables_from_lines`, inline, and left the
function behind - so there were two implementations of what a row is, one of them dead.

Found by a revert harness. Breaking the function to repair a misread into a figure left the
test green, which can only mean the test was not on the path. A grep then showed
`_split_figures` appearing exactly three times in the repo: its own definition, and twice in
the P158 test I had just written - so **the test was the only thing keeping it in the tree**,
which is this repo's named defect with a test propping it up.

The reachability scans do not catch this one: `tests/p71` fails on a *public* function nothing
calls, and a leading underscore puts this outside it. Worth noting rather than fixing, because
widening that scan to private functions would fire on every helper a module calls only from
one place, and a scan whose findings are mostly not findings is the thing B-086 was taken out
over.

The function is gone, and the P158 test asks `read_document` instead. Doing so measured
something the helper could not have: a line carrying no figure **breaks the run of lines that
do**, so the row above a misread is lost as well. One letter costs two rows, which is a
stronger reason for the check than the one the phase was written on.

## B-130 Nothing checked the cash, and footing has nothing to say about it
status: fixed (P160)
2026-10-03. Three tie-outs matter to a reviewer and this build had two. `footings_in` re-adds
a column; `two_sides` compares the two halves of a balance sheet; the cash roll-forward -
beginning plus the net change against the stated ending - had nothing producing it.

Measured on page 59 of the public filing, which the reader already parses into five tables
and ninety-eight rows. All three columns reconcile exactly, and each year's ending is the
next year's beginning:

| column | beginning | net change | ending stated |
|---|---|---|---|
| FY2025 | 172,881 | (75,781) | **97,100** |
| FY2024 | 333,111 | (160,230) | **172,881** |
| FY2023 | 391,975 | (58,864) | **333,111** |

**The argument got stronger when C89 asked it from the outside.** The phase was written on
the claim that a cash flow statement's subtotals all foot and merely fail to cover the ending
cash, because the ending is stated rather than summed. That is wrong: **footing finds no
totals on that page at all.** `is_a_total` reads what the statement calls a row, and not one
line on a cash flow statement begins with the word total - they are `Net cash provided by
operating activities` and `Net decrease in cash, cash equivalents and restricted cash`. So
every figure on that statement was uncovered by construction, which is the state P99 found
the whole build in, and this is the only arithmetic there is over it.

**The same measurement says which check not to write.** The obvious fourth one is that the
ending cash equals the balance sheet's cash line, and here it does not: page 56 says **95,635**
where page 59 says **97,100**, because the cash flow line reads *cash, cash equivalents and
restricted cash*. The difference of 1,465 is the restricted cash, both statements are correct,
and a check comparing them would open every engagement by reporting a discrepancy on a
document with nothing wrong with it. Not made, and the figures are written into
`CashRollForward` so the next person to think of it finds the measurement rather than the idea.

It speaks about one page in a hundred and eight, which is the calibration.

Two of my own, both from the harness. A `len(stated) < 2` guard on the column chain changed
no answer in any case, because with one column the pairing below it runs no times - the state
P151 removed `COLUMN_SHARE` in, so it is gone. And C89's first draft pooled every table on a
page into one list, which collides the ordinals footing depends on and made `Total current
assets` come back with a part whose value was `None`. The three checks are given **different
groupings on purpose** - a footing's run is a block's, and a balance sheet's two sides are in
different blocks because the reader starts a new one at every heading - and the test says so
now rather than flattening them.

## B-131 Accuracy had no answer in this build, only evidence
status: fixed (P161)
2026-10-03. A total that re-adds and a balance sheet that balances prove **arithmetic**, and
arithmetic is satisfied by eight wrong rows that add correctly - `guards/tieout.py` says it of
its own half: *"Tie-out proves arithmetic, not selection."* So "is every figure right" had
never been answerable, and every claim about extraction rested on one document that had been
read until it read correctly.

**The SEC publishes the filer's own numbers as structured data.** Every figure on these
statements is tagged in XBRL and served from `data.sec.gov`, so `Assets` at 2025-12-31 is
521,728,000 - which is the 521,728 on page 56 times the thousand the statement says it is in.
Ground truth, from the same regulator, for the same filing.

**No label-to-concept mapping is needed**, which is the part that would have made this hard.
`Accounts receivable, net of reserves` could be `AccountsReceivableNetCurrent` or a filer's
own tag, and guessing would make the comparison an opinion. The question is not which concept
a row is - it is whether every figure the reader produced is one the filer reported **at the
date that column is as of**. A figure out of the wrong column is still a figure the filer
reported, and that is B-030, this repository's worst extraction defect; matching by date is
the only thing that sees it. Proved by declaring the columns backwards, which turns 61 right
figures into 55+ reported as out of the wrong column, and by reversing the layout reader's
columns - B-030 itself - which makes the check fail.

**What it says, over three filings and two filers:**

| | |
|---|---|
| right, at the column's own date and the statement's scale | **194** |
| right, but only at another scale | 2 |
| **reported at a different date - out of the wrong column** | **0** |
| not in this feed, so not checkable | 3 |

The number worth having is ResMed's, because the reader had never been run on that document:
**70 of 70 at the right date**, both columns balance, eight footings re-add. The 3D Systems
filing was read until it read correctly, which is how it should be and is why its score says
less.

Three documents were added with their provenance: a second ARS PDF from a different filer
(fiscal year ending 30 June, 124 pages), **EDGAR's own `Financial_Report.xlsx`** - a workbook
of real statements laid out by the regulator rather than by openpyxl - and the trimmed XBRL
facts for each.

**It is offline.** The facts are committed under `fixtures/public/filer-facts/`, trimmed to
the dates each filing's statements are as of, because a tool that needed `data.sec.gov` would
answer differently on a train and a test that needed it would fail for a reason that is not
about the code. `--fetch` is the one networked path.

**What it cannot see** is in its own docstring, because a measurement whose limits are not
written down gets quoted as though it had none: `companyfacts` serves the *dimensionless*
facts, so a figure tagged only against a segment or a share class is absent and is a figure
this cannot speak about rather than one the reader got wrong. It compares figures and not
words, so a label read wrongly is invisible. A right figure in the wrong row would pass.

Two of my own, both caught by the harness. The summary closed with *"every figure matched a
figure the filer reported at its own column's date"* while five had matched nothing, which is
the kind of sentence that gets quoted. And the first draft had three answers where there are
four, so the defect below was reported as *"no fact in this feed"* - a limitation of the data,
reading as nobody's fault.

## B-132 A figure not in the statement's unit carried the statement's scale
status: fixed (P162)
2026-10-03. Found by `tools/check_against_filer.py` on EDGAR's own workbook, where a figure
matched the filer exactly and **only without the scale**:

    Common stock, shares, issued (in shares)        135,361,000   in the cell
    Common stock, par value (in dollars per share)        0.001    in the cell
    ... and every dollar figure on the same sheet in thousands

The scale is per *file* - `SourceFile.scale`, applied to every row of it - and
`harness/procedures/ebitda_normalization.py:366`, `deliver/workpaper.py:178` and
`harness/restate.py:89` each multiply a figure by its scale. So the share count is reported as
**135 billion** and the par value as **$1.00**. Both are plausible numbers, which is exactly
why nothing downstream catches either: the total still foots, the balance sheet still
balances, and the figure cites a locator that resolves.

**The statement says so itself.** ResMed's balance sheet is headed *(In US$ and in thousands,
**except share and per share data**)*, and EDGAR writes the exception into each row's label.
Reading that is not guessing - it is what `two_sides` does with the two labels a balance sheet
writes and what `is_a_total` does with the word *total*.

**The contract was built for this and had never been exercised.** `figure.schema.json` has
carried `"unit": {"enum": [..., "shares"]}` since P02, allows a scale of 1, and *forbids* a
currency code on anything that is not currency. The producer only ever wrote `"currency"`.

**Calibrated over 2,373 rows** - every row carrying a figure on 108 pages of one filing, 124
of another and every readable sheet of the workbook. 53 rows declare a unit, over 22 distinct
labels, and every one of them is genuinely not in the statement's unit. The rule stops at a
parenthetical, and the two looser rules are not merely weaker but **harmful in the other
direction**:

* adding `par value` and `shares issued` takes `Common stock, $0.001 par value, authorized
  220,000 shares; shares issued 145,581 and`, whose figure is **146** - a real $146 thousand
  - and declares it not currency, so the scale stops applying to a figure that needs it;
* matching any mention of a share also costs `Taxes paid related to net-share settlement of
  equity awards` (-1,025) and `Treasury stock, at cost, 46,798,043 shares at June 30, 2026`
  (-2,778,591), both ordinary dollar amounts.

The end-anchor came off for the same reason it went on - measurement. It missed four, and all
four were real: `Beginning balance (in shares) at Dec. 31, 2023` declares its unit and then
qualifies it with a date, and that is a share count of 133,619,000. Relaxing it over the same
2,373 rows added exactly those four and nothing else.

**It does not bite on a PDF**, which is why one document could not have found it: a typesetter
keeps the share count inside the label and every figure in the column is a dollar amount. All
53 declared rows are on the workbook - and a client's workbook looks far more like a workbook
than like typesetting.

**Rows that disagree keep the file's scale and say so**, on the trail. Summing a share count
with a dollar amount is meaningless at any scale, so there is no right answer to pick; what
there is is a fact somebody needs, and the figure stays as the file said so a disagreement
cannot quietly change one.

The known limit is recorded rather than left to be discovered: a row that is a share count and
says so only in words is missed. `Entity Common Stock, Shares Outstanding` at 136,412,866 is
the one such row in three filings, on a cover page rather than a statement.

My third exit criterion was wrong and `gate amend` carries the correction: I expected the
check to stop reporting those two rows, and it correctly goes on reporting them. It reads the
readers' *rows*, which hold the cell value as the file wrote it, and the fix is at the
**figure** built from them. And the harness found that every test called `_unit_of` directly,
so breaking the **call site** in the figure assembly left all of them green - a unit rule with
tests on the rule and none on the wire, which is this repository's most repeated defect wearing
a new hat.

## B-133 The years printed above a statement's columns were thrown away
status: fixed (P163)
2026-10-03. `layout._tables` kept `heading_band = last_plain_band` - the most recent band
with no figure in it - and handed that to `_headings` when a run of figure rows began. On a
real statement the date header is **never** the last plain band: `ASSETS`,
`Current assets:`, `Non-current liabilities:` and `Cash flows from investing activities:`
always sit between the header and the first figure row, and overwrote it. By the second
block of a balance sheet the header is five bands up.

`_headings` was already positional and already places the dates correctly when handed the
right band - its own docstring predicted that the `(in thousands)` prefix would be three to
four hundred points away and lose, and it is. **And the consumer was already wired:**
`periods.py` collects the tables that carry more than one column and name none of them, and
that cue is why `settled` was False on *every* real statement - `0 of 3 tables name their
columns` on 3D's balance sheet, `0 of 5` on ResMed's. So a comparative statement escalated
to a person on every filing, forever, for want of a band two bands further up.

The detector was right about everything else, which is what made this worth finding: scale
1,000, currency USD, fiscal year end month 12 and **6** (ResMed's June year end), and both
period ends exactly. It reports those ends **sorted ascending**, while a statement prints the
current year first - so anything that mapped them positionally would date every column a year
wrong.

**Measured over 232 pages, 119 multi-column tables: 48 named today, 118 under the new read -
70 gained, 0 changed, 0 lost.** Per filing: 3D 72 tables and 815 rows unchanged with named
going 27 -> 45; ResMed 70 tables, 960 rows, 59 named. The figures do not move - this writes
column headings and touches neither the columns nor the rows - and
`tools/check_against_filer.py` still reports the same 194 right and 0 out of the wrong column.

**The wider rule was refused on measurement, not on taste.** "The nearest band above whose
words could name the columns" gains the same 70 and four of them come out of a sentence:
`The following table sets forth the Company's operating working capital at December 31, 2025,
and 2024.` crosses all three columns and offers `December`, `2025,` and `2024.`. Nothing
separates that from a header either - over all 118 candidate bands the share of a band's
words sitting at a column is **0.38** for that sentence and **0.50** for the legitimate
header `(in thousands) 2025 2024`, so no cut keeps the one and refuses the other. A threshold
that does not separate is one this repo has removed twice already (B-086, and P151's
`COLUMN_SHARE`). A bare year is not prose, and the punctuation on `2025,` is the whole of the
distinction.

## B-134 A column the page prints and the table never built, so figures land a year out
status: fixed (P163) - detected and reported; the column is still not read
2026-10-03. `_columns` establishes a column only from **money-shaped** figures
(`_ESTABLISHES`: comma-grouped, or a parenthesised decimal), and keeps a right-edge cluster
only when at least `COLUMN_NEEDS = 3` of them are in it. A column whose figures are mostly
small or nil falls short, is never built, and **every figure to its right then sits at a
column index belonging to another year**. That is B-030, this repository's worst extraction
defect, reached by a new route.

**3D Systems page 59, the investing block.** Its 2024 column holds `(16,121)`, a dash, `96`
and `(3,000)`. `96` is four figures short of needing a comma and a dash is nil, so two
figures establish the column where three are needed. The table is built with two columns
instead of three, three figures are lost, and 2023's land where 2024's belong.

**The filer says so, in its own words.** `ProceedsFromDivestitureOfBusinesses` is **96** over
2024 and **194** over 2023. The page prints `Proceeds from sale of assets and businesses, net
of cash sold 122,681 96 194`; the reader dropped the 96 and put the 194 at column index 2.
The same concept, in the same table, read off by a year - with both years in the feed to
prove it. Three more land the same way: `-27,183` is
`PaymentsToAcquirePropertyPlantAndEquipment` over 2023, `180,925` is
`ProceedsFromSaleAndMaturityOfAvailableForSaleSecurities`, `-29,152` is
`PaymentsToAcquireBusinessesNetOfCashAcquired`.

Found twice over, independently and from opposite ends: by checking the figures against the
filer's XBRL at each column's date, and by noticing that the table's dated years are **not
consecutive**. The second is what became the guard, because it needs no XBRL: a two-column
table dated 2025 and 2023 under a header reading `2025 2024 2023` says a column between them
was never built. Two tables over 232 pages - p59/t4 and p104/t1 - which is the honest
frequency and exactly the frequency that matters, because rare and silent is the combination
nothing catches.

**Why the balance sheets never exposed it:** every table on those pages carries the
statement's full column count. It took a cash flow statement, where a section is nearly all
nil and small amounts.

**And this is why naming the columns is dangerous alone.** Naming them is what lets the rest
of the page settle, so a table that dropped a column would now settle **on a wrong date**.
The same read does both, and the gap keeps the page escalating.

**Reported, not repaired.** Rebuilding the missing column is a guess; saying its indices
cannot be trusted is a fact. Reading the column is left open: the honest fix is to let a
cluster beside an established column, at the statement's own column spacing, count the things
that may *fill* a column rather than only the things that may establish one - and that needs
its own calibration, because `_ESTABLISHES` and `_FILLS` are deliberately different and the
reason is written where they are defined.

## B-135 The restater reads a figure's scale and ignores its unit
status: proposed - **live today**, and it is B-132 one stage later
2026-10-03. P162 stopped the statement's dollar scale being applied to a share count, by
giving such a figure `unit: "shares"` and `scale: 1`. `harness/restate.py` then divides it
anyway. The word `unit` does not appear in that file: `restated(figures, to_scale)` reads
`scale` alone, and `workers/driver.py` calls it over every figure bound to the model.

    135,361,000 shares at scale 1, into a template declaring thousands  ->  135,361

And the figure comes back as `{**figure, "value": after, "scale": to_scale}`, so it now says
`unit: shares` and `scale: 1000` together - a share count claiming to be in thousands.

**The refusal for this already exists and the division is what stops it firing.**
`deliver/builder.py:247` refuses a figure whose scale is not the template's, with the right
sentence - *"restating is arithmetic and does not happen in the writer"*. A shares figure
left at its own scale would hit that refusal and reach a person. Moving it silently is what
makes the guard unreachable.

The general shape, which matters more than the instance: **`unit` is read by two lines in
the whole repository and both ask only "is it currency?"** (`deliver/builder.py`,
`tools/normalize.py`), while six lines across three modules multiply a figure by its scale -
`deliver/workpaper.py:178`, `harness/procedures/ebitda_normalization.py:246`, `:366`, `:428`
and `harness/restate.py:89-90`. So the fix is not a patch to the restater. It is **one place
that turns a figure into a number, and it asks the unit** - the same argument as "no second
answer", applied to arithmetic. Note also that `units.py:10` and B-132 say "three places"
and name three line numbers; there are six lines, which is the count that matters when the
fix has to reach all of them.

## B-136 Nothing asserts a sign, so a wholly flipped column foots perfectly
status: proposed - the highest-value missing check found this session
2026-10-03. All three tie-outs were run against correct input and against the same input
wholly negated, and **all three pass both ways**:

* `footings_in`: rows -12,000 and -3,000 under a total of -15,000 reports *"all 1 total(s)
  re-add"*; so does +12,000, +3,000, +15,000.
* `two_sides`: -521,728 against -521,728 reports *"the two sides agree at -521,728.00"*.
* `cash_roll_forward`: 100,000 / -4,365 / 95,635 flipped rolls forward to -95,635.00.

**A cash flow investing or financing section is all-negative**, so a column read with every
sign inverted foots exactly. And arithmetic cover is precisely what stops a person looking:
`review/router.py:172` sends a figure to review when `not item.arithmetic_cover`. So the
acceptance rule the analyst gave - *a figure is proved by arithmetic, or it is seen* - is
satisfied here by a proof that proves nothing, and the figure is neither.

What would catch it is a statement about the table rather than about its arithmetic:
`Total assets` is not negative, and a row labelled `Net cash **used** in investing
activities` is not positive. Nothing anywhere looks. Related: `tools/statement_checks.py:161`
takes `abs(amount)` for a CONTRA line and, unlike the MINUS and PLUS branches, does not
increment `negative_fixed` - so a contra account read with the wrong sign ties perfectly and
is not mentioned in `_sign_note`.

## B-137 A footing certifies a total across two unrelated statements, and certifies a row with no label
status: proposed - a false proof, which is worse than a missing one
2026-10-03. Two ways `footings_in` grants arithmetic cover to figures it has not proved.
Both matter for the same reason as B-136: cover is what stops a person looking.

**It walks through a blank row.** `normalize_workbook` makes one block per *numeric column*,
so an income statement and a balance sheet stacked on one sheet with a blank row between
them become one block, and `footings_in` skips rows whose value is `None` and carries
`standing` straight across. Measured: `Total assets 8,000` was reported as re-adding *"the
subtotals and the lines above it"* from the **income statement's** `Total expenses 3,000`
plus `Cash 5,000`. `covered_rows` 4 of 5, `did_not_foot` empty. Nothing on the balance sheet
adds to 8,000. `tools/formula_audit.py` already has a `total_crosses_a_blank_row` check, so
the reviewer tool knows a blank row ends a block and the reader does not.

**It certifies a row that has no label.** Merging `A2:A4` over the label column gives rows
`{label: "", value: 60000}` and `{label: "", value: 18400}`; `Total officer comp 318,400`
re-adds over all three and nothing is flagged. Two figures bound for an input workbook with
no idea which line they are, holding a certificate. `ws.merged_cells` is available and
openpyxl is already read in non-read-only mode; an empty label on a row carrying a value is
also a one-line refusal.

## B-138 A spreadsheet with two decimal conventions reads a figure a thousand times out, silently
status: proposed
2026-10-03. `intake/readers/tabular.py::_convention` takes the **first** regex class that
matches anywhere in the file and applies it to every cell, including the cells that
contradict it. The `ambiguous` reporting path is behind `if not decimal:`, so a file that
settles on a convention reports nothing at all.

    1.234,56 then 402,000   ->  402.0        (should be 402,000)
    1,234.56 then 1.234,56  ->  1.23456      (should be 1,234.56)

Both silent: `ambiguous` empty, no finding, and no total over them to break. The module
already has the sentence for this - *"the file is telling two stories"* - and applies it only
to the grouped-only branch. If `_US` and `_EU` both match anywhere, the file decides nothing;
and a cell that does not parse under the settled convention belongs in `ambiguous` rather
than being reinterpreted. Same family, a different reader: `documents._number("1.234,56")`
returns **1.23456** and has none of this machinery, so a European figure in a `.txt` or a
Word table is wrong by a thousand with nothing to say so.

## B-139 The reachability walk lets dead code vouch, and one allowlist reason is false
status: proposed - the scan, not the allowlist
2026-10-03. `tests/p82`'s `vouched_for()` applies its fixpoint **only to package
`__init__.py` files**. Every import made by any other module counts as evidence that the
imported module is reached, whether or not the importing module is itself reachable. The
docstring explains at length why an `__init__` has to earn the right to vouch - `report/`, a
whole package, passed that way once - and then exempts every other module from the same test.

Running p82's own collectors with the fixpoint over *every* module reports **18** unreachable
modules where p82 reports 11. The seven it hides, each imported only by dead code:
`governance.adapt`, `governance.drop`, `governance.registry`, `governance.sandbox`,
`governance.shadow`, `orchestrate.manifest`, `privacy.unmask`.

The worst is `governance/registry.py`, whose own docstring opens *"The Skill Registry: the
only way a skill becomes live, and the single writer to the tree... This is the one edge from
governance back into the live system."* Nothing can reach it, so no candidate skill can be
published. And the allowlist's stated reason for `governance.chain` is **false**: it says
production reaches the chain's steps by hand, and five of the nine - adapt, drop, registry,
sandbox, shadow - are invoked by nothing. `privacy/unmask.py` is the inversion these scans
exist to prevent: B-043 already records in words that it is unreached, and the scan does not
see it.

**Two excuses rest on a premise the build invalidated at P101.** `privacy.verify` and
`deliver.workpaper` are both excused on *"no run has reached release at all"*; all four
recipes have a `release` step and `valuation-input-prep` ends at one. B-077 records this and
carries no `status:` line; the same stale sentence is also in `workers/driver.py`'s docstring
and in a comment beside it. p82's decay tests check the module, the item id and the item's
status - **not whether the reason is still true**, which is the thing that went stale.

Also unscanned by either walk, and found by hand: a method of a live class that nothing calls
(`AdminConsole.edit_watch`, whose only reference in the repo is its own `def`, while
`add_watch` refuses with *"watch exists; edit it instead"*), a dataclass field written and
never read (`Line.confidence`, whose docstring claims *"it reaches a person through the review
surface"*; `RegisteredTemplate.binding_layer`; `LLMResponse.request_id`, fetched off the SDK
response and dropped), and an HTTP route no page reaches - ten of those, including
`POST /api/admin/report/start`, which is the first half of a shipped feature and has no button.

## B-140 A scan that read nothing is not reported as a scan
status: proposed
2026-10-03. `ParsedDocument.scanned_pages()` exists, is documented as the honest answer to
"was there a text layer", and is called by **nothing but `tests/p17`**. `ReadReport` has no
field for it and the `intake.read` event payload does not carry it. So with no OCR adapter
`Trial balance.png` records `0 block(s) written; trial_balance (0.83)` - confident, no review
item, and indistinguishable from a readable file that happened to hold no figures. On a
machine doing real work that is the default state of most inbound PDFs, and CLAUDE.md's rule
is that a page yielding nothing is reported rather than filled in.

Same class, same path: `Line.ocr` is wired through to the misreads payload, and
`ops.source_parse.Row` has **no `ocr` field** - so a figure OCR'd off a scan is stored
identically to one lifted from a text layer, which is exactly what the acceptance rule turns
on. And there is no outcome code for *readable, and yielded no figures*: a source that
produced zero blocks is checked nowhere downstream.

## B-141 A non-negotiable with no test
status: proposed
2026-10-03. CLAUDE.md lists eleven non-negotiables and says *"each one is an invariant with a
test behind it."* Ten have one. **"No Excel, COM, VBA or Power Query anywhere" has none.**
Nothing in `tests/` looks for `win32com`, `xlwings`, `comtypes`, `pythoncom`,
`Excel.Application`, `keep_vba`, VBA or Power Query, in any file type; `tests/p28` covers
cloud SDKs, not Excel automation; none of the 25 architecture invariants is about it. The
rule exists as one sentence in one docstring, `tools/write_template.py:14`.

This is the shape P120 was written to eliminate - *"guards that were checked by looking for a
word"* - except there is not even a word being looked for, which is why P120's audit did not
find it. (The list also has eleven items and CLAUDE.md calls it ten.)

## B-142 Counts and commands in the documentation that no longer hold
status: proposed
2026-10-03. Found by checking every command line, number and named path in the documentation
against the code. The ones a reader would act on:

* **`docs/USING.md:369`** - the sentence that teaches the `python -m uv run` rule now states
  the opposite: *"A bare `python -m uv run python tools/serve.py` works only in a shell where
  the virtualenv is already activated"*. It was written correctly and a later commit pasted
  the prefix onto every `python tools/` in the file, including the negative example.
  `tests/p58` cannot see it, because p58 enforces exactly the thing that broke it.
* **"Eight checks in three severities"** - `tools/formula_audit.CHECKS` has **9**
  (`total_crosses_a_blank_row` was there from the start). Said in three places: `CLAUDE.md:160`,
  `tools/formula_audit.py:10`, `knowledge/backlog.md:1209`. `tests/p125` asserts every
  finding's check is *in* `CHECKS` and never how many there are.
* **"Fourteen checks over the live configuration"** in `docs/USING.md` - `admin.preflight.CHECKS`
  has 15. This is P148's defect surviving in the guide: `tests/p148` derives the *page's*
  sentence from `len(CHECKS)` and reads `admin/page.py`, never `docs/USING.md`.
* **"two of the skills the shipped recipes name have no mechanical half"** - there are five
  (`ddr-tagging`, `qc-tieout`, `gpc-scrub`, `cost-of-capital`, `dcf-build`). In `README.md`
  and `docs/USING.md`.
* **Four bare commands** that fail outside an activated shell, on pages no test covers:
  `README.md:13-14`, `HANDOFF.md:111`, `knowledge/README.md:8,11`. README.md is the first
  file a clone opens and both of its "Start here" lines are wrong.
* **`HANDOFF.md` section 2a** - *"Nothing executes yet"* and *"Neither surface has
  authentication"*. `harness/runner.py:74` implements the step runner and P34, P35 and P36
  all closed on 2026-09-07/18. `serve.py --check` prints the opposite.
* **`MORNING.md`** - says *"62 of 62 phases closed, every checkpoint green through C35"* and
  is self-marked for deletion once read. It is now a trap for a session that reads it as
  current state.
* **`python -m uv run python -m evals`** is documented bare and exits 2: it needs a skill
  name, `--all` or `--coverage`. `tests/p58`'s regex only matches `tools/*.py`, so `-m evals`
  is invisible to it.
* **Nothing holds CLAUDE.md's own command lines to parsing.** `tests/p128` holds every slash
  command to a subcommand that parses and a flag something takes; `tests/p58` holds CLAUDE.md
  only to the prefix and to `--help` exiting cleanly. The standard exists and is not applied
  to the file an agent reads first. (Checked by hand: every flag in CLAUDE.md parses today.)

Two pieces of prose overstate the test they name. `tests/p74` is described as walking the
imports to prove nothing on the OCR path can reach a model; it reads the **top-level imports
of `ports/ocr/*.py` only**, is not transitive, and its sibling still hardcodes
`("none.py", "tesseract.py")` without `rapidocr.py` - the real coverage is `tests/p75` and
`tests/p120`, which glob the directory. And `tests/p73`'s `SHIPPED` is hand-written and omits
`orchestrate`, `report` and `tools`, which is the staleness its own sibling's docstring
forbids in those words. No defect hides in the three today; the list is the problem.

## B-143 A figure read off a page skips tie-out, and two declared operations have no producer
status: proposed
2026-10-03. From an audit of all 34 registered schemas against 114,184 real figure envelopes
out of `runs/`.

* **`engagement_profile.checkpoint_policy.review_floors` is consumed and cannot be produced.**
  `review/policy.py` refuses a policy that lowers a floor and returns the tighter of skill and
  policy, on every routed item. Nothing writes the field: the profile skeleton in
  `admin/console.py` does not contain it and the page renders the keys the profile has. So
  *"an admin may raise a review requirement, never lower one"* is half-built - the refusal
  exists, the raise is unreachable - and the console's own help text promises it.
* **`figure.derivation.op = "annualize"` is dispatched live by `guards/tieout.py` and written
  by nothing**, and its arithmetic is wrong: `sum(values) * 12 / len(values)` over operands
  flattened across locators, so the divisor is the row count rather than the period count.
  Two half-year rows stated 1200 recompute to 7200. Its one test uses three rows of 100
  against 1200 and so passes. `restate_scale` is the same shape and contradicts
  `harness/restate.py`, which restates the value and leaves the rows alone; its only test
  asserts the key is in the table.
* **`guards/tieout.py` has `if not derivation: continue  # read off the page`** - a fail-open
  branch for a shape `figure.schema.json` forbids, which does not even increment the checked
  count. Today `tools/normalize.py` manufactures a one-row `sum` to satisfy the contract. The
  day `derivation` becomes optional, a figure read straight off a page skips tie-out silently.
* **`workpaper@1.0.0` is validated only by tests.** Both `check` call sites are test files;
  `deliver/workpaper.py` writes the contract id as a label. A body carrying
  `concluded_value: 4200000` and five missing required fields draws seven violations from the
  registry and is refused by nothing on the release path. It is the one artifact that leaves
  the system unrefused, and `additionalProperties: false` is set on it and never runs.
* **The interim period is one missing capability wearing four empty contract fields**:
  `period.type` in {YTD, Q, LTM}, `period.start`, and `op: "annualize"`. All unproduced; every
  one of 114,184 real figures is `FY`. `intake/readers/periods.py` already *meets* one - it
  names `2024 Feb YTD` on a real client tab and escalates rather than typing it - so this is
  not hypothetical, and a valuation date mid-year makes a stub period routine.
* **`period.fiscal_year_end_month` is established by the reader and thrown away.** The consumer
  reads the person-entered profile instead, so a document whose stated year end disagrees with
  the profile cannot be detected - B-030's shape, one axis over.
* `destinations[].adapter` enumerates `box_mcp` and `box_client_credentials`; the port factory's
  keys are `local_folder` and `box`, so no enum member matches a factory key - and nothing reads
  the field as a routing decision anyway.

## B-144 `documents._number` returns a positive for an unbalanced parenthesis
status: proposed - one line, and it turns a sign flip into a dropped figure
2026-10-03. `_number("12,000)")` and `_number("(12,000")` both return **+12,000**, because
the negative test is `startswith("(") and endswith(")")` and `strip("()")` then discards the
orphan. It is the root cause under two sign flips: a figure printed `(12,000 )` - a space
before the paren, which several accounting packages emit - is matched by `_FIGURES` as
`(12,000` and read as **+12,000**, and `tabular._number` handles the same input correctly, so
the two readers disagree. Reachable from three callers, including the laid-out cell, because
`_FILLS` admits `(12,000` as a legitimate cell. Measured over both filings: 10 open-paren-only
and 80 close-paren-only words, **0 reaching a table cell** - so no live wrong figure, and no
gate between the glyph and the figure either. Refusing instead of guessing makes it a dropped
figure, which the footing check then catches.

Same reader, adjacent: a trailing minus (`12,000-`, how Sage, SAP and QuickBooks write a
credit) and a unicode minus (U+2212, what Word autoformat emits) each read as **positive** in
the line reader and make the coordinate reader return **no table at all**, because neither
`_ESTABLISHES` nor `_FILLS` nor `_NIL` admits them. And `documents.py:449,483` strip
`" .â€¦\t"` - mojibake: the bytes are space, `.`, U+00E2, U+20AC, U+00A6, tab, so the intended
ellipsis **U+2026 is not in the set** and three characters of ordinary European text are. The
same expression decides whether a line has a label at all.

## B-145 The repeat-client tracker deletes last year's items and keeps honouring a vanished one
status: proposed - small, and not blocked on the analyst
2026-10-03. `AdminConsole.dd_tracker` takes its items from the shipped
`intake/request_lists/valuation-non-esop.yaml` - 46 items, `origin: "starting point"` - and
nothing reads last year's list. `read_tracker` carries forward only the three person-owned
columns, keyed by ref, and only from the tracker in the same folder; `write_tracker` iterates
the shipped list's rows. Reproduced with a prior-year tracker holding A.1, A.14, E.7 and F.9:
**three of four refs vanished** along with the analyst's notes, and `Tracker.not_applicable`
reads all held refs, so **F.9 is still treated as Not Applicable with no row to show or unset
it**.

This matters because `BUILD/OPEN.md` frames the request-list gap as a *missing-data* problem
waiting on the analyst. It is also a code problem, and the data is not missing for a repeat
client: it is in last year's workbook, which is where it always is. Two more things in the same
area are not blocked on anybody either - **neither rehearsal ever runs a repeat engagement in
the focus division, and neither runs version 1's own recipe** (`simulate_firm` watches
`monthly-refresh`; its only `repeat` client is in the parked ESOP division), and **there is no
prior-year fixture of any kind**, where the smallest honest one is twenty lines of openpyxl.
`prior_model` is also stored as a *sibling* of `engagement["profile"]` and the driver puts only
the profile on a run, so the path a person sets at Setup is read by nothing but a screen.

## B-146 Nothing bounds anything on the intake path
status: proposed
2026-10-03. There is no size cap, page cap, row cap or inflated-size cap anywhere in
`intake/`. The de facto bounds are library-internal and accidental. Measured, per file:

* a PDF with 100,000 tiny text objects on **one page**: 48.8 s and 1,344 MB, writing 9,091
  rows of noise to the parse store; 20,000 objects is 8.8 s and 334 MB, so it scales linearly;
* an `.xlsx` with one real cell at row 1,048,576: 16.4 s and 621 MB for two figures, because
  `normalize_workbook` does `list(ws.iter_rows(...))`. **This one is not adversarial** - a
  stray keystroke at the bottom of a client workbook does it, and it is the likeliest of these
  to appear in real work;
* an `.xlsx` whose `sharedStrings.xml` inflates from ~1 MB to 200 MB: 473 MB, read without
  comment. This is the real zip-bomb vector, because shared strings is a member openpyxl must
  parse. Scaled up it ends in `MemoryError`, which `except Exception` turns into
  `UNREADABLE_FILE`, so it fails closed - after taking the memory.

What *is* bounded is bounded well and should not be re-examined: a naive zip bomb (300 MB of
zeros named `.xlsx`) is refused in 0.28 s **without inflating**, a declared `<dimension>` of a
million rows is correctly ignored, and an RTF nested 500,000 deep is 0.69 s.

Separately, four refusals send a person to do the wrong thing. A **password-protected
`.xlsx`** is reported as *"cannot be opened as a workbook (BadZipFile: File is not a zip
file)"* plus *"ask the client for a readable copy"*, when the right sentence is that the file
is protected - and `documents.looks_like` already holds the OLE2 signature, it is simply not
consulted on the spreadsheet branch. That asymmetry costs the other lying extensions too: a
PDF named `.xlsx` gets BadZipFile where the same PDF named `.txt` gets *"Notes.txt is a PDF
under another name"*, and a TSV named `.xls` - extremely common from legacy systems - gets
xlrd's *"Expected BOF record"* for a perfectly readable file. A **UTF-16 CSV** (Excel's "Save
as Unicode Text") is refused only by coincidence: `_decode` checks the UTF-8 BOM and nothing
else, so `FF FE` falls through to cp1252, the grid builds out of NUL-interleaved text, and what
stops it three layers later is openpyxl's `IllegalCharacterError`. And a CSV with lone-`\r`
endings is refused with *"do you need to open the file with newline=''?"* - advice to a
programmer, in a diagnostic written for an analyst.

## B-147 Tests that assert nothing, and the scanner that would have caught all of them
status: proposed
2026-10-03. An AST sweep of all 778 test files, then line coverage over the 135 files
holding a candidate, to prove which assertion bodies execute **zero** times. Confirmed, in
the order a fix should take them:

* **`tests/checkpoints/c65:214-217`** - a parametrized test that checks nothing in any of
  its three cases. `plan.targets` is `()` for all three parameters, so `all(...)` over an
  empty sequence is True and the loop body never runs. Three green tests, zero assertions
  evaluated, and the test cannot tell *"the planner never guessed a folder"* from *"the
  planner planned nothing at all"*. The right folder is the one shape **not** in the
  parametrize. The planner itself is correct; only the test is empty.
* **`tests/p19/test_skill.py:405`** - a live `or True`, and the precedence is the trap:
  `all(...) or True`. This is the **only** place that checks every disagreement carries
  `review_required`, which is what P19's sign-off in STATE.md claims - *"nothing material
  auto-accepted"*. `disagreed` holds 17 entries, so the predicate really is computed over 17
  items and thrown away. **Whether the claim holds is unknown**, and removing three words
  answers it.
* **`tests/checkpoints/c08:202`** - a second live `or True`, on the config-change-log
  ordering. And **`:184`** - `... or replayed.nodes`, a bare dict as the last disjunct, which
  any non-empty dict satisfies; the lines above it already prove it is non-empty. These three
  are the complete census: an extended scan for a truthy constant or a non-empty literal
  container as a disjunct finds exactly two in 778 test files, and none in production.
* **Six tests over three empty allowlists** (`tests/p71:141,146`, `tests/p73:137,142`,
  `tests/checkpoints/c42:41,48`). All three allowlists are `{}`, so the loop bodies execute
  zero times. **CLAUDE.md non-negotiable 7 states this as enforced** - *"an entry without a
  reason fails as loudly as the defect"* - and the twelve-word rule has never once been
  evaluated. Proved both ways: injecting a reasonless entry does fail, so the rule works and
  is simply never reached. The empty allowlist is deliberate and good; the dormant rule is
  the defect. The fix is to lift the check into a helper and test the helper against a
  fixture allowlist, so it is proved on every run rather than on the day somebody adds an
  excuse.
* **`tests/regression/test_serve.py:322-324`** - green and empty on exactly the machines
  that matter. It does not pass `AA_NO_ENV_FILE=1`, so the subprocess reads `.env`, which
  sets `AA_OCR_ADAPTER=rapidocr`; the OCR seam then reports installed, `missing` is `[]`, and
  the two assertions about what a NOT INSTALLED line must say never run. CLAUDE.md tells a
  person to configure that adapter, so the test is live only on a clean clone.
* **`tests/p62:58,68`** - two regex loops that match nothing against 99 live rows of
  `BUILD/OPEN.md`. Correct today; the extractor is never exercised against a row known to
  contain the pattern, so rephrasing a row to *"close phase P28"* would retire the guard
  silently. The same file gets this right next door, proving `SETTLED_BY` both ways.

**And four shapes that are claimed and not checked**: `tests/p74:170-189` walks
`(ROOT/"ports"/"ocr").rglob("*.py")` and asserts `not offenders`, so **renaming the
directory leaves it green with nothing examined** - and that is the test CLAUDE.md names as
the guarantee behind *"OCR is local, and that is not a preference"*. `tests/p97:109` and
`tests/p99:247` have the same gap. One line each fixes it, and `tests/p73` already shows how:
`assert len(found) > 20`.

**The recommendation that outlasts the individual fixes.** No scanner exists for this class -
P160 found its `or True` by reading, and the two surviving ones sat in the repo for a month.
An AST check in `tests/p07` would be about twenty lines: a truthy-literal disjunct in an
`assert`, an `assert` on a tuple, a self-comparison outside a declared determinism check, and
the highest-yield rule - **an assert-only loop, or an `all()`/`not any()` over a computed
iterable, with no non-emptiness guard in the same function**. That last rule alone would have
flagged six of the findings above on the day each was written.

## B-148 The skip census, and the four nobody has counted
status: proposed - and B-101's own number has drifted
2026-10-03. 108 skip declaration sites in `tests/`. Four groups, and only one is a problem.

* **82 are the checkpoint stubs** - `@pytest.mark.skip(reason="written at the end of PNN")`
  over a `raise NotImplementedError`, each beside a real sibling test that is written and
  green (all 90 checkpoint directories were verified to have real coverage). **B-101 says 69.
  It is 82**, and B-101's own text says *"a backlog item that quietly stops being true about
  its own size is the same defect it is describing"* - it has drifted by 13 since C85.
* **Four have expired and are outside that group**, and two of them are gate refusals:
  `tests/p01:256` needs **two** phases open at once to run, and this build closes one phase at
  a time, so *the gate's refusal to close a phase out of order is untested* and the window
  never opens. `tests/p01:277` needs a checkpoint with an open covered phase, so *the gate's
  refusal to run a checkpoint early is untested*. Both are structurally dead rather than
  waiting on anything. `tests/checkpoints/c27:78` and `:93` skip because the identifier
  register has been filled, so the **empty-register refusal is untested on any working
  machine** - and `interview.py scan` refusing an empty register is a privacy guard. All four
  want the same fix, and the repo already records the discipline for it: drive them against a
  temp copy, with a synthetic `plan.json` holding two open phases and a temp `knowledge/`
  with an empty register.
* 6 are opt-in (`--ocr`, `--container`, `--postgres`), each counted and printed in the
  session summary, and the container one fails rather than skipping if the flag is given with
  no runtime. 16 are environment-conditional and most now run here. Neither group is a
  finding.

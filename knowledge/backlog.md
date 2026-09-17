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
status: built (2026-09-17, P40)
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
status: built (2026-09-17, P41: tools/beta.py; the formula is a required argument until the firm's is confirmed)
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


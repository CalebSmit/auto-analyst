# EBITDA adjustments

> **Draft knowledge file.** Mined from five recorded interview sessions (2026-09-16 to
> 2026-09-21), the firm-generic methodology draft, and the build's own EBITDA reference files.
> Firm-generic: no client, person or place is named. Everything the analyst promised "from the
> work computer" is listed under *What is still unknown*, not guessed at.

This file is what the model consults when it is deciding whether a line in a client's
financial statements is an adjustment to EBITDA - an add-back, a removal, or a normalization -
and how to present that candidate so a reviewer can accept or reject it. It covers where
candidates come from, the one test the analyst applies to a one-time item, what is rare and
what is common, how a repeat client differs from a new one, and what evidence an item has to
carry. It does not cover working capital (see `nwc-*.md`) or forecast drivers.

## What we know

1. **EBITDA adjustments are a major focus of the work.** "We definitely focus a lot on the
   EBITDA adjustments." (2026-09-17-1, Q1)

2. **Owner compensation is very rarely adjusted** in this division. "Not often normalizing
   adjustments on owner pay, very rare." The reason was not given; the build's draft methodology
   infers market-rate pay and marks that as unconfirmed. (2026-09-17-1, Q1; decisions.md)

3. **Interest income is the common adjustment**, named first and unprompted. "Interest income
   comes up a lot." It is "usually" removed from EBITDA. Whether interest on operating cash is
   treated differently is beyond what the analyst knows and was not pursued. (2026-09-17-1, Q1;
   2026-09-17-2, Q14)

4. **What is being looked for is one-time and discretionary expense.** "We look for one time,
   or discretionary expenses usually." (2026-09-17-1, Q2)

5. **Where candidates are found, in the analyst's order:** (1) the detail of other income and
   expense; (2) line detail in the client's internal financials; (3) what management says in the
   due diligence meeting; (4) the notes to the audited financials, when provided. "Usually we
   just have to decide based off the info we have." (2026-09-17-1, Q2)

6. **The decision is mostly the analyst's own judgement on the information available**, rather
   than something the client states. (2026-09-17-1, Q2; decisions.md)

7. **The one-time test, in two steps.** "We first just look if it showed up only 1 or 2 times,
   and not in previous years. But we do usually ask management as well to confirm." So: present
   in only one or two periods, absent in the years before, then confirmed with management.
   (2026-09-17-1, Q3)

8. **The firm asks the client for the candidates outright.** The due diligence request list's
   financial-records section includes, for the past five fiscal years: compensation paid to
   each owner/principal (base, bonus, share of profits); discretionary payments to any
   owner/principal; and "any one-time or non-operational expense or income items". So the
   add-back inputs are partly *supplied* by the client, not only inferred from statement detail.
   (2026-09-18-1, Q11)

9. **The due diligence meeting rarely changes the model, but management sometimes names a
   one-time item there**, and the meeting is where the explanation of an unusual year's costs
   comes from - material for the report rather than for the model. (2026-09-17-1, Q2, Q7)

10. **Repeat client: same items, new amounts.** "If it is a repeat client, we use the same
    adjustment items as last year, and just fill in the values for the new year. But if it is
    new, you will have to think through it." (2026-09-17-1, Q1; confirmed 2026-09-17-2, Q7)

11. **Audited statements win over internal ones** when both describe the same year and
    disagree, because they are more trustworthy; the most recently received document wins
    otherwise. An older audited statement against a newer internal one is "probably" audited -
    the analyst was not certain. (2026-09-17-2, Q8-Q10)

12. **Real examples are owed.** Twice the analyst promised "a bunch of EBITDA adjustment examples
    that we have used" from the work computer. None has been provided. (2026-09-17-1, Q1;
    2026-09-17-2, Q14)

13. **What a reviewer looks at.** At the internal value review the MD looks first at the
    transaction multiples, then the comps, then the industry and market. Afterwards "usually
    nothing much" changes - the multiples used, or a WACC assumption. Adjustments were not named
    as something the MD revisits. (2026-09-17-2, Q11-Q12)

14. **Version 1 scope.** Version 1 gathers data and fills an input-help workbook; it does not
    run the model. The adjustments are therefore inputs the analyst keys, and the system's job is
    to find and evidence candidates, not to compute a normalized EBITDA. (2026-09-18-1, Q1a-Q2)

15. **The build's current add-back categories** (`owner_related`, `discretionary`,
    `related_party`, `non_recurring`, `accounting_normalization`) and its officer-compensation
    benchmark test are the build's own design, written before the interviews. The analyst has
    only ever named one-time, discretionary, interest income and (rarely) owner pay. Related-party
    rent and accounting normalizations have not come up in any session.
    (skills/valuation/_group/ebitda-normalization/references/*, 2026-09-17-1)

## What the model should do with it

- Look for candidates first in the detail behind other income and other expense, then in the
  line detail of the internal financials, then in the notes to the audited financials. Cite
  the source row for every candidate.
- Treat interest income as a candidate for removal on every engagement, and say so plainly;
  do not decide the operating-cash question, because the analyst does not.
- Treat a client-supplied schedule of one-time items, discretionary payments or owner
  compensation (request-list items) as the primary source when one exists; the statement
  detail is the fallback and the cross-check.
- Apply the one-time test as the analyst states it: a candidate must appear in one or two
  periods only and not in earlier years. An item present in three or more periods, or in the
  earliest period of the history, is not one-time, however it is described - put it in front of
  a person rather than proposing it.
- Attach to every one-time candidate the question for management ("will this recur?"), and
  record whether management confirmed it; do not mark a one-time item settled without that.
- For a repeat client, start from last year's adjustment list: carry every item forward, find
  this year's amount for each, and flag any item whose line cannot be found this year or any
  new line that looks like a candidate. Do not re-decide last year's items.
- Do not propose an owner-compensation adjustment by default. If owner pay is on the
  client-supplied compensation schedule, show it with the schedule's figures and leave the
  judgement to a person.
- Never assume a market price for a related-party item; if one is proposed, name the missing
  fact.
- Prefer audited figures over internal ones when both exist for a period; prefer the most
  recently received document otherwise; show the disagreement either way.
- Never conclude. Present candidates with evidence, period pattern and source; a person
  accepts each one.

## What is still unknown

1. The real adjustment examples: for each, the line, the amount's source, the reason, and who
   accepted it. (Promised 2026-09-17-1 and 2026-09-17-2; needs the work laptop.)
2. Why owner pay is rarely adjusted here - market-rate pay, engagement type, level of value, or
   something else - and the exceptions where it *is* adjusted.
3. Whether interest income is ever left in, and whether interest on operating cash is
   distinguished from interest on excess cash.
4. Which discretionary expenses actually come up (travel, vehicles, charitable, family on
   payroll, insurance) and how each is supported.
5. Whether related-party rent, management fees or purchases from affiliates ever appear, and
   what is done about them.
6. Materiality: a percentage, a dollar amount, or judgement - and whose.
7. For a repeat client, whether anything is ever added to or dropped from last year's list,
   and what triggers it.
8. How management's confirmation of a one-time item is recorded today (meeting notes, email,
   nowhere), and whether the add-back schedule in the model has a place for it.
9. Whether adjustments are ever negative (an expense that should be *higher*), and how those
   are shown.
10. Where the adjustments live in the model - which tab, which rows - so the input-help workbook
    can mirror it. (Needs the master model file.)
11. An adjustment a reviewer pushed back on, and who was right. (Asked for in the topic map;
    never reached.)

# Guideline public company screening

> **Draft knowledge file.** Mined from five recorded interview sessions (2026-09-16 to
> 2026-09-21) and the owner's brief for these files. The build's `gpc-scrub` reference files
> (`comparability-criteria.md`, `multiple-scrubbing.md`) are empty placeholders, so nothing
> here comes from them. The inclusion criteria were promised from the work laptop and have not
> been provided; they are the main open item.

This file is what the model consults when the task touches the guideline public company (GPC)
set: how comps are found, what makes one belong or not, what the set is used for downstream
(the exit multiple and the beta), and how a repeat client's set is reused. It also covers what
is known about the guideline M&A transactions set, because the analyst treats the two together
and the same database serves both. Version 1 does not run the GPC analysis; this file is for
reading an export, reusing last year's set, and presenting the set and its multiples so a
person can decide.

## What we know

1. **A GPC analysis and guideline M&A transactions are run on nearly every engagement**,
   alongside a DCF, "just to get a better idea of what is going on." (2026-09-16-1, Q5)

2. **The source is Capital IQ, pulled by hand.** "We use cap iq. So that we will have to do
   manually (for the actual pull), because we don't pay for the api." The system can only
   start from an export a person made. (2026-09-17-1, Q9)

3. **Two kinds of search: by keyword and by industry.** "We do comps by keyword, and comps by
   industry searches for gpc comps." (owner's brief, 2026-10-05)

4. **Drop criteria, stated.** A company or transaction is dropped when "their financial
   situation would have to change a lot. Or they would have to get out of the similar line of
   business from our subject company being valued." (2026-09-17-1, Q9)

5. **Inclusion criteria, owed.** "To add some, there are a lot of criteria I can give you at a
   later date when I get you on my work computer." Not yet given. (2026-09-17-1, Q9)

6. **Repeat clients keep last year's set.** "Comps stay the same unless there is good reason to
   add or get rid of." (2026-09-17-2, Q7)

7. **The multiples used are EV/EBITDA and EV/revenue**, and what is read from the set is their
   medians and averages. (2026-09-17-1, Q8)

8. **The set feeds the DCF's terminal value.** When the DCF uses the exit (terminal) multiple
   method rather than Gordon Growth, "medians and averages of the GPC multiples and M&A
   transaction multiples ... would be used to help support the multiple we choose." The MD picks
   the multiple, "usually around the median and average". (2026-09-17-1, Q8; 2026-09-17-2, Q4)

9. **A "good" comp set changes two methods.** With a good set the team is confident in, the
   DCF uses the exit multiple method and the cost of equity uses CAPM; without one, Gordon
   Growth and the build-up method. "It seems like a lot of these non esop dcfs use the multiple
   method." Who decides what "good" means is not clear to the analyst; a repeat client does what
   was done last year. (2026-09-17-2, Q4)

10. **The set also supplies beta.** Beta is "the median unlevered beta of comps pulled from
    cap iq", relevered to the subject company's target capital structure by the model
    automatically. So the WACC is not final until the comp set is. (2026-09-17-2, Q5;
    2026-09-18-1, Q1)

11. **The pulls are independent; the use is not.** Comps, transactions and WACC data can be
    gathered side by side, but the DCF's terminal multiple and the cost of equity wait on the
    final set. (2026-09-17-1, Q8; 2026-09-17-2, Q5)

12. **What the MD looks at first.** At the internal value review: the multiples used in the
    M&A transactions method, then the comps, then "what is going on in this industry and market
    that the subject company is involved in." After the review, what changes - when anything
    does - is "the multiples used". (2026-09-17-2, Q11-Q12)

13. **The methods are not weighted.** Each gives an enterprise value range; a final value is
    chosen within the ranges by the MD. The GPC analysis's output is a range and its support,
    never a point. (2026-09-17-1, Q10)

14. **Nothing was said about scrubbing a multiple** - normalizing a comp's EBITDA, removing a
    negative or outlier multiple, LTM versus forward, or control premiums on transactions. The
    topic map's angle "how you select and scrub comparables" was answered only with the drop
    criteria above. (2026-09-17-1, Q9)

15. **There is no transactions skill in the build.** Guideline M&A transactions are one of the
    three core methods and the build has nothing for them. (2026-09-16-1, Q5 finding;
    backlog B-005)

16. **Version 1 scope.** `gpc` is out of version 1's path; the deliverable is organized data
    the analyst keys into the model. (2026-09-18-1, Q1a-Q2)

## What the model should do with it

- Never look a company up. Take the comp set from a Capital IQ export a person pulled, and
  record which export and when.
- For a repeat client, start from last year's set. Carry every company and transaction
  forward; for each, ask only the two drop questions the analyst stated - has its financial
  situation changed a lot, has it left the subject's line of business - and present the answer
  with its evidence rather than dropping anything. A candidate for dropping is a review item.
- For a repeat client, show any company in last year's set that is missing from this year's
  export, and any new company in the export that was not in last year's set, each as a
  question.
- Compute the median and the average of EV/EBITDA and EV/revenue over the set as it stands,
  and show them beside the set; show how each would move if any flagged company were removed.
  Do not pick a multiple - the MD does, near those two figures.
- Compute the median unlevered beta over the set and name every company included and left
  out; do not relever it (the model does that, automatically, to the target capital structure).
- Say whether the set is being treated as "good" only by inheritance - what last year did -
  and never decide it fresh; put the question to a person when there is no prior year.
- Present a range and its support for the GPC method, never a point value, and never a
  weighting against the other methods.
- Keep the GPC set and the transactions set apart in the output, because the MD reads the
  transaction multiples first.

## What is still unknown

1. The inclusion criteria, in full - size bands, geography, business description match,
   profitability, trading liquidity, data availability, anything else - and which are hard
   rules versus preferences. (Promised from the work laptop, 2026-09-17-1.)
2. What a keyword search and an industry search each look like in Capital IQ: the screen
   fields, the industry classification used, how many hits a screen typically returns, and how
   the analyst narrows them.
3. The layout of a Capital IQ export as the firm pulls it - columns, units, LTM versus fiscal,
   currency - so a reader can be written against it. (A sample export is owed.)
4. What makes a set "good enough" for the exit multiple and CAPM - how many companies, how
   close in business - and who decides.
5. How many companies, and how many transactions, make a typical set.
6. Whether any multiple is scrubbed or excluded before the median and average are taken
   (negative EBITDA, extreme outliers, non-recurring items in a comp's EBITDA), and whether
   comps' EBITDA is normalized at all.
7. Whether the multiples are LTM, NFY, or both, and at what as-of date.
8. For guideline transactions: the search criteria, the look-back period, how deal multiples
   are read, and whether a control or size adjustment is made.
9. Whether and how a size or growth adjustment is applied to the chosen multiple against the
   set's median.
10. Where the GPC and transactions sets live in the master model and what the analyst keys
    per company. (Needs the master model file.)
11. What "industry and market" context the MD wants at the internal value review, and where it
    comes from today.

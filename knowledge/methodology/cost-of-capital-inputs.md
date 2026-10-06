# Cost of capital - the inputs the model takes

> **Draft knowledge file.** Mined from five recorded interview sessions (2026-09-16 to
> 2026-09-21) and the owner's brief for these files. The build's `cost-of-capital` references
> (`buildup-method.md`, `size-premium-sources.md`) and `dcf-build/references/wacc-buildup.md`
> are empty placeholders, so nothing here comes from them. This file is about **what the model
> takes as inputs and where each comes from** - not a calculation this tool performs. The
> analyst's words: the model "just has inputs for the wacc".

This file is what the model consults when the task is gathering or checking the cost-of-capital
inputs for the firm's model: which figures are needed, which source each comes from, which are
judgement calls that belong to a person, which depend on the comp set, and what a repeat client
refreshes. The WACC itself, the relevering of beta and the DCF are computed in the firm's Excel
template; version 1 does not run them.

## What we know

1. **The model does the computation; the analyst supplies inputs.** "The model already does
   different types of DCFs, and just has inputs for the WACC which we get from Cap IQ."
   (owner's brief, 2026-10-05) The DCF "is already set up in the template model before
   anything." (2026-09-17-1, Q8)

2. **Market data for the WACC comes from Kroll.** "We pull data from Kroll for WACC data."
   Which figures that covers (risk-free rate, equity risk premium, size premium, industry
   premium) was not itemized. (2026-09-17-2, Q5)

3. **Beta does not come from Kroll.** "Beta is found by median unlevered beta of comps pulled
   from Cap IQ. Then we relever it to our subject company." (2026-09-17-2, Q5)

4. **Relevering uses the subject company's target capital structure and is automatic in the
   model.** The formula lives in the Excel template, not in the analyst's hands; "you can look
   for these things" in the model when it is shared. (2026-09-18-1, Q1)

5. **The WACC is not final until the comp set is in**, because beta comes from the set. The
   data pulls happen side by side; the rate waits. (2026-09-17-2, Q5)

6. **CAPM with a good comp set; build-up without.** "If we have good comp set we use CAPM, if
   not use build up. But not sure who decides that, if it's a repeat client then we just do what
   they did last year." (2026-09-17-2, Q4)

7. **Pretax cost of debt comes from an implied credit rating.** "We do that by deciding what
   type of credit rating it would be, then choose based off the cost of debt attached to that
   rating." The rating is "kinda eyeballed right now and the MD decides." The cost of debt for
   each rating "comes from Cap IQ as well." (2026-09-17-2, Q5-Q6)

8. **The analyst wants the rating call supported by ratios.** "It would be good to set
   something up that compares things like interest coverage, debt to equity, and other things
   to make good judgment calls." The call stays the MD's. (2026-09-17-2, Q6)

9. **The company-specific risk premium is the WACC assumption most often revisited.** After
   the internal value review, what changes - when anything does - is "the multiples used, or
   like a different assumption in the WACC for CSRP." (2026-09-17-2, Q12)

10. **A repeat client gets fresh WACC data as of the new valuation date**, while the method
    choice (CAPM or build-up) follows last year. "We get new WACC data based on the new
    valuation date." (2026-09-17-2, Q4, Q7)

11. **The valuation date is an Input-tab field** and one of only two that change on a repeat
    engagement (the other is latest fiscal year end), "usually just one year later". The WACC
    data is pulled as of it. (2026-09-18-1, Q9)

12. **Forecast interest expense comes from the debt tab, not the client's forecast**, built
    from every long-term debt instrument entered with its maturity date, amount, term, fixed or
    variable rate and the other D-tab fields. So the actual cost of the company's existing
    debt is in the model independently of the WACC's pretax cost of debt. (2026-09-17-1, Q4;
    2026-09-17-2, Q2; 2026-09-18-1, Q3)

13. **The methods are not weighted and nothing concludes.** Each method gives a range; the MD
    picks within them. (2026-09-17-1, Q10)

14. **Size premium, industry risk premium, the risk-free rate's tenor, tax rate for the
    after-tax cost of debt, and how the target capital structure is set were never discussed.**
    The topic map's angles "size premium source and how you pick the decile" and "capital
    structure - actual, industry or target" were not reached beyond the word "target".
    (interview/topics.yaml; 2026-09-18-1, Q1)

15. **Tax inputs on the Input tab**: first-year tax status (C-Corp or S-Corp), state, C-Corp
    tax, S-Corp tax, applicable capital gains. These exist on the tab; how they reach the cost
    of debt or the DCF was not asked. (2026-09-18-1, Q3)

16. **Version 1 scope.** `cost-of-capital` is out of version 1's path. The build's `tools/beta.py`
    (unlever, relever, median) duplicates what the template does automatically.
    (2026-09-18-1, Q1, Q1a)

## What the model should do with it

- Treat the cost of capital as a list of inputs to gather and label, each with its source and
  its as-of date, never as a number to compute.
- Record the valuation date first, because every market input is pulled as of it; on a repeat
  client, propose last year's date plus one year and have a person confirm it.
- Separate the inputs by source: Kroll for market data; Capital IQ for the comps' unlevered
  betas and for the cost of debt by rating; the comp set for the median unlevered beta.
- Compute the median unlevered beta over the comp set and name every company included and
  left out. Do not relever it; the model does, against the target capital structure.
- Do not choose between CAPM and build-up. For a repeat client, show what last year used and
  carry it; for a new client, put the choice to a person with the state of the comp set
  beside it.
- Do not assign a credit rating. Where the normalized historicals and the debt tab allow it,
  show interest coverage, debt to equity and similar measures with the rows they came from, so
  the MD's call rests on something visible. Recommend no rating.
- Treat the company-specific risk premium as a judgement that belongs to a person and will be
  revisited at the internal value review; leave it blank or carry last year's with a flag,
  never propose one.
- Make the WACC inputs easy to change after review - which they are in the template, because
  they are inputs - and do not lock any of them.
- Never produce a WACC, a cost of equity or a discount rate as the tool's own figure.

## What is still unknown

1. The exact list of WACC inputs on the model's input tab (or wherever they live), each one's
   named range, and which are typed versus linked. (Needs the master model file.)
2. Which figures come from Kroll - risk-free rate, equity risk premium, size premium, industry
   premium - and which product or report each is read from.
3. **Reconcile two statements:** the owner's brief says the WACC inputs come from Capital IQ;
   the interview says Kroll for WACC data and Capital IQ for betas and cost of debt by rating.
   Both may be true for different inputs; confirm which input comes from which.
4. Size premium: the source, how the decile or size band is chosen, and from which measure
   (market value of equity, total assets, revenue).
5. The build-up method's components and sources when it is used, and how often it is used in
   this division.
6. How the target capital structure is set - the comps' median, industry data, the subject's
   actual, or judgement - and where in the model it is entered.
7. The relevering formula the template uses (read it from the file, do not guess).
8. The credit-rating bands: whether the firm already trusts a published table mapping
   coverage, leverage and other ratios to ratings, and which ratios the MD weighs most.
9. How the company-specific risk premium is sized and supported, and whether there is a
   typical range.
10. Which tax rate is used for the after-tax cost of debt, and how pass-through entities
    (S-Corp status on the Input tab) are tax-effected.
11. Whether the cost-of-capital inputs are presented at the internal value review, and in what
    form.
12. Who decides CAPM versus build-up on a new client - the analyst said "not sure who decides
    that".

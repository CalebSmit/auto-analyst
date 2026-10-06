# Cost of capital - the inputs the model takes

> **Draft, from one analyst.** The rules below are the rules section of
> `knowledge/methodology/cost-of-capital-inputs.md`, verbatim; that file holds what was said
> about Kroll, Capital IQ, beta, the credit rating and the company-specific premium, with each
> session cited, and the inputs that are still unknown. This is about what the firm's model
> takes as inputs and where each comes from - not a calculation this tool performs. Clearing
> this file at `/admin` is a person's confirmation; until then no run attaches it.

## Scope

Every valuation run, when the task is gathering or checking the cost-of-capital inputs for the
firm's model. The WACC, the relevering of beta and the DCF are computed in the firm's Excel
template.

## Rules

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

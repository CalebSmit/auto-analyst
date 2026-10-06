# Net working capital - the normal level as a percentage of revenue

> **Draft, from one analyst - and thin, because no session asked how a normal level of
> working capital is chosen.** The rules below are the rules section of
> `knowledge/methodology/nwc-normal-level.md`, verbatim: the general driver-setting method the
> analyst described for the income statement, applied no further than it reaches. That file
> holds the citations and the questions. Clearing this file at `/admin` is a person's
> confirmation; until then no run attaches it.

## Scope

Every valuation run, when the question is what a normal level of net working capital is for
the subject company, as a percentage of revenue, and what goes into the model's input for it.

## Rules

- From the historical balance sheet lines that the firm's NWC grouping includes (see
  `nwc-excluded-items.md` - today unknown), compute net working capital per historical year and
  as a percentage of that year's revenue, with the rows each figure came from.
- Show the last-year value and the three-year and five-year averages of that percentage, each
  labelled with the years it covers and never over an empty column. Do not compute a ten-year
  average over five years of data.
- Propose nothing as "normal". Present the candidates (last year, three-year, five-year) and
  the history side by side, and let the analyst choose - the analyst's own words are that
  which baseline is normal is a belief about the company going forward.
- Where a client sent an NWC line-item forecast, show it beside the history as client-sourced;
  do not reconcile it to a percentage on the tool's own authority.
- Where monthly balance sheets exist, note that they exist and could show seasonality; do not
  build a seasonality adjustment nobody asked for.
- For a repeat client, show what last year's model used as the working-capital assumption, if
  it can be read from the prior workbook, beside this year's candidates.

# Net working capital - the normal level as a percentage of revenue

> **Draft knowledge file.** Mined from five recorded interview sessions (2026-09-16 to
> 2026-09-21). **No session asked how a normal level of working capital is chosen.** The topic
> map carried the question ("whether you set a normal level (a peg), and from what months") and
> it was never reached. What is here is the general driver-setting method the analyst described
> for the income statement - which may or may not apply to working capital - plus what the model
> visibly has, plus the questions. Nothing below states a working-capital rule as the firm's.

This file is what the model consults when the question is what a *normal* level of net working
capital is for the subject company, expressed as a percentage of revenue, and what goes into
the model's input for it. It exists because the owner asked for "one that decides what a normal
% of net working capital is for the company (% of revenue)" (owner's brief, 2026-10-05). Today it
can say how the analyst sets a percentage driver in general, and that the model has averaging
columns; it cannot say what the working-capital input is or how it is set.

## What we know

1. **How the analyst sets a percentage driver, in general.** For forecast drivers "we usually
   base them on an average from the last year, or few years, depending what we believe a
   normal % is going forward, then step up or down that % in the future years moving forward."
   This was said about revenue growth, cost of goods sold and operating expenses as a percentage
   of revenue - not about working capital. (2026-09-17-1, Q5-Q6)

2. **Assumptions are kept modest.** "We don't make too big of assumptions, just forecast it
   based off of what we think the company is going to do in the future." Clients rarely push
   back. (2026-09-17-1, Q5)

3. **The model computes three averages itself.** The WS and IS tabs carry `10-Yr Avg.`,
   `5-Yr Avg.` and `3-Yr Avg.` columns before the historical years; the build must not compute
   them, only fill the year columns. The IS tab shows each line as a percentage of sales. Whether
   the working-capital tabs carry the same averages and percentages was not seen.
   (2026-09-18-1, Q3)

4. **Usually only the last five years are filled**, though the template has ten columns; the
   request list asks for five fiscal years. So any historical average is over at most five
   years in practice, and the ten-year average column is over half-empty data - what the
   template does with that is an open question. (2026-09-18-1, Q10-Q11)

5. **Monthly statements are requested.** The request list asks for monthly income statements
   and balance sheets for the past sixty months. The analyst did not say what they are used
   for; seasonality in working capital is one obvious use, but that is an inference, not an
   answer. (2026-09-18-1, Q11)

6. **Clients sometimes send an NWC line-item forecast.** When a client sends a forecast, the
   firm treats it as the source of truth and does not change it - said about the income
   statement forecast, with interest expense the one exception. Whether an NWC forecast is
   treated the same way was not asked. (2026-09-16-1, Q9; 2026-09-17-1, Q4)

7. **Repeat clients keep the methodology, not the assumptions.** "Forecast it the same way, not
   necessarily same assumptions. But same methodology." (2026-09-17-2, Q7)

8. **The model has `NWC`, `NWC (M)` and `WC` tabs and an `NWC or WC?` input switch.** Their
   contents and the switch's meaning were not described. (2026-09-18-1, Q3)

9. **Industry benchmarks for working capital were never mentioned.** The only benchmark
   sources named in any session are Capital IQ (comps, transactions, betas, cost of debt by
   rating) and Kroll (cost of capital data). (2026-09-17-1, Q9; 2026-09-17-2, Q5-Q6)

10. **Version 1 does not run the model.** A normal-NWC percentage, if version 1 produces one at
    all, is a figure shown with its derivation for the analyst to key - not a value written into
    the model. (2026-09-18-1, Q1a-Q2)

## What the model should do with it

Only what the general driver method supports, and labelled as such:

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

## What is still unknown

1. Whether the firm sets a normal (target) level of net working capital at all, and if so
   whether it is a percentage of revenue, a dollar amount, a number of days, or something else.
2. Which model input receives it - the tab, the row, the named range - and whether it is one
   number or a percentage per forecast year. (Needs the master model file.)
3. What history it is set from: the last year, an average of several, the monthly balance
   sheets (a sixty-month average, or a specific month), or the valuation-date balance.
4. Whether seasonality is considered, and how - the sixty months of statements are requested,
   but nobody has said why.
5. Whether industry or peer working-capital levels are used as a benchmark, and from where.
6. Whether an excess or deficit of working capital against the normal level is treated as a
   non-operating item in the enterprise-to-equity bridge, and where that lives in the model.
7. How the client's NWC line-item forecast, when provided, is used - as the source of truth
   like the income statement forecast, or as a cross-check.
8. What `NWC (M)` is (monthly? a mirror? a different method?) and when `WC` is used instead of
   `NWC`.
9. For a repeat client, whether last year's working-capital assumption is carried forward or
   re-derived, and what changes it.
10. Who decides the normal level - the analyst, the associate, or the MD at the internal value
    review - and whether it is one of the assumptions that changes there.

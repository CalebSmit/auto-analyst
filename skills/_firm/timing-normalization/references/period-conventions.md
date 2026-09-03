# Period conventions

Reference for `timing-normalization`. How periods are named, typed and ended, so that
two people - or a model and a tool - mean the same thing by "FY2025".

## Types

| type  | means                                   | label form   | end date                 |
|-------|-----------------------------------------|--------------|--------------------------|
| FY    | a fiscal year                           | `FY2025`     | the fiscal year end      |
| CY    | a calendar year, when it is not the FY  | `CY2025`     | 31 December              |
| LTM   | the twelve months to a date             | `LTM2025-06` | that month's end         |
| YTD   | the fiscal year to a date               | `YTD2025-06` | that month's end         |
| Q     | a fiscal quarter                        | `Q3 2025`    | the quarter's last day   |
| M     | one month                               | `M2025-04`   | the month's last day     |
| POINT | a balance at a date (a balance sheet)   | `AT2025-12-31` | that date              |

A label names the period a person would say out loud. The type and the end date are
what the tool aligns on; the label is what the reviewer reads.

## Fiscal years

- The engagement profile carries the fiscal calendar. A file whose year end disagrees
  with it is not wrong - it is a fact to report - but its periods are typed `CY` or
  `FY` by what the file says, never by what the profile expects.
- "FY25", "FY2025", "Fiscal 2025" and "Year ended December 31, 2025" are the same
  period when the year end is December. When the year end is June, "FY2025" ends
  30 June 2025 and the file's own header decides.

## Month ends

A month is its last calendar day. `Feb-25` is `M2025-02` ending 2025-02-28. A 52/53-week
calendar is typed by its stated week end and noted; it is not rounded to a month.

## Grids and gaps

A set of monthly periods forms a grid from the earliest to the latest month. Every month
in between that no block covers is a **period gap**. The same for years. A gap is
reported with the reason "no block covers it". It is never filled: not from the months
either side, not from a run-rate, not from the prior year. The table simply has no
figure there, and the report says so.

## Scale and currency

Scale (units, thousands, millions) and currency are read by the Period Detector from the
file's own headers and travel with every figure the tool produces. A file the detector
marked ambiguous on scale is escalated before this skill runs. The skill never restates
between scales; a table with one file in thousands and another in units carries both
scales, figure by figure, and the model template restates at load.

## Two files, one period

When two blocks claim the same period, both are listed. The tool compares line by line:
where they agree the figure is taken with both locators in its derivation; where they
disagree there is no figure, and the alignment report carries the conflict with both
values for a person to settle. The skill does not choose the newer file, the larger
figure or the one that looks right.

# How non-ESOP valuation work is done

> **Draft, from one analyst.** Written from the first three `/improve-agent` interviews.
> Not yet confirmed by an associate or an MD. Clearing this file at `/admin`
> is that confirmation; until then no run attaches it.

## The methods

A DCF, a guideline public company analysis and guideline M&A transactions are run on
nearly every engagement, because together they show what is going on. One-off or custom
analyses (a tangible asset model, for example) are added when the engagement calls for
them. Presenting all three is expected; dropping one needs a stated reason.

The data for all three is gathered side by side, but the cost of capital is not final until
the guideline company set is, because its beta comes from that set. The DCF's structure already
exists in the firm's template: the work is its inputs, not its construction.

For a mature operating company the standard of value is usually fair market value, on a
controlling basis.

## Ranges, not weights

The methods are not weighted. Each produces a range for enterprise value. The final value is
chosen somewhere within those ranges, and that choice belongs to the managing director. Output
from this system is the ranges and their support - never a point value, never a weighting.

## Historical financials

- Audited or internal financial statements are both acceptable sources.
- The historicals are the foundation of the model and are completed first. Little else can
  be done until they arrive.
- Figures taken from a client's own workbook are marked as client-sourced, never blended
  silently into the firm's figures.
- When sources disagree about a period: audited statements over internal ones, and the most
  recently received document over an older one - including a restated prior-year column. When
  an older audited statement disagrees with a newer internal one, a person decides; audited is
  the likely answer. A disagreement is always shown, even when a rule settles it.
- For a returning client, prior periods come from last year's model; only the new period is
  entered from this year's documents.

## Earnings adjustments

- EBITDA adjustments get close attention. Owner pay is rarely adjusted. Interest income is a
  common adjustment and is usually removed.
- Candidates are looked for first in the detail of other income and expense, then in the
  internal financials' line detail, in what management says in the due diligence meeting, and
  in the notes to audited financials when they are provided. Most are one-time or discretionary
  expenses.
- An expense is a one-time candidate only when it appears in one or two periods and not in the
  years before. Management is then asked to confirm. An item that keeps appearing is part of
  normal operations, whatever it is called.
- For a returning client, last year's adjustment items are carried forward with this year's
  amounts. For a new client they are worked out from the information available.

## The forecast

- When the client provides a forecast, it is the source of truth: used unchanged, and the
  firm's model ties to it wherever possible. The one exception is interest expense, which is
  built from every long-term debt instrument entered in the model's debt tab rather than taken
  from the client's line.
- When the client provides none, the firm builds one from drivers beneath the income
  statement: a revenue growth rate per year, cost of goods sold as a percentage of revenue,
  and operating expenses as a percentage of revenue. Each driver starts from last year's
  percentage or an average of the last few years - whichever is the normal level going
  forward - and is stepped up or down over the later years. Assumptions stay modest. The
  client sees the forecast and may ask for changes; a forecast the client has not seen is not
  final.
- For a returning client the forecast follows the same methodology as last year, with fresh
  assumptions.
- The due diligence meeting rarely changes the forecast. It explains it - why management
  expects what it does, why a year's costs were unusual.

## Debt

- Each long-term debt instrument is taken from the debt note in the audited financial
  statements - maturity date, starting amount, years remaining, interest rate - and entered in
  the model's debt tab, which produces the forecast's interest expense.
- Without audited statements, one of three: match the client's own interest expense, ask the
  client for the debt details, or - if nothing is provided - forecast interest at zero or flat.
  Which one is a person's call; a forecast of zero interest is a stated assumption.

## Cost of capital

- Market data for the cost of capital comes from the firm's cost of capital data provider, pulled
  as of the valuation date - refreshed every year for a returning client.
- Beta is the median unlevered beta of the guideline companies, relevered to the subject
  company.
- A good guideline company set means CAPM for the cost of equity; without one, the build-up
  method. A returning client follows last year's choice.
- The pretax cost of debt follows from the credit rating the subject company would carry, at the
  rate for that rating. The rating is the managing director's call.
- The company-specific risk premium is judgment, and one of the assumptions most often revisited
  at the internal value review.

## Guideline companies and transactions

- The data comes from a database export pulled by the analyst.
- The medians and averages of the guideline companies' and transactions' EBITDA and revenue
  multiples support the terminal multiple when the DCF uses the exit multiple method rather
  than Gordon Growth. The exit multiple method is used when the guideline company set is good;
  the managing director picks the multiple, usually near the median and average.
- A company or transaction is dropped from a set when its financial situation has changed a
  lot, or when it is no longer in the subject company's line of business. A returning client's
  set is kept unless there is good reason to change it.

## The model checks

A model is not ready for review until all three hold:

1. Net income in the model ties to the client's net income.
2. The balance sheet balances.
3. Ending cash on the cash flow statement equals cash on the balance sheet.

A check that does not hold is reported with both numbers and the difference. It is never
forced to pass. A failure is almost always a mistake in the model, not in the client's figures.

## Review

The associate reviews the model before it goes to the MD at the internal value review. There
the MD looks first at the transaction multiples, then the guideline companies, then what is
happening in the subject company's industry and market; afterwards, little usually changes
beyond the multiples or a cost of capital assumption. The MD decides whether the report is
written. Nothing here concludes a value; every output is input to that review.

# Documents and the order they arrive in

Each document type: what it is, the formats it comes in, when it usually arrives,
what it feeds, and what to do when it is late, missing, revised or out of order.

## Where they arrive

- Client uploads to ShareFile; the analyst copies them into the internal Box folder. (2026-09-16-1)

## The pilot document set - mature operating company (2026-09-16-1)

| Document | How often | Notes |
|---|---|---|
| Audited financial statements **or** internal financials | Always one of them | Either is used. When both arrive and disagree, audited wins (2026-09-17-2). |
| Income statement forecast | Almost always | Usually Excel. |
| Net working capital line-item forecast | Sometimes | |
| Fixed asset schedule | Sometimes | |
| Interim financials | Sometimes | See below. |
| Long-term debt detail | When the company has debt | The debt note in the audited financials (2026-09-17-2). |

## Historical financial statements

- Formats: often a separate PDF for each year; sometimes Excel. (2026-09-16-1)
- Feeds: the historical financials in the model - the first thing filled in. (2026-09-16-1)
- When Excel: the relevant tabs are copied into the firm's model and highlighted yellow. (2026-09-16-1)
- Which statements (IS, BS, cash flow), audited/reviewed/compiled/internal, tax returns: unknown.
- The detail of other income and expense, and the internal financials' line detail, are where adjustment candidates are looked for first; notes to audited financials when provided. (2026-09-17-1)

## Interim financials

- Provided sometimes, in addition to the annual historicals. (2026-09-16-1)
- How they are used (TTM, stub period, as-of date): unknown.

## Client forecast

- Usually Excel when provided. Copied into the model as a yellow client tab. (2026-09-16-1)
- Not always provided; when missing, the firm builds the forecast and sends it for client approval. (2026-09-16-1)

## Long-term debt instruments

- Every long-term debt instrument the company has is entered individually into the model's debt tab; slow. (2026-09-16-1)
- Source: almost always the long-term debt note in the audited financial statements, when provided - a page describing each instrument. (2026-09-17-2)
- Entered per instrument: maturity date, starting amount, years remaining, interest rate, and similar terms; the full field list is the template's debt tab. (2026-09-17-2)
- When there are no audited statements: match the client's interest expense, or ask the client for the long-term debt details, or - if nothing is provided - forecast interest at zero or flat. (2026-09-17-2)

## Due diligence meeting notes

- Firm-produced, not client-uploaded: notes taken in the due diligence meeting(s) the MD holds with the client, covering how the last year went and the client's view of the forecast. (2026-09-16-1)
- ~~Feeds: the forecast, at least.~~ Corrected 2026-09-17-1: rarely changes the forecast or the model. Mainly explains it - why management expects the forecast, why a year's costs were unusual - which is material for writing the report. Format, who writes them, where they are stored: unknown.
- Also a source of EBITDA adjustment candidates: management sometimes names one-time items in the meeting. (2026-09-17-1)

## Arrival order and exceptions

- **Historical financials are the gate.** Wanted first; without them little can be done. (2026-09-16-1)
- With historicals in, the model is set up, so a client forecast arriving later can be used straight away to build the firm's forecast. (2026-09-16-1)
- Anything else is used as it arrives ("we just use what we can"). (2026-09-16-1)
- Late or revised documents: the most recent one received wins; restated past periods are updated in the model (2026-09-17-2). Contradictory: audited over internal (2026-09-17-2). Never-arriving: not yet asked.
- Also known: that the model is not presented to the MD until the client has provided all information. (2026-09-16-1)

## The due diligence request list (2026-09-18-1)

The schedule everything else is tracked against. Sent to the client at the start. Seven
sections: A Financial Records (16 items), B Corporate Documents (8), C Operational Matters
(11), D Employment/Labor Matters (6), E Properties & Equipment (7), F Contracts (2),
G Legal Matters (4).

It doubles as the tracker: columns `In Model? | <firm> Notes | Provided | Not Applicable`,
with a free-text status in the notes column - `Done`, `Received`, `Outstanding`, `NA?`,
`FY 23 only`, `Received past 2 years`, `Received FY 23 compensation, see D.5`. Supporting data
gets its own worksheet named after the item (`B.6`, `C.7`, `D.5`, `E.1 & E.2`), so a request
number addresses both a status and a tab.

Tailored per engagement - the example seen is written for a medical practice ("by doctor",
"payor mix", "procedure count by type").

**What feeds the model** is section A: audited/reviewed/compiled statements and annual
internal statements for five fiscal years, YTD stubs, sixty months of monthly IS and BS,
forecasts, compensation by owner, discretionary payments, one-time/non-operational items,
aged receivables, fixed asset schedule, tax depreciation and amortization forecasts, lease
amortization (ASC 842), contingent claims, prior appraisals.

**Folder structure (2026-09-18-1).** Each request-list section is a folder in Box and a folder
in ShareFile. The section groupings are stable across engagements; the items inside them vary,
and stay similar year to year for a repeat client.

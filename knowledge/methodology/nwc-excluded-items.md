# Net working capital - excluded balance sheet items

> **Draft knowledge file.** Mined from five recorded interview sessions (2026-09-16 to
> 2026-09-21). **Working capital was never the subject of an interview question.** The topic
> map asked for it under `normalization` ("normalized working capital - whether you set a
> normal level") and `asset-approach` ("excess working capital"), and neither angle was
> reached. What follows is everything the sessions touch, which is little, and a precise list
> of what to ask. A short honest file beats a long plausible one.

This file is what the model consults when it is deciding which balance sheet lines belong in
net working capital for the subject company and which are excluded - cash, debt,
related-party balances and the like - and how to show that decision so a reviewer can check
it. It exists because the owner asked for "one that looks for excluded NWC line items in the
balance sheet" (owner's brief, 2026-10-05). It does not yet hold the firm's rule for any line,
because no session stated one.

## What we know

1. **The model has working-capital tabs.** The master template's tab strip, read from
   screenshots, includes `NWC`, `NWC (M)` and `WC` beside `BS`, `CF` and `D`. Nothing was
   said about what each holds or how they differ. (2026-09-18-1, Q3)

2. **The Input tab has a switch, `NWC or WC?`**, in its General Inputs block. It carries over
   unchanged from last year on a repeat client. Its meaning - which tab drives the model, or
   which definition is used - was not asked. (2026-09-18-1, Q3, Q9)

3. **Clients sometimes send a forecast of NWC line items**, alongside the income statement
   forecast they almost always send. (2026-09-16-1, Q9; documents.md)

4. **The balance sheet is a version-1 tab** - filled the same way as the income statement,
   from last year's model plus the new year, or wholly from the client documents for a new
   client - and its structure for a repeat client is read from the client's own prior
   workbook. (2026-09-18-1, Q3; 2026-09-21-1, Q2)

5. **The request list asks for an aged receivables summary as of the valuation date** and a
   fixed asset schedule as of the valuation date, among the financial records. Both bear on
   what is and is not working capital, though the analyst did not connect them to it.
   (2026-09-18-1, Q11)

6. **Debt is entered instrument by instrument on the D tab**, from the audited debt note,
   and the D tab foots to "Debt per Balance Sheet" plus deferred financing fees and unamortized
   warrant discount. So interest-bearing debt is identified and tied out separately from the
   balance sheet, which implies it is not a working-capital line. The analyst did not say this;
   it is read off the tab's foot. (2026-09-17-2, Q2; 2026-09-18-1, Q3)

7. **Cash is checked, not classified.** The one thing said about cash is a model check: ending
   cash on the cash flow statement must equal cash on the balance sheet. Nothing was said
   about operating cash versus excess cash. (2026-09-16-1, Q8)

8. **Related-party balances never came up** in any session, for the balance sheet or the
   income statement.

9. **The build's taxonomy already carries flags** named `excluded_from_al` and `include_in_nwc`
   on its balance sheet categories. These are the build's own design and have not been shown
   to or confirmed by the analyst. (knowledge/backlog.md, build note)

10. **Version 1 scope.** Version 1 fills an input-help workbook and does not run the model, so
    any NWC classification is something the workbook shows beside the balance sheet for the
    analyst to carry into the model, not something the tool computes a value from.
    (2026-09-18-1, Q1a-Q2)

## What the model should do with it

The interviews support very little here. Only these:

- Fill the balance sheet tab with the client's lines as stated, in the structure of last
  year's model for a repeat client; do not reclassify a line into or out of working capital
  on the tool's own authority.
- For a repeat client, where last year's model shows which balance sheet lines fed its NWC
  tab, carry that grouping forward exactly as the WS grouping is carried forward, and flag any
  line that has no counterpart.
- Treat the D tab's instruments as the list of interest-bearing debt, and show every balance
  sheet line that ties to one of them as such, so the reviewer can see what is debt.
- Where the client sent an NWC line-item forecast, present it beside the historical balance
  sheet lines in the same grouping, highlighted as client-sourced.
- If a line looks like cash, debt, a related-party balance or anything else a reviewer might
  exclude, raise it as a question with the line's label and amount; do not decide.

## What is still unknown

1. Which balance sheet lines the firm includes in net working capital, and which it excludes
   - cash, current debt and the current portion of long-term debt, lines of credit, accrued
   interest, related-party receivables and payables, income taxes, deferred revenue, operating
   lease liabilities under ASC 842, shareholder distributions payable - line by line.
2. What the `NWC`, `NWC (M)` and `WC` tabs each hold, and which lines on the BS tab feed each.
3. What `NWC or WC?` on the Input tab selects, and when each setting is used.
4. Whether the firm distinguishes operating cash from excess cash, and how much cash (if any)
   is treated as working capital.
5. How a related-party balance is treated when one appears.
6. How the exclusion decisions are shown in the model - a flag per row, a separate schedule, a
   formula range - so the input-help workbook can mirror it. (Needs the master model file.)
7. For a repeat client, whether the NWC grouping is carried forward unchanged like the WS
   grouping, and what changes it.
8. Whether the client's NWC line-item forecast is used unchanged, as the income statement
   forecast is, or rebuilt from the firm's own grouping.
9. Whether the build's `include_in_nwc` / `excluded_from_al` flags match any practice the firm
   actually has, or should be replaced by the firm's list.
10. Whether non-operating assets and liabilities are identified on the same pass, and where
    they go (the topic map's `asset-approach` angle, never asked).

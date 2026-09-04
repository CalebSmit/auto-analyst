# The two flags: Excluded from A/L, Include in NWC

Both flags describe the balance sheet. An income statement line carries both false,
always, and the procedure refuses nothing here - it simply sends a departure to review.

## Excluded from A/L

The valuation starts from the operating assets and liabilities. A line is *excluded*
when it is removed from that base and dealt with separately - valued on its own, added
back or netted at the end, or treated as a financing item:

- **Cash** - excluded by default; the operating requirement is set separately, and the
  rest is excess.
- **Investments and marketable securities**, cash surrender value of life insurance -
  excluded; non-operating, valued separately.
- **Amounts due from or to owners, officers, shareholders and affiliates** - excluded;
  these are equity in substance or are settled at the transaction.
- **Interest-bearing debt** of any maturity: line of credit, current portion, term
  loans, mortgages, notes payable - excluded; financing, not operations.
- **Equity** - excluded; it is what the valuation concludes on, not an input to it.

Everything else stays in: receivables, inventory, prepaids, fixed assets and their
depreciation, intangibles, lease assets and liabilities, payables, accruals, deferred
revenue, deferred taxes.

## Include in NWC

Net working capital is the operating current items, and only those:

| Included | Not included |
|---|---|
| accounts receivable, net of allowance | cash and equivalents |
| inventory, all stages | line of credit, current portion of debt |
| prepaid expenses | related-party balances either way |
| other operating current assets (unbilled, contract assets) | investments |
| accounts payable | lease liabilities |
| accrued liabilities (payroll, vacation, sales tax) | equity |
| deferred revenue and customer deposits | |
| other operating current liabilities | |

Cash and interest-bearing debt are never NWC, whatever their maturity. A line that is
excluded from A/L is never NWC either - the two flags agree on every default in the
taxonomy, and a proposal where they do not is reviewed.

## Departing from the default

The taxonomy's defaults are the firm's rule. Depart when the description says the line
is something other than what its category usually is:

- A "deposit" under other current assets that is a **customer's** deposit held is a
  liability (`deferred_revenue`), not an asset: change the category, not the flag.
- A "note receivable" from a **customer**, current, is operating: `other_current_assets`
  with NWC true. From an **officer**, it is `related_party_receivable`, excluded.
- "Accrued interest" is a financing accrual: `accrued_liabilities` stays the category,
  but NWC false and excluded from A/L true.
- "Income taxes payable" on a pass-through entity is an owner-level item: excluded.
- A **restricted** cash balance held for operations (a bonding requirement, an escrow
  the business must keep) may be included in A/L: `cash` with excluded false, and say
  why.

Every departure goes to a person, whatever the confidence. That is not a penalty; it is
the reason the flags can have defaults at all.

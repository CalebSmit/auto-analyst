# Edge cases

The lines that are tagged wrong most often, and what the firm does with each.

## Descriptions that name two things

- **"Salaries - officers and staff"** - `officer_compensation` only if the source labels
  show a separate staff line; otherwise `salaries_wages`, low confidence, rationale says
  the line is combined. Never split a line.
- **"Depreciation and amortization"** - `depreciation`, rationale says combined.
- **"Rent and utilities"** - `rent`, same treatment.
- **"Taxes and licenses"** - `other_operating_expense`; it is not income tax and it is
  not payroll tax unless the description says so.

## Descriptions that mean different things in different places

- **"Interest"** on an income statement is `interest_expense` unless the source sheet is
  an income section and the label says income. On a balance sheet, "accrued interest"
  is `accrued_liabilities` (excluded, not NWC) and "interest receivable" is
  `other_current_assets`.
- **"Deposits"** as an asset: prepaid if paid *by* the company (utility, lease,
  security deposits are `other_noncurrent_assets` when long-term); `deferred_revenue`
  when held *from* a customer. The source labels usually say which side.
- **"Notes payable"** with no maturity: `long_term_debt`. With "current" anywhere in the
  description or the source labels: `current_debt`. To an owner: `related_party_payable`.
- **"Distributions"** on an income statement extract of a pass-through: still `equity`,
  statement BS, and say the sheet is wrong about where it put it.

## Owner-related lines

Everything that names an owner, officer, shareholder, member or partner, or an entity
that shares ownership, is related-party: `officer_compensation` on the income statement,
`related_party_receivable` or `related_party_payable` on the balance sheet, `equity` for
capital movements. These are the lines EBITDA normalization reads first, so the
category has to be right even when the amount would look immaterial - which you cannot
see, and should not want to.

## Things that are not line items

Subtotals and totals ("Total operating expenses", "Gross profit", "Net income") should
not be in a normalized table; timing normalization aligns rows, and a total is not a
row. If one reaches you, tag it `unmapped`, `uncategorisable`, rationale "subtotal",
and let the reviewer remove it upstream. Do not give a total the category of its
section.

## Sparse descriptions

"Misc", "Other", "Adjustment", "Reclass", "Account 6", a bare code: `unmapped` with
`uncategorisable: true`. The source labels may add enough to place it - "Misc - office"
is `office_supplies` - but a bare "Misc" is not, and the cost of guessing is that the
guess looks finished.

## Precedents that no longer fit

A precedent carries the taxonomy version it was decided under. If its category is not
in the pinned list, the taxonomy has moved since; tag from the current list, cite the
precedent, and the reviewer sees both. If its category exists but you would tag
differently, you may - and the departure is reviewed, so the rationale has to carry the
reason, not just the conclusion.

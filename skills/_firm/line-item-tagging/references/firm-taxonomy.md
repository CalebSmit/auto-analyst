# Firm taxonomy - how to read it

The category list itself is not in this file. It arrives in the payload at the version
the run pinned (`coa-taxonomy@x.y.z`), because a reference document that restated it
would drift from the data the moment somebody added a category. This file is about how
the list is organised and where lines usually go wrong.

## Shape

Every category has a `statement` (IS, BS, or NA for `unmapped`) and a `section`.

Income statement sections, top to bottom: `revenue`, `cost_of_sales`,
`operating_expenses`, `other_income_expense`, `taxes`. Balance sheet sections:
`current_assets`, `noncurrent_assets`, `current_liabilities`, `liabilities` (either
maturity), `noncurrent_liabilities`, `equity`.

The section is not something you tag; it is what makes the category list navigable and
what the flags follow from. A line's statement should agree with the statement its
source sheet suggests. When they disagree - an "interest" line on a balance sheet
extract - trust the description, lower the confidence, and say so.

## The categories, by where lines usually land

**Revenue and cost of sales.** `revenue` is what the business sells; `contra_revenue`
is what it gives back (returns, allowances, discounts). `cost_of_sales` is everything a
chart puts above gross profit: direct materials, direct labour, subcontractors, freight
in. A "wages" line *above* gross profit is cost of sales; the same line below it is
`salaries_wages`. The source labels and periods you are given carry the ordering; the
description alone often does not.

**Compensation.** `officer_compensation` is the owners' and officers' pay, wherever the
chart puts it - the description says "officer", "owner" or names the role. Everything
else that is pay is `salaries_wages` (including commissions, bonuses and overtime).
`payroll_taxes` and `employee_benefits` are the employer's costs on top; an ESOP
contribution is a benefit.

**Occupancy and operations.** `rent`, `utilities`, `repairs_maintenance`, `insurance`,
`vehicle_expense`, `office_supplies`. Software subscriptions and dues sit in
`office_supplies` in this taxonomy - a convention, not a truth; follow it.

**Fees and selling.** `professional_fees` (legal, accounting, audit, consulting, tax
preparation), `advertising_marketing`, `travel_entertainment`.

**Non-cash and write-offs.** `depreciation`, `amortization`, `bad_debt`. Keep
depreciation and amortization apart even when the chart combines them; if a line
genuinely combines them, take `depreciation` and say the line is combined.

**Below the line.** `interest_expense`, `interest_income`, `gain_loss_on_disposal`,
`other_income_expense`, `income_tax`. "Other income" that is plainly operating (a
recurring service line the chart mislabelled) is `revenue`; when the description does
not say, it is `other_income_expense` with a low confidence.

**Current assets.** `cash`, `accounts_receivable`, `allowance_doubtful`, `inventory`
(all stages), `prepaid_expenses`, `other_current_assets`, and
`related_party_receivable` for anything due from owners, officers, shareholders or
affiliates.

**Non-current assets.** `investments`, `ppe` (every fixed-asset class at cost),
`accumulated_depreciation`, `intangibles` (goodwill included, accumulated amortization
included), `right_of_use_asset`, `other_noncurrent_assets` (deposits, deferred tax
assets).

**Current liabilities.** `accounts_payable`, `accrued_liabilities` (accrued payroll,
vacation, sales tax payable, payroll taxes payable), `deferred_revenue` (customer
deposits, unearned revenue, billings in excess), `other_current_liabilities`,
`line_of_credit`, `current_debt`.

**Long-term.** `lease_liability` (either maturity), `long_term_debt` (term loans,
mortgages, equipment loans, SBA loans, notes payable), `related_party_payable`
(shareholder loans, due to owner, due to affiliate), `other_noncurrent_liabilities`
(deferred taxes, deferred compensation).

**Equity.** One category for all of it: stock, paid-in capital, retained earnings,
members' or partners' capital, treasury stock, distributions, dividends, draws.

## `unmapped`

The honest answer. A description with nothing to go on ("Misc", "Adj", "Account 6", a
bare number) is `unmapped` with `uncategorisable: true`. It is always reviewed, and a
reviewer who can open the ledger finishes it in seconds. A near-miss category costs
far more, because it looks finished.

## What decides the tag

The description, the source labels, and the statement the source sheet suggests. Not
the amount - you never see one - and not the line's neighbours, beyond the ordering the
source labels carry. A precedent is stronger evidence than any of these, because a
person approved it.

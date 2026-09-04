# Disagreements - line-item-tagging, 400-item fixture

Where the replayed proposals and the gold set differ. The sign-off for P19 is a
person confirming the gold set is right on each of these rows.

Top-1 category agreement: 383/400 = 95.8%. Category and both flags:
380/400 = 95.0%.

## Category disagreements

| # | ref | description | gold | proposed | conf | why the gold is right |
|---|---|---|---|---|---|---|
| 1 | li_ade855c3e7 | Raw material purchases | cost_of_sales | inventory | 0.80 | purchases of materials are cost of sales on the income statement; inventory is the balance-sheet account they flow through |
| 2 | li_df7c7da258 | Salaries - office | salaries_wages | office_supplies | 0.68 | 'office' says which staff are paid, not office supplies; pay is salaries and wages |
| 3 | li_a48c27551d | Building maintenance | repairs_maintenance | ppe | 0.62 | maintenance is an expense; 'building' names what was maintained, not a fixed asset |
| 4 | li_089edf37ca | Interest earned | interest_income | interest_expense | 0.97 | 'earned' makes it income; a bare 'interest' would be expense |
| 5 | li_3237a58d39 | Allowance - A/R | allowance_doubtful | accounts_receivable | 0.80 | the allowance is a contra account with its own category; it is not the receivable |
| 6 | li_66c93a306c | Prepaid insurance | prepaid_expenses | insurance | 0.62 | a prepaid anything is the balance-sheet prepaid; the insurance expense is the income-statement line |
| 7 | li_2e111e5906 | CSV - life insurance | investments | insurance | 0.62 | cash surrender value is a non-operating asset valued separately, not an insurance expense |
| 8 | li_e3ff6d2f6b | Current portion of long-term debt | current_debt | long_term_debt | 0.82 | the current portion has its own category so the maturity split survives; excluded from A/L either way |
| 9 | li_8c8c489951 | Mortgage payable | long_term_debt | accounts_payable | 0.68 | a mortgage is interest-bearing debt; 'payable' does not make it trade payables |
| 10 | li_4df043a6d9 | Salaries - officers and staff | salaries_wages | officer_compensation | 0.74 | a combined line takes the general category; never split (edge-cases.md) |
| 11 | li_f23b3ef45d | Depreciation and amortization | depreciation | amortization | 0.68 | combined D&A takes depreciation and says so (edge-cases.md) |
| 12 | li_4d9ceeb535 | Depreciation & amortization | depreciation | amortization | 0.68 | combined D&A takes depreciation and says so (edge-cases.md) |
| 13 | li_028dae314e | Accrued interest payable | accrued_liabilities | accounts_payable | 0.68 | a financing accrual stays in accrued liabilities, not trade payables; the flags carry the treatment |
| 14 | li_a1cb1972c2 | Other income - service contracts | revenue | other_income_expense | 0.80 | a service-contract line labelled other income is operating revenue |
| 15 | li_e095e8296d | 6307 - Sales returns and allowances | contra_revenue | allowance_doubtful | 0.66 | sales allowances reduce revenue; they are not the allowance for doubtful accounts |
| 16 | li_9516e40d1b | 6677 - Raw material purchases | cost_of_sales | inventory | 0.76 | purchases of materials are cost of sales on the income statement; inventory is the balance-sheet account they flow through |
| 17 | li_1ed81b9df3 | 6543 - Salaries - office | salaries_wages | office_supplies | 0.62 | 'office' says which staff are paid, not office supplies; pay is salaries and wages |

## Flag departures (category agreed, a flag differs)

| ref | description | category | gold A/L excl · NWC | proposed A/L excl · NWC | why the gold is right |
|---|---|---|---|---|---|
| li_ac0a799b0b | Accrued interest | accrued_liabilities | True · False | False · True | a financing accrual: excluded from A/L, never NWC (nwc-inclusion-rules.md) |
| li_fdc953d98c | Income taxes payable | other_current_liabilities | True · False | False · True | owner-level on a pass-through: excluded from A/L, not NWC |
| li_a5371c49b5 | Restricted cash - bonding | cash | False · False | True · False | held for operations: stays in the A/L base; still not NWC |

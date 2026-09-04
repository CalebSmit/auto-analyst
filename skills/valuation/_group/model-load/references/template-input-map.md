# Template input map

How the firm's model templates name their inputs, and how the historical table's lines
land on them. The template's declared inputs arrive in the payload at the pinned
version; this is the reading guide.

## Names

An input is `<Line>_<Period>`: `Revenue_FY2`, `Officer_Comp_FY3`, `Payroll_Taxes_FY1`.
The line part is the template's own label for a taxonomy category, not the client's
chart of accounts. The period part is a slot on the template, not a year.

| template line | taxonomy category the table's lines carry |
|---|---|
| `Revenue` | revenue (net of contra_revenue, when the table carries both as one line) |
| `COGS` | cost_of_sales |
| `Officer_Comp` | officer_compensation - salary, bonus and any other officer pay, as the table aligned them |
| `Wages` | salaries_wages |
| `Payroll_Taxes` | payroll_taxes |
| `Rent` | rent |
| `Repairs` | repairs_maintenance |
| `Utilities` | utilities |
| `Insurance` | insurance |
| `Professional_Fees` | professional_fees |
| `Depreciation` | depreciation (amortization is separate on the table and unrouted here) |
| `Travel` | travel_entertainment |
| `Office` | office_supplies |
| `Other_Opex` | other_operating_expense, vehicle_expense, advertising_marketing, bad_debt and anything else operating the template has no line for |
| `Owner_Comp_Benchmark` | the engagement profile's owner-compensation baseline, not a table line |

## Periods

`FY1`, `FY2`, `FY3` are the three most recent fiscal years on the historical table,
oldest first. A table with more than three periods routes the latest three; a table with
fewer leaves the earliest slots unmapped and says so. A monthly or LTM table does not
route to a fiscal-year slot - list its figures as unrouted with the reason.

## One figure, one input

A template input takes exactly one figure. Where the table carries a line the template
combines (officer salary and officer bonus against `Officer_Comp`), bind the figure the
table carries for the combined line if timing normalization produced one, and otherwise
list the input as unmapped with the reason: combining is arithmetic, and arithmetic is
not yours. Where the table carries a line the template has no slot for, list the figure
as unrouted; the reviewer decides whether the template needs a line.

## What is never an input

Subtotals and totals: the template computes them. Add-backs: the schedule carries them
and the reviewer applies them. Anything below EBITDA the template does not name.

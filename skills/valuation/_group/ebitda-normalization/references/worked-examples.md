# Worked examples

Synthetic, from the Henderson Manufacturing fixture. Each shows the candidate as
proposed and what the procedure made of it.

## Officer salary, three years

Tagged `officer_compensation`, present FY2023 through FY2025. Proposed `owner_related`,
`officer_compensation: true`, periods all three, confidence 0.95. The procedure summed
salary and bonus per period through `recompute`, compared each total to the profile's
benchmark (survey median, ERI 2025, as of 2025-06-30), cited the benchmark on all six
items, marked every one above materiality, and sent every one to review. The proposal
never said an amount; the schedule carries six figures that each tie to their rows.

## Legal settlement, one year

Tagged `professional_fees`, present in FY2024 only. Proposed `non_recurring`,
confidence 0.9, rationale "a settlement line that appears in one period". Above
materiality, reviewed. A reviewer who knows the settlement was the second of three
will reject it, and the rejection teaches nothing - which is why the write-back skips
rejections.

## Rent paid to the owner's LLC

Tagged `rent`, every period. Proposed `related_party` with `needs_fact: "market rent
for the facility"`. The procedure kept the candidate, marked it reviewed, and put the
missing fact in the rationale. No market rent was assumed. The amount on the schedule
is the rent as paid; the adjustment is the reviewer's once the fact is supplied.

## Repairs and maintenance, proposed as non-recurring

Tagged `repairs_maintenance`, every period, ordinary amounts. Proposed `non_recurring`
for FY2024 on the strength of the description alone. The procedure found the line in
every period, set `recurs_in_all_periods`, and sent it to a person. It is on the
schedule as flagged, not as proposed; model load skips it.

## Q3 special project, one year, immaterial

Present in FY2025 only, below the materiality threshold, confidence 0.92. The first
pass's item would have auto-accepted. The verification pass, seeing only the row and
the excerpt, answered that "special project" does not say the project will not recur -
so the item went to review. That is the verification pass doing its one job: it sees
the excerpt without the first pass's reasoning, and it disagrees when the evidence is
thinner than the rationale was.

## Bad-debt write-off, missed

Present in FY2023 only, tagged `bad_debt`, not proposed. The fixture's recall is
measured against the analyst's list, and this is the miss in it. The model builder
sees nothing; the reviewer sees the recall figure on the scorecard.

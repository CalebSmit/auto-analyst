# Line-item matching

Reference for `timing-normalization`. What counts as the same line item across periods,
what does not, and how to say which.

## The four kinds

| kind   | what happened                                              | example                                                   |
|--------|------------------------------------------------------------|-----------------------------------------------------------|
| exact  | the same label in every period                             | `Revenue` / `Revenue`                                     |
| rename | one line, a different label                                | `Repairs & Maint.` / `Repairs and Maintenance`            |
| split  | one earlier line became several later ones                 | `Rent` / `Rent - facilities` + `Rent - equipment`         |
| merge  | several earlier lines became one                           | `Bank charges` + `Merchant fees` / `Bank and card fees`   |

A split or a merge is still one canonical line item. Its sources in the period where it
is several rows are several locators; the tool sums them for that period and records the
derivation, so the figure ties out to the rows it came from.

## Rules

1. **Match on meaning, not on spelling.** Abbreviations, punctuation, case and
   re-ordering ("Maint. & Repairs") do not make a different line. A different account
   does: `Rent - facilities` and `Rent - equipment` are two lines, and only a split
   relates them to an earlier `Rent`.
2. **One canonical label per line item.** Prefer the most recent period's label unless
   it is an abbreviation of an earlier one. Never invent a label that appears in no
   period.
3. **Every row goes somewhere.** Each locator appears exactly once: under a canonical
   label or in `unmatched`. A row you leave out is reported as "not in the proposal",
   which is a worse outcome than an honest unmatched entry.
4. **Never invent a predecessor.** A line present in FY2025 with nothing like it in
   FY2023 or FY2024 is a line item with one period, listed once as unmatched for the
   periods it lacks, with the reason. Do not attach it to the nearest-sounding earlier
   line to make the table look complete.
5. **Subtotals are lines too.** `Total operating expenses` is matched like any other row,
   so the tie-out guard can recompute it from the rows above. Do not drop subtotals and
   do not compute them.
6. **When in doubt, unmatched.** The alignment report reaches a person. A wrong match
   reaches the model template.

## What "unmatched" needs

`source_id`, `locator`, the label as read, and a reason a reviewer can act on:

- `no counterpart in the other periods`
- `two plausible counterparts: Rent - facilities and Rent - equipment; not split by the file`
- `subtotal of rows the file does not itemise`

A reason is not "unmatched".

## What the report is for

The match rate on this skill's fixtures is at least 98%, and every unmatched line is on
the report. The number is a floor for the fixtures; on a real engagement, the report is
the product. A client whose chart of accounts changed is a fact the analyst needs to
know, and a forced 100% would hide it.

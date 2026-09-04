# fixtures/skills/ebitda-normalization/

The golden case for EBITDA normalization. Synthetic throughout: Henderson
Manufacturing, the blueprint's own invented company, three fiscal years of income
statement, round numbers.

## cases/henderson/

| file | what it is |
|---|---|
| `case.json` | Three IS files as the readers leave them: blocks of rows with labels, values and ordinals. Twenty lines, three of which appear in one year only. |
| `timing_proposal.json` | The alignment, every label exact. The tests run the real timing tool over it so the historical table's figures carry real derivations and tie out. |
| `tagging.json` | The tagged line items, in P19's output shape. |
| `proposal.json` | What the first pass is expected to propose: eight candidates, no amount anywhere. One is a trap - repairs proposed as non-recurring. |
| `verification.json` | What the verifier is expected to answer: every item supported except the special project. |
| `gold.json` | The analyst's add-back list, eighteen line-periods. One of them - the bad-debt write-off - is not proposed, so recall is 17/18. |
| `expected.json` | The counts the tests check. |

## What the case proves

- **Every amount ties.** The schedule's figures are the lines' own figures, re-derived
  by `recompute` from the rows behind them; the tie-out guard then re-derives every one
  independently.
- **Recall against the analyst.** Seventeen of eighteen; the miss is stated.
- **Material means reviewed.** Every item at or above the engagement threshold is
  `review_required`, and the router refuses to auto-accept one even when handed a
  confidence of 0.99 and a cleared flag.
- **Recurring is not non-recurring.** The repairs trap is flagged `recurs_in_all_periods`
  and reviewed, never proposed as an add-back.
- **The verifier disagrees.** The special project would have auto-accepted; the
  verification pass, seeing the excerpt without the rationale, sends it to a person.

## cases/no_benchmark/

A profile with no owner-compensation baseline. The skill escalates before any model
call; nothing is masked, assembled or sent.

## How the gold list was built

Authored, per line, by the rules in `addback-taxonomy.md`. The blueprint's plan is that
add-backs on a real engagement are confirmed by an analyst at the pilot; until P24 the
sign-off is on this case.

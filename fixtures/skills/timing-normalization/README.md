# fixtures/skills/timing-normalization/

Golden cases for the first real skill. Synthetic throughout - the company is the
blueprint's own invented Henderson Manufacturing and every figure is a round number
chosen so the subtotals foot.

Each case holds `case.json` (the files as the readers leave them: blocks of rows with
labels, values and ordinals, plus what the period detector read), `proposal.json` (the
alignment a model is expected to propose - a mapping, never a number) and
`expected.json` (values computed independently of the tool, plus the counts).

| case | what it proves |
|---|---|
| annual_drift | three years with a rename, a split, a merge and one line with no predecessor |
| monthly_gap | five months with April missing: a gap reported, never filled |
| conflict | two files claim FY2024 and disagree on revenue: both figures reported, neither taken |
| ambiguous | a file the period detector could not settle on scale: escalates before any model call |

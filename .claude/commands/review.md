---
description: Read a workbook, a report or a folder for the mistakes a reviewer would catch, and offer to fix the mechanical ones
argument-hint: "<file or folder> [what you want me to pay attention to]"
---

Run the three reads over what I pointed you at, then help me act on what they found.

## 1. Run it

```
python -m uv run python tools/aa.py review <target> --json
```

Work out `<target>` from `$ARGUMENTS`. If I gave you no path at all, ask for one - do not
guess at a folder. If I named a folder, that is the whole folder.

When a `.json` normalized table is in scope, add the tolerances, because the ratio
questions have **no defaults on purpose** and will otherwise report themselves as unasked:

```
python -m uv run python tools/aa.py review <target> --json --move points=5 --move days=10 --move x=0.5 --years 5
```

Those four numbers are a starting point, not the firm's. If I have told you the firm's
thresholds before, use those; if not, use these and say in one line that you did.

## 2. Tell me what matters, in this order

1. **`wrong` from the formula audit** - the file disagrees with itself. A total whose range
   stops a row short of its block, a total counting another total, a saved total that does
   not equal what it adds. Each of these is provable from the file, so lead with them and
   quote the cell and the formula.
2. **`slip` from the prose checks** - mechanical and provably a mistake.
3. **`fail` from the questions** - these are *questions for me*, not defects. Say them as
   questions. Do not answer them: whether a margin moving eight points is a problem
   depends on the business, and you do not know the business.
4. **`suspect`, `inconsistent`, `tell`** - worth an eye, grouped, not one line each.

Do not restate the tool's output. Read it and tell me what you would look at first and
why. If nothing was found, say so in one line.

## 3. Offer the fixes you can actually make

- **Prose slips** in a `.md` or `.txt`: offer
  `python -m uv run python tools/prose_checks.py <file> --fix --out <file>.fixed.md`,
  which makes four mechanical substitutions and touches nothing else. It writes a new
  file unless I say `--in-place`. Show me the diff before I keep it.
- **Prose slips in a `.docx`**: the tool refuses, and it is right to - a paragraph's text
  is split across runs that carry the formatting. Give me the paragraph number and the
  sentence so I can make the change in Word.
- **Em dashes and the register words**: these are tells, not errors. Propose the specific
  rewrite per sentence. Never do a blanket replace: swapping every em dash for a comma
  produces sentences that do not parse.
- **A wrong formula**: tell me the cell, what the range covers, and what it looks like it
  was meant to cover. **Do not edit the workbook.** Nothing in this project writes into a
  spreadsheet outside `tools/write_template.py`, and a tool that widened a SUM to what it
  guessed was meant would be the most dangerous thing here.

## 4. If a file could not be read

Say which one and why, and keep going with the rest. An unreadable workbook in a folder of
forty is one refusal and thirty-nine readings, never a stop.

Anything I typed after the command tells you what to pay attention to: $ARGUMENTS

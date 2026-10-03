"""A figure that is not in the statement's unit, because its own label says so.

A statement states one scale for itself - *in thousands* - and then prints rows that are not
in it. The filing says so out loud: ResMed's balance sheet reads **"(In US$ and in thousands,
except share and per share data)"**, and EDGAR's own workbook writes the exception into each
row's label: `Common stock, shares, issued (in shares)`, `Common stock, par value (in dollars
per share)`, `Basic (in dollars per share)`.

**What went wrong without this.** The scale is per *file* - `SourceFile.scale`, applied to
every row of it - and six lines in three modules multiplied a figure by its scale
(`harness/procedures/ebitda_normalization.py` three times, `deliver/workpaper.py` once and
`harness/restate.py` twice; P165 made them one place that asks the unit first).
So on a statement in thousands a share count of 135,361,000 is reported as 135 **billion**
shares, and a par value of $0.001 becomes **$1.00**. Both are plausible numbers, which is why
nothing downstream catches either. Found by `tools/check_against_filer.py` against EDGAR's
own workbook, where the figure matched the filer exactly and only without the scale.

**It does not bite on a PDF**, and that is why one document could not show it. A typesetter
keeps the share count inside the label - `Common stock, $0.001 par value, authorized 220,000
shares; shares issued 145,581 and` - so the only figures in the column are dollars, and the
146 printed there really is $146 thousand. A workbook gives each one its own row, and a
client's workbook looks far more like a workbook than like typesetting.

**Reading what the label says is not guessing.** It is what `two_sides` does with the two
labels a balance sheet writes, and what `is_a_total` does with the word *total*. What would
be guessing is the looser rule, and the measurement below is why it is not used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["DECLARES", "Declared", "declared_unit"]

DECLARES = re.compile(
    r"\(\s*(?:in\s+)?(?P<said>"
    r"shares"
    r"|dollars?\s+per\s+share"
    r"|usd\s+per\s+share"
    r"|per\s+share"
    r")\s*\)",
    re.IGNORECASE,
)
"""A unit named in a parenthetical, anywhere in the label, and nothing looser than that.

Measured over **2,373 rows** - every row carrying a figure on all 108 pages of one filing,
all 124 of another, and every readable sheet of EDGAR's workbook. **53 rows** match, which are
22 distinct labels: a comparative statement prints each one once per column, and the
statements of equity print several. Every one of them is genuinely not in the statement's
unit: `Basic (in dollars per share)` at -0.280, `Basic (in shares)` at 132,462,
`Conversion price (in dollars per share)` at 35.92.

**Not anchored to the end**, which it was at first. That missed four and all four were real:
`Beginning balance (in shares) at Dec. 31, 2023` declares its unit and then qualifies it with
a date, and that is a share count of 133,619,000. Relaxing the anchor over the same 2,373
rows added exactly those four distinct labels and nothing else, which is the measurement that
settled it rather than an opinion about where a parenthetical sits.

**The looser rules are not merely weaker, they are harmful**, and that is why this stops at
a parenthetical. Adding the phrases a typesetter writes - `par value`, `shares issued` -
takes `Common stock, $0.001 par value, authorized 220,000 shares; shares issued 145,581 and`
whose figure is **146**, a real $146 thousand, and declares it not currency: the scale then
stops applying to a figure that needs it, which is the same thousand-fold error in the other
direction. Matching any mention of a share is worse again, and costs `Taxes paid related to
net-share settlement of equity awards` (-1,025) and `Treasury stock, at cost, 46,798,043
shares at June 30, 2026` (-2,778,591), both ordinary dollar amounts.

**What it does not catch**, measured rather than left to be discovered: a row that is a share
count and says so only in words. `Entity Common Stock, Shares Outstanding` at 136,412,866 is
the one such row in these three filings, on a cover page rather than a statement. A filing
that declares its exception in prose at the top of the page and nowhere else is the same
limit, and it is a real one - a reader cannot tell which of a page's rows a sentence was
about, and guessing is what the two rejected rules above do.
"""


@dataclass(frozen=True)
class Declared:
    """What a row's own label says it is in."""

    unit: str
    """One of the `figure.schema.json` enum - here `shares` or `currency`.

    A per-share amount is **currency**, because it is an amount of money; what is different
    about it is its scale. The contract has carried this enum since P02 and the producer has
    only ever written `currency`, so this is a field that existed for exactly this and had
    never been exercised.
    """
    scale: int = 1
    """The scale that applies to this row instead of the statement's, which is always 1:
    `(in shares)` means the count itself and `(in dollars per share)` means the dollars
    themselves. `figure.schema.json` allows 1, 1000 and 1000000."""
    said: str = ""
    """The words in the label that said so, carried so a person reading a figure can see
    why it is not at the statement's scale."""


def declared_unit(label: str) -> Declared | None:
    """What this row's label declares, or `None` where it declares nothing.

    `None` rather than a currency default, because the two are different facts: a label that
    says nothing leaves the statement's own scale in force, and a caller that could not tell
    those apart would have to decide what silence means in two places.
    """
    found = DECLARES.search(label or "")
    if found is None:
        return None
    said = " ".join(found.group("said").lower().split())
    if said == "shares":
        return Declared(unit="shares", scale=1, said=found.group(0).strip())
    return Declared(unit="currency", scale=1, said=found.group(0).strip())

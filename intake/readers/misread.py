"""A figure that is nearly a figure, and the row that vanished because of it.

**The failure this build says it most cares about** is a figure a machine read confidently
and wrongly, because no probability catches it. The usual answer here is arithmetic: a total
that stops adding up is what finds a misread, and `footing.py` is that. This is the other
half of the same problem - a misread that does not produce a wrong figure, but no figure at
all.

Measured on page 56 of the filing in `fixtures/public`, read by a real engine: the printed
**5,000** came back as **`5,0o0`**, a zero read as the letter o, **at 0.938 confidence**. Too
high for any score to flag, and in the ordinary run of things not flagged by anything else
either, because of what happens next. Put through the reader:

    Inventories l27,496   ->  label '', values []

The whole row disappears, label and all. That is the safe direction - nothing wrong is
stored, and the total above it stops footing - but it is **silent**: a scanned statement
quietly loses rows and the only thing a person is told is that some total is out by an amount
nobody can account for. The amount it is out by is the row that went missing.

So a token that is shaped like a figure but for one letter is named, with the line it sits
on, and reported where the figure would have been.

**It reports and never repairs.** Substituting a digit for a letter would be this code
guessing at a client's number, which is the most dangerous thing this repository could
contain: it would produce a plausible figure, carrying a real locator, that the document does
not print. `reads_as` is offered because it is the first thing a person wants to see - and it
is deliberately a **string**, never a float, so that nothing downstream can add it up.

**Calibrated against text nobody misread**, which is the rule here: a check whose findings
are mostly not findings teaches a reader to skip the section it is in. Over all 108 pages of
the filing's text layer - 58,606 tokens - this reports **nothing**, and it names the one
token the engine really got wrong.

Three decisions were made on that measurement rather than on taste. The **two-digit floor**
stays: without it the rule reported `1B` and `9B` on four pages, which are billions written
the way people write them. **`D` for zero** went: a real confusion on a bad photocopy, and it
reported `21D` twice - a section of the Securities Exchange Act - in a filing belonging to a
company called 3D Systems. And a **one-letter rule** went, because it changed no answer on
either input and was silently skipping `1O,5O0`, which is an ordinary scan of a bad copy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = ["CONFUSIONS", "Misread", "misreads_in", "nearly_a_figure"]

CONFUSIONS = {
    "o": "0",
    "O": "0",
    "l": "1",
    "I": "1",
    "i": "1",
    "S": "5",
    "s": "5",
    "B": "8",
    "b": "6",
    "Z": "2",
    "z": "2",
    "G": "6",
    "q": "9",
}
"""Which digit each letter stands in for when an engine gets it wrong.

The family every OCR writeup names, and the direction that matters is this one: a letter
*where a digit belongs*. The reverse - a digit inside a word, `1nventories` - is a different
failure and a harmless one, because nothing tries to read a label as a number.

`G` for six is here because it turns up on a photocopy rather than on a screen; `b` is six
rather than eight because a lowercase b has the loop at the bottom.

**`D` for zero was here and is gone**, which is the only entry that cost anything. It is a
real confusion on a bad photocopy, and over the filing's text layer it reported `21D` twice -
*"contribution under Section 10(b) and 21D of the Securities Exchange Act"*. A statutory
section number is not a misread, and two findings that are not findings out of three is the
ratio this repo takes a check out over. The same measurement is why the rest of the table
stays: without `D` it reports nothing at all across 58,606 tokens.
"""

_LETTERS = "".join(CONFUSIONS)

NEARLY = re.compile(
    # Digits, commas and periods, at least one letter from the family, at least two digits.
    rf"^(?=(?:[^\d]*\d){{2}})(?=.*[{_LETTERS}])[\d,.{_LETTERS}]+$"
)
"""Figure-shaped but for its letters.

**At least two digits**, which is measured: without that floor the rule reported `1B` and
`9B` on four pages of the filing, and those are billions written the way people write them.
It is also what keeps a word out, because a word has no digits in it - `lOSS` is excluded by
the floor and not by anything about letters.

**Any number of letters, not exactly one.** A one-letter rule was here first, on the
reasoning that a token with two of them is a word rather than a near miss. Measured over the
filing's text layer and over the engine's own output it **changed no answer at all** - the
same nothing, and the same one finding - which is the state this repo removes a threshold in
rather than keeping it as caution. It was also wrong about what it excluded: `1O,5O0` is two
digits misread in one figure, which is an ordinary photocopy, and the rule skipped it in
silence.

Not anchored on comma grouping, though a statement's figures almost always carry it, because
a cell can hold a bare number - the Common stock balance on the filing's own balance sheet is
`146` - and `l46` is exactly the misread worth catching there.
"""

_STRIP = ".,:;%*()$ "


@dataclass(frozen=True)
class Misread:
    """One token that is almost a figure, and where it was."""

    token: str
    """As it was read, unchanged."""
    reads_as: str
    """What it would say if each letter were the digit it resembles.

    A **string**, deliberately, and not a number. It is here because it is the first thing a
    person wants to see, and it must stay something nothing can add up: the moment this is a
    float, something downstream totals it and the system has invented a figure the document
    does not print.
    """
    line: str
    """The whole line it sits on, because the label beside it is what says which row was
    lost."""
    ocr: bool = False
    """Whether the line was read by an engine off an image rather than lifted from a text
    layer.

    Carried because it changes what a person does. On a scan this is a misread and the thing
    to do is read the figure off the page. In a text layer the document really does contain
    this, which is a worse fact about the file and not one re-reading fixes.
    """

    def as_line(self) -> str:
        where = "read off a scan" if self.ocr else "printed in the file"
        return (
            f"{self.token!r} is not a number ({where}); "
            f"if its letters are digits: {self.reads_as}"
        )


def nearly_a_figure(token: str) -> str | None:
    """What this token would read as if its one letter were a digit, or `None`.

    `None` rather than False so that the caller gets the answer and the question together -
    a predicate here would mean every caller re-did the substitution to say anything useful,
    and one of them would do it differently.
    """
    stripped = token.strip(_STRIP)
    if not stripped or not NEARLY.match(stripped):
        return None
    return "".join(CONFUSIONS.get(c, c) for c in stripped)


def misreads_in(lines: Sequence[object]) -> tuple[Misread, ...]:
    """Every almost-a-figure in a page's lines, in the order they appear.

    Takes the reader's own `Line` objects - anything with `text` and `ocr` - rather than
    strings, because whether an engine read the line changes what a person does about it.
    """
    found: list[Misread] = []
    for line in lines:
        text = str(getattr(line, "text", line) or "")
        for token in re.split(r"[\s()$]+", text):
            reads_as = nearly_a_figure(token)
            if reads_as is None:
                continue
            found.append(
                Misread(
                    token=token.strip(_STRIP),
                    reads_as=reads_as,
                    line=text.strip(),
                    ocr=bool(getattr(line, "ocr", False)),
                )
            )
    return tuple(found)

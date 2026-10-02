"""A number written out in words, in one place.

`tests/counting.py` has had this table since P114 and says why: the count of preflight
checks came to be typed in three places and was wrong in all three the day a check was
added. Its rule is *assert that the prose and the list agree, and derive the prose from the
list - never write the number down twice.*

It lived under `tests/` and so could only be used to check a page after the fact, never to
build one. The pages went on typing their numbers: the Setup page said "Fourteen checks"
beside a panel that printed `15 checks` from the live configuration, and the help page said
"Three colours" above four of them. A rule a page cannot reach is a rule a page will break.

So the table is here now, where a page can read it, and `tests/counting.py` re-exports it -
one table, and the test that holds a sentence to a list is measuring the same thing the
sentence was built from.
"""

from __future__ import annotations

WORDS = (
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
    "Twenty",
)


def in_words(count: int) -> str:
    """`14` -> `"Fourteen"`. Raises rather than guessing past the end of the table.

    Refusing is the point. A page that quietly rendered `21 checks` where every other
    sentence says a word would be a worse outcome than a page that does not build, because
    nobody would notice it for a hundred phases - which is exactly what happened to the
    number this replaced.
    """
    if not 0 <= count < len(WORDS):
        raise AssertionError(
            f"{count} is past this table; extend WORDS rather than writing the number down"
        )
    return WORDS[count]

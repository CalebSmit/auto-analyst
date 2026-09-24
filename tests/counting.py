"""One place for a number that is written out in words.

The blueprint is prose and the code is a list, and a test that ties them together has to
turn one into the other. Written here rather than in each test that needs it, because that
is exactly how the count of preflight checks came to be typed in three places and be wrong
in all three the day P114 added one - B-066's ninth and tenth instances, both found by a
checkpoint rather than by anyone reading.

The rule this file exists to make easy: **assert that the prose and the list agree, and
derive the prose from the list.** Never write the number down twice.
"""

from __future__ import annotations

WORDS = [
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
]


def in_words(count: int) -> str:
    """`14` -> `"Fourteen"`. Raises rather than guessing past the end of the table."""
    if not 0 <= count < len(WORDS):
        raise AssertionError(
            f"{count} is past this table; extend WORDS rather than writing the number down"
        )
    return WORDS[count]

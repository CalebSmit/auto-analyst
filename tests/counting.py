"""One place for a number that is written out in words.

The blueprint is prose and the code is a list, and a test that ties them together has to
turn one into the other. Written here rather than in each test that needs it, because that
is exactly how the count of preflight checks came to be typed in three places and be wrong
in all three the day P114 added one - B-066's ninth and tenth instances, both found by a
checkpoint rather than by anyone reading.

The rule this file exists to make easy: **assert that the prose and the list agree, and
derive the prose from the list.** Never write the number down twice.

**The table moved in P148.** It lived here, under `tests/`, which meant a test could check
a sentence after the fact but a page could never build one - so the pages went on typing
their numbers, and two of the four on the consoles were wrong. It is `ui/words.py` now,
where production can reach it, and this module re-exports it so there is still one table
and the test measures the same thing the sentence was built from.
"""

from __future__ import annotations

from ui.words import WORDS, in_words

__all__ = ["WORDS", "in_words"]

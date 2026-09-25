"""How a procedure's payload is written down.

One function, because the alternative was five call sites each deciding independently how
to serialize - and they had all decided the same wrong thing, which is what a copied
default looks like from the inside.

**Why it is compact.** Every payload here is read by a model and by nothing else. The
context assembler measures the whole in bytes against a declared ceiling, the provider
charges by the token, and `indent=1` spends a newline and a space on every key of every
row for a reader that does not exist. On a catalogue shaped like the first real client
folder - about 1,100 figures - that was 52 KB of whitespace inside 269 KB, and the
assembled model-load context was 305 KB against a ceiling of 400 KB. The step closest to
refusing a real client was carrying a fifth of its bulk as indentation.

**What it does not do.** It changes no key, no value and no structure: the same object
parses out the other side, which is the whole reason it is safe to do the night before a
first real run. Dropping the repeated key names as well would mean a different shape for
the model to understand, and that is a change to what is asked rather than to how it is
spelled - it belongs in a phase that can measure whether the answers got worse (B-083).

A person reading a stored context sees one long line. That is what `json.tool` is for,
and it is the right trade: the payload is written for the model that reads it every time,
not for the person who reads it twice a year.
"""

from __future__ import annotations

import json
from typing import Any

COMPACT = (",", ":")
"""No space after the comma, none after the colon. The tightest JSON that is still JSON."""


def as_payload(body: Any) -> str:
    """The text of a payload: the same object, with nothing spent on looking nice."""
    return json.dumps(body, separators=COMPACT)

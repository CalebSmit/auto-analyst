"""Read an assembled message as what it carries, not as how it is spelled.

The fourth of the shared helpers, and it exists for the same reason as the other three.
`tests/counting.py` is because a number written twice drifts; `tests/importing.py` is
because a substring cannot answer "does this module import that package";
`tests/reading.py` is because a comment explaining a fix satisfies the grep meant to check
it. This one is because of what P124 found:

    **an assertion about what the model was given, written as an assertion about
    punctuation.**

`assert '"id": "officer_compensation"' in user` is a test about whether the taxonomy
reaches the model. It passed for a year, and it failed the day a space after a colon was
removed - while the taxonomy still reached the model, in full, unchanged. Three tests
across `tests/p19` and `tests/p20` had the same shape, and every one of them was asking
the message's serializer for an answer about the message's content.

An assembled context is several sections, each wrapped in untrusted-content markers, so it
is not one JSON document: `text[find("{"):rfind("}")]` spans several and parses as none.
Decoding them one at a time is what lets a test ask the real question.

The rule: **assert what was sent, not how it was written down.**
"""

from __future__ import annotations

import json
from typing import Any


def json_objects(text: str) -> list[dict[str, Any]]:
    """Every JSON object embedded anywhere in an assembled message, in the order they
    appear. Prose between and around them is skipped, as are the section markers."""
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    at = text.find("{")
    while at >= 0:
        try:
            body, end = decoder.raw_decode(text, at)
        except ValueError:
            at = text.find("{", at + 1)
            continue
        if isinstance(body, dict):
            found.append(body)
        at = text.find("{", max(end, at + 1))
    return found


def sections_with(text: str, *keys: str) -> list[dict[str, Any]]:
    """The embedded objects carrying every one of these keys at the top level.

    How a test names the section it means - "the one with `taxonomy` and `items`" - rather
    than by its position, which changes whenever the context gains a section.
    """
    return [body for body in json_objects(text) if all(k in body for k in keys)]


def anywhere(text: str, key: str, value: Any) -> bool:
    """Whether `key` is set to `value` anywhere in any embedded object, at any depth.

    For the claims that are about a field being present and correct rather than about
    where it sits - a citation's `locator`, an amount's `raw`, a flag's `true`.
    """

    def walk(node: Any) -> bool:
        if isinstance(node, dict):
            if key in node and node[key] == value:
                return True
            return any(walk(v) for v in node.values())
        if isinstance(node, list):
            return any(walk(v) for v in node)
        return False

    return any(walk(body) for body in json_objects(text))


def values_at(text: str, key: str) -> list[Any]:
    """Every value this key takes anywhere in the message, at any depth. For asserting
    the shape of a set of citations rather than one of them."""
    out: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for name, value in node.items():
                if name == key:
                    out.append(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for body in json_objects(text):
        walk(body)
    return out

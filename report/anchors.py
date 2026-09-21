"""Where a thing is in a document, by name.

The binding rule this whole package exists to keep: **a bookmark or a heading, never a
paragraph index**. The model's version of the same rule is *bind by named range, never by
cell address* - `B44` is not a contract because somebody inserts a row and `B44` is now a
different number. A report is worse, because a report is edited in prose: somebody adds a
sentence to the market commentary and every index below it moves by one, silently, and
Appendix F gets written into Appendix E.

Two kinds of anchor, and the order matters:

* a **bookmark** is what somebody put there deliberately. It survives editing, it survives
  text changes, and Word carries it around with the content it marks. It wins.
* a **heading** is the fallback, because a report that nobody has bookmarked still has
  "Appendix C - Economic Conditions" in it as a heading, and asking a person to bookmark
  six places in last year's document before the tool will work is a way of not being used.

A heading match is on the text, normalised for the things that differ between two years of
the same document: case, the kind of dash, the amount of whitespace. It is deliberately
**not** fuzzy beyond that. A near-match that silently picked the wrong heading would put an
appendix in the wrong place, and the whole point of binding by name is that it does not
have to be guessed at.

An anchor that is not there is a refusal naming it. Never the closest thing, and never the
end of the document.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from registries.errors import BINDING_MISSING, RegistryError, diagnose

__all__ = ["Anchor", "anchors_in", "find_anchor", "normalise", "span_of"]

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

BOOKMARK = "bookmark"
HEADING = "heading"

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")


def normalise(text: str) -> str:
    """The same heading, written two ways in two years, compared as one thing.

    Case, dash characters and runs of whitespace differ between one year's document and
    the next without meaning anything. Everything else is left alone on purpose: this is
    normalisation, not matching, and a near-match that quietly picked a different heading
    would put an appendix in the wrong place.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_DASHES)
    return re.sub(r"\s+", " ", folded).strip().casefold()


@dataclass(frozen=True)
class Anchor:
    """A named place, and the block element it sits on."""

    name: str
    kind: str
    """`bookmark` or `heading`."""

    element: Any
    """The `w:p` or `w:tbl` this anchor is attached to."""

    level: int = 0
    """For a heading, its outline level. Zero for a bookmark, which has no depth - and
    that is why a bookmarked span is bounded by the *next* bookmark rather than by a
    heading level."""


def anchors_in(document: Any) -> tuple[Anchor, ...]:
    """Every named place in a document, in document order.

    Bookmarks first at each position, because a bookmark is deliberate and a heading is
    what happened to be written.
    """
    found: list[Anchor] = []
    for block in document.element.body.iterchildren():
        if not isinstance(block.tag, str):
            continue
        for mark in block.iter(f"{W}bookmarkStart"):
            name = mark.get(f"{W}name")
            # Word's own hidden bookmark. Present in most documents, meaning nothing.
            if name and name != "_GoBack":
                found.append(Anchor(name, BOOKMARK, block))
        if block.tag == f"{W}p":
            level = _heading_level(block)
            if level:
                found.append(Anchor(_text_of(block), HEADING, block, level))
    return tuple(found)


def find_anchor(document: Any, name: str) -> Anchor:
    """The place called `name`, or a refusal naming it.

    A bookmark beats a heading with the same name: the bookmark was put there on purpose.
    """
    named = anchors_in(document)
    wanted = normalise(name)

    for anchor in named:
        if anchor.kind == BOOKMARK and normalise(anchor.name) == wanted:
            return anchor
    for anchor in named:
        if anchor.kind == HEADING and normalise(anchor.name) == wanted:
            return anchor

    raise RegistryError(
        diagnose(
            BINDING_MISSING,
            f"there is no bookmark or heading called {name!r} in this report. Nothing is "
            f"written to a guessed location - add a bookmark with that name, or correct "
            f"the anchor the appendix binds to.",
            locator=f"report/anchor/{name}",
            expected=name,
            found=_nearest(named, wanted),
        )
    )


def span_of(document: Any, anchor: Anchor) -> tuple[Any, ...]:
    """The block elements this anchor owns - what an update replaces.

    Where it stops is the whole question, and the two kinds of anchor answer it
    differently:

    * a **heading** owns everything until the next heading at the same level or above. A
      sub-heading inside Appendix C belongs to Appendix C; Appendix D does not.
    * a **bookmark** owns everything until the next anchor of any kind, because a bookmark
      has no depth to compare. Somebody who bookmarks a place is saying "this bit", and the
      next named place is where "this bit" stops.

    The anchor's own block is included: replacing an appendix replaces its heading too,
    because the new content brings its own.
    """
    blocks = [b for b in document.element.body.iterchildren() if isinstance(b.tag, str)]
    try:
        start = blocks.index(anchor.element)
    except ValueError:  # pragma: no cover - an anchor always comes from this document
        return ()

    owned = [anchor.element]
    for block in blocks[start + 1 :]:
        if _ends_the_span(block, anchor):
            break
        owned.append(block)
    return tuple(owned)


def _ends_the_span(block: Any, anchor: Anchor) -> bool:
    if anchor.kind == HEADING:
        level = _heading_level(block) if block.tag == f"{W}p" else 0
        return bool(level and level <= anchor.level)
    # A bookmark stops at the next named place of any kind.
    if block.tag == f"{W}p" and _heading_level(block):
        return True
    return any(
        mark.get(f"{W}name") not in (None, "_GoBack") for mark in block.iter(f"{W}bookmarkStart")
    )


def _heading_level(paragraph: Any) -> int:
    """Its outline level, or zero.

    Read from the style name rather than from `w:outlineLvl`, because that is what a
    person editing the document actually sets and what carries between two copies of the
    same template.
    """
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    if style is None:
        return 0
    value = (style.get(f"{W}val") or "").strip()
    match = re.fullmatch(r"(?i)heading\s*([1-9])", value.replace("Heading", "Heading "))
    if match:
        return int(match.group(1))
    # Word writes the built-in styles without a space; a template may localise them.
    match = re.fullmatch(r"(?i)heading([1-9])", value)
    return int(match.group(1)) if match else 0


def _text_of(paragraph: Any) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{W}t"))


def _nearest(named: tuple[Anchor, ...], wanted: str) -> str:
    """What is there, for the refusal to show.

    Not a suggestion to act on - the point of binding by name is that it is not guessed
    at. It is so somebody reading the error can see that the anchor they meant is spelled
    differently, which is what it usually is.
    """
    same_start = [a.name for a in named if normalise(a.name)[:8] == wanted[:8]]
    if same_start:
        return f"nearest: {', '.join(same_start[:3])}"
    return f"{len(named)} named place(s), none with that name"

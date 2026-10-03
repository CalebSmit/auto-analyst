"""The OCR Port: what is on a page nobody can copy from.

Any PDF this firm's clients send is a scan. There is no text layer, nothing can be
selected, and every figure on it is keyed by hand - one to three hours on a repeat
engagement, which is most of what version 1 exists to save.

**Why this is a port and not a call to a model.** The guarantee downstream is that a model
only ever sees masked payloads. Masking needs text; text from a scan needs OCR. An OCR step
that was itself a model call would therefore put the unmasked client document in front of a
model *before* masking could happen - inverting the order the whole guarantee rests on, in a
way no downstream guard could recover. So the adapters here are deterministic local code,
`privacy/` stays deterministic Python throughout, and `tests/p74` walks the imports to prove
nothing on this path can reach `ports.llm`.

**What the port returns, and why that shape.** Per page: the lines, and the same page as
words with their boxes - not tables, not figures. `intake/readers/` turns those into rows and
rows into tables, and every provenance locator in the system (`p14/t2/r7`) is built from
that. So a scanned page and a page with a text layer travel the same road from here on, and
none of the locators, guards or citations need to know which it was.

**Both granularities, because the two consumers want different things.** Prose wants lines:
that is what reads as a document and what a model is sent. A statement wants words with
their edges, because a row is a band of the page and a column is a band too. It is the same
split the text-layer path already makes - `pypdf` for the lines, `pdfplumber`'s
`extract_words` for the geometry.

**The box is not decoration.** The port used to return text alone, and some engines return a
fragment per *cell*: `Total assets`, then `521,728`, then `608,846`, separately. The reader's
line-based row builder expects one line carrying a label and all of its figures, so nothing
reassembled them - with `rapidocr` configured, a scanned balance sheet gave **122 fragments,
0 tables and 0 rows**, with 295 of its 296 figures read correctly and every one discarded.
Since every PDF this firm's clients send is a scan, and `rapidocr` is the adapter a managed
laptop can actually install, that was the main inbound path extracting nothing. Tesseract
happened to escape it by grouping into lines itself - which is the second row-builder this
port's own docstring warned about, and is why the geometry is carried rather than each
engine left to guess at rows.

The adapter takes the document's bytes rather than a page image, so rendering a PDF page is
the adapter's problem. That keeps the reader free of a rendering dependency and keeps the
port honest about what it is for: given this document, what does it say.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "TEXT_HEIGHT",
    "Box",
    "OCRLine",
    "OCRPage",
    "OCRPort",
    "OCRUnavailable",
    "OCRWord",
]

TEXT_HEIGHT = 10.0
"""The height of ordinary body text, in points, used to put an image into page points.

A PDF states its own page size, so an adapter rendering one knows its scale exactly and
divides by it. A screenshot states nothing: the same statement at 96 and at 300 dpi gives
boxes seven times apart, and the layout tolerances are absolute - 3 points of shared height
to be one row, 4 of right-edge spread to be one column, calibrated in P151 on a page set in
10-point type.

So an image is scaled by what its own text measures, which is an estimate and is marked as
one on the page. Measured on the filing's page 56: pdfplumber reports a median word height
of 10.00 points, and the same page rendered at 300 dpi gives a median fragment height of
45.53 pixels - 10.93 points once divided by the render scale, the difference being the
padding an engine's box carries around an ascender. Close enough that the tolerances mean
what their own comments say, which is the only thing this constant is for.
"""


@dataclass(frozen=True)
class Box:
    """Where a fragment sits on the page, in points from the top left.

    The same four names and the same orientation `pdfplumber` uses - `top` grows downward -
    so a box and a word off a text layer can be grouped into rows by one implementation
    rather than two that have to agree.
    """

    x0: float
    top: float
    x1: float
    bottom: float

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def as_word(self, text: str) -> dict[str, Any]:
        """The shape `intake/readers/layout.py` groups: a word and its edges.

        A dict rather than a type of its own because that is what pdfplumber hands back and
        what the band reader was written against. Converting here rather than there keeps
        the reader free of anything to do with this port.
        """
        return {
            "text": text,
            "x0": self.x0,
            "top": self.top,
            "x1": self.x1,
            "bottom": self.bottom,
        }


class OCRUnavailable(Exception):
    """No engine could read this, and nothing has been guessed.

    Raised rather than returning an empty page, because the two are not the same thing and
    the difference is the whole of the reader's existing promise: a page that yields nothing
    is a fact the manifest carries, not a blank the pipeline fills in. An empty result would
    read as "this page is blank" to everything downstream.
    """


@dataclass(frozen=True)
class OCRLine:
    """One line of text an engine read, and how sure it was."""

    text: str
    confidence: float | None = None
    """The engine's own confidence, 0 to 1, or None where it offers none.

    Carried rather than acted on here. It reaches a person through the review surface: a
    figure read off a scan is weaker evidence than one lifted from a text layer, and the
    acceptance rule turns on evidence.
    """


@dataclass(frozen=True)
class OCRWord:
    """One piece of text an engine read, and where on the page it sits.

    Smaller than a line, and the reason the port returns both. A page of prose is wanted as
    lines - that is what reads as a document and what a model is sent. A statement is wanted
    as words with their edges, because a row is a band of the page and a column is a band
    too, and no amount of reading the text recovers either.

    The same split `pdfplumber` makes, and the same split the text-layer path already uses:
    `pypdf` gives the lines and `extract_words` gives the geometry. An adapter that offered
    only lines forced the reader to find columns inside a string, which is the defect P151
    was about; an adapter that offered only words would make a page of prose read as a
    column of single words.
    """

    text: str
    box: Box
    confidence: float | None = None


@dataclass(frozen=True)
class OCRPage:
    number: int
    lines: tuple[OCRLine, ...] = field(default_factory=tuple)

    words: tuple[OCRWord, ...] = field(default_factory=tuple)
    """The same page at word granularity, with every box in page points.

    Empty from an engine that offers no geometry, and a reader that gets nothing here falls
    back to reading the lines - which is the honest order: a layout it was not given is not
    one to guess at.
    """

    geometry: str = "none"
    """Whether the boxes are in real page points: `exact`, `estimated`, or `none`.

    Three states rather than two, because the difference changes what a reader may conclude.
    `exact` is a PDF, whose page size the adapter knows and whose render scale it chose, so
    dividing by that scale is arithmetic. `estimated` is an image, which states no size at
    all - its boxes are scaled by what its own text measures against `TEXT_HEIGHT`, and a
    statement set in 7-point type would come out a little wide. `none` is an engine offering
    no geometry, and the reader falls back to reading the fragments as lines rather than
    pretending to a layout it was not given.

    Said here rather than inferred from `box is None`, because an engine that returned boxes
    for some fragments and not others is a different thing from one that measures in a unit
    nobody can check, and a reader that could not tell them apart would treat an estimate as
    a measurement.
    """

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def confidence(self) -> float | None:
        """The weakest line on the page, which is the one worth knowing about."""
        scored = [line.confidence for line in self.lines if line.confidence is not None]
        return min(scored) if scored else None

    def laid_out(self) -> list[dict[str, Any]]:
        """The words in the shape `intake/readers/layout.py` groups, or empty with no
        geometry.

        Empty rather than partial, and empty rather than a guess: a band reader handed a
        page whose unit nobody can check would group it at the wrong tolerance and report
        tables that are coincidences.
        """
        if self.geometry == "none":
            return []
        return [word.box.as_word(word.text) for word in self.words]


@runtime_checkable
class OCRPort(Protocol):
    name: str

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        """The text on each page. `kind` is the document's own kind, as the reader knows it.

        Raises `OCRUnavailable` when no engine is installed, rather than returning nothing.
        """
        ...

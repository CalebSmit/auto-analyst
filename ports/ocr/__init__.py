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

**What the port returns, and why that shape.** Lines, per page - not tables, not figures.
`intake/readers/documents.py` already turns lines into rows and rows into tables, and every
provenance locator in the system (`p14/t2/r7`) is built from that. Handing back lines means a
scanned page and a page with a text layer travel the same road from here on, and none of the
locators, guards or citations need to know which it was.

The adapter takes the document's bytes rather than a page image, so rendering a PDF page is
the adapter's problem. That keeps the reader free of a rendering dependency and keeps the
port honest about what it is for: given this document, what does it say.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = ["OCRLine", "OCRPage", "OCRPort", "OCRUnavailable"]


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
class OCRPage:
    number: int
    lines: tuple[OCRLine, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def confidence(self) -> float | None:
        """The weakest line on the page, which is the one worth knowing about."""
        scored = [line.confidence for line in self.lines if line.confidence is not None]
        return min(scored) if scored else None


@runtime_checkable
class OCRPort(Protocol):
    name: str

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        """The text on each page. `kind` is the document's own kind, as the reader knows it.

        Raises `OCRUnavailable` when no engine is installed, rather than returning nothing.
        """
        ...

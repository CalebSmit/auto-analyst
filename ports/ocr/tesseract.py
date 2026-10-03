"""OCR adapter: Tesseract, on this machine.

Local and deterministic, which is the requirement rather than a preference: the text has
to exist before masking can happen, so an engine that sent the page anywhere would invert
the order every downstream guarantee rests on.

Two optional dependencies, both imported inside the call so that listing adapters costs
nothing and a machine without them keeps every other port working:

* `pypdfium2` renders a PDF page to an image. A wheel, no system binary.
* `pytesseract` drives the Tesseract executable, which is the part a person installs.

Rendering is the adapter's problem on purpose - the reader hands over the document's bytes
and gets lines back, and stays free of anything to do with images.
"""

from __future__ import annotations

import io
import statistics
from typing import Any

from ports.ocr import TEXT_HEIGHT, Box, OCRLine, OCRPage, OCRUnavailable, OCRWord

# Below this, Tesseract is guessing at noise. Kept as a named floor rather than a literal:
# it is the line between "read faintly" and "invented", and it belongs in one place.
MIN_CONFIDENCE = 0.0

# One word Tesseract read: its text, which line it is on, top, left, bottom, right, and
# how sure it was. A tuple rather than a dataclass because it never leaves this module -
# the lines and the words are both built from it and only those two shapes get out.
Word = tuple[str, tuple[int, int, int], float, float, float, float, float]

RENDER_SCALE = 300 / 72
"""Render at about 300 dpi. Tesseract is trained near it, and a scan of a financial
statement at 72 dpi loses the difference between an 8 and a 3 - which is the error this
whole path exists to avoid making silently."""


class TesseractOCR:
    name = "tesseract"

    def __repr__(self) -> str:
        return "TesseractOCR()"

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        if kind == "image":
            return self._read_image(data)
        if kind != "pdf":
            raise OCRUnavailable(f"this adapter reads pdf and image, not {kind!r}")
        render, tess = self._tools()
        pages: list[OCRPage] = []
        document = render.PdfDocument(data)
        try:
            for number, page in enumerate(document, start=1):
                image = page.render(scale=RENDER_SCALE).to_pil()
                # Divided by the scale this adapter chose, so the boxes come back in the
                # page own points and the layout tolerances downstream mean what they were
                # calibrated to mean. Exact, because both numbers are known here.
                pages.append(self._page(tess, image, number, 1 / RENDER_SCALE, "exact"))
        finally:
            document.close()
        return tuple(pages)

    def _read_image(self, data: bytes) -> tuple[OCRPage, ...]:
        """A screenshot, or a photograph of a page.

        One page, and no rendering - so this path needs `pytesseract` and the Tesseract
        executable, and not `pypdfium2`.

        The scale has to be estimated, because an image states no page size and the row and
        column tolerances are absolute points. The page is scaled by what its own text
        measures - the median word height against `TEXT_HEIGHT` - and marked `estimated`,
        which is what it is.
        """
        tess = self._tesseract_only()
        image = self._open(data)
        read = self._read_words(tess, image)
        if not read:
            return (OCRPage(number=1),)
        middle = statistics.median([word[4] - word[2] for word in read])
        scale = TEXT_HEIGHT / middle if middle > 0 else 1.0
        return (self._page(tess, image, 1, scale, "estimated", read=read),)

    @classmethod
    def _page(
        cls,
        tess: Any,
        image: Any,
        number: int,
        scale: float,
        geometry: str,
        read: list[Word] | None = None,
    ) -> OCRPage:
        """One page, as lines and as words.

        Tesseract reports which line each word belongs to, so the lines here are its own
        grouping rather than this adapter inventing one - which is why this path read a
        scanned statement when the RapidOCR path did not, and also why the geometry is
        carried now. An engine own line grouping is a second row-builder, and the two
        engines disagreeing about what a row is was the whole defect: one produced rows and
        the other produced cells, and the reader could not tell which it had.

        So the words carry their boxes and `intake/readers/layout.py` decides what a row is,
        for both engines. The lines are kept because a page of prose is wanted as lines.
        """
        found = cls._read_words(tess, image) if read is None else read
        return OCRPage(
            number=number,
            lines=cls._lines(found),
            words=cls._words(found, scale),
            geometry=geometry if found else "none",
        )

    @staticmethod
    def _read_words(tess: Any, image: Any) -> list[Word]:
        """Every word Tesseract read: text, which line it is on, its edges, its confidence.

        One call to the engine, because the lines and the words are two views of the same
        reading and calling twice could return two different ones.
        """
        data = tess.image_to_data(image, output_type=tess.Output.DICT)
        out: list[Word] = []
        for index, word in enumerate(data["text"]):
            text = str(word).strip()
            if not text:
                continue
            raw = float(data["conf"][index])
            left = float(data["left"][index])
            top = float(data["top"][index])
            out.append(
                (
                    text,
                    (
                        int(data["block_num"][index]),
                        int(data["par_num"][index]),
                        int(data["line_num"][index]),
                    ),
                    top,
                    left,
                    top + float(data["height"][index]),
                    left + float(data["width"][index]),
                    raw / 100.0 if raw >= 0 else 0.0,
                )
            )
        return out

    @staticmethod
    def _lines(read: list[Word]) -> tuple[OCRLine, ...]:
        """One `OCRLine` per line Tesseract found, with the weakest word's confidence.

        The weakest word rather than the mean: a row whose label read cleanly and whose
        figure did not is exactly the case worth surfacing, and an average hides it.
        """
        grouped: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
        for text, key, _, _, _, _, score in read:
            grouped.setdefault(key, []).append((text, score))
        lines = []
        for key in sorted(grouped):
            words = grouped[key]
            text = " ".join(word for word, _ in words).strip()
            if not text:
                continue
            lines.append(OCRLine(text=text, confidence=min(score for _, score in words)))
        return tuple(lines)

    @staticmethod
    def _words(read: list[Word], scale: float) -> tuple[OCRWord, ...]:
        """Every word with its box in page points, which is what the band reader groups."""
        return tuple(
            OCRWord(
                text=text,
                box=Box(
                    x0=left * scale,
                    top=top * scale,
                    x1=right * scale,
                    bottom=bottom * scale,
                ),
                confidence=score,
            )
            for text, _, top, left, bottom, right, score in read
        )

    @staticmethod
    def _open(data: bytes) -> Any:
        """An image Tesseract can be given, from bytes."""
        try:
            from PIL import Image
        except ImportError as missing:  # pragma: no cover - depends on the machine
            raise OCRUnavailable(
                f"{missing.name} is not installed. Reading an image with this adapter "
                "needs Pillow - `pip install pillow` - which pytesseract depends on "
                "already."
            ) from missing
        return Image.open(io.BytesIO(data))

    def _tesseract_only(self) -> Any:
        """Tesseract without the renderer, for a path that has nothing to render."""
        try:
            import pytesseract
        except ImportError as missing:  # pragma: no cover - depends on the machine
            raise OCRUnavailable(
                f"{missing.name} is not installed. This adapter needs pytesseract, which "
                "needs the Tesseract executable on PATH."
            ) from missing
        return pytesseract

    @staticmethod
    def _tools() -> tuple[Any, Any]:
        try:
            import pypdfium2
            import pytesseract
        except ImportError as missing:  # pragma: no cover - depends on the machine
            raise OCRUnavailable(
                f"{missing.name} is not installed. This adapter needs pypdfium2 to render a "
                "page and pytesseract to read it, and pytesseract needs the Tesseract "
                "executable on PATH."
            ) from missing
        return pypdfium2, pytesseract


def build() -> TesseractOCR:
    return TesseractOCR()

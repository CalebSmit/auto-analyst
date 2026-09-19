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

from typing import Any

from ports.ocr import OCRLine, OCRPage, OCRUnavailable

# Below this, Tesseract is guessing at noise. Kept as a named floor rather than a literal:
# it is the line between "read faintly" and "invented", and it belongs in one place.
MIN_CONFIDENCE = 0.0

RENDER_SCALE = 300 / 72
"""Render at about 300 dpi. Tesseract is trained near it, and a scan of a financial
statement at 72 dpi loses the difference between an 8 and a 3 - which is the error this
whole path exists to avoid making silently."""


class TesseractOCR:
    name = "tesseract"

    def __repr__(self) -> str:
        return "TesseractOCR()"

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        if kind != "pdf":
            raise OCRUnavailable(f"this adapter reads pdf, not {kind!r}")
        render, tess = self._tools()
        pages: list[OCRPage] = []
        document = render.PdfDocument(data)
        try:
            for number, page in enumerate(document, start=1):
                image = page.render(scale=RENDER_SCALE).to_pil()
                pages.append(OCRPage(number=number, lines=self._lines(tess, image)))
        finally:
            document.close()
        return tuple(pages)

    @staticmethod
    def _lines(tess: Any, image: Any) -> tuple[OCRLine, ...]:
        """One `OCRLine` per line Tesseract found, with the weakest word's confidence.

        The weakest word rather than the mean: a row whose label read cleanly and whose
        figure did not is exactly the case worth surfacing, and an average hides it.
        """
        data = tess.image_to_data(image, output_type=tess.Output.DICT)
        grouped: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
        for index, word in enumerate(data["text"]):
            if not str(word).strip():
                continue
            key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
            raw = float(data["conf"][index])
            grouped.setdefault(key, []).append((str(word), raw / 100.0 if raw >= 0 else 0.0))

        lines = []
        for key in sorted(grouped):
            words = grouped[key]
            text = " ".join(word for word, _ in words).strip()
            if not text:
                continue
            lines.append(OCRLine(text=text, confidence=min(score for _, score in words)))
        return tuple(lines)

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

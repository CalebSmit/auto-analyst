"""OCR adapter: RapidOCR, on this machine, with no administrator.

Local and deterministic like the Tesseract adapter, and installed differently - which is
the whole reason it exists. Tesseract is an executable that has to be on PATH, and putting
it there on a managed laptop is a request to somebody. RapidOCR is a wheel with its ONNX
models bundled: `pip install rapidocr-onnxruntime` and it is there, no admin rights, no
system binary, nothing for IT to approve.

On the three financial statement pages of a real annual report - a public SEC filing,
rendered to images at 300 dpi and scored against the document's own text layer - it read
every figure in every column correctly, at about 0.99 mean confidence. That is an upper
bound rather than a forecast: those pages were born digital, so they have no skew, no
scanner noise and no photocopy generation loss. What it establishes is that the engine is
not the weak part.

Two optional dependencies, imported inside the call so that listing adapters costs nothing
and a machine without them keeps every other port working:

* `pypdfium2` renders a PDF page to an image. A wheel, no system binary.
* `rapidocr-onnxruntime` reads it. A wheel, models included.

Neither is in `pyproject.toml`. They are the cost of one adapter on machines that select
it, and adding them to the project would put an ONNX runtime into every clone and every
container that never reads a scan.
"""

from __future__ import annotations

import io
from typing import Any

from ports.ocr import OCRLine, OCRPage, OCRUnavailable

RENDER_SCALE = 300 / 72
"""Render at about 300 dpi, as the Tesseract adapter does. A statement at 72 dpi loses the
difference between an 8 and a 3, which is the error this whole path exists not to make
silently."""


class RapidOCREngine:
    name = "rapidocr"

    def __init__(self) -> None:
        self._engine: Any = None

    def __repr__(self) -> str:
        return f"RapidOCREngine(loaded={self._engine is not None})"

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        if kind != "pdf":
            raise OCRUnavailable(f"this adapter reads pdf, not {kind!r}")
        render, engine = self._tools()
        pages: list[OCRPage] = []
        document = render.PdfDocument(data)
        try:
            for number, page in enumerate(document, start=1):
                image = page.render(scale=RENDER_SCALE).to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                pages.append(OCRPage(number=number, lines=self._lines(engine, buffer.getvalue())))
        finally:
            document.close()
        return tuple(pages)

    @staticmethod
    def _lines(engine: Any, png: bytes) -> tuple[OCRLine, ...]:
        """One `OCRLine` per fragment the engine found, in reading order.

        RapidOCR returns a box, the text and a score per fragment, and a fragment is
        roughly a cell rather than a row - a statement line comes back as the label, then
        each figure, separately. They are kept separate rather than stitched into rows
        here: `intake/readers/documents.py` is what turns lines into rows, it does that for
        a text layer too, and a second row-builder in an adapter would be a second place
        for the two to disagree about what a row is.
        """
        found, _ = engine(png)
        if not found:
            return ()
        lines = []
        for item in found:
            text = str(item[1]).strip()
            if not text:
                continue
            try:
                score = float(item[2])
            except (TypeError, ValueError, IndexError):  # pragma: no cover - engine's shape
                score = None
            lines.append(OCRLine(text=text, confidence=score))
        return tuple(lines)

    def _tools(self) -> tuple[Any, Any]:
        try:
            import pypdfium2
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as missing:  # pragma: no cover - depends on the machine
            raise OCRUnavailable(
                f"{missing.name} is not installed. This adapter needs pypdfium2 to render a "
                "page and rapidocr-onnxruntime to read it. Both are wheels - "
                "`pip install pypdfium2 rapidocr-onnxruntime` - and neither needs an "
                "administrator or a system binary."
            ) from missing
        if self._engine is None:
            self._engine = RapidOCR()
        return pypdfium2, self._engine


def build() -> RapidOCREngine:
    return RapidOCREngine()

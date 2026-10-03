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

* `rapidocr-onnxruntime` reads an image. A wheel, models included.
* `pypdfium2` renders a PDF page to one. A wheel, no system binary - and needed only for a
  PDF, so a screenshot is read on a machine that has the engine and nothing else.

Neither is in `pyproject.toml`. They are the cost of one adapter on machines that select
it, and adding them to the project would put an ONNX runtime into every clone and every
container that never reads a scan.

**Every fragment comes back with its box, in the page's own points.** The engine measures in
pixels of whatever it was handed, and the row and column tolerances downstream are absolute
points calibrated on a real page - so the conversion belongs here, where the render scale is
known, rather than in a reader that would have to be told. For a PDF that is exact. For an
image, which states no size at all, the page is scaled by what its own text measures and
marked `estimated`.
"""

from __future__ import annotations

import io
import statistics
from typing import Any

from ports.ocr import TEXT_HEIGHT, Box, OCRLine, OCRPage, OCRUnavailable, OCRWord

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
        if kind == "image":
            return self._read_image(data)
        if kind != "pdf":
            raise OCRUnavailable(f"this adapter reads pdf and image, not {kind!r}")
        render, engine = self._tools()
        pages: list[OCRPage] = []
        document = render.PdfDocument(data)
        try:
            for number, page in enumerate(document, start=1):
                image = page.render(scale=RENDER_SCALE).to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                # Divided by the scale this adapter chose, so the boxes come back in the
                # page's own points and the layout tolerances downstream mean what they
                # were calibrated to mean. Exact, because both numbers are known here.
                pages.append(
                    self._page(
                        number,
                        self._fragments(engine, buffer.getvalue()),
                        1 / RENDER_SCALE,
                        "exact",
                    )
                )
        finally:
            document.close()
        return tuple(pages)

    def _read_image(self, data: bytes) -> tuple[OCRPage, ...]:
        """A screenshot, a photograph of a page, an image pasted into an email.

        One page, and the bytes go straight to the engine - no rendering, so this path needs
        only the engine wheel and works on a machine without `pypdfium2`.

        The scale has to be guessed, because an image states no page size: the same statement
        at 96 and at 300 dpi gives boxes seven times apart, and the row and column tolerances
        are absolute points. So the page is scaled by what its own text measures - the median
        fragment height against `TEXT_HEIGHT` - and marked `estimated`, because that is what
        it is. An image whose text is all headline would come out small; nothing here can
        know better from the pixels alone.
        """
        found = self._fragments(self._engine_only(), data)
        if not found:
            return (OCRPage(number=1),)
        heights = [max(p[1] for p in box) - min(p[1] for p in box) for _, box, _ in found]
        middle = statistics.median(heights)
        scale = TEXT_HEIGHT / middle if middle > 0 else 1.0
        return (self._page(1, found, scale, "estimated"),)

    @classmethod
    def _page(
        cls,
        number: int,
        found: list[tuple[str, Any, float | None]],
        scale: float,
        geometry: str,
    ) -> OCRPage:
        """One page, as lines and as words.

        RapidOCR returns a box, the text and a score per fragment, and a fragment is roughly
        a **cell** rather than a row - a statement line comes back as the label, then each
        figure, separately. They are not stitched into rows here:
        `intake/readers/layout.py` is what groups a page into rows and columns, it does that
        for a text layer too, and a second row-builder in an adapter would be a second place
        for the two to disagree about what a row is.

        So the same fragments are reported twice, which is not duplication: as `lines` they
        are the page's text in reading order, which is what prose and a model want, and as
        `words` they carry the geometry, which is what a statement needs. The one thing the
        adapter must do is put the box in the page's own unit, because only the adapter knows
        what it rendered at.
        """
        words = cls._words(found, scale)
        return OCRPage(
            number=number,
            lines=tuple(
                OCRLine(text=text, confidence=score) for text, _, score in found
            ),
            words=words,
            geometry=geometry if words else "none",
        )

    @staticmethod
    def _fragments(engine: Any, png: bytes) -> list[tuple[str, Any, float | None]]:
        """The engine's own output, tidied: text, box, score, with the empties dropped.

        Separate from `_from` so the image path can measure the boxes before deciding what
        to scale them by, without running the engine twice.
        """
        found, _ = engine(png)
        out: list[tuple[str, Any, float | None]] = []
        for item in found or []:
            text = str(item[1]).strip()
            if not text:
                continue
            try:
                score: float | None = float(item[2])
            except (TypeError, ValueError, IndexError):  # pragma: no cover - engine's shape
                score = None
            out.append((text, item[0], score))
        return out

    @staticmethod
    def _words(
        found: list[tuple[str, Any, float | None]], scale: float
    ) -> tuple[OCRWord, ...]:
        """The fragments as words, with every box multiplied into page points.

        RapidOCR gives four corners rather than two edges, because it detects rotated text.
        The extremes are taken: a box's edges are what the band reader groups on, and a
        statement photographed at a slight angle should still land in the right row.

        A fragment whose box cannot be read contributes no word, and the page then reports
        `geometry="none"` rather than a layout with holes in it - a band reader given most
        of a page would group what it can see and drop the rest, which is a worse answer
        than reading the lines.
        """
        words = []
        for text, box, score in found:
            try:
                xs = [float(point[0]) * scale for point in box]
                ys = [float(point[1]) * scale for point in box]
            except (TypeError, ValueError, IndexError):  # pragma: no cover - engine's shape
                return ()
            words.append(
                OCRWord(
                    text=text,
                    box=Box(x0=min(xs), top=min(ys), x1=max(xs), bottom=max(ys)),
                    confidence=score,
                )
            )
        return tuple(words)

    def _engine_only(self) -> Any:
        """The engine without the renderer, for a path that has nothing to render.

        An image needs no `pypdfium2`, and asking for it would refuse a screenshot on a
        machine that can read one perfectly well.
        """
        self._insist("rapidocr_onnxruntime")
        from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415

        if self._engine is None:
            self._engine = RapidOCR()
        return self._engine

    def _tools(self) -> tuple[Any, Any]:
        """The renderer and the engine, for the path that has a PDF to render."""
        self._insist("pypdfium2", "rapidocr_onnxruntime")
        import pypdfium2  # noqa: PLC0415

        return pypdfium2, self._engine_only()

    @staticmethod
    def _insist(*modules: str) -> None:
        """Refuse once, naming everything this path needs and does not have.

        Every one of them, not the first - a message that names one wheel sends a person to
        install it and come back for the next, and on a managed laptop that is two trips to
        somebody else. The refusal is this port's own so it reads as an unconfigured machine
        rather than as an ImportError from the middle of a run, which reads as a broken build.
        """
        import importlib.util  # noqa: PLC0415

        def absent(name: str) -> bool:
            # `find_spec` answers without importing, which matters because importing an ONNX
            # runtime to find out whether it is there is not free. It can also *raise* rather
            # than return None - a finder may say so, and a submodule of a missing package
            # does - and either way the module is not available.
            try:
                return importlib.util.find_spec(name) is None
            except (ImportError, ValueError):
                return True

        missing = [name for name in modules if absent(name)]
        if not missing:
            return
        wheels = [name.replace("_", "-") for name in missing]
        raise OCRUnavailable(
            f"{', '.join(wheels)} is not installed. This adapter needs "
            "rapidocr-onnxruntime to read a page - a wheel, models included - and "
            "pypdfium2 to render one out of a PDF first; an image needs only the engine. "
            f"`pip install {' '.join(wheels)}` - no administrator and no system binary."
        )


def build() -> RapidOCREngine:
    return RapidOCREngine()

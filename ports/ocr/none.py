"""OCR adapter: there is no engine here, and it says so.

The default, and not a degraded mode. A clean clone, a container and a machine where
nobody has installed anything are the same case, and on all three the honest answer to
"what does this scan say" is that nothing read it.

`OCRUnavailable` rather than an empty page, because an empty page is a claim - it says
this sheet is blank - and the reader's existing behaviour is exactly right: a page that
yields nothing is a fact the manifest carries rather than a blank the pipeline fills in.
"""

from __future__ import annotations

from ports.ocr import OCRPage, OCRUnavailable


class NoOCR:
    name = "none"

    def __repr__(self) -> str:
        return "NoOCR()"

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        # An image and a scanned PDF page are not the same loss, and a person reading this
        # should not have to work out which they have: a scan of a report still has its
        # other pages, and an image has nothing else in it at all.
        lost = "an image has no text layer to fall back on" if kind == "image" else (
            "the page stays reported as scanned rather than read as empty"
        )
        raise OCRUnavailable(
            f"no OCR engine is configured, so a scanned {kind} cannot be read here. "
            f"Install one and set AA_OCR_ADAPTER - {lost}."
        )


def build() -> NoOCR:
    return NoOCR()

"""P155: a scanned statement read as nothing, and every figure on it was read correctly.

Measured, with an engine configured and a real scanned page - page 56 of the filing in
`fixtures/public`, the consolidated balance sheet, rendered to an image and wrapped in a PDF
with no text layer:

| | text layer | the same page scanned |
|---|---|---|
| lines | 61 rows | 122 fragments |
| tables | 3 | **0** |
| figures with a locator | 61 | **0** |
| footings that re-add | 10 | **0** |
| states both sides | yes | no |

**The engine was not the weak part.** Over pages 55 to 63 it read 295 of 296 printed figures
and invented none. All of it was discarded, because the OCR port returned text and nothing
else, and an engine returns a *cell* at a time - `Total assets`, then `521,728`, then
`608,846`, as three fragments. The reader's line-based row builder wants one line carrying a
label and all of its figures, and nothing between the two reassembled them. CLAUDE.md records
that every PDF this firm's clients send is a scan, so this was the main inbound path
extracting nothing - and `rapidocr` is the adapter a managed laptop can install without
asking anybody, so it is the one that matters.

**A row is a band of the page and a column is a band too**, which is what P151 built for a
text layer. Everything in `intake/readers/layout.py` below `lay_out` is geometry and knows
nothing about PDFs, so the fix is to carry the engine's boxes through the port and send both
paths through one reader. A scan and a text layer go on agreeing about what a row is for the
reason they agree about anything: there is one implementation of it.

Three defects had to go, and only the first was the one planned for:

* the port carried no geometry at all;
* the engine returns `$` as its own fragment, and in its own detection order it came
  **first** - so the label was `$ Total assets`, the exact match in `two_sides` failed, and
  the balance sheet stopped stating its two sides. That rule is positional now, and it
  turned out to be hiding four real totals on the *text layer* too (`tests/p154`);
* `_is_figure` was asked of a whole word to decide whether a band is part of a table, and an
  OCR fragment is a phrase. `Common stock, $0.001 par value, authorized 220,000 shares;
  shares issued 145,581 and` is not money-shaped, so that band read as prose, the table never
  started over it, and the two figures on the row - 146 and 136 - were taken for the names of
  the next table's columns. That is the row this reader is most careful about: before P151 it
  stored **220,000**, the authorized share count, as the common stock balance.

**The engine is replayed, not run.** `rapidocr-onnxruntime` is deliberately not in
`pyproject.toml` - it would put an ONNX runtime into every clone and every container that
never reads a scan - so a test needing it would fail on a clean one. What it read off page 56,
boxes and all, is captured in `fixtures/public/ocr-sec-ars-3d-systems-p56.json` in the
engine's own unit, which is the same answer this repo already gives for the model adapter.
The conversion is therefore proved rather than assumed.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from intake.fingerprint import IMAGE, READ, kind_of, mime_of
from intake.readers.documents import IMAGES, Page, ParsedDocument, read_document
from intake.readers.footing import footings_in, two_sides
from intake.readers.layout import lay_out_words
from ports.ocr import TEXT_HEIGHT, Box, OCRLine, OCRPage, OCRUnavailable, OCRWord

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"
CAPTURE = ROOT / "fixtures" / "public" / "ocr-sec-ars-3d-systems-p56.json"
PAGE = 56

PNG = bytes.fromhex("89504e470d0a1a0a")
"""A PNG signature, built from its bytes.

Written as an escape it is at the mercy of every layer between an editor and the file,
and one of them resolved it: the fixture became the character it stood for and the
test stopped being about a PNG at all.
"""


@pytest.fixture(scope="module")
def captured() -> dict:
    return json.loads(CAPTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def blank_pdf() -> bytes:
    """A real one-page PDF carrying no text at all - a photocopy, as far as the reader is
    concerned. Built rather than faked, because the reader opens it with pypdf before it
    ever decides the page is scanned, and a handful of plausible bytes is not a PDF."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=594, height=774)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def one_page() -> bytes:
    """Page 56 on its own. The whole filing is a hundred and eight pages and this asks
    about one of them."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(FILING.read_bytes())).pages[PAGE - 1])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class Replay:
    """The OCR port, answering with what a real engine really read.

    Converts the capture the way an adapter does - divide by the render scale it recorded -
    so what is being tested is the reader, with the adapter's arithmetic done honestly
    rather than assumed.
    """

    name = "replay"

    def __init__(self, captured: dict, *, geometry: str = "exact") -> None:
        self._captured = captured
        self._geometry = geometry

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        scale = 1 / self._captured["render_scale"]
        lines = tuple(
            OCRLine(text=f["text"], confidence=f["confidence"])
            for f in self._captured["fragments"]
        )
        words = (
            ()
            if self._geometry == "none"
            else tuple(
                OCRWord(
                    text=f["text"],
                    box=Box(
                        x0=f["box"][0] * scale,
                        top=f["box"][1] * scale,
                        x1=f["box"][2] * scale,
                        bottom=f["box"][3] * scale,
                    ),
                    confidence=f["confidence"],
                )
                for f in self._captured["fragments"]
            )
        )
        return (OCRPage(number=1, lines=lines, words=words, geometry=self._geometry),)


def figures(built) -> list[tuple[str, float]]:
    return [
        (row.label, row.value)
        for table in built
        for column in table.columns
        for row in column.rows
        if row.value is not None
    ]


# ------------------------------------------------------- the scan reads what the page prints


def test_a_scanned_balance_sheet_reads_the_same_as_its_text_layer(
    captured, one_page, monkeypatch
) -> None:
    """The exit criterion, and the whole point of the phase.

    Not "the scan finds some rows" - the same rows. A reader that found most of a statement
    would be the worst of the three outcomes, because the figures it found would carry
    locators and arithmetic cover and nothing would say which ones were missing.
    """
    import ports

    monkeypatch.setattr(ports, "get_ocr", lambda: Replay(captured))

    from_text = read_document(one_page, "p56.pdf")
    printed = figures(from_text.pages[0].tables)
    assert len(printed) == 61, f"the text layer moved: {len(printed)}"

    words = [w.box.as_word(w.text) for w in Replay(captured).read(b"")[0].words]
    from intake.readers.documents import _tables_from_layout

    read = figures(_tables_from_layout(1, lay_out_words(1, words)))

    assert len(read) == 61, f"the scan gives {len(read)} rows"
    assert sorted(v for _, v in read) == sorted(v for _, v in printed), (
        "the scan and the text layer disagree about the figures on the page"
    )
    # Labels compared with their whitespace removed, because an engine drops the occasional
    # space inside a fragment - `Accumulatedother comprehensiveloss` - and that is a
    # difference in the spacing rather than in the statement. Said as a separate claim
    # below, counted rather than waved at, because losing spaces is the one way these
    # labels do differ and a reader should know its size.
    def letters(label: str) -> str:
        return "".join(label.split())

    assert [letters(label) for label, _ in read] == [
        letters(label) for label, _ in printed
    ], "the scan and the text layer disagree about more than spacing"

    spaced = sum(
        1 for (a, _), (b, _) in zip(read, printed, strict=True) if a != b
    )
    assert spaced == 4, f"{spaced} of 61 labels lost a space, not 4"


def test_the_scanned_balance_sheet_still_balances(captured) -> None:
    """The check an analyst makes first, off a photocopy. It failed on a stray `$`."""
    words = [w.box.as_word(w.text) for w in Replay(captured).read(b"")[0].words]
    from intake.readers.documents import _tables_from_layout

    tables = _tables_from_layout(1, lay_out_words(1, words))
    rows = [r for t in tables for c in t.columns for r in c.rows]

    sides = two_sides(rows)
    assert sides.stated, "the scan does not state both sides"
    assert sides.assets == 521_728.0
    assert sides.liabilities_and_equity == 521_728.0
    assert sides.balances is True

    covered = [f for f in footings_in(rows).footings if f.covered]
    assert len(covered) == 10, f"{len(covered)} footings re-add, not 10"


def test_the_common_stock_row_survives_being_one_fragment(captured) -> None:
    """The row this reader is most careful about.

    Its label carries an authorized share count of 220,000 and an issued count of 145,581,
    and its value is a balance of 146 printed in the column. The engine returns the whole
    label as one fragment, which is not money-shaped - so the band read as prose and the
    two balances became the names of the next table's columns instead.
    """
    words = [w.box.as_word(w.text) for w in Replay(captured).read(b"")[0].words]
    from intake.readers.documents import _tables_from_layout

    tables = _tables_from_layout(1, lay_out_words(1, words))
    rows = figures(tables)
    common = [(label, value) for label, value in rows if label.startswith("Common stock")]
    assert [v for _, v in common] == [146.0, 136.0], common
    assert "220,000" in common[0][0], "the share count belongs in the label"
    assert all(t.headings != ("146", "136") for t in tables), (
        "the balances were taken for column names"
    )


# -------------------------------------------------------------- what the adapter must convert


def test_the_boxes_arrive_in_page_points(captured) -> None:
    """The adapter's one job, and the reason the capture is stored in pixels.

    The layout tolerances are absolute points, calibrated on a real page. An engine measures
    in pixels of whatever it was handed: page 56 is 594 by 774 points and was rendered to
    2475 by 3226 pixels, so a box handed over unconverted would be grouped at a seventh of
    the intended tolerance and find nothing.
    """
    assert captured["page_size_points"] == [594.0, 774.0]
    assert captured["image_size"] == [2475, 3226]
    page = Replay(captured).read(b"")[0]

    widest = max(word.box.x1 for word in page.words)
    assert 540 < widest < 560, f"the right edge is at {widest:.1f}, not on a 594pt page"
    tallest = max(word.box.bottom for word in page.words)
    assert tallest < 774, f"a word sits at {tallest:.1f} on a 774pt page"

    # The figure columns P151 measured on this page: right edges near 482 and 549.
    from intake.readers.layout import _is_figure

    edges = sorted({round(w.box.x1) for w in page.words if _is_figure(w.text)})
    assert any(480 <= e <= 488 for e in edges), edges
    assert any(547 <= e <= 555 for e in edges), edges


def test_a_column_is_only_ever_placed_by_a_word_that_is_entirely_a_figure() -> None:
    """Where a table *is* and where its columns *are* are two questions with two answers.

    Reaching inside a word is what lets a scanned row exist at all, because an engine hands
    over a phrase. It must not also decide where a column sits: a phrase's right edge is its
    last word's, and three phrases that happen to end level would put a column wherever
    sentences happen to stop.

    The filing cannot show this. `COLUMN_NEEDS` wants three figures sharing an edge, and one
    phrase cannot make a column on its own - loosening the rule changed nothing on page 56,
    which is a reason to write the case rather than to assume the rule is idle. Here three
    prose lines end level at x=300, where a phrase ending in a figure would plant a third
    column and take the last word of each sentence for a cell. The statement's own two
    columns are at 500 and 570.
    """
    from intake.readers.layout import lay_out_words

    def word(text: str, x1: float, top: float) -> dict:
        return {"text": text, "x0": x1 - 60, "x1": x1, "top": top, "bottom": top + 10}

    page = []
    for n, phrase in enumerate(
        ("note 1,250 applies", "under 2,500 of it", "about 3,750 remains")
    ):
        top = 100.0 + n * 20
        page.append(word(phrase, 300.0, top))
        page.append(word(f"{(n + 1) * 1000:,}", 500.0, top))
        page.append(word(f"{(n + 1) * 1100:,}", 570.0, top))

    tables = lay_out_words(1, page)
    assert tables, "the three rows are a table - that is what reaching inside a word buys"
    columns = [round(c) for table in tables for c in table.columns]
    assert columns == [500, 570], f"a column was placed at {columns}"
    cells = [row.cells for table in tables for row in table.rows]
    assert cells == [
        ("1,000", "1,100"),
        ("2,000", "2,200"),
        ("3,000", "3,300"),
    ], cells
    labels = [row.label for table in tables for row in table.rows]
    assert labels == [
        "note 1,250 applies",
        "under 2,500 of it",
        "about 3,750 remains",
    ], "the prose is the label, figure inside it and all"


def test_an_engine_with_no_geometry_still_reads_through_the_lines(
    captured, blank_pdf, monkeypatch
) -> None:
    """A real case, not a formality. The port's own contract allows an engine that offers no
    boxes, and the honest answer there is the path that existed - reading the fragments as
    lines - rather than a layout nobody was given."""
    page = Replay(captured, geometry="none").read(b"")[0]
    assert page.lines, "the text still arrives"
    assert page.words == ()
    assert page.laid_out() == [], "no geometry means no layout, not a guess at one"

    import ports

    monkeypatch.setattr(ports, "get_ocr", lambda: Replay(captured, geometry="none"))
    doc = read_document(blank_pdf, "scan.pdf")
    assert [line.text for line in doc.pages[0].lines][:1] == ["3DSYSTEMSCORPORATION"]
    assert all(line.ocr for line in doc.pages[0].lines)


def test_a_page_whose_geometry_is_estimated_says_so() -> None:
    """An image states no page size, so its scale is a guess and must read as one.

    `exact` is arithmetic - a PDF whose page size is known, divided by a render scale the
    adapter chose. `estimated` is an image scaled by what its own text measures. A reader
    that could not tell them apart would treat an estimate as a measurement.
    """
    one = OCRWord(text="1,000", box=Box(x0=0, top=0, x1=10, bottom=TEXT_HEIGHT))
    assert OCRPage(number=1, words=(one,), geometry="exact").laid_out()
    assert OCRPage(number=1, words=(one,), geometry="estimated").laid_out()
    assert OCRPage(number=1, words=(one,), geometry="none").laid_out() == []
    assert OCRPage(number=1).geometry == "none", "nothing is the default"


# -------------------------------------------------------------- and an image is a document


def test_an_image_is_routed_to_a_reader_rather_than_nowhere() -> None:
    """A screenshot of a trial balance was `kind="other"` and reached no reader at all.

    The types are asserted to be **declared** rather than only to come out right, which is
    the whole point of `BY_EXTENSION`: the same bytes must get the same type on every host,
    and `mimetypes` reads a registry that differs between machines. Removing `.png` from the
    table left this test green when it only checked the answer, because this host's
    `mimetypes` happens to know PNG.

    **Showing the table is load-bearing used to be a claim about this host.** The line was
    `mimetypes.guess_type("page.webp")[0] is None` - true on Windows and in a slim image,
    false on an Ubuntu runner with `/etc/mime.types` installed, so it failed on the first
    remote job that ever ran the suite to completion and passed everywhere it had been run
    before. Its own message admitted the problem: *if the platform learns webp, this line is
    stale rather than wrong*. A test that is one host away from stale is a test asserting
    something this build did not decide, which is the opposite of the point being made.

    So the claim is made directly instead, and it is a stronger one: the platform is made to
    lie about every declared extension, and the table is unmoved. That holds on a host that
    knows webp, a host that does not, and a host that is wrong about it.
    """
    import mimetypes

    from intake.fingerprint import BY_EXTENSION

    for extension in IMAGES:
        assert extension in BY_EXTENSION, f"{extension} is left to the platform"
    for name in ("Trial balance.png", "statement.JPG", "scan.tiff", "page.webp"):
        assert kind_of(mime_of(name)) == "document", name
        assert mime_of(name) in READ, name
    assert mime_of("Trial balance.png") == "image/png"
    assert mime_of("statement.jpeg") == mime_of("statement.jpg") == "image/jpeg"

    # The table decides, whatever the host says. Patched to a wrong answer rather than to
    # None, because falling through to the platform would then be invisible: a declared
    # extension that consulted `mimetypes` would come back with this and not with its own
    # type, and every extension in the table is checked rather than one of them.
    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(mimetypes, "guess_type", lambda *a, **kw: ("application/x-wrong", None))
        for extension, declared in BY_EXTENSION.items():
            assert mime_of(f"anything{extension}") == declared, (
                f"{extension} came back as something other than the type this build "
                f"declares, so the host's table is deciding and not ours"
            )
        assert mime_of("mystery.zzz") == "application/x-wrong", (
            "an extension outside the table should still get whatever the host knows; "
            "this fall-through is what the declared table exists to sit in front of"
        )


def test_the_two_lists_of_image_formats_name_the_same_thing() -> None:
    """`intake/fingerprint.py` says what a file is and `documents.py` says which reader
    takes it. They are spelled separately on purpose - importing one into the other would
    drag a database session into a module that reads bytes - so a test holds them level,
    which is what catches a format added to one and forgotten in the other."""
    from intake.fingerprint import BY_EXTENSION

    by_extension = {ext for ext, mime in BY_EXTENSION.items() if mime in IMAGE}
    assert by_extension == set(IMAGES), by_extension ^ set(IMAGES)


def test_an_image_reaches_the_port_as_an_image(captured, monkeypatch) -> None:
    """Not as a PDF. An adapter asked to render a PNG with a PDF renderer would raise, and
    the whole file would be lost rather than one page of it."""
    asked: list[str] = []

    class Watching(Replay):
        def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
            asked.append(kind)
            return super().read(data, kind=kind)

    import ports

    monkeypatch.setattr(ports, "get_ocr", lambda: Watching(captured))
    doc = read_document(PNG + bytes(64), "Balance sheet.png")

    assert asked == ["image"], asked
    assert doc.kind == "image"
    assert len(doc.pages) == 1
    rows = figures(doc.pages[0].tables)
    assert len(rows) == 61, f"a screenshot of this page gives {len(rows)} rows"
    assert two_sides(
        [r for t in doc.pages[0].tables for c in t.columns for r in c.rows]
    ).assets == 521_728.0


def test_an_image_with_no_engine_is_an_empty_page_rather_than_a_refusal() -> None:
    """The reader's standing promise, applied to a format that had never reached it: a page
    that yields nothing is a fact the manifest carries, not a blank the pipeline fills in -
    and not an exception either, because the file was read and is simply unreadable without
    an engine."""
    import ports

    doc = read_document(PNG + bytes(64), "Screenshot.png")
    assert isinstance(doc, ParsedDocument)
    assert doc.kind == "image"
    assert [p.scanned for p in doc.pages] == [True]
    assert doc.pages[0].tables == []
    assert doc.blocks() == {}, "nothing is written to the parse store"
    assert ports.get_ocr().name == "none", "this is the default, and the test assumes it"

    # And the refusal really is caught rather than merely absent from this path: the port
    # raises, and what the reader does with that is return an empty page. An engine that
    # raised for any other reason - installed but broken - has to land in the same place,
    # because a file that was read and yielded nothing is a fact, and an exception here
    # would lose the whole document instead of recording that one page is a scan.
    class Broken:
        name = "broken"

        def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
            raise OCRUnavailable("the engine is installed and will not start")

    import intake.readers.documents as documents

    original = ports.get_ocr
    ports.get_ocr = lambda: Broken()  # type: ignore[assignment]
    try:
        still = documents.read_document(PNG + bytes(64), "shot.png")
    finally:
        ports.get_ocr = original  # type: ignore[assignment]
    assert [p.scanned for p in still.pages] == [True]
    assert still.blocks() == {}


def test_the_default_adapter_says_what_an_image_loses() -> None:
    """A scan of a report still has its other pages; an image has nothing else in it. A
    person reading the diagnostic should not have to work out which they have."""
    from ports.ocr.none import NoOCR

    with pytest.raises(OCRUnavailable) as refused:
        NoOCR().read(b"", kind="image")
    assert "image has no text layer to fall back on" in str(refused.value)

    with pytest.raises(OCRUnavailable) as scan:
        NoOCR().read(b"", kind="pdf")
    assert "reported as scanned" in str(scan.value)


def test_an_image_is_not_refused_as_a_binary_file() -> None:
    """`looks_like` catches a PNG signature on purpose - it is how a `.doc` renamed `.txt`
    is found - so the image branch has to come first, or every screenshot is refused as the
    very thing it is."""
    from intake.readers.documents import NotText, looks_like

    png = PNG + bytes(64)
    assert looks_like(png) == "a PNG image", "the signature is still recognised"
    assert read_document(png, "shot.png").kind == "image"
    with pytest.raises(NotText):
        read_document(png, "notes.txt")


def test_the_page_an_image_builds_is_the_shape_the_rest_of_the_build_reads() -> None:
    """One page, numbered 1. Every locator in this system is built from a page number and a
    table index, and an image that numbered its page anything else would cite a page the
    document does not have."""
    doc = read_document(PNG + bytes(64), "shot.png")
    assert [p.number for p in doc.pages] == [1]
    assert isinstance(doc.pages[0], Page)

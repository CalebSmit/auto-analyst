"""P75: an OCR engine that installs without an administrator.

P74 built the port and reached for Tesseract, which needs an executable on PATH. Testing it
against a real SEC filing turned up a better answer to the same question:
`rapidocr-onnxruntime` is a wheel with its ONNX models bundled - no admin rights, no system
binary, nothing for IT to approve - and on the three financial statement pages of a real
annual report it read every figure in every column correctly at about 0.99 confidence.

Both engines stay registered. Which reads this firm's scans better is a question a
benchmark answers, and a benchmark needs two engines to be a comparison.

The test that matters is `test_it_refuses_by_name_rather_than_failing_to_import`: an
adapter whose optional dependency is missing must say what to install, not raise an
ImportError from somewhere in the middle of a run.
"""

from __future__ import annotations

import ast
import importlib.abc
import io
import sys
from pathlib import Path

import pytest

import ports
from ports.ocr import OCRPort, OCRUnavailable
from tests.importing import reaches_any

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ports" / "ocr" / "rapidocr.py"


def test_it_is_registered_beside_the_other_engines() -> None:
    assert set(ports.adapters("ocr")) == {"none", "rapidocr", "tesseract"}
    assert "rapidocr" in ports.ready("ocr"), "it has an implementation, not just a contract"


def test_it_satisfies_the_port_without_its_dependencies_installed() -> None:
    """Built and checked like every other adapter, on a machine that cannot run it. That is
    what the deferred import buys: listing what exists costs nothing."""
    engine = ports.get_ocr("rapidocr")
    assert isinstance(engine, OCRPort)
    assert engine.name == "rapidocr"


class _NotInstalled(importlib.abc.MetaPathFinder):
    """Makes named modules unimportable for the length of a `with` block.

    Needed because the machine decides the answer otherwise. Until 2026-09-21 no machine in
    this build had the wheels, so `import pypdfium2` raised on its own and the refusal test
    below passed without ever forcing the condition it names. The first machine to install
    an engine - which is any machine doing real work - turned it red, and the failure was
    the test's premise rather than the adapter.
    """

    def __init__(self, *names: str) -> None:
        self.names = set(names)
        self.hidden: dict[str, object] = {}

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> None:
        if fullname.split(".")[0] in self.names:
            raise ModuleNotFoundError(f"hidden for this test: {fullname}", name=fullname)
        return None

    def __enter__(self) -> _NotInstalled:
        for name in list(sys.modules):
            if name.split(".")[0] in self.names:
                self.hidden[name] = sys.modules.pop(name)
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, *_: object) -> None:
        sys.meta_path.remove(self)
        sys.modules.update(self.hidden)


def test_it_refuses_by_name_rather_than_failing_to_import() -> None:
    """The one that matters. A missing wheel must arrive as this port's own refusal, naming
    what to install - not as an ImportError from the middle of a run, which reads as a
    broken build rather than an unconfigured machine.

    The absence is forced rather than borrowed from the machine, so this says the same thing
    on a laptop with the wheels and on a container without them."""
    engine = ports.get_ocr("rapidocr")
    hidden = _NotInstalled("pypdfium2", "rapidocr_onnxruntime")
    with hidden, pytest.raises(OCRUnavailable) as refused:
        engine.read(b"%PDF-1.4", kind="pdf")
    said = str(refused.value)
    assert "pip install" in said
    assert "rapidocr-onnxruntime" in said
    assert "administrator" in said, "the reason to prefer it should be in the refusal"


def test_the_refusal_names_whichever_wheel_is_the_missing_one() -> None:
    """Half-installed is the state a person actually lands in, because the two wheels are
    installed by one command that can partly fail. A refusal that named the other one would
    send them to reinstall what they already have."""
    engine = ports.get_ocr("rapidocr")
    with _NotInstalled("rapidocr_onnxruntime"), pytest.raises(OCRUnavailable) as refused:
        engine.read(b"%PDF-1.4", kind="pdf")
    assert "rapidocr_onnxruntime is not installed" in str(refused.value)


def _a_scanned_page(saying: str) -> bytes:
    """A one-page PDF whose page is an image and nothing else - which is what a scan is.

    Drawn here rather than committed as a fixture so that what the engine is asked to read
    is visible in the test that reads it. `build_pdf` in `tests/p17` makes the other kind:
    a text layer, which OCR never touches.
    """
    from PIL import Image, ImageDraw

    page = Image.new("L", (1200, 400), color=255)
    # The default bitmap font is small; scaling a drawn-then-enlarged image also gives the
    # engine the soft edges a real scan has, which a crisply rendered glyph does not.
    label = Image.new("L", (300, 40), color=255)
    ImageDraw.Draw(label).text((6, 12), saying, fill=0)
    page.paste(label.resize((1050, 140), Image.LANCZOS), (60, 120))
    buffer = io.BytesIO()
    page.convert("RGB").save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def test_with_the_wheels_present_it_reads_rather_than_refusing() -> None:
    """The other half of the same property, and the half no test held: an engine that
    refused a real PDF while installed would be indistinguishable, from the refusal alone,
    from one that was never installed. Skips where the wheels are not there, because that is
    a fact about the machine and not about the code."""
    pytest.importorskip("pypdfium2")
    pytest.importorskip("rapidocr_onnxruntime")
    engine = ports.get_ocr("rapidocr")
    pages = engine.read(_a_scanned_page("TOTAL ASSETS"), kind="pdf")
    assert len(pages) == 1
    assert pages[0].number == 1
    said = " ".join(line.text for line in pages[0].lines).upper()
    assert "TOTAL" in said, f"the engine read a page and did not find its one word: {said!r}"
    assert all(
        line.confidence is None or 0.0 <= line.confidence <= 1.0 for line in pages[0].lines
    ), "a score outside 0..1 would be read as a confidence and is not one"


def test_it_reads_pdfs_and_says_so_when_asked_for_anything_else() -> None:
    engine = ports.get_ocr("rapidocr")
    with pytest.raises(OCRUnavailable, match="reads pdf"):
        engine.read(b"x", kind="png")


# ------------------------------------------------------------------ the invariants hold


def test_nothing_on_this_path_reaches_a_model_either() -> None:
    """P74's invariant, asked of the new adapter. Masking happens after the text exists, so
    an engine that called a model would hand it the unmasked page first."""
    for node in ast.walk(ast.parse(ADAPTER.read_text(encoding="utf-8"))):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert not name.startswith(("ports.llm", "anthropic", "openai")), name


REACHES_OUT = ("requests", "httpx", "httpx2", "urllib", "http", "socket", "boto3", "ftplib")


@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "ports" / "ocr").glob("*.py")),
    ids=lambda p: p.name,
)
def test_no_ocr_adapter_reaches_the_network(path: Path) -> None:
    """A wheel that phoned home would be the same failure as a vision model: the page
    would leave this machine before anything masked it.

    Every adapter, by import tree. This read `"urllib.request" not in source` against one
    file - `from urllib import request` contains neither phrase, `import http.client`
    evades it entirely, and `rapidocr.py`, the adapter CLAUDE.md recommends for the work
    machine, was not among the files checked at all."""
    reaching = reaches_any(path.read_text(encoding="utf-8"), REACHES_OUT)
    assert reaching == (), (path.name, reaching)


def test_its_dependencies_are_imported_inside_the_call() -> None:
    """Not at module scope, or importing `ports` at all would need an ONNX runtime."""
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    top_level = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}
    assert not {"pypdfium2", "rapidocr_onnxruntime"} & top_level, top_level


def test_the_heavy_dependencies_stay_out_of_the_project() -> None:
    """An ONNX runtime in `pyproject.toml` would land in every clone and every container
    that never reads a scan. They are the cost of selecting this adapter, and the refusal
    above is what tells somebody to pay it."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for heavy in ("rapidocr", "onnxruntime", "pypdfium2"):
        assert heavy not in pyproject, heavy

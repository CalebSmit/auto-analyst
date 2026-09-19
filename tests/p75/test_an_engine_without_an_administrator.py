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
from pathlib import Path

import pytest

import ports
from ports.ocr import OCRPort, OCRUnavailable

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


def test_it_refuses_by_name_rather_than_failing_to_import() -> None:
    """The one that matters. A missing wheel must arrive as this port's own refusal, naming
    what to install - not as an ImportError from the middle of a run, which reads as a
    broken build rather than an unconfigured machine."""
    engine = ports.get_ocr("rapidocr")
    with pytest.raises(OCRUnavailable) as refused:
        engine.read(b"%PDF-1.4", kind="pdf")
    said = str(refused.value)
    assert "pip install" in said
    assert "rapidocr-onnxruntime" in said
    assert "administrator" in said, "the reason to prefer it should be in the refusal"


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


def test_it_does_not_reach_the_network() -> None:
    """A wheel that phoned home would be the same failure as a vision model: the page would
    leave this machine before anything masked it."""
    source = ADAPTER.read_text(encoding="utf-8")
    for reaching in ("requests", "httpx", "urllib.request", "boto3", "socket"):
        assert reaching not in source, reaching


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

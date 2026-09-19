"""C46 - The first hour on a machine that has never seen this.

P77 and P78 both exist for one moment: somebody sitting down at the work machine with a
clone, no session history, and an evening. Everything else in this build is checked against
the code. These two are checked against each other and against what a person would actually
type.

The failure they guard against is specific. Skipping the OCR engine does not produce an
error - the reader reports a scanned page rather than inventing content for it, which is
correct - so what somebody sees is documents going in and nothing coming out. A packet that
did not warn about that would send them looking in the pipeline for a fault that is not
there.
"""

from __future__ import annotations

import re
from pathlib import Path

import ports

ROOT = Path(__file__).resolve().parents[3]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_the_setup_path_is_the_same_in_every_document_that_gives_one() -> None:
    """Three documents tell somebody how to start. Two different answers is one wrong."""
    for name in ("HANDOFF.md", "docs/USING.md"):
        body = read(name)
        assert "uv sync" in body or "start.cmd" in body, name


def test_the_ocr_step_is_consistent_wherever_it_is_told() -> None:
    """The adapter name, the packages and the variable have to match across the packet,
    the rules and the example env - a person will meet whichever they open first."""
    packet, rules, env = read("HANDOFF.md"), read("CLAUDE.md"), read(".env.example")
    for text in (packet, rules, env):
        assert "AA_OCR_ADAPTER" in text
    for text in (packet, rules):
        assert "rapidocr" in text and "tesseract" in text
    assert "pypdfium2" in packet and "rapidocr-onnxruntime" in packet


def test_every_adapter_named_in_a_document_is_one_the_ports_accept() -> None:
    registered = set(ports.adapters("ocr"))
    for name in ("rapidocr", "tesseract", "none"):
        if any(name in read(d) for d in ("HANDOFF.md", "CLAUDE.md", ".env.example")):
            assert name in registered, f"{name} is documented and not registered"


def test_the_quiet_failure_is_described_somewhere_a_person_will_look() -> None:
    """The whole point. Not "it errors" - it does not, and that is the problem."""
    packet = read("HANDOFF.md")
    assert "looks like nothing happening" in packet
    assert "scan" in packet.lower()


def test_what_is_owed_is_one_list_rather_than_two() -> None:
    """The packet's list and the register's must not disagree about what is waiting, or
    somebody picks up work that is already done or misses work that is not."""
    packet, register = read("HANDOFF.md"), read("BUILD/OPEN.md")
    for owed in ("Model Template - MASTER 2026", "hand-keyed"):
        assert owed in packet or owed.lower() in packet.lower(), owed
    assert "OCR" in register, "the register should still carry the OCR story"


def test_no_document_promises_a_flag_the_suite_does_not_have() -> None:
    """`--ocr` is offered to somebody at work. If the suite ever stops defining it, the
    packet becomes a command that fails on the one evening it is followed."""
    conftest = read("tests/conftest.py")
    for flag in re.findall(r"pytest[^\n`]*--(\w+)", read("HANDOFF.md")):
        assert f'"--{flag}"' in conftest, f"the packet offers --{flag}, the suite has no such flag"


def test_the_rules_and_the_packet_agree_about_what_version_one_is() -> None:
    """P77 corrected one of them. Two documents describing different products is the
    failure that survives longest, because each reads fine alone."""
    rules = read("CLAUDE.md")
    assert "input-help workbook" in rules.lower()
    assert "input-help workbook" in read("HANDOFF.md").lower()

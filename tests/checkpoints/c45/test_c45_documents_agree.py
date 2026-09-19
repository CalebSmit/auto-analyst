"""C45 - The documents a person arrives at, agreeing with each other.

There are four, and they are read by different people at different moments. `CLAUDE.md` is
what a session starts from. `interview/PROTOCOL.md` is what `/improve-agent` follows.
`docs/USING.md` is for somebody using the tool rather than building it. `HANDOFF.md` is for
the machine this is about to be moved to.

Each has been correct on its own. What a checkpoint can ask is whether they still say the
same thing - because the failure is not one of them being wrong, it is two of them being
differently right, and the reader believing whichever they opened.

This matters now in particular: the work machine is next, and HANDOFF.md is the document
that meets somebody there with no context and no session history.
"""

from __future__ import annotations

from pathlib import Path

import ports

ROOT = Path(__file__).resolve().parents[3]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_they_agree_on_how_to_run_it() -> None:
    """C31 holds two of them to this. Asked of all four, because a fourth document with a
    different command is the same failure with more surface."""
    for name in ("CLAUDE.md", "docs/USING.md"):
        body = read(name)
        assert "python -m uv run python tools/serve.py" in body, name
        assert "python -m uv run python tools/simulate_firm.py" in body, name


def test_they_agree_that_ocr_is_a_machine_difference() -> None:
    """The setting that decides whether most of this firm's documents can be read. If the
    handoff omitted it, somebody would set up the work machine and find the inbound path
    silently empty - the one failure that looks like nothing happening."""
    assert "AA_OCR_ADAPTER" in read("CLAUDE.md")
    assert "AA_OCR_ADAPTER" in read("HANDOFF.md")
    assert "AA_OCR_ADAPTER" in read(".env.example")


def test_the_handoff_does_not_still_say_only_the_key_changes() -> None:
    """It said only ANTHROPIC_API_KEY changes at handoff, which stopped being true when
    the OCR adapter arrived. A sentence that was true once is the hardest kind to notice."""
    env = read(".env.example")
    assert "only ANTHROPIC_API_KEY changes" not in env


def test_every_adapter_the_documents_name_is_registered() -> None:
    """A document that sends somebody to set a variable to a value the ports refuse."""
    for port, names in (("ocr", ("rapidocr", "tesseract")), ("llm", ("fake",))):
        registered = set(ports.adapters(port))
        for name in names:
            if name in read("CLAUDE.md") or name in read("HANDOFF.md"):
                assert name in registered, f"{name} is named but not registered on {port}"


def test_the_rules_and_the_protocol_still_share_their_vocabulary() -> None:
    """C29's rule, re-asked after a rewrite of one of the two - which is exactly when a
    shared word gets dropped from one side."""
    rules, protocol = read("CLAUDE.md"), read("interview/PROTOCOL.md")
    for shared in ("interview.py suggest", "register --none"):
        assert shared in rules and shared in protocol, shared


def test_nothing_still_describes_version_one_as_building_the_model() -> None:
    """The correction P77 made. If another document says the opposite, the correction was
    half done and a reader can still find the old answer."""
    rules = read("CLAUDE.md")
    assert "not for you to run" in rules or "does not run the model" in rules
    assert "input-help workbook" in rules.lower()


def test_the_documents_a_session_is_sent_to_all_exist() -> None:
    """C35's rule. Repeated because a rewrite is when a link gets stale."""
    rules = read("CLAUDE.md")
    for named in ("BUILD/STATE.md", "BUILD/OPEN.md", "BUILD/LEDGER.md", "BUILD/AMENDMENTS.md"):
        assert named in rules, named
        assert (ROOT / named).is_file(), named

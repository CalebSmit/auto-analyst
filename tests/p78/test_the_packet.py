"""P78: the packet that meets somebody at work.

`HANDOFF.md` is read once, by somebody with no context, at the moment they are least able
to tell a stale sentence from a current one. Its whole value is being true.

Its headline said `.env` changes and nothing else. That was true until P74 put an OCR
engine on the inbound path - and the failure of skipping it is not an error message. The
reader reports a scanned page rather than inventing content for it, which is correct, so
what somebody sees is documents arriving and nothing coming out of them. That is the
hardest kind of failure to meet on a first evening, and the document that is supposed to
prevent it said the opposite.

`test_no_document_claims_that_only_the_env_changes` is the one that matters: the claim was
in two files, and correcting one would have left the other to be found later.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def handoff() -> str:
    return (ROOT / "HANDOFF.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ what changes


def test_the_portability_claim_is_kept_and_scoped_rather_than_weakened() -> None:
    """The first correction here went too far and C10 caught it.

    `.env changes and nothing else` is load-bearing: the packet says that anything else
    needing to change to make the suite pass is a defect in the portability claim rather
    than a step to add quietly. Replacing it with "software gets installed too" would have
    invited exactly those steps. The suite *does* pass with no OCR engine - so the claim
    is true, and what needed saying is that it is a claim about the build.
    """
    # Whitespace-normalised: these are sentences in prose, and a rewrap should not fail a
    # test about what the prose says.
    text = " ".join(handoff().split())
    assert "**`.env` changes, and nothing else.**" in text, "the claim must survive"
    assert "That claim is about the build" in text
    assert "not a portability exception" in text
    assert "operational dependency" in text


def test_the_env_example_no_longer_says_only_the_key_changes() -> None:
    """A second, looser copy of the same claim, which did need correcting: the adapter is
    a setting, so `.env` really does change in one more place."""
    assert "only ANTHROPIC_API_KEY changes" not in (ROOT / ".env.example").read_text(
        encoding="utf-8"
    )


def test_the_engine_is_named_as_what_the_work_needs() -> None:
    text = handoff()
    assert "OCR engine" in text
    assert "NOT INSTALLED" in text and "NOT WIRED" in text


def test_it_says_what_skipping_the_engine_looks_like() -> None:
    """Not that it fails - that it does not. Somebody who knows to expect emptiness can
    diagnose it; somebody expecting an error cannot."""
    text = handoff()
    assert "looks like nothing happening" in text
    assert "arrives empty" in text or "arrive empty" in text


# ------------------------------------------------------------------ getting it running


def test_the_install_command_is_there_and_names_both_packages() -> None:
    text = handoff()
    assert "pypdfium2" in text and "rapidocr-onnxruntime" in text
    assert "AA_OCR_ADAPTER=rapidocr" in text


def test_it_says_how_to_check_the_engine_took() -> None:
    """A step with no way to confirm it worked is a step somebody repeats."""
    text = handoff()
    assert "serve.py --check" in text
    assert "pytest tests/p76 --ocr" in text


def test_the_alternative_engine_is_offered_with_its_cost() -> None:
    text = handoff()
    assert "tesseract" in text
    assert "executable on PATH" in text


def test_every_command_the_packet_gives_names_a_real_target() -> None:
    """A packet that sends somebody to a file or a flag that does not exist."""
    text = handoff()
    assert "serve.py" in text and "tests/p76" in text
    assert (ROOT / "tools" / "serve.py").is_file()
    assert (ROOT / "tests" / "p76").is_dir()
    conftest = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert '"--ocr"' in conftest, "the packet offers --ocr and the suite must define it"


# ------------------------------------------------------------------ what is owed


def test_what_is_owed_carries_the_fourth_session() -> None:
    """P28's list was the whole list until the interview changed what version 1 is for."""
    text = handoff()
    assert "Model Template - MASTER 2026" in text
    assert "per-engagement request items" in text.lower() or "request items" in text
    assert "upper bound, not a forecast" in text


def test_it_says_which_owed_thing_is_largest() -> None:
    """A list of eight with no order is a list somebody starts at the top of."""
    assert "largest single thing waiting" in handoff()


def test_the_session_it_cites_is_there_to_read() -> None:
    """It points at the session log for the template's structure. A packet citing a file
    nobody can open is worse than one citing nothing."""
    text = handoff()
    assert "knowledge/sessions/2026-09-18-1.md" in text
    assert (ROOT / "knowledge" / "sessions" / "2026-09-18-1.md").is_file()


def test_it_still_says_client_data_never_enters_the_repo() -> None:
    """P28 holds this. Re-asked because a rewrite is when a line like it goes missing."""
    assert "Client data never enters the repo" in handoff()

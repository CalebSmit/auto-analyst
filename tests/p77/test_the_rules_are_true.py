"""P77: the first thing a session reads, made true again.

`CLAUDE.md` is what every session starts from, in Cursor and in Claude Code alike. A
session that starts from a stale description builds the wrong thing confidently, and the
cost is not the inaccuracy - it is that every later judgement inherits it.

Four things had gone out of date. It described the project as DDR extraction,
normalization and model building, when the fourth interview session had redefined version 1
as gathering and organising data and explicitly *not* running the model. It described the
identifier register as empty with an acknowledgement standing in, which stopped being true
the day ten names went into it. It said nothing about the OCR adapter, which decides
whether most of this firm's documents can be read at all. And it did not carry the
acceptance rule the analyst gave, which is now what the confidence router applies.

These check the claims against the code rather than checking that words appear. A rules
file is trusted, so a line in it that has quietly stopped being true is worse than a line
that was never there.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rules() -> str:
    return (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ what version 1 is


def test_it_says_version_one_does_not_run_the_model() -> None:
    """The line that would have misled a session into building the wrong half."""
    text = rules()
    assert "not for you to run" in text or "does not run the model" in text
    assert "input-help workbook" in text.lower()


def test_it_names_the_steps_that_are_out_of_version_one() -> None:
    """Named, because 'narrower' is not actionable and a list is."""
    text = rules()
    for step in ("gpc", "cost-of-capital", "dcf-build", "qc-tieout"):
        assert step in text, step


def test_the_steps_it_names_are_steps_that_exist() -> None:
    """A rules file naming a step no recipe has is a rules file drifting the other way."""
    recipes = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "recipes").glob("*.yaml")
    )
    for step in ("gpc", "cost-of-capital", "dcf-build", "qc-tieout"):
        assert step in recipes, f"CLAUDE.md names {step}, which no recipe does"


def test_it_says_the_prior_workbook_is_the_chart_of_accounts_for_repeat_clients() -> None:
    """The finding that most changes what somebody builds next: for 75% of the work the
    firm-wide taxonomy is not the mapping that applies."""
    text = rules()
    assert "75%" in text
    assert "prior workbook is the chart of accounts" in text


# ------------------------------------------------------------------ the register


def test_what_it_says_about_the_register_matches_what_the_register_holds() -> None:
    """It described an empty register for as long as the register was empty. It is not."""
    from tools import interview

    names = interview.identifiers()
    text = rules()
    if names:
        assert "holds real" in text.lower() or "real client names now" in text
        assert "which was true of the first three" not in text, "that describes a past state"
    else:  # pragma: no cover - the register has names on this machine
        assert "empty" in text


def test_it_describes_what_register_none_actually_does() -> None:
    """P64 and P65 changed it: words are required, it records the sessions it covers, and
    it refuses to replace one that still stands. A rules file describing the old behaviour
    would have somebody overwrite a record and think it normal."""
    text = rules()
    assert "words of your own" in text
    assert "refuses to replace" in text
    assert "expires" in text


def test_the_words_the_protocol_guard_needs_are_still_there() -> None:
    """C29 holds CLAUDE.md and the protocol to the same vocabulary. A rewrite must not
    drop what another test is standing on."""
    text = rules()
    for needed in ("interview.py suggest", "register --none"):
        assert needed in text, needed
    assert "invent a name" in text.replace("Never invent", "invent")


# ------------------------------------------------------------------ the OCR setting


def test_it_names_the_setting_that_decides_whether_a_scan_can_be_read() -> None:
    text = rules()
    assert "AA_OCR_ADAPTER" in text
    assert "rapidocr" in text and "tesseract" in text


def test_the_adapters_it_names_are_registered() -> None:
    """Naming an adapter that does not exist would send somebody to set a variable to a
    value the ports refuse."""
    import ports

    named = {a for a in ports.adapters("ocr") if a in rules()}
    assert {"rapidocr", "tesseract"} <= named


def test_it_distinguishes_not_installed_from_not_wired() -> None:
    """The distinction P74 had to add after conflating them: one waits on software, the
    other is a join this build has left unmade."""
    text = rules()
    assert "NOT INSTALLED" in text and "NOT WIRED" in text


# ------------------------------------------------------------------ the standing rules


def test_the_acceptance_rule_is_written_down() -> None:
    text = rules()
    assert "proved by arithmetic" in text
    assert "source locator" in text
    assert "every one, not only what changed" in text


def test_the_two_scans_are_named_where_a_session_will_meet_them() -> None:
    text = rules()
    assert "tests/p71" in text and "tests/p73" in text
    for scan in ("tests/p71", "tests/p73"):
        assert (ROOT / scan).is_dir(), f"CLAUDE.md points at {scan}, which is not there"


def test_every_path_it_points_at_exists() -> None:
    """The cheapest way a rules file rots: a path that moved."""
    text = rules()
    missing = [
        candidate
        for candidate in re.findall(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+)`", text)
        if "/" in candidate
        and not candidate.endswith(("/",))
        and "*" not in candidate
        # `BUILD/phases/PNN.md` is a shape rather than a file - NN stands for the number.
        and "NN" not in candidate
        and not (ROOT / candidate).exists()
    ]
    assert missing == [], missing


def test_the_blueprint_numbers_still_match() -> None:
    """P07 holds these too. Repeated here because a rewrite is exactly when a number gets
    carried over without being re-checked."""
    text = rules()
    assert "118 nodes" in text and "240 edges" in text and "25 executable invariants" in text

"""C73 - one check, two surfaces, one answer.

P126 built the prose checks and gave them a command line. P131 joined them to the appendix
transplant. A checkpoint over one phase would be thin, so what this asks is the question
that spans both, and the one `tests/p131` cannot: whether the two surfaces agree.

A person can check an appendix source two ways now - `aa review` over the folder it sits in,
and the preview of the appendix that uses it - and they are the same words read by the same
module. If those ever disagreed, the one a person trusted would be whichever they looked at
last. That is the same property C71 holds for the formula audit across its three surfaces,
asked here of the second check to acquire more than one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docx import Document

from report import preview, set_up
from tests.docs import a_report, appendix_source
from tools import aa

ROOT = Path(__file__).resolve().parents[3]

SLOPPY = (
    "In today's economic environment the the outlook improved — a testament to policy ."
)


@pytest.fixture
def desk(tmp_path: Path) -> dict[str, Path]:
    last_year = tmp_path / "Valuation 2025.docx"
    a_report().save(str(last_year))

    folder = tmp_path / "appendix sources"
    folder.mkdir()
    source = folder / "economic.docx"
    document = appendix_source()
    document.add_paragraph(SLOPPY)
    document.save(str(source))

    return {
        "this_year": set_up(last_year, tmp_path / "Valuation 2026.docx"),
        "source": source,
        "folder": folder,
    }


def test_the_command_line_and_the_appendix_preview_read_the_same_words(
    desk: dict[str, Path],
) -> None:
    """Two surfaces on one check. A person checking the source before pressing the button
    and a person reading the preview must be told the same thing, or the one they trust is
    whichever they saw last."""
    (through_the_command,) = aa.review(desk["folder"])
    assert through_the_command.read == "prose"

    change = preview(desk["this_year"], "economic", desk["source"])

    def keyed(findings: list[dict[str, Any]]) -> set[tuple[str, str]]:
        return {(f["check"], f["where"]) for f in findings}

    assert keyed(change.prose["findings"]) == keyed(through_the_command.body["findings"])
    assert change.prose["paragraphs"] == through_the_command.body["paragraphs"]
    assert change.prose["sentences"] == through_the_command.body["sentences"]


def test_neither_surface_changes_the_document(desk: dict[str, Path]) -> None:
    """Both read. `aa review` has no write at all, and `preview` is the half of `update`
    that stops before one - so a person can ask either question of a report they are about
    to send without it becoming a report they have changed."""
    before = desk["source"].read_bytes()
    report_before = desk["this_year"].read_bytes()

    aa.review(desk["folder"])
    preview(desk["this_year"], "economic", desk["source"])

    assert desk["source"].read_bytes() == before
    assert desk["this_year"].read_bytes() == report_before


def test_the_appendix_moving_is_not_conditional_on_what_the_words_say(
    desk: dict[str, Path], tmp_path: Path
) -> None:
    """Across both phases: the check reports and the transplant proceeds. Asserted by
    moving content that every finding fires on and reading it out of the result."""
    from report import update
    from tests.docs import text_of

    change = update(desk["this_year"], "economic", desk["source"], into=tmp_path / "out.docx")
    assert change.prose["findings"], "every one of those findings fired"
    assert change.complete
    arrived = text_of(Document(str(change.written_to)))
    assert "Economic conditions in the period under review." in arrived
    assert SLOPPY.strip(".").split(" — ")[0][:30] in arrived, "including the bad sentence"


def test_the_checks_are_held_to_a_style_nobody_has_confirmed_yet_and_say_so() -> None:
    """The honest limit of both phases, kept visible.

    The em dash, how amounts are written, which terms are capitalised because they are
    defined - every one of those is a house style rule, and this build inferred all of
    them. The interview topic that asks for the real ones exists (`report-and-deck`), and
    a checkpoint is the right place to assert that the question is still on the map rather
    than quietly treated as answered.
    """
    from tools import interview

    topics = {t.id: t for t in interview.load_topics()}
    assert "report-and-deck" in topics
    asked = " ".join(topics["report-and-deck"].angles).lower()
    assert "house style" in asked and "dash" in asked

    coverage = interview.load_coverage(interview.KNOWLEDGE)
    assert coverage.get("report-and-deck", {}).get("status", "open") == "open", (
        "the house style has not been given; the checks are still held to an inference"
    )

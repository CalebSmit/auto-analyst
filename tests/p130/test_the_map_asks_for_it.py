"""P130: the three questions the interview map was not asking.

A topic is data, and the temptation with a data change is to let the existing suites cover
it - `tests/p37` already asserts that every topic has angles, a `done_when` and `feeds`,
and `tests/checkpoints/c27` already asserts the map stays generic. Both would have passed
over a change that added nothing.

What is held here is the thing those cannot see: that each of the three asks for what the
code it `feeds` is actually waiting on. A topic whose `feeds` names a module, and whose
angles never ask for what that module needs, is a question that will be answered without
unblocking anything - which is worse than no question, because an answered topic reads as
covered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout
from tools import interview

ROOT = Path(__file__).resolve().parents[2]
TOPICS = {t.id: t for t in interview.load_topics()}


def test_the_three_topics_are_on_the_map() -> None:
    assert {"work-machine-context", "report-and-deck", "excel-models"} <= set(TOPICS)


@pytest.mark.parametrize("topic", ["work-machine-context", "report-and-deck", "excel-models"])
def test_every_module_a_topic_feeds_is_something_that_exists(topic: str) -> None:
    """A `feeds` entry naming a module that moved is a promise the answer cannot keep."""
    for fed in TOPICS[topic].feeds:
        target = fed.split(" ")[0].rstrip("/")
        if not target or target.startswith("knowledge"):
            continue  # knowledge/ is created on first use by `interview.py init`
        assert (ROOT / target).exists() or (ROOT / f"{target}.py").exists(), (
            f"{topic} feeds {fed!r}, which is not there"
        )


def test_the_work_machine_topic_asks_what_is_already_built_and_whether_it_can_move() -> None:
    """The handoff. Knowledge this build is missing and the analyst has already written
    down - and the one thing that has to be asked before any of it moves, which is
    whether it carries a client's name."""
    topic = TOPICS["work-machine-context"]
    angles = " ".join(topic.angles).lower()
    assert topic.priority == 1, "the handoff is not a nice-to-have"
    assert "slash command" in angles or "skills" in angles
    assert "master model" in angles
    assert "report" in angles
    assert "client" in angles and "name" in angles, (
        "anything moved here comes under the outbound scan; the topic has to ask"
    )
    assert "client" in topic.done_when.lower()


def test_the_report_topic_asks_for_what_the_report_path_and_the_prose_checks_need() -> None:
    """`report/appendices.py` is 'data, not code' and has no restricted-use set in it.
    `tools/prose_checks.py` has a house style it inferred and nobody confirmed. Both are
    waiting on this topic, and both are named in its `feeds`."""
    topic = TOPICS["report-and-deck"]
    angles = " ".join(topic.angles).lower()
    assert "appendices" in angles or "appendix" in angles
    assert "house style" in angles
    assert "dash" in angles, "the em dash is the finding the analyst asked for by name"
    assert "capitalised" in angles, "'the Company' versus 'the company' is a real finding"
    assert "report/appendices.py" in topic.feeds
    assert "tools/prose_checks.py" in topic.feeds


def test_the_template_topic_asks_for_a_command_rather_than_a_transcription() -> None:
    """It used to ask the analyst to write the input map - four hundred rows by hand.
    `tools/read_template.py` reads the names off the file, so what is left to ask is the
    only part the file cannot state."""
    topic = TOPICS["excel-models"]
    angles = " ".join(topic.angles)
    assert "read_template.py" in angles
    assert "REVIEW" in topic.done_when, "and the markers are what the answer removes"
    assert "what each one means" in angles.lower()


def test_the_two_new_topics_read_as_open_so_a_session_is_offered_them() -> None:
    """A topic the coverage file has never heard of has to arrive as `open`. One that
    arrived as anything else would be a question nobody is asked."""
    needs_a_checkout("the interview's topic map")
    coverage = interview.load_coverage(interview.KNOWLEDGE)
    for topic in ("work-machine-context", "report-and-deck"):
        # A topic the coverage file has no entry for is open by absence, which is the
        # state a new one arrives in. An entry claiming anything else would mean somebody
        # marked it covered without it having been asked.
        assert coverage.get(topic, {}).get("status", "open") == "open", f"{topic} is not open"
    assert coverage.get("role", {}).get("status") == "covered", (
        "and the reader is working: a topic that has been covered reads as covered"
    )


def test_the_map_names_no_client_and_no_figure() -> None:
    """The map is committed and generic; `knowledge/` is where a name is allowed to be.
    Asserted on the new topics specifically, because the file-wide version of this check
    lives in c27 and would pass on a map whose new entries were the only offenders."""
    names = interview.identifiers()
    if not names:
        pytest.skip("register empty; `scan` refuses for the same reason and says so")
    text = (ROOT / "interview" / "topics.yaml").read_text(encoding="utf-8")
    for name in names:
        assert name.lower() not in text.lower(), f"{name!r} is on the interview map"

"""C72 - the handoff, read end to end.

P129 reads the firm's model and drafts the binding it needs. P130 makes the interview ask
for the things that draft cannot state. Separately, each is a small, well-tested piece.
Together they are supposed to be a route: a command on the work machine produces something,
a question gets the rest, and the result loads into this build and can be bound.

What this checkpoint asks is whether that route actually joins up, which neither suite can
see:

* **the command produces what the question asks for.** `excel-models`'s `done_when` names
  `read_template.py` and the `REVIEW` markers. If the tool stopped writing markers, or
  started calling them something else, the topic would be asking for something that does
  not exist and nothing would have failed.
* **the thing it produces loads where the question says it goes.** The topic's `feeds`
  names `templates/inputs/`, and the registry reads that folder by a key derived from the
  filename. A draft whose header told somebody the wrong filename would be a template the
  registry reports as unregistered - which reads as the system being broken rather than as
  a file in the wrong place.
* **and the whole of it stays generic.** The map is committed; `knowledge/` is where a
  client's name is allowed to be. A route that invites somebody to copy their work-machine
  files here has to be a route the outbound scan still passes over.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
import yaml
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from deliver.registry import TemplateInputs, version_key
from tools import interview
from tools.read_template import NEEDS_A_PERSON, as_yaml, draft

ROOT = Path(__file__).resolve().parents[3]
TOPICS = {t.id: t for t in interview.load_topics()}


def a_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Input"
    for name, ref in (("Revenue_FY1", "B2"), ("Revenue_FY2", "B3"), ("Wages_FY1", "B4")):
        wb.defined_names.add(DefinedName(name, attr_text=f"Input!${ref[0]}${ref[1:]}"))
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_the_question_asks_for_what_the_command_produces() -> None:
    """The join. The topic names the tool and the markers; the tool writes them."""
    topic = TOPICS["excel-models"]
    asked = " ".join([*topic.angles, topic.done_when])
    assert "read_template.py" in asked
    assert NEEDS_A_PERSON in asked

    drafted = draft(a_template(), file="M.xlsx", template_version="1.0", sheet="Input")
    body = as_yaml(drafted)
    assert NEEDS_A_PERSON in body, "the marker the topic asks about is in what the tool writes"
    assert (ROOT / "tools" / "read_template.py").is_file(), "and the tool the topic names is here"


def test_what_the_command_produces_loads_where_the_question_says_it_goes(
    tmp_path: Path,
) -> None:
    """`templates/inputs/` is in the topic's `feeds`, and the registry reads that folder
    by a key derived from the filename. The draft's header has to name that filename, or
    somebody follows it and the registry reports the template as unregistered."""
    assert "templates/inputs/" in TOPICS["excel-models"].feeds

    drafted = draft(
        a_template(), file="Model Template - MASTER 2026.xlsx",
        template_version="2026.1", sheet="Input",
    )
    key = version_key("Model Template - MASTER 2026.xlsx", "2026.1")
    body = as_yaml(drafted)
    assert f"templates/inputs/{key}.yaml" in body, (
        "the header names the filename the registry wants"
    )

    raw = yaml.safe_load(body)
    for entry in raw["required"]:
        entry["line"] = entry["line"].removeprefix(f"{NEEDS_A_PERSON}: ")
        if NEEDS_A_PERSON in entry["period"]:
            entry["period"] = "FY1"
    (tmp_path / f"{key}.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")

    schema = TemplateInputs.load(key, folder=tmp_path)
    assert schema.key == key
    assert set(schema.required) == set(drafted.proposed)
    assert (ROOT / "templates" / "inputs").is_dir(), "and the folder it goes in is there"


def test_the_route_that_invites_files_here_asks_whether_they_carry_a_name() -> None:
    """`work-machine-context` invites the analyst to copy things from the work machine.
    Anything copied comes under the outbound payload scan, so the question that invites
    it has to be the question that asks - and `interview.py scan` has to still pass over
    the map that asks it."""
    topic = TOPICS["work-machine-context"]
    asked = " ".join([*topic.angles, topic.done_when]).lower()
    assert "client" in asked and ("name" in asked or "figure" in asked)

    names = interview.identifiers()
    if not names:
        pytest.skip("register empty; `scan` refuses for the same reason and says so")
    assert interview.scan(interview.committable_files(), names) == []


def test_the_three_reads_are_named_where_the_report_question_will_answer_them() -> None:
    """`report-and-deck` feeds `tools/prose_checks.py`, which has a house style it
    inferred. The route is only real if the thing it feeds is still there and still has
    the checks the answer would set."""
    topic = TOPICS["report-and-deck"]
    assert "tools/prose_checks.py" in topic.feeds
    assert (ROOT / "tools" / "prose_checks.py").is_file()

    from tools.prose_checks import CHECKS

    assert "em_dash" in CHECKS, "the finding the analyst asked for by name"
    assert "term_both_ways" in CHECKS, "the Company versus the company"
    assert "money_both_ways" in CHECKS, "how amounts are written"
    # Each of those is a rule the answer to this topic sets. A check the topic implies and
    # the module has not got would be a question whose answer nothing could use.
    for implied in ("dash", "capitalised"):
        assert implied in " ".join(topic.angles).lower()

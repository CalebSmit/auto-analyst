"""P167: methodology, not procedures.

The owner's decision of 2026-10-05: `dcf-build`, `gpc-scrub` and `cost-of-capital` will not
be built as procedures. The firm's own Excel model does the DCFs and takes its WACC inputs
from Capital IQ, and comps screening is the analyst's judgement with keyword and industry
screens. What the tool needs is **knowledge the model consults** when deciding how to handle
something in the model - and the mechanism for that already existed: `foundations/` is
scope-walked into every context by the Context Builder and cleared by digest, and it held
four skeletons.

So the knowledge lives in two places with one content. `knowledge/methodology/<topic>.md`
holds everything: what the analyst said, cited to the session; what the model should do with
it; what is still unknown, as the questions the work laptop answers.
`foundations/valuation/_group/<topic>.md` holds the rules section of that file, **verbatim**,
and is what a valuation run attaches once a person has cleared it. These tests hold the pair
together, hold the layer under its byte ceiling, and hold every file clean to the clearance
scan and the identifier register - because a methodology file reaches every prompt for
every client, and a leak there travels everywhere.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from registries.methodology import MethodologyRegister

ROOT = Path(__file__).resolve().parents[2]
FOUNDATIONS = ROOT / "foundations"
KNOWLEDGE = ROOT / "knowledge" / "methodology"
LAYER = "valuation/_group"
TOPICS = (
    "ebitda-adjustments",
    "nwc-excluded-items",
    "nwc-normal-level",
    "gpc-screening",
    "cost-of-capital-inputs",
    "report-writing",
)
RULES_HEADING = "## What the model should do with it"


def section(text: str, heading: str) -> str:
    """The body under one `##` heading, up to the next."""
    start = text.index(heading) + len(heading)
    rest = text[start:]
    stop = re.search(r"^## ", rest, re.M)
    return (rest[: stop.start()] if stop else rest).strip()


def bullets(text: str) -> list[str]:
    """Each `- ` item as one string, wrapped lines joined, so a reflow is not a drift."""
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            out.append(line[2:].strip())
        elif line.startswith("  ") and out:
            out[-1] += " " + line.strip()
    return out


# ---------------------------------------------------------------- the pair, held together


@pytest.mark.parametrize("topic", TOPICS)
def test_the_rules_in_foundations_are_the_rules_in_knowledge_verbatim(topic: str) -> None:
    """Every bullet under *What the model should do with it* in the knowledge file is a
    bullet under *Rules* in the foundations file, and nothing else is. Change the rules in
    knowledge and this says the foundations copy is stale - which is the point, because the
    foundations copy is the one a run reads."""
    knowledge = (KNOWLEDGE / f"{topic}.md").read_text(encoding="utf-8")
    foundations = (FOUNDATIONS / LAYER / f"{topic}.md").read_text(encoding="utf-8")
    assert bullets(section(foundations, "## Rules")) == bullets(
        section(knowledge, RULES_HEADING)
    ), topic


@pytest.mark.parametrize("topic", TOPICS)
def test_each_knowledge_file_has_the_three_parts(topic: str) -> None:
    text = (KNOWLEDGE / f"{topic}.md").read_text(encoding="utf-8")
    assert "## What we know" in text
    assert RULES_HEADING in text
    assert "## What is still unknown" in text
    # Every item under *What we know* cites where it came from; a knowledge file that does
    # not say where a sentence came from is an opinion with a heading.
    known = section(text, "## What we know")
    items = [i for i in re.split(r"^\d+\. ", known, flags=re.M) if i.strip()]
    assert len(items) >= 5, topic
    for item in items:
        cited = re.search(
            r"\(.*?20\d\d-\d\d-\d\d.*?\)|owner's brief|backlog|OPEN\.md|topics\.yaml"
            r"|build note|skills/",
            item,
            re.S,
        )
        # An honest negative - "never came up in any session" - is a citation of absence.
        absent = re.search(
            r"never (?:came up|mentioned|discussed).*?(?:any|no) session|no session", item, re.S
        )
        assert cited or absent, (topic, item[:80])
    unknown = section(text, "## What is still unknown")
    assert len(re.findall(r"^\d+\. ", unknown, flags=re.M)) >= 5, topic


@pytest.mark.parametrize("topic", TOPICS)
def test_each_foundations_file_points_at_its_knowledge_file(topic: str) -> None:
    foundations = (FOUNDATIONS / LAYER / f"{topic}.md").read_text(encoding="utf-8")
    # Flattened across lines and without the blockquote marks, so a reflow of the note is
    # not a failure.
    flat = " ".join(line.lstrip("> ").strip() for line in foundations.splitlines())
    assert f"knowledge/methodology/{topic}.md" in flat
    assert "Clearing this file at `/admin`" in flat, "a person's confirmation is the gate"


# ----------------------------------------------------- what a valuation run would attach


def test_a_valuation_run_walks_the_six_in_its_group_layer() -> None:
    register = MethodologyRegister(root=FOUNDATIONS)
    carried = register.for_layers(("_firm", LAYER))
    names = [register.name_of(p) for p in carried]
    for topic in TOPICS:
        assert f"{LAYER}/{topic}.md" in names, names
    # And a consulting run would carry none of them.
    consulting = register.for_layers(("_firm", "consulting/_group"))
    assert all(LAYER not in register.name_of(p) for p in consulting)


def test_the_layer_is_under_its_byte_ceiling() -> None:
    import yaml

    constraints = yaml.safe_load(
        (ROOT / "constraints" / "constraints.yaml").read_text(encoding="utf-8")
    )
    ceiling = int(constraints["ceilings"]["per_methodology_layer"]["bytes_max"])
    register = MethodologyRegister(root=FOUNDATIONS)
    assert register.bytes_at(LAYER) <= ceiling, (register.bytes_at(LAYER), ceiling)
    assert register.bytes_at(LAYER) > 5_000, "six rule files are not six empty files"


@pytest.mark.parametrize("topic", TOPICS)
def test_each_rule_file_passes_the_clearance_scan(topic: str, tmp_path: Path) -> None:
    """The scan a person's clearance runs: nothing shaped like an engagement's data, nothing
    shaped like an instruction to the model reading it. Run against a register in a temp
    directory so nothing is recorded as cleared by a test."""
    register = MethodologyRegister(path=tmp_path / "cleared.yaml", root=FOUNDATIONS)
    path = FOUNDATIONS / LAYER / f"{topic}.md"
    assert register.scan(path.read_bytes(), register.name_of(path)) == ()


def test_the_clearance_register_stays_out_of_the_repository() -> None:
    """A clearance is a person's act, so `foundations/cleared.yaml` is not committed: a
    fresh clone - the work laptop - starts with nothing cleared and says so. (On a developer
    machine the suite's own session fixture clears the repo's foundations into the local
    register, which is why this does not assert the file is absent.)"""
    done = subprocess.run(
        ["git", "check-ignore", "foundations/cleared.yaml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, "foundations/cleared.yaml must be gitignored"
    tracked = subprocess.run(
        ["git", "ls-files", "foundations/cleared.yaml"], cwd=ROOT, capture_output=True, text=True
    )
    assert tracked.stdout.strip() == "", (
        "the register is tracked, which ships a decision nobody made"
    )


# ------------------------------------------------------------------- nothing identifying


def test_the_identifier_scan_is_clean_over_both_trees() -> None:
    """`interview.py scan` checks every file outside knowledge/ against the register; the
    knowledge files are checked here directly, because they feed foundations and a name in
    one would be a name in every prompt."""
    done = subprocess.run(
        [sys.executable, "tools/interview.py", "scan"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "clean" in done.stdout

    register = [
        line.strip()
        for line in (ROOT / "knowledge" / "identifiers.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert register, "an empty register would make this a tautology"
    for path in sorted(KNOWLEDGE.glob("*.md")):
        text = path.read_text(encoding="utf-8").lower()
        hits = [i for i in register if i.lower() in text]
        assert not hits, (path.name, hits)


# ---------------------------------------------------------- the three skills, superseded


SUPERSEDED = ("cost-of-capital", "dcf-build", "gpc-scrub")


@pytest.mark.parametrize("name", SUPERSEDED)
def test_a_superseded_skill_says_what_supersedes_it(name: str) -> None:
    """The frontmatter stays - the tree, the resolver and the contracts resolve against
    it - and the body says the one thing a reader needs: this is not owed, and here is
    where the knowledge went."""
    from registries.skills import SkillTree

    skill = next(s for s in SkillTree.load().all() if s.name == name)
    assert skill.status == "superseded"
    body = (ROOT / skill.path).read_text(encoding="utf-8")
    assert "Superseded by methodology (P167)" in body
    assert "knowledge/methodology/" in body and "foundations/valuation/_group/" in body
    assert "Not written, and not to be written" in body
    assert "Skeleton" not in body


def test_nothing_dispatches_a_superseded_skill() -> None:
    """The one fact that made retiring them safe: nothing in production reads a skill's
    status except the surface snapshot, and no procedure exists for any of the three - so
    `procedure_for` refuses each by name, as it always did."""
    from harness.procedures import PROCEDURES, procedure_for

    for name in SUPERSEDED:
        assert name not in PROCEDURES
        with pytest.raises(KeyError):
            procedure_for(name)


def test_version_one_names_none_of_them() -> None:
    import yaml

    recipe = yaml.safe_load(
        (ROOT / "recipes" / "valuation-input-prep.yaml").read_text(encoding="utf-8")
    )
    named = {step.get("skill") for step in recipe.get("steps", []) if step.get("skill")}
    assert not named & set(SUPERSEDED)


# ----------------------------------------------------------- the topic map writes here


def test_the_interview_feeds_the_knowledge_files() -> None:
    """The next session on the work laptop writes where the model reads: the three topics
    that used to feed the compute skills feed the knowledge files now, and every file a
    topic feeds exists."""
    import yaml

    topics = yaml.safe_load((ROOT / "interview" / "topics.yaml").read_text(encoding="utf-8"))
    rows = topics["topics"] if isinstance(topics, dict) else topics
    by_id = {row["id"]: row for row in rows}
    assert "knowledge/methodology/cost-of-capital-inputs.md" in by_id["cost-of-capital"]["feeds"]
    assert "knowledge/methodology/gpc-screening.md" in by_id["market-approach"]["feeds"]
    for row in rows:
        for fed in row.get("feeds", []):
            if fed.startswith("knowledge/methodology/"):
                assert (ROOT / fed).exists(), fed
            retired = ("gpc-scrub", "dcf-build", "cost-of-capital)")
            assert not any(name in fed for name in retired), (
                row["id"], fed
            )

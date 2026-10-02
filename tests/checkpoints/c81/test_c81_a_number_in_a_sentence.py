"""C81 - a number in a sentence, wherever a reader meets one.

**P148.** Four sentences on the consoles count something and two counted wrong: the Setup
page said *Fourteen checks* where preflight has fifteen, and said it directly above a panel
printing `15 checks` from the live configuration; the help page said *Three colours* above
four of them. `tests/counting.py` had existed since P114 for exactly this, with the rule
*derive the prose from the list, never write the number down twice* - and it had six users,
none of them a console, because the table lived under `tests/` where no page could reach it.

What a checkpoint can ask that the phase could not.

**The table moved, and six tests were already standing on it.** A phase proves its own
pages; it does not prove that `tests/p30`, `tests/p117` and the rest are still measuring the
same thing rather than a copy that happens to agree today.

**And a page is now allowed to reach for it**, which is new: `admin/page.py` imports from
`admin/preflight.py` and `ops/console/help_page.py` from `ui/words.py`. A page that states a
count and imports nothing is a page that typed one, and that is the shape of the defect
rather than any particular number.

**`docs/USING.md` is the other prose a reader is given**, and CLAUDE.md says to keep it true
because a test holds it to the setup path it describes. It counts the reviewer's commands,
and that is a count of a list of files.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from admin.page import PAGE as SETUP
from admin.preflight import CHECKS
from ops.console.help_page import MEANINGS
from ops.console.help_page import PAGE as HELP
from tests.counting import WORDS, in_words
from ui import words as production

ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------ one table, still


def test_there_is_one_table_and_both_sides_use_it() -> None:
    """The move is the whole fix. Two tables that agree today is the state P148 found."""
    assert in_words is production.in_words
    assert WORDS is production.WORDS
    assert production.WORDS[14] == "Fourteen" and production.WORDS[15] == "Fifteen"


def assigns_a_word_table(source: str) -> bool:
    """Whether this module binds a name to its own list of number words.

    Asked of the tree, because a module whose job is to forbid a second table necessarily
    contains the text of the thing it forbids - this test found itself the first time it
    ran, which is `tests/reading.py`'s rule arriving for the third time in this block.
    """
    for node in ast.walk(ast.parse(source)):
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        names = {t.id for t in targets if isinstance(t, ast.Name)}
        if not names & {"WORDS", "NUMBERS", "IN_WORDS"}:
            continue
        value = node.value
        if isinstance(value, ast.Name | ast.Attribute):
            continue  # a re-export, which is the point
        if isinstance(value, ast.List | ast.Tuple) and any(
            isinstance(e, ast.Constant) and e.value == "Eleven" for e in value.elts
        ):
            return True
    return False


def test_every_module_that_counts_in_words_stands_on_the_one_table() -> None:
    """They were written against `tests/counting`, which now re-exports. If one of them ever
    grows its own table the rule is back to being two rules that happen to agree today."""
    users, spare = [], []
    for folder in ("tests", "ui", "ops", "admin", "tools", "report", "deliver"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "__pycache__" in path.parts or path == ROOT / "ui" / "words.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "in_words" in source or "counting" in source:
                users.append(str(path.relative_to(ROOT)))
            if assigns_a_word_table(source):
                spare.append(str(path.relative_to(ROOT)))
    assert spare == [], f"a second table of number words: {spare}"
    assert len(users) >= 7, f"only {len(users)} modules count in words: {users}"


# -------------------------------------------- a page that counts has to reach for it


def test_a_page_that_states_a_count_imports_what_it_counts() -> None:
    """The property behind the two numbers, rather than the two numbers. A sentence that
    names a count and a module that imports nothing to produce it is a typed number, and
    which number it is today says nothing about tomorrow.
    """
    PAGES = {
        "admin/page.py": (SETUP, r"(\w+) checks over the live configuration"),
        "ops/console/help_page.py": (HELP, r"(\w+) colours carry meaning"),
    }
    for rel, (rendered, pattern) in PAGES.items():
        said = re.search(pattern, rendered)
        assert said, f"{rel} no longer states its count"
        source = (ROOT / rel).read_text(encoding="utf-8")
        imported = {
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "in_words" in imported, f"{rel} states a count and imports no way to write one"
        assert f'"why">{said.group(1)}' not in source, (
            f"{rel} renders {said.group(1)!r} and also has it typed in the source"
        )


def test_the_two_counts_are_what_their_lists_hold() -> None:
    """Said again at this level, because a checkpoint that took the phase's word for it
    would be the apparatus not working."""
    assert re.search(r"(\w+) checks over the live", SETUP).group(1) == in_words(len(CHECKS))
    assert re.search(r"(\w+) colours carry", HELP).group(1) == in_words(len(MEANINGS))


# ---------------------------------------------- and the other prose a reader is given


def test_the_guide_counts_the_reviewers_commands_correctly() -> None:
    """`docs/USING.md` is written for the people who use this rather than build it, and
    CLAUDE.md says to keep it true. It says how many checks a person can point at a file,
    and that is a count of a list of files in `tools/`.
    """
    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    said = re.search(r"(\w+) checks you can point at anything", guide)
    assert said, "the guide no longer says how many checks a person can run"
    commands = [
        name
        for name in ("formula_audit", "prose_checks", "reasonableness")
        if (ROOT / "tools" / f"{name}.py").exists()
    ]
    assert said.group(1) == in_words(len(commands)), (
        f"the guide says {said.group(1)!r} and tools/ has {len(commands)}: {commands}"
    )


def test_the_guide_shows_a_command_line_for_each_check_it_counts() -> None:
    """The count above is only worth having if the three it counts are reachable. The guide
    writes them in prose - *the formula audit*, *the prose checks* - so what is checked here
    is that each one's command line is printed somewhere a reader can copy it.
    """
    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    missing = [
        name
        for name in ("formula_audit", "prose_checks", "reasonableness")
        if f"tools/{name}.py" not in guide and f"tools{chr(92)}{name}.py" not in guide
    ]
    assert missing == [], f"the guide counts these and prints no way to run them: {missing}"

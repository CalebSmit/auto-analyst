"""P114 - files one level above where anybody is looking.

Setting up the first real client folder, I registered the engagement's folder as
`Test Client` under a pattern watch at depth 2. The sweep looks at `<root>/<a>/<b>`, so
every file sat one level above where it looks. The planner skipped them, no target was
produced, no arrival was recorded, and nothing was reported unclaimed - so preflight said
*"every swept folder maps to an engagement"*, which was true and useless, because none
were.

A green Setup page, thirteen client files on disk, and silence, for as long as anyone
cared to wait. It took reading the planner's source to find.

This is the step the analyst's own test begins with - point it at the folder where the
documents live - and it was the one place the system watched somebody make a mistake and
said nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from intake.config import Watch
from intake.sweep import SweepPlanner, folder_too_shallow

ROOT = Path(__file__).resolve().parents[2]


def watch(depth: int = 2, kind: str = "pattern") -> Watch:
    return Watch(
        id="w-clients", kind=kind, name="Clients", root="Clients", recipe="r", depth=depth
    )


class Files:
    """A storage port that lists exactly what it was given."""

    def __init__(self, *paths: str) -> None:
        self.paths = paths

    def list(self, prefix: str) -> list[Any]:
        del prefix  # the planner lists the root; this stands in for the whole tree
        return [type("Ref", (), {"path": path})() for path in self.paths]

    def __repr__(self) -> str:
        return f"Files({len(self.paths)})"


# ============================================================ provable at registration


def test_a_folder_shallower_than_the_watch_can_never_be_swept() -> None:
    """The whole finding in one call. Not "usually wrong", not "wrong until somebody
    files differently" - a folder with one segment matches nothing a depth-2 watch will
    ever list, and that is knowable from two numbers on one form."""
    problem = folder_too_shallow("Test Client", watch())
    assert problem is not None
    assert "would ever be listed" in problem


def test_the_refusal_says_the_shape_it_wants() -> None:
    """"Wrong" is not actionable. "It looks at Clients/<a>/<b>" is."""
    problem = folder_too_shallow("Test Client", watch())
    assert problem is not None
    assert "Clients/<a>/<b>" in problem


def test_a_folder_at_the_right_depth_is_fine() -> None:
    assert folder_too_shallow("Kestrel Precision/2026 Valuation", watch()) is None


def test_a_folder_deeper_than_the_watch_is_also_a_problem() -> None:
    """The mirror. A three-segment folder under a depth-2 watch is keyed by its first two,
    so two engagements filed that way collide - and neither is the folder anybody named."""
    assert folder_too_shallow("Kestrel/2026/Valuation", watch()) is not None


def test_a_bound_watch_has_no_depth_to_disagree_with() -> None:
    """One folder to one engagement, explicit. There is nothing to be shallow about."""
    assert folder_too_shallow("anything", watch(kind="bound")) is None


def test_an_empty_folder_is_somebody_else_s_check() -> None:
    """A missing folder is a different question and `bindings` already asks it. Reporting
    it twice, in different words, is worse than reporting it once."""
    assert folder_too_shallow("", watch()) is None


# ============================================================ the planner says so


def planner(*paths: str, folder: str, depth: int = 2) -> Any:
    from intake.roster import RosterEntry, RosterState

    entry = RosterEntry(
        engagement_id="KSPW-2026-01",
        client="Kestrel Precision Works",
        scope_path="valuation/non-esop/non-repeat",
        watch_id="w-clients",
        destination_id="d-out",
        folder=folder,
        state=RosterState.ACTIVE,
    )
    roster = type("R", (), {"entries": lambda self: (entry,), "get": lambda self, i: entry})()
    config = type("C", (), {"watches": lambda self: (watch(depth),)})()
    return SweepPlanner(roster, config, Files(*paths)).plan()


def test_files_above_the_depth_are_counted_rather_than_dropped() -> None:
    """This used to be a `continue` with a comment saying a file above engagement depth
    belongs to nobody in particular. True - and saying nothing about it is how thirteen
    files sat behind a green page."""
    plan = planner(
        "Clients/Test Client/Balance Sheets.xlsx",
        "Clients/Test Client/Income Statements.xlsx",
        folder="Test Client",
    )
    assert plan.targets == (), "nothing could be swept, which is the point"
    assert len(plan.shallow) == 1
    found = plan.shallow[0]
    assert found.files == 2
    assert found.location == "Clients/Test Client"
    assert found.depth == 2


def test_a_correctly_filed_folder_produces_no_warning() -> None:
    """The other half. A check that fires on a correct setup is a check people learn to
    ignore, and this one has to survive being read every day."""
    plan = planner(
        "Clients/Kestrel Precision/2026 Valuation/Balance Sheets.xlsx",
        folder="Kestrel Precision/2026 Valuation",
    )
    assert plan.shallow == ()
    assert [t.engagement_id for t in plan.targets] == ["KSPW-2026-01"]


def test_both_can_be_true_at_once() -> None:
    """One folder filed right and a stray file beside it. The stray is reported and the
    engagement still runs - the warning stops nothing."""
    plan = planner(
        "Clients/Kestrel Precision/2026 Valuation/IS.xlsx",
        "Clients/readme.txt",
        folder="Kestrel Precision/2026 Valuation",
    )
    assert len(plan.targets) == 1
    assert len(plan.shallow) == 1 and plan.shallow[0].files == 1


# ============================================================ where a person is told


def console_with(*watches: Watch) -> Any:
    """An AdminConsole with nothing behind it but a list of watches.

    Enough to reach the folder check, which happens before the roster is touched - and a
    stand-in rather than a real console because this is about one refusal, and a test that
    needed a database to ask about it would be a test nobody ran."""
    from admin.console import AdminConsole

    console = AdminConsole.__new__(AdminConsole)
    console.config = type("C", (), {"watches": lambda self: watches})()  # type: ignore[attr-defined]
    return console


def entry_for(folder: str) -> Any:
    from intake.roster import RosterEntry, RosterState

    return RosterEntry(
        engagement_id="KSPW-2026-01",
        client="Kestrel Precision Works",
        scope_path="valuation/non-esop/non-repeat",
        watch_id="w-clients",
        destination_id="d-out",
        folder=folder,
        state=RosterState.PAUSED,
    )


def test_registration_refuses_it_rather_than_waiting_for_preflight() -> None:
    """Preflight says the same thing and keeps saying it. This is the sentence that
    arrives while the person who typed the folder is still looking at the screen - so it
    is asked of the console rather than of its source."""
    from admin.console import AdminRefused

    with pytest.raises(AdminRefused) as refused:
        console_with(watch()).register_engagement(
            entry_for("Test Client"), profile=None, who="Caleb", reason="letter signed"
        )
    said = " ".join(str(d) for d in refused.value.diagnostics)
    assert "Clients/<a>/<b>" in said, "the refusal says the shape it wants"


def test_registration_at_the_right_depth_is_not_refused() -> None:
    """It gets past the folder check and fails on the roster this stand-in does not have,
    which is proof it got past the folder check."""
    from admin.console import AdminRefused

    with pytest.raises(Exception) as raised:  # noqa: B017, PT011 - anything but a refusal
        console_with(watch()).register_engagement(
            entry_for("Kestrel Precision/2026 Valuation"),
            profile=None,
            who="Caleb",
            reason="letter signed",
        )
    assert not isinstance(raised.value, AdminRefused)


def test_preflight_has_a_check_of_its_own_for_it() -> None:
    """Not folded into `unclaimed_folders`, which was the check that reported everything
    was fine. A person reads the label, and "every swept subfolder maps to an engagement"
    is not the question being answered."""
    from admin.preflight import CHECKS

    labels = dict(CHECKS)
    assert "folder_depth" in labels
    assert "as deep as its watch looks" in labels["folder_depth"]


def preflight_over(folder: str, *paths: str) -> Any:
    """`Preflight._folder_depth` with a roster, a watch and a listing behind it."""
    from admin.preflight import Preflight

    entry = entry_for(folder)
    check = Preflight.__new__(Preflight)
    check.config = type("C", (), {"watches": lambda self: (watch(),)})()  # type: ignore[attr-defined]
    check.roster = type("R", (), {"entries": lambda self: (entry,)})()  # type: ignore[attr-defined]
    check.storage = Files(*paths)  # type: ignore[attr-defined]
    return check._folder_depth((entry,))  # noqa: SLF001


def test_a_folder_that_cannot_be_swept_blocks_that_engagement() -> None:
    """There is no state of the world in which it runs, so it is a failure and it names
    the engagement it stops."""
    result = preflight_over("Test Client", "Clients/Test Client/IS.xlsx")
    blocking = [f for f in result.failures if f.severity == "fail"]
    assert len(blocking) == 1
    assert blocking[0].engagement_ids == ("KSPW-2026-01",)


def test_a_stray_file_is_said_and_stops_nothing() -> None:
    """It may be a filing mistake or a folder that lives beside the client folders, and
    which one is a person's call - so it is a warning, and it blocks no engagement at
    all, not even the one it was found near."""
    result = preflight_over(
        "Kestrel Precision/2026 Valuation",
        "Clients/Kestrel Precision/2026 Valuation/IS.xlsx",
        "Clients/readme.txt",
    )
    assert [f.severity for f in result.failures] == ["warn"]
    assert result.failures[0].engagement_ids == ()
    assert not result.failures[0].blocks_everything


def test_a_clean_setup_produces_nothing_at_all() -> None:
    result = preflight_over(
        "Kestrel Precision/2026 Valuation",
        "Clients/Kestrel Precision/2026 Valuation/IS.xlsx",
    )
    assert list(result.failures) == []


def test_the_form_says_how_deep_before_anybody_is_refused() -> None:
    """The best refusal is the one nobody meets. The hint reads the depth off the watch
    that is selected, so it is right for each one rather than a sentence about the usual
    case."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    assert "function folderHint()" in page
    assert "e_folder_hint" in page
    assert "$('e_watch').addEventListener('change', folderHint);" in page
    block = page[page.index("function folderHint()") : page.index("ACTIONS.testModel")]
    assert "watch.depth" in block, "from the watch, not from a constant"
    assert "'bound'" in block, "a bound watch has no depth to explain"


def test_the_hint_is_a_hint_rather_than_an_inline_style() -> None:
    """The page has a spacing scale and a `.hint` class. A margin chosen by eye is how the
    P109 note failed the design check in C63."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    assert '<p class="hint" id="e_folder_hint"></p>' in page


# ============================================================ what it does not do


def test_nothing_is_moved_or_renamed() -> None:
    """The system reports; a person files. Guessing that `Clients/Test Client` meant
    `Clients/Test Client/2026` would be the system inventing an engagement folder, which
    is the same class of mistake as inventing a figure."""
    source = (ROOT / "intake" / "sweep.py").read_text(encoding="utf-8")
    body = source[source.index("def folder_too_shallow") : source.index("class SweepPlanner")]
    for verb in ("rename", "mkdir", "move", "shutil"):
        assert verb not in body


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_the_shape_matches_whatever_depth_a_watch_declares(depth: int) -> None:
    problem = folder_too_shallow("one", watch(depth)) if depth != 1 else None
    if depth == 1:
        assert folder_too_shallow("one", watch(1)) is None
        return
    assert problem is not None
    assert problem.count("<") == depth

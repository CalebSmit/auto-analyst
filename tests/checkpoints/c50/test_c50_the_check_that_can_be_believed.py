"""C50 - The check that can be believed.

P82 turned a scan that had reported nothing into one that gates the build, and a gate is
only worth having if its verdict matches what happens. Two ways it could be worthless and
they fail in opposite directions: a false positive blocks a phase over a module that is
perfectly well reached, and a false negative is decoration that lets the next P68 through
exactly as the last one went through.

So this exercises the mechanism against the tree it now judges, rather than reading it.
Every module it calls reachable is found on disk and parsed; every module it excuses is
checked to be genuinely unreachable by a second route sharing no code with the first. And
the scan is shown noticing, on a tree built here for the purpose: an allowlist nothing can
fall off is a list of permanent exemptions. It reads the real repo everywhere the *verdict*
is the claim, and a small built tree everywhere the *mechanism* is - the first version did
the mechanism by editing `guards/__init__.py` and putting it back, which is a test that can
leave the repo edited if it is interrupted.

It has already earned itself. `from guards import reconcile` records `guards` on the
`ImportFrom` node and the submodule only in `names`, so the scan read the first and missed
the second - a false negative in a check whose whole job is not to have one. Found here by
writing that line into a production file and watching the scan not move.

`test_the_scan_notices_when_a_module_becomes_reachable` is the one worth having. The
failure it prevents is the one P71 had: a check that is green because it cannot see, and
that stays green through the whole life of the defect it was written for.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.p82.test_nothing_a_run_cannot_reach import (
    ALLOWED,
    backlog_items,
    dotted,
    imported_by_production,
    imports_in,
    invoked_as_a_command,
    named_by_the_ports_registry,
    shipped_modules,
    unreachable,
)

ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------- the verdict matches what happens


def test_every_module_the_scan_calls_reachable_is_a_real_module() -> None:
    """The cheapest way this check could be wrong is by naming things that are not modules
    and then agreeing with itself about them.

    Checked by finding and parsing the file rather than by importing it: importing all 130
    pulls in openpyxl, fastapi and sqlalchemy for an answer the rest of the suite gives
    anyway, since a module that cannot load fails the phase that uses it long before it
    reaches here.

    `unreachable()` is read once. Written inside the comprehension it was re-computed for
    every module - a hundred and forty walks of the tree, a hundred and sixty seconds - and
    the cache could not help, because its own fingerprint stats every file.
    """
    unreached = set(unreachable())
    reachable = [dotted(p) for p in shipped_modules() if dotted(p) not in unreached]
    assert len(reachable) > 100, f"only {len(reachable)} reachable modules - the scan is lost"
    for name in reachable:
        path = ROOT / (name.replace(".", "/") + ".py")
        assert path.is_file(), f"the scan calls {name} reachable and there is no such file"
        ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_every_excused_module_is_unreachable_by_a_second_route(module: str) -> None:
    """Counted a different way, sharing nothing with `imported_by_production` but the
    standard library: a text search for the module's own dotted name in every file that is
    not a test. Cruder than the parse and wrong in the safe direction - it matches a
    mention in a comment, so anything it fails to find is certainly not imported.
    """
    needle = module
    own_package_init = ROOT / (module.rsplit(".", 1)[0].replace(".", "/")) / "__init__.py"
    for path in ROOT.rglob("*.py"):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.parts[len(ROOT.parts)] == "tests" or path.name == "conftest.py":
            continue
        if dotted(path) == module:
            continue
        if dotted(path) in ALLOWED:
            # A module that is itself excused naming another one is not a second route.
            # `orchestrate/orchestrator.py` mentions `orchestrate.plan.RunPlanner` in its
            # docstring, and both are unreachable: one piece of dead code pointing at
            # another is evidence about neither.
            continue
        if path == own_package_init:
            # A package's own `__init__.py` naming its submodule is not a second route.
            # It says the module is part of the package; it says nothing about whether
            # anything reaches the package - and treating it as evidence is how a whole
            # package can be built, wired to nothing, and pass the check written to catch
            # that. P91 taught the main scan this; the cross-check has to agree or the two
            # disagree about what reachable means, which is worse than either being wrong.
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert needle not in text, f"{module} is excused and {path.name} names it"


def test_the_three_ways_of_being_reachable_do_not_overlap_by_accident() -> None:
    """Each way excuses something, so each one widening silently widens the check's blind
    spot. They are disjoint today and if that stops being true it is worth knowing."""
    imported = imported_by_production()
    registered = named_by_the_ports_registry()
    commanded = invoked_as_a_command()
    assert registered, "the ports registry named no adapter at all"
    assert commanded, "no command was found in any document"
    assert not (registered & commanded), sorted(registered & commanded)
    # An adapter imported by something *outside* `ports/` is the port being gone around:
    # the whole arrangement is that a caller asks for the port and the registry decides
    # which adapter answers. Inside `ports/` it is ordinary reuse - `scripted` is built on
    # `fake` - and that is what this used to fail on.
    from_outside = {
        node.module
        for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts
        and "__pycache__" not in path.parts
        and path.parts[len(ROOT.parts)] not in ("tests", "ports")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8", errors="replace")))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    went_around = registered & from_outside
    assert not went_around, (
        f"adapter(s) reached for by name instead of through the port: {sorted(went_around)}"
    )
    assert imported, "nothing was found to be imported by production at all"


# ------------------------------------------------- and the scan can be shown noticing


def a_little_tree(root: Path, wired: bool) -> None:
    """Two modules in a package, and a caller that imports one of them or neither.

    The shapes that matter, in six lines: `pkg.used` is reached the way a submodule
    actually gets reached - `from pkg import used`, whose name lives in `names` and not in
    `module`, which is the false negative C50 found in the real scan. `pkg.spare` is
    reached by nothing. `tests/` is there to be ignored.
    """
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "used.py").write_text('"""Reached, when the caller is written."""\n', "utf-8")
    (root / "pkg" / "spare.py").write_text('"""Reached by nothing, ever."""\n', "utf-8")
    (root / "app.py").write_text(
        "from pkg import used\n" if wired else "", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_all.py").write_text(
        "from pkg import used, spare  # a test is not production\n", encoding="utf-8"
    )


def test_the_scan_notices_when_a_module_becomes_reachable(tmp_path: Path) -> None:
    """The property P71 did not have, and the one thing this whole phase turns on.

    Run against a tree built here rather than against this repo. The first version of this
    demonstrated it by writing an import into `guards/__init__.py` and taking it out again,
    which worked and was wrong: a test that edits the repo is a test that can leave the repo
    edited if it is interrupted between the write and the `finally`, and this project has
    lost committed records that way before. What has to be true is that the scan reads a
    tree; which tree is not the claim.
    """
    unwired_tree, wired_tree = tmp_path / "before", tmp_path / "after"
    a_little_tree(unwired_tree, wired=False)
    a_little_tree(wired_tree, wired=True)

    assert "pkg.used" not in imports_in(unwired_tree), "nothing imports it and the scan sees one"
    assert "pkg.used" in imports_in(wired_tree), (
        "`from pkg import used` was added and the scan did not notice - the submodule is in "
        "`names`, not in `module`, which is the false negative this check exists to prevent"
    )


def test_a_module_reached_only_by_a_test_is_not_reached(tmp_path: Path) -> None:
    """P71's blind spot, stated on a tree small enough to see all of. `pkg.spare` is
    imported by `tests/test_all.py` and by nothing else, and that is not wiring."""
    tree = tmp_path / "t"
    a_little_tree(tree, wired=True)
    imported = imports_in(tree)
    assert "pkg.spare" not in imported, "a test import counted as production"
    assert "pkg.used" in imported, "the production import was missed as well"


def test_the_scan_notices_a_module_that_nothing_reaches_at_all() -> None:
    """And the same question asked of this repo, which is where the verdict has to be
    right. `guards.reconcile` is reached by nothing today - if that changes, the allowlist
    decay check above fails first and says so."""
    assert "guards.reconcile" in unreachable()
    assert "guards" not in unreachable(), "a package with a live `__init__` reads as unreached"


# ------------------------------------------------- and the record it rests on


def test_the_backlog_is_readable_by_the_thing_that_depends_on_it() -> None:
    """The allowlist cites backlog ids and the scan parses them out of a markdown file. A
    heading somebody reformats would silently stop being found, and every entry citing it
    would fail at once - so the parse is checked against the file's own shape."""
    items = backlog_items()
    assert len(items) >= 40, f"only {len(items)} backlog items parsed - the headings moved"
    assert all(i.startswith("B-") for i in items)
    assert {item for item, _ in ALLOWED.values()} <= set(items)


def test_nothing_the_allowlist_cites_has_been_closed_elsewhere() -> None:
    """An item closed in the backlog while the gap is still live is the record disagreeing
    with the code, and the allowlist is where the two are compared."""
    items = backlog_items()
    for module, (cited, _) in sorted(ALLOWED.items()):
        assert not items[cited].startswith("built ("), f"{cited} closed while {module} is unreached"


def test_the_two_checks_for_this_defect_ask_different_questions() -> None:
    """P71 finds a dead function inside a live module; P82 finds a module no run reaches.
    Neither subsumes the other, and a tidy-up deleting one as redundant would reopen half
    the defect class.

    This has now been stated three ways, and the first two were wrong in instructive ways.
    The original ended on `excused - {f.rsplit('.', 1)[0] for f in functions} == excused`,
    which is true whatever either check reports - P71 yields bare function names, so
    splitting one on a dot gives the name back and the subtraction removes nothing. A test
    asserting nothing, in the checkpoint for the phase about things that do nothing.

    The second used `tools` as the territory only P82 covered. That premise died in P91,
    when both scans stopped taking a hand-written package list and started deriving one -
    `tools` has an `__init__.py`, so P71 covers it now.

    What is actually true, and does not depend on either scan's scope: **P82 reports whole
    modules that P71 has nothing to say about, because the functions inside them are
    called - by each other.** A package that is internally busy and externally unreached
    is invisible to "is this function called" and obvious to "does a run get here".
    """
    from tests.p71.test_nothing_is_unwired import unwired as unwired_functions

    dead_modules = set(unreachable())
    assert dead_modules, "nothing is unreachable, so the two checks cannot be compared"

    reported_by_p71 = {f"{where}.{name}" for where, _, name in unwired_functions()}
    functions_in_dead_modules = set()
    for module in dead_modules:
        path = ROOT / (module.replace(".", "/") + ".py")
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions_in_dead_modules.add(f"{module}.{node.name}")

    assert functions_in_dead_modules, "the dead modules hold no public functions to compare"
    assert not (functions_in_dead_modules & reported_by_p71), (
        "P71 now reports functions inside modules P82 already calls unreachable, so one "
        "check is starting to subsume the other"
    )


def test_the_scan_reads_the_shipped_packages_and_not_a_subset() -> None:
    """P71's own list of packages omits `tools`, which is where four of the unreachable
    modules live. This one says which packages it covers, so the omission is visible."""
    from tests.p82.test_nothing_a_run_cannot_reach import SHIPPED

    on_disk = {
        p.name
        for p in ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").exists() and p.name != "tests"
    }
    assert set(SHIPPED) == on_disk, (
        f"shipped packages the scan does not look at: {sorted(on_disk - set(SHIPPED))}"
    )


def test_no_excused_module_is_imported_by_another_excused_one() -> None:
    """Two unreachable modules importing each other look wired to a naive check and are a
    connected island nothing docks to. The scan is not naive - it asks about production, and
    an excused module is not production - but the island is worth naming if one forms."""
    for module in ALLOWED:
        path = ROOT / (module.replace(".", "/") + ".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                # The same blind spot the scan had, and this test had it too until a revert
                # of `from tools import rollforward` left it green: the submodule is in
                # `names`, not in `module`.
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        assert not (imported & set(ALLOWED)), f"{module} imports another excused module"

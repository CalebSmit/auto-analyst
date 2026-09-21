"""P82: nothing a run cannot reach is called built.

P71 built a scan for this build's most repeated defect and the scan counts a mention in a
test as wiring. It walks every `.py` under the root, `tests/` included, and asks whether a
name appears anywhere - so a module whose only caller is its own test file is "referenced"
and passes. That is the defect exactly, and it was invisible to the check written for it.

Eleven modules were in that state when this was written, about two thousand lines. Two are
what the fourth interview session asked for: `intake/request_list.py` (P68) and
`tools/rollforward.py` (P69). One is `privacy/verify.py`, the unmask integrity check, which
the blueprint asserts dominates every deliverable and which no production module imports.

The question here is different, and it is the one P71 meant to ask: **can anything a person
or a run reaches touch this module.** Two ways a module is legitimately reached without
anything importing it, and both are recognised rather than excused, because an allowlist
that fills up with things that are fine stops being read:

  1. an adapter the ports registry names - wired by name through `AA_*_ADAPTER`
  2. a command somebody types - `python tools/verify.py` and its like

What is left is a real decision every time, so an entry needs a reason **and a backlog item
that exists and is still open**. CLAUDE.md already said a deliberately unjoined seam is said
out loud in the backlog; nothing checked that it was, and four items said `built` for a
module nothing could reach.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "knowledge" / "backlog.md"

SHIPPED = (
    "admin",
    "deliver",
    "evals",
    "governance",
    "graph",
    "guards",
    "harness",
    "intake",
    "ops",
    "orchestrate",
    "ports",
    "precedent",
    "privacy",
    "registries",
    "review",
    "tools",
    "ui",
    "workers",
)

# A module nothing reaches, excused. Each entry is a decision, so each names the backlog
# item carrying it and says what is actually missing. The test below refuses an entry whose
# item does not exist or is already closed, which is what stops this list going stale
# quietly - the failure mode of every allowlist.
ALLOWED: dict[str, tuple[str, str]] = {
    "privacy.verify": (
        "B-043",
        "The unmask integrity check. Nothing in production imports it or `privacy.unmask`, "
        "so no run has ever resolved a token back, while the blueprint asserts every "
        "deliverable is dominated by `unmask_verify` and `deliver/builder.py` opens by "
        "claiming its inputs are unmasked. Where the unmask belongs on the release path is "
        "a design decision and not one to take while tidying a scan, so it is recorded "
        "rather than wired - and it has not bitten because no run has reached release.",
    ),
    "intake.request_list": (
        "B-038",
        "P68 built the seven sections, the item references and the coverage report. The "
        "items inside a section are written per engagement and the only list in hand "
        "belongs to a client, so there is nothing yet for a run to carry - the caller "
        "arrives with the first real request list.",
    ),
    "tools.rollforward": (
        "B-036",
        "P69 built the arithmetic half - the ten-year window, the date roll and the line "
        "items carried forward. The Excel half binds the firm's real model by named range "
        "and the analyst has not supplied it, so wiring this would mean guessing the "
        "binding and replacing it days later.",
    ),
    "tools.forecast_drivers": (
        "B-019",
        "Computes forecast driver baselines from history. Version 1 gathers data and does "
        "not run the model, so a forecast is not on its path; kept because the analyst "
        "described the drivers and the arithmetic is the part that does not change.",
    ),
    "tools.beta": (
        "B-021",
        "Beta and cost of debt. Cost of capital is explicitly outside version 1's path in "
        "CLAUDE.md, and the firm's own formula is still a required argument rather than a "
        "default, so nothing can call this until the practice confirms the formula.",
    ),
    "guards.reconcile": (
        "B-044",
        "Collates outputs across skills and surfaces contradictions. `conflict_resolution` "
        "is declared on monthly-refresh over two steps and can never be entered: this is "
        "never called outside tests, and the executor re-runs only the head of a region. "
        "Already recorded in OPEN.md section 4b as needing executor machinery that does "
        "not exist.",
    ),
    "registries.diagnostics": (
        "B-046",
        "Renders a diagnostic for a person to read. The codes themselves live in "
        "`registries.errors`, which is imported everywhere; this is the presentation half "
        "and no surface calls it, so every diagnostic a person sees is formatted somewhere "
        "else. Two ways to render one is the thing to resolve.",
    ),
}


# ------------------------------------------------------------------ reading the tree


def dotted(path: Path, root: Path = ROOT) -> str:
    return str(path.relative_to(root)).replace("\\", "/").removesuffix(".py").replace("/", ".")


def shipped_modules() -> list[Path]:
    """Every module in a shipped package. `__init__.py` is excluded: a package's exports
    are reached through the package, and asking whether one is imported asks nothing."""
    found = []
    for package in SHIPPED:
        for path in sorted((ROOT / package).rglob("*.py")):
            if "__pycache__" not in path.parts and path.name != "__init__.py":
                found.append(path)
    return found


_REMEMBERED: dict[str, object] = {}


def _fingerprint() -> int:
    """What the tree looks like right now, cheaply.

    Stat is about a hundredth of the cost of the parse, so the answers can be remembered
    and thrown away the moment a file changes, rather than being remembered until somebody
    remembers to say otherwise. That difference is the whole point: a cache you have to
    clear by hand is a cache that will one day not be cleared, and this check going stale
    without saying so is the same shape of defect as the one it was written to find.
    """
    return hash(
        tuple(
            (str(p), p.stat().st_mtime_ns, p.stat().st_size)
            for p in sorted(ROOT.rglob("*.py"))
            if ".venv" not in p.parts and "__pycache__" not in p.parts
        )
    )


def forget() -> None:
    """Drop what was read from the tree.

    Rarely needed - the fingerprint notices an edit on its own - and kept as the explicit
    way to say "I changed something" for anything that changes what is read but not a
    `.py` file, such as the backlog or CLAUDE.md.
    """
    _REMEMBERED.clear()


def _remembered(key: str, compute: Callable[[], set[str]]) -> set[str]:
    now = _fingerprint()
    if _REMEMBERED.get("fingerprint") != now:
        _REMEMBERED.clear()
        _REMEMBERED["fingerprint"] = now
    if key not in _REMEMBERED:
        _REMEMBERED[key] = compute()
    return _REMEMBERED[key]  # type: ignore[return-value]


def imports_in(root: Path) -> set[str]:
    """Every module imported by something under `root` that is not a test.

    The whole of the difference from P71. `conftest.py` is a test file wherever it sits,
    and a module importing itself does not make itself reachable.

    Takes the tree it reads rather than assuming this one, so the mechanism can be shown
    working on a tree built for the purpose. C50 used to demonstrate it by writing an
    import into `guards/__init__.py` and taking it out again: a test that edits the repo
    is a test that can leave the repo edited, and this project has lost committed records
    that way before.
    """
    imported: set[str] = set()
    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.parts[len(root.parts)] == "tests" or path.name == "conftest.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover - not our files to fix
            continue
        me = dotted(path, root)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module != me:
                imported.add(node.module)
                # `from guards import reconcile` imports the submodule, and reading only
                # `node.module` records `guards` and misses it entirely. C50 found this by
                # adding exactly that line and finding the scan unmoved - a false negative
                # in a check whose whole job is not to have one. What it costs is that a
                # `from x import y` where y is a name rather than a module records `x.y`,
                # which no module is called, so nothing is wrongly excused.
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
    return imported


def imported_by_production() -> set[str]:
    return _remembered("imported", lambda: imports_in(ROOT))


def _named_by_the_ports_registry() -> set[str]:
    """Adapters are chosen by name through `AA_*_ADAPTER` and imported by the registry, so
    nothing names the module in code. Asked of the registry rather than listed here, which
    is why adding an adapter does not mean editing this file."""
    import ports

    return {
        module for spec in ports.PORTS.values() for module in spec.adapters.values()
    }


def named_by_the_ports_registry() -> set[str]:
    return _remembered("registered", _named_by_the_ports_registry)


def _invoked_as_a_command() -> set[str]:
    """Modules somebody is told to run.

    Read out of real invocations - `python tools/verify.py`, `python -m evals` - and not
    out of prose. A first cut counted any `*.py` appearing in any document, and OPEN.md
    names a dozen files it is *reporting on*: that excused six modules, including
    `privacy/verify.py`, which is the one finding that mattered most.
    """
    text = ""
    for path in [*ROOT.rglob("*.md"), ROOT / "BUILD" / "plan.json", *ROOT.glob("*.cmd")]:
        if path.is_file() and ".venv" not in path.parts:
            text += path.read_text(encoding="utf-8", errors="replace")
    found = set(re.findall(r"python\s+([\w/\\.-]+\.py)", text))
    modules = {n.replace("\\", "/").removesuffix(".py").replace("/", ".") for n in found}
    # `python -m evals` runs `evals/__main__.py`, so a package named this way reaches it.
    for package in re.findall(r"python\s+-m\s+([\w.]+)", text):
        modules |= {package, f"{package}.__main__"}
    return modules


def invoked_as_a_command() -> set[str]:
    return _remembered("commands", _invoked_as_a_command)


def unreachable() -> list[str]:
    """Shipped modules nothing a person or a run reaches."""
    reachable = imported_by_production() | named_by_the_ports_registry() | invoked_as_a_command()
    return sorted(dotted(p) for p in shipped_modules() if dotted(p) not in reachable)


# ------------------------------------------------------------------ the backlog


def backlog_items() -> dict[str, str]:
    """Every `## B-0NN` heading in the backlog, mapped to its status line."""
    text = BACKLOG.read_text(encoding="utf-8")
    items = {}
    for match in re.finditer(r"^## (B-\d+)[^\n]*\n(?:status:\s*([^\n]*))?", text, re.M):
        items[match.group(1)] = (match.group(2) or "").strip()
    return items


# ------------------------------------------------------------------ the check


def test_nothing_shipped_is_beyond_the_reach_of_a_run() -> None:
    """The check itself. A module here is either a seam somebody meant to join and did
    not, or code no run can execute - and both want saying out loud."""
    surprises = [name for name in unreachable() if name not in ALLOWED]
    assert not surprises, (
        "shipped module(s) nothing in production imports, no port registers and no "
        "documented command runs. Wire it, delete it, or add it to ALLOWED with a backlog "
        f"item and the reason it stays: {surprises}"
    )


def test_the_check_would_have_caught_the_two_it_was_written_for() -> None:
    """P68 and P69 were closed, checkpointed and committed in this state, and P71 - written
    for this exact defect three phases earlier - reported nothing. If this test ever has to
    be deleted because those two became reachable, that is the good ending."""
    reported = set(unreachable())
    assert "intake.request_list" in reported
    assert "tools.rollforward" in reported


def test_a_reference_from_a_test_does_not_count_as_wiring() -> None:
    """The whole of what was wrong with P71, stated as a property: the tests are not part
    of what a run can reach, so nothing under `tests/` may make a module look wired."""
    from_tests = {
        node.module
        for path in (ROOT / "tests").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8", errors="replace")))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert from_tests & set(ALLOWED), "no excused module is imported by a test at all"
    assert set(ALLOWED) - imported_by_production() == set(ALLOWED), (
        "something excused here is imported by production and should not be excused"
    )


# ------------------------------------------------------------------ and the allowlist decays


def test_every_excused_module_still_exists() -> None:
    """An entry for a module that has been deleted or renamed excuses nothing and reads as
    though the check covers more than it does."""
    shipped = {dotted(p) for p in shipped_modules()}
    assert set(ALLOWED) <= shipped, f"excused but gone: {sorted(set(ALLOWED) - shipped)}"


def test_nothing_is_excused_that_something_now_reaches() -> None:
    """The decay that matters. A seam joined later leaves its excuse behind, and the next
    person reads a list of things that are supposedly unwired and half of them are not."""
    still = set(unreachable())
    assert set(ALLOWED) <= still, (
        f"excused and now reachable - remove the entry: {sorted(set(ALLOWED) - still)}"
    )


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_an_excused_module_says_why_and_where(module: str) -> None:
    """What stops this being switched off one quiet line at a time."""
    item, why = ALLOWED[module]
    assert re.fullmatch(r"B-\d+", item), f"{module} cites {item!r}, which is not a backlog id"
    assert len(why.split()) >= 20, f"{module} is excused without saying enough"


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_an_excused_module_cites_a_backlog_item_that_exists(module: str) -> None:
    """CLAUDE.md: if a seam is deliberately unjoined, say so in the backlog and point the
    allowlist at it. Nothing checked the second half until now."""
    item, _ = ALLOWED[module]
    items = backlog_items()
    assert item in items, f"{module} cites {item}, which is not in knowledge/backlog.md"


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_an_excused_module_cites_an_item_still_open(module: str) -> None:
    """A closed item excusing a live gap is the record disagreeing with itself."""
    item, _ = ALLOWED[module]
    status = backlog_items()[item]
    assert not status.startswith("built ("), (
        f"{module} is unreachable and {item} is recorded as {status!r}"
    )


# ------------------------------------------------------------------ and the record agrees


def test_the_backlog_does_not_call_built_what_no_run_can_reach() -> None:
    """The finding this phase started from, as a standing check.

    `built` had come to mean "the code exists" rather than "a run can reach it", which for
    a tool whose point is that the analyst gets working software is the whole distinction.
    Four items said it. Two of them - B-036 and B-037 - were already honest, saying which
    half was built; the other two were not.
    """
    items = backlog_items()
    wrong = []
    for module in unreachable():  # read once; the loop body does not walk the tree
        if module not in ALLOWED:
            continue
        item, _ = ALLOWED[module]
        status = items.get(item, "")
        if re.match(r"^(built|done)\b", status) and "part" not in status:
            wrong.append(f"{item} says {status!r} and nothing reaches {module}")
    assert not wrong, wrong


def test_every_backlog_item_the_allowlist_cites_says_what_is_missing() -> None:
    """A status of `proposed` on something half-built tells the next reader less than the
    code does. Each cited item has to carry the words that say which half is owed."""
    items = backlog_items()
    for module, (item, _) in sorted(ALLOWED.items()):
        status = items[item]
        assert status, f"{item}, cited for {module}, has no status line at all"

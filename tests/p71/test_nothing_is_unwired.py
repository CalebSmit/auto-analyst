"""P71: nothing is built and wired to nothing.

The defect keeps coming back. P55 found precedent retrieval handed to every collaborator
but the Context Builder, a release gate read off a field `RunWiring` never had, and
`RepairNeeded` raised in exactly one place - a test double. P60 found `on_failure` parsed,
validated, carried on every `Step`, folded into every plan hash, and read by nothing. Each
was found by somebody reading carefully, which is lucky rather than repeatable.

So this looks. A public function in a shipped package that nothing anywhere references -
not another module, not its own, not a test - is either dead or a seam somebody meant to
join and did not. Both want saying out loud.

The allowlist carries a reason for each entry, because the answer "nothing calls this, on
purpose" is a decision and decisions belong on the record. An entry with no reason fails
as loudly as an unwired function, which is the point:
`test_an_allowlist_entry_without_a_reason_is_refused` is what stops this check being
switched off one quiet line at a time.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SHIPPED = (
    "graph",
    "ops",
    "harness",
    "intake",
    "review",
    "privacy",
    "guards",
    "precedent",
    "registries",
    "deliver",
    "workers",
    "evals",
    "governance",
    "ports",
    "admin",
    "ui",
)

ALLOWED: dict[str, str] = {
    "evals.metrics.provenance_of": (
        "Not wired, and the gap is the point. Its docstring says 'Exposed for the harness' "
        "and it is the only mention of ProvenanceGate anywhere in evals/ - so the eval "
        "harness has never measured a provenance failure, and a candidate skill could "
        "promote while faulting one. Recorded as B-041 rather than deleted, because "
        "deleting it would remove the only trace of the intent, and wiring it changes what "
        "promotion measures, which is not a decision to take while tidying."
    ),
}


def public_functions() -> list[tuple[str, int, str, str]]:
    """Every public module-level function in the shipped packages."""
    found = []
    for package in SHIPPED:
        directory = ROOT / package
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for node in ast.parse(source).body:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if node.name.startswith("_"):
                        continue
                    found.append((str(path.relative_to(ROOT)), node.lineno, node.name, source))
    return found


def referenced_names() -> set[str]:
    """Every name actually *referenced* anywhere in the tree.

    Parsed rather than searched. A textual search cannot tell a call from a mention, and
    the difference matters here more than anywhere: this module's own `ALLOWED` names the
    functions it excuses, and C40 names them again - so under a text search an allowlist
    entry made its own function look wired and quietly emptied the check. Both times the
    allowlist's decay test caught it, which is the one thing that stopped it being silent.

    `ast` sees a name in code and not a name in a string, a docstring or a comment, which
    is exactly the distinction wanted. What it cannot see is dispatch through `getattr` or
    a name in a config file; that is what `ALLOWED` is for, with its reason.
    """
    seen: set[str] = set()
    for path in ROOT.rglob("*.py"):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover - not our files to fix
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                seen.add(node.id)
            elif isinstance(node, ast.Attribute):
                seen.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                seen.update(alias.name for alias in node.names)
    return seen


def unwired() -> list[tuple[str, int, str]]:
    """Public functions nothing references - not elsewhere, not in their own module.

    A reference inside the defining module counts: a helper used only by its own file is
    wired, just narrowly. A decorator on the function, and the `def` itself, do not.
    """
    referenced = referenced_names()
    return [
        (where, line, name)
        for where, line, name, _ in public_functions()
        if name not in referenced
    ]


def key(where: str, name: str) -> str:
    return where.replace("\\", "/").removesuffix(".py").replace("/", ".") + "." + name


# ------------------------------------------------------------------ the check


def test_no_public_function_is_wired_to_nothing() -> None:
    surprises = [
        f"{where}:{line} {name}"
        for where, line, name in unwired()
        if key(where, name) not in ALLOWED
    ]
    assert not surprises, (
        "public function(s) nothing references anywhere. Wire it, delete it, or add it to "
        f"ALLOWED with the reason it stays: {surprises}"
    )


def test_every_allowed_entry_is_actually_unwired() -> None:
    """The allowlist decays too. An entry for something that is now wired is a stale excuse,
    and it would hide the day that function became unwired again."""
    live = {key(where, name) for where, _, name in unwired()}
    stale = [entry for entry in ALLOWED if entry not in live]
    assert not stale, f"allowed but no longer unwired - remove the entry: {stale}"


def test_an_allowlist_entry_without_a_reason_is_refused() -> None:
    """What stops this check being switched off one quiet line at a time."""
    for entry, why in ALLOWED.items():
        assert len(why.split()) >= 12, f"{entry} is excused without saying why"


# ------------------------------------------------------------------ the scan itself works


def test_the_scan_sees_a_call_and_not_a_mention() -> None:
    """The distinction the whole check rests on, exercised on the real collector.

    A check that cannot fail is worse than none, and this one nearly could not: under a
    text search, naming a function in the allowlist was enough to make it look wired.
    """
    referenced = referenced_names()

    # Called all over the build, so it must be seen.
    assert "compile_recipe" in referenced

    # A name that appears in this repository only inside strings - the allowlist key and
    # the backlog entry - and is never called. If mentions counted, this would be in.
    assert "evals.metrics.provenance_of" not in referenced


def test_the_function_this_phase_excused_is_genuinely_unwired() -> None:
    """Not taken on trust from the allowlist: the scan itself still reports it."""
    assert "evals.metrics.provenance_of" in {key(w, n) for w, _, n in unwired()}


def test_a_helper_used_only_inside_its_own_module_is_not_reported() -> None:
    """Narrowly wired is still wired, and reporting it would make the check noise."""
    assert "split_frontmatter" not in {name for _, _, name in unwired()}


def test_the_dead_duplicate_found_today_is_gone() -> None:
    """`governance.conformance.read_draft` was a one-line copy of what drop.py already ran
    inline. Deleted rather than allowlisted, because there was nothing to record."""
    source = (ROOT / "governance" / "conformance.py").read_text(encoding="utf-8")
    assert "def read_draft" not in source
